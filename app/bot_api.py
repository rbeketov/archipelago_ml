import os
import requests
import json
from requests import Response
from logger import Logger
from typing import Dict, List, TypedDict, Optional, Union
from functools import reduce
from threading import Lock
from collections import defaultdict

import schedule
from gpt_utils import send_request_to_gpt

logger = Logger().get_logger(__name__)

# --- util

class HTTPStatusException(Exception):
    def __init__(self, res):
        self.res = res
        super().__init__(res)


def wrap_http_err(res: Response) -> Response:
    try:
        res.raise_for_status()
    except Exception as e:
        raise HTTPStatusException(res)

    return res

# ----

class RecallApiBase:
    url = 'https://us-west-2.recall.ai{path}'

    def __init__(self, recall_api_token):
        self.headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "Authorization": f"Token {recall_api_token}"
        }

    def _url(self, path):
        return self.url.format(path = path)

    def recall_post(self, path, json_body):
        url = self._url(path)
        return wrap_http_err(requests.post(url, headers=self.headers, json=json_body))

    def recall_get(self, path):
        url = self._url(path)
        return wrap_http_err(requests.get(url, headers=self.headers))


class RecallApi(RecallApiBase):
    def start_recording(self, bot_name, meeting_url, destination_transcript_url, destination_audio_url, destination_speaker_url):
        body = {
            "bot_name": bot_name,
            "meeting_url": meeting_url,
            "transcription_options": {
                "provider": 'meeting_captions',
            },
            "real_time_transcription": {
                "destination_url": destination_transcript_url,
                "partial_results": True,
            },
            "zoom": {
                "request_recording_permission_on_host_join": True,
                "require_recording_permission": True,
            },
            "recording_mode": "audio_only",
            "real_time_media": {
                "websocket_audio_destination_url": destination_audio_url,
                "websocket_speaker_timeline_destination_url": destination_audio_url,
            }
        }

        return self.recall_post('/api/v1/bot', body)

    def stop_recording(self, bot_id):
        return self.recall_post(f"/api/v1/bot/{bot_id}/leave_call", json_body={})

    def recording_state(self, bot_id):
        return self.recall_get(f'/api/v1/bot/{bot_id}')

    def transcript(self, bot_id, diarization: bool):
        diarization_str = '?enhanced_diarization=true' if diarization else ''
        return self.recall_get(f'/api/v1/bot/{bot_id}/transcript{diarization_str}')

# ---- Bot

class SpeakerTranscription(TypedDict):
    message: str
    is_final: bool
    speaker: str

class Transcription(TypedDict):
    id: int
    sp: SpeakerTranscription

    @staticmethod
    def from_recall_resp(recall_resp_tr):
        id = recall_resp_tr['original_transcript_id']

        speaker = recall_resp_tr['speaker']
        is_final = recall_resp_tr['is_final']
        message = reduce(lambda text,new_part: f"{text}\n{new_part['text']}", recall_resp_tr['words'], "")[1:]

        return Transcription(id=id, sp=SpeakerTranscription(message=message, speaker=speaker, is_final=is_final))


class FullTranscription:
    def __init__(self):
        self.t: Dict[int, SpeakerTranscription] = {}
        self.summ = ""

    def add(self, tr_id, sp: SpeakerTranscription):
        self.t[tr_id] = sp

    def to_prompt(self, only_final=True) -> Optional[str]:
        # self.t.update(sorted(self.t.items(), key=lambda item: item[1]))

        prompt = ""
        for tr_id in sorted(self.t):
            tr_by_sp = self.t[tr_id]
            if only_final and not tr_by_sp["is_final"]:
                continue

            if 'Noise.' in tr_by_sp["message"]:
                continue

            new_part = f'{tr_by_sp["speaker"]}: {tr_by_sp["message"]}\n'
            prompt = f"{prompt}{new_part}"

        if prompt == "":
            return None

        if self.summ == "":
            return prompt

        final_prompt = f"Вот начало диалога: {self.summ}, вот продолжение: {prompt}"

        return final_prompt

    def drop_to_summ(self, summary: str):
        self.summ = summary
        self.t = {}

class BotWebHooks(TypedDict):
    transcription_url: str
    speaker_ws_url: str
    audio_ws_url: str

class Bot:
    def __init__(self, user_id, recall_api_token, bot_name, webhooks: BotWebHooks, join_callback: callable = lambda _: _, leave_callback: callable = lambda _: _):
        self.bot_name = bot_name
        self.webhooks = webhooks
        self.recall_api = RecallApi(recall_api_token=recall_api_token)
        self.transcription = FullTranscription()

        self.user_id = user_id

        self.join_callback = join_callback
        self.leave_callback = leave_callback

    def join_and_start_recording(self, meeting_url):
        logger.debug("Before start_recording")
        resp = self.recall_api.start_recording(
            self.bot_name, 
            meeting_url=meeting_url, 
            destination_transcript_url=self.webhooks["transcription_url"],
            destination_audio_url=self.webhooks["audio_ws_url"],
            destination_speaker_url=self.webhooks["speaker_ws_url"],
        ).json()

        logger.debug(resp)
        self.bot_id = resp['id']

        self.join_callback(self)

    def leave(self):
        resp = self.recall_api.stop_recording(self.bot_id).json()
        logger.debug(resp)

        self.leave_callback(self)

    def recording_state(self) -> Union[str, bool]:
        resp = self.recall_api.recording_state(self.bot_id).json()
        logger.debug(resp)

        status = resp["status_changes"][-1]

        if status['code'] in ['call_ended', 'fatal', 'recording_permission_denied', 'recording_done', 'done']:
            return f"{status['sub_code']}: {status['message']}"

        return True

    def transcript_full(self, diarization: bool) -> str:
        resp = self.recall_api.transcript(self.bot_id, diarization).json()
        return json.dumps(resp)

    # add_transcription(Transcription.from_recall_resp(response['transcipt']))
    def add_transcription(self, tr: Transcription):
        self.transcription.add(tr['id'], tr["sp"])

    def make_summary(self, summary_transf: callable, summary_cleaner: Optional[callable]) -> None:
        prompt = self.transcription.to_prompt()
        logger.info(f'Промпт: {prompt}')
        if prompt is None:
            return
        
        logger.info(f"sync transcrpt: {self.transcript_full(False)}")

        summ = summary_transf(self.transcription.to_prompt())
        logger.info(f"make_summary: {summ}")

        if summary_cleaner is not None:
            summ = summary_cleaner(summ)
            logger.info(f"cleaned_sum: {summ}")

        return None if summ is None else self.transcription.drop_to_summ(summ)


    def get_summary(self) -> Optional[str]:
        summ = self.transcription.summ
        logger.info(f"get_summary: {summ}")
        if summ == "":
            return None
        return summ


# ---- Bot Factory

class BotConfig(TypedDict):
    RECALL_API_TOKEN: str
    NAME: str
    WEBHOOKS: BotWebHooks

# bot can be accessed by user id (string)
class BotNet:
    def __init__(self, config: BotConfig):
        self.botnet: Dict[str, Bot] = {}
        self.user_id_by_bot_id = {}

        # self.jobs_by_bot: Dict[str, List[schedule.Job]] = {}
        self.jobs_by_bot = defaultdict(list)

        logger.info(f"Botnet config: {config}")

        self.mutex = Lock()

        self.config = config

    def get_by_user_id(self, user_id: str):
        with self.mutex:
            bot = self.botnet.get(user_id, None)

        return bot

    def get_by_bot_id(self, bot_id: str):
        with self.mutex:
            bot = None

            user_id = self.user_id_by_bot_id.get(bot_id, None)
            if user_id is not None:
                bot = self.botnet.get(user_id, None)

        return bot

    def new_bot(self, user_id, summary_transf: callable, summary_interval_sec, summary_cleaner: Optional[callable]):
        if self.get_by_user_id(user_id) is not None:
            return None

        def leave_callback(bot: Bot):
            with self.mutex:
                logger.info("leaving")
                self.botnet.pop(bot.user_id, None)
                self.user_id_by_bot_id.pop(bot.bot_id, None)

                stop_jobs(self.jobs_by_bot.get(bot.bot_id, None))
                self.jobs_by_bot.pop(bot.bot_id, None)

        def join_callback(bot: Bot):
            with self.mutex:
                self.botnet[bot.user_id] = bot
                self.user_id_by_bot_id[bot.bot_id] = bot.user_id

                def schedule_wrapper():
                    logger.info("schedule_wrapper called")
                    state = bot.recording_state()
                    logger.info(f"State: {state}")
                    if isinstance(state, str):
                        with self.mutex:
                            logger.info("stopping schedule_wrapper")
                            stop_jobs(self.jobs_by_bot[bot.bot_id])
                            self.jobs_by_bot.pop(bot.bot_id, None)

                        leave_callback(bot)

                    bot.make_summary(summary_transf, summary_cleaner)

                job = schedule.every(summary_interval_sec).seconds.do(schedule_wrapper)
                self.jobs_by_bot[bot.bot_id].append(job)

        return Bot(
            user_id=user_id,
            recall_api_token=self.config["RECALL_API_TOKEN"],
            bot_name=self.config["NAME"],
            webhooks=self.config["WEBHOOKS"],
            join_callback=join_callback,
            leave_callback=leave_callback
        )

def stop_jobs(jobs):
    if jobs is None:
        return

    for job in jobs:
        schedule.cancel_job(job)
