from threading import Lock
from collections import deque
from ..audio import AudioRaw, AudioConverter
from ..speach_kit import YaSpeechToText

from ..logger import Logger

logger = Logger().get_logger(__name__)

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .bot_net import Transcription


class SpeakerEvent:
    speaker: str
    unmute_ts: float

    def __init__(self, speaker, unmute_ts):
        self.speaker = speaker
        self.unmute_ts = unmute_ts

LAGS = 6400 * 3

class RealTimeAudio:
    from .bot import Transcription

    def __init__(self, bot_id, speech_kit: YaSpeechToText):
        # self.audio_file_manager = AudioFileManager(bot_id)
        self.events_queue: deque[SpeakerEvent] = deque()
        self.tr_counter = 0
        self.timestamp_counter = 0
        self.speech_kit = speech_kit
        self.buffer = []

        self.mutex = Lock()

    # get sync transcript (Roman typing)
    def set_speaker_event(self, speaker, unmute_ts) -> Transcription:
        t = None
        with self.mutex:
            self.events_queue.append(SpeakerEvent(speaker=speaker, unmute_ts=unmute_ts))
            t = self.get_transcription()

        return t

    def save_segment(self, audio):
        self.buffer.extend(audio)

    def get_transcription(self) -> Transcription:
        #current_audio_data = bytes(self.buffer)
        #self.buffer = []

        # XXX: Roman costyl'
        if len(self.buffer) > LAGS:
            current_audio_data = bytes(self.buffer[:-LAGS])
            self.buffer = self.buffer[len(self.buffer)-LAGS:]
        else:
            current_audio_data = bytes(self.buffer)
            self.buffer = []

        if len(self.events_queue) != 1:
            current_speaker = self.events_queue.popleft()
        else:
            current_speaker = self.events_queue[-1]

        logger.info(f"Processed {current_speaker.speaker}")

        transcipt_text = None
        try:
            audio_raw = AudioRaw(current_audio_data)

            opus_audio = AudioConverter(audio_raw.get()).convert_to_opus()

            # DEBUG
            # with open("output/test.mp3", "ab") as f:
            #    f.write(opus_audio)

            transcipt_text = self.speech_kit.get(opus_audio)
            logger.info(f"Getted transcription {transcipt_text}")
        except Exception as e:
            logger.error(f"Error while getting transcription: {e}")
            self.timestamp_counter = 0
            return None

        if not transcipt_text or transcipt_text == "":
            self.timestamp_counter = 0
            return None

        transcription: "Transcription" = {
            "id": self.tr_counter,
            "sp": {
                "is_final": True,
                "message": transcipt_text,
                "speaker": current_speaker.speaker,
            },
        }
        self.tr_counter += 1
        self.timestamp_counter = 0
        return transcription

    """
    def flush_to_transcripts(self) -> list[Transcription]:
        events_to_flush = self.events_queue
        with self.mutex:
            self.events_queue = self.events_queue[len(self.events_queue) - 1]

        raw_data = self.audio_file_manager.get_file()
        audio_raw = AudioRaw(raw_data=raw_data)

        transcriptions: list[Transcription] = []

        for i, e in enumerate(events_to_flush):
            if i == len(events_to_flush) - 1:
                break

            duration = events_to_flush[i + 1].unmute_ts - e.unmute_ts
            transcipt_text = self.speech_kit.get(
                AudioConverter(audio_raw.get(e.unmute_ts, duration)).convert_to_opus()
            )

            if transcipt_text is not None:
                transcription: Transcription = {
                    "id": self.tr_counter,
                    "sp": {
                        "is_final": True,
                        "message": transcipt_text,
                        "speaker": e.speaker,
                    },
                }

                transcriptions.append(transcription)
                self.tr_counter += 1

        logger.info(f"getted transcriptions: {transcriptions}")
        return transcriptions
    """
