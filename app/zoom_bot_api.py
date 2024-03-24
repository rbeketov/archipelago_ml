import os
import requests
from requests import Response
from logger import Logger
from typing import Dict, TypedDict
from functools import reduce
from threading import Lock

logger = Logger().get_logger(__name__)

# --- util

class HTTPStatusException(Exception):
    def __init__(self, res):
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
    def start_recording(self, bot_name, meeting_url, destination_url):
        body = {
            "bot_name": bot_name,
            "meeting_url": meeting_url,
            "transcription_options": {
                "provider": 'meeting_captions',
            },
            "real_time_transcription": {
                "destination_url": destination_url,
                "partial_results": True,
            },
            "zoom": {
                "request_recording_permission_on_host_join": True,
                "require_recording_permission": True,
            },
        }

        return self.recall_post('/api/v1/bot', body)

    def stop_recording(self, bot_id):
        return self.recall_post(f"/api/v1/bot/{bot_id}/leave_call", json_body={})

    def recording_state(self, bot_id):
        return self.recall_get(f'/api/v1/bot/{bot_id}')

# ---- Zoom bot
    
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
        t: Dict[int, SpeakerTranscription] = {}

    def add(self, tr_id, sp: SpeakerTranscription):
        self.t[tr_id] = sp

    def to_summary_prompt(self, only_final=True) -> str | None:
        # self.t.update(sorted(self.t.items(), key=lambda item: item[1]))

        prompt = ""
        for tr_id in sorted(self.t):
            tr_by_sp = self.t[tr_id]
            if only_final and not tr_by_sp["is_final"]:
                continue

            prompt = f"""Speaker: {tr_by_sp['speaker']}
            Text:
            {tr_by_sp["message"]}

            """
        
        if prompt == "":
            return None
        
        return prompt


class ZoomBot:
    def __init__(self, user_id, recall_api_token, bot_name, webhook_url, join_callback: callable = lambda _: _, leave_callback: callable = lambda _: _):
        self.bot_name = bot_name
        self.webhook_url = webhook_url
        self.recall_api = RecallApi(recall_api_token=recall_api_token)
        self.transcription = FullTranscription()

        self.user_id = user_id

        self.join_callback = join_callback
        self.leave_callback = leave_callback

    def join_and_start_recording(self, meeting_url):
        logger.debug("Before start_recording")
        resp = self.recall_api.start_recording(self.bot_name, meeting_url=meeting_url, destination_url=self.webhook_url).json()
        logger.debug(resp)
        self.bot_id = resp['id']

        self.join_callback(self)

    def leave(self):
        resp = self.recall_api.stop_recording(self.bot_id).json()
        logger.debug(resp)

        self.leave_callback(self)
        
    def recording_state(self) -> str | bool:
        resp = self.recall_api.recording_state(self.bot_id).json()
        logger.debug(resp)

        status = resp['status_changed']

        if status['code'] in ['call_ended', 'fatal', 'recording_permission_denied']:
            return f"{status['sub_code']}: {status['message']}"

        return True

    # add_transcription(Transcription.from_recall_resp(response['transcipt']))
    def add_transcription(self, tr: Transcription):
        self.transcription.add(tr['id'], tr["sp"])

    def get_summary_prompt(self) -> str | None:
        return self.transcription.to_summary_prompt()

# ---- Bot Factory

class ZoomBotConfig(TypedDict):
    RECALL_API_TOKEN: str
    NAME: str
    WEBHOOK_URL: str

# bot can be accessed by user id (string)
class ZoomBotNet:
    def __init__(self, config: ZoomBotConfig):
        self.botnet: Dict[str, ZoomBot] = {}
        self.user_id_by_bot_id = {}

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
    
    def new_bot(self, user_id):

        def join_callback(bot: ZoomBot):
            with self.mutex:
                self.botnet[bot.user_id] = bot
                self.user_id_by_bot_id[bot.bot_id] = bot.user_id

        def leave_callback(bot: ZoomBot):
            with self.mutex:
                self.botnet.pop(bot.user_id, None)
                self.user_id_by_bot_id.pop(bot.bot_id)

        return ZoomBot(
            user_id=user_id,
            recall_api_token=self.config["RECALL_API_TOKEN"],
            bot_name=self.config["NAME"],
            webhook_url=self.config["WEBHOOK_URL"],
            join_callback=join_callback,
            leave_callback=leave_callback
        )
