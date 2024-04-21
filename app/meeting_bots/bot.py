import re
import json
from requests import Response
from app.meeting_bots.recall_api import RecallApi, RealTimeAudio
from app.utils import wrap_http_err
from app.logger import Logger
from typing import Dict, List, TypedDict, Optional, Union
from functools import reduce
from threading import Lock
from collections import defaultdict
from app.speach_kit import YaSpeechToText

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
        )


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


class BotWebHooks(TypedDict):
    transcription_url: str
    speaker_ws_url: str
    audio_ws_url: str


class Bot:
    def __init__(
        self,
        user_id,
        recall_api_token,
        bot_name,
        webhooks: BotWebHooks,
        speech_kit: YaSpeechToText,
        join_callback: callable = lambda _: _,
        leave_callback: callable = lambda _: _,
    ):
        self.speech_kit = speech_kit
        self.real_time_audio = None
        self.bot_name = bot_name
        self.webhooks = webhooks
        self.recall_api = RecallApi(recall_api_token=recall_api_token)
        self.transcription = FullTranscription()

        self.user_id = user_id

        self.join_callback = join_callback
        self.leave_callback = leave_callback

    @property
    def real_time_audio(self) -> Optional[RealTimeAudio]:
        return self.real_time_audio

    def join_and_start_recording(self, meeting_url):
        logger.debug("Before start_recording")
        resp = self.recall_api.start_recording(
            self.bot_name,
            meeting_url=meeting_url,
            destination_transcript_url=self.webhooks["transcription_url"],
            destination_audio_url=self.webhooks["audio_ws_url"],
            destination_speaker_url=self.webhooks["speaker_ws_url"],
        ).json()

        logger.debug("%s", resp)
        self.bot_id = resp["id"]

        self.real_time_audio = RealTimeAudio(self.bot_id, self.speech_kit)

        self.join_callback(self)

    def leave(self):
        resp = self.recall_api.stop_recording(self.bot_id).json()
        logger.debug(resp)

        self.leave_callback(self)

    def recording_state(self) -> Union[str, bool]:
        resp = self.recall_api.recording_state(self.bot_id).json()
        logger.debug(resp)

        status = resp["status_changes"][-1]

        if status["code"] in [
            "call_ended",
            "fatal",
            "recording_permission_denied",
            "recording_done",
            "done",
        ]:
            return f"{status['sub_code']}: {status['message']}"

        return True

    def transcript_full(self, diarization: bool) -> str:
        resp = self.recall_api.transcript(self.bot_id, diarization).json()
        return json.dumps(resp)

    # add_transcription(Transcription.from_recall_resp(response['transcipt']))
    def add_transcription(self, tr: Transcription):
        self.transcription.add(tr["id"], tr["sp"])

    def make_summary(
        self,
        summary_transf: callable,
        min_prompt_len,
        summary_cleaner: Optional[callable],
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

        return None if summ is None else self.transcription.drop_to_summ(summ)

    def get_summary(self) -> Optional[str]:
        summ = self.transcription.summ
        logger.info("get_summary: %s", summ)
        if summ == "":
            return None
        return summ
