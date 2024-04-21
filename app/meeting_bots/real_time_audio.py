import queue
from threading import Lock
from app.audio import AudioFileManager, AudioRaw, AudioConverter
from app.speach_kit import YaSpeechToText
from app.meeting_bots.bot import Transcription
from _typeshed import ReadableBuffer


class SpeakerEvent:
    speaker: str
    unmute_ts: float

    def __init__(self, speaker, unmute_ts):
        self.speaker = speaker
        self.unmute_ts = unmute_ts


class RealTimeAudio:
    def __init__(self, bot_id, speech_kit: YaSpeechToText):
        self.audio_file_manager = AudioFileManager(bot_id)
        self.events_queue: list[SpeakerEvent] = []
        self.tr_counter = 0
        self.speech_kit = speech_kit

        self.mutex = Lock()

    def add_speaker_event(self, speaker, unmute_ts):
        with self.mutex:
            self.events_queue.append(SpeakerEvent(speaker=speaker, unmute_ts=unmute_ts))

    def save_segment(self, audio: ReadableBuffer):
        self.audio_file_manager.save_segment(audio)

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

        return transcriptions
