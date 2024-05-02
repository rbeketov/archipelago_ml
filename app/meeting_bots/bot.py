import re
import json
import requests
from .recall_api import RecallApi
from ..logger import Logger
from typing import Callable, Dict, TypedDict, Optional, Union
from functools import reduce
from ..speach_kit import YaSpeechToText

from .platform_parser import platform_by_url, Platform

logger = Logger().get_logger(__name__)


class SpeakerTranscription(TypedDict):
    message: str
    is_final: bool
    speaker: str


class Transcription(TypedDict):
    id: int
    sp: SpeakerTranscription

    @staticmethod
    def from_recall_resp(recall_resp_tr):
        id = recall_resp_tr["original_transcript_id"]

        speaker = recall_resp_tr["speaker"]
        is_final = recall_resp_tr["is_final"]
        message = reduce(
            lambda text, new_part: f"{text}\n{new_part['text']}",
            recall_resp_tr["words"],
            "",
        )[1:]

        return Transcription(
            id=id,
            sp=SpeakerTranscription(
                message=message, speaker=speaker, is_final=is_final
            ),
        ) # type: ignore


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

            # if 'Noise.' in tr_by_sp["message"]:
            #    continue

            # TODO: make copy of self.t[tr_id]
            tr_by_sp["message"] = self.remove_word_any_regexp(
                tr_by_sp["message"], "noise"
            )

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

    def remove_word_any_regexp(self, inp, word) -> str:
        def c(all_inp, word_inp):
            return re.sub(word_inp, "", all_inp, flags=re.IGNORECASE)

        return c(c(inp, f"{word} "), f" {word}")


# ---- SummaryRepo
class SummaryModel(TypedDict):
    id:  str
    text: str
    text_with_role: str
    active:       bool
    role:         str
    platform:     str
    started_at:   str # ????
    detalization: str

class SummaryRepo:
    def __init__(self, save_endp, get_endp, finish_endp):
        self.save_endp = save_endp
        self.get_endp = get_endp
        self.finish_endp = finish_endp

    def save(self, bot_id, summary: str, platform: str, detalization: str) -> bool:
        try:
            requests.post(
                self.save_endp,
                json={
                    "text": summary,
                    "id": bot_id,
                    "platform": platform,
                    "detalization": detalization,
                },
            )
            return True
        except Exception as e:
            logger.error("failed to save summary:", e)

        return False

    '''
    def update_text(self, summary: str) -> bool:
        try:
            requests.post(
                self.save_endp,
                json={
                    "text": summary,
                    "id": bot_id,
                    "platform": platform,
                    "detalization": detalization,
                },
            )
            return True
        except Exception as e:
            logger.error("failed to save summary:", e)

        return False
    '''

    def update_role_text(self, bot_id, summary_with_role, role) -> bool:
        try:
            requests.post(
                self.save_endp,
                json={
                    "text_with_role": summary_with_role,
                    "role": role,
                    "id": bot_id,
                },
            )
            return True
        except Exception as e:
            logger.error("failed to update summary text role:", e)

        return False

    def get_summary(self, bot_id) -> Optional[SummaryModel]:
        try:
            resp = requests.get(f"{self.get_endp}/{bot_id}")
            resp_json: SummaryModel = resp.json()
            return resp_json
        except Exception as e:
            logger.error("failed to get summary:", e)

        return None

    def get_summ(self, bot_id) -> Optional[tuple[str, bool]]:
        try:
            resp = requests.get(f"{self.get_endp}/{bot_id}")
            resp_json: SummaryModel = resp.json()
            text = resp_json["text"]
            active = resp_json["active"]
            return (text, active)
        except Exception as e:
            logger.error("failed to get summary:", e)

        return None

    def get_summ_with_role(self, bot_id) -> Optional[tuple[str, str, bool]]:
        try:
            resp = requests.get(f"{self.get_endp}/{bot_id}")
            resp_json: SummaryModel = resp.json()
            return (resp_json["text_with_role"], resp_json["role"], resp_json["active"])
        except Exception as e:
            logger.error("failed to get summary:", e)

        return None

    def finish(self, bot_id) -> bool:
        try:
            resp = requests.get(f"{self.finish_endp}/{bot_id}")
        except Exception as e:
            logger.error("failed to finish summary:", e)
            return False

        return resp.status_code == 200

# ----- Bot
class BotWebHooks(TypedDict):
    transcription_url: str
    speaker_ws_url: str
    audio_ws_url: str


class Bot:
    from .real_time_audio import RealTimeAudio

    def __init__(
        self,
        bot_id,
        platform: Platform,
        detalization: str,
        recall_api: RecallApi,
        summary_repo: SummaryRepo,
        speech_kit: YaSpeechToText,
        leave_callback: Callable = lambda _: _,
    ):
        self.bot_id = bot_id
        self.speech_kit = speech_kit
        self.recall_api = recall_api
        self.transcription = FullTranscription()
        self.summary_repo = summary_repo
        self.real_time_audio = RealTimeAudio(self.bot_id, self.speech_kit)

        self.platform = platform
        self.detalization = detalization

        self.leave_callback = leave_callback

    @staticmethod
    def from_join_meeting(
        bot_name,
        detalization: str,
        recall_api_token,
        meeting_url,
        summary_repo: SummaryRepo,
        webhooks: BotWebHooks,
        speech_kit: YaSpeechToText,
        leave_callback: Callable = lambda _: _,
    ):
        recall_api = RecallApi(recall_api_token=recall_api_token)

        logger.debug("Before start_recording")
        resp = recall_api.start_recording(
            bot_name,
            meeting_url=meeting_url,
            destination_transcript_url=webhooks["transcription_url"],
            destination_audio_url=webhooks["audio_ws_url"],
            destination_speaker_url=webhooks["speaker_ws_url"],
        ).json()

        logger.debug("%s", resp)
        bot_id = resp["id"]
        return Bot(
            bot_id=bot_id,
            platform=platform_by_url(meeting_url),
            detalization=detalization,
            summary_repo=summary_repo,
            recall_api=recall_api,
            leave_callback=leave_callback,
            speech_kit=speech_kit,
        )

    @property
    def real_time_audio(self) -> Optional["RealTimeAudio"]:
        return self.real_time_audio

    def leave(self):
        resp = self.recall_api.stop_recording(self.bot_id).json()
        logger.debug(resp)

        self.leave_callback(self)

    def recording_state(self) -> Union[str, bool]:
        return self.recall_api.recording_state_crit(self.bot_id)

    def transcript_full(self, diarization: bool) -> str:
        resp = self.recall_api.transcript(self.bot_id, diarization).json()
        return json.dumps(resp)

    # add_transcription(Transcription.from_recall_resp(response['transcipt']))
    def add_transcription(self, tr: Transcription):
        self.transcription.add(tr["id"], tr["sp"])

    def make_summary(
        self,
        summary_transf: Callable,
        min_prompt_len,
        summary_cleaner: Optional[Callable],
    ) -> None:
        prompt = self.transcription.to_prompt()
        logger.info(f"Промпт: {prompt}")
        if prompt is None:
            return

        logger.info("sync transcrpt: %s", self.transcript_full(False))

        if len(prompt) < min_prompt_len:
            logger.info(f"prompt less than {min_prompt_len}")
            return

        summ = summary_transf(self.transcription.to_prompt())
        logger.info("make_summary: %s", summ)

        if summary_cleaner is not None:
            summ = summary_cleaner(summ)
            logger.info("cleaned_sum: %s", summ)

        if summ is not None:
            self.transcription.drop_to_summ(summ)

        self.summary_repo.save(summary=summ, bot_id=self.bot_id, platform=str(self.platform), detalization=self.detalization)
