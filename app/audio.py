from threading import Lock
from pydub import AudioSegment
import io

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from _typeshed import ReadableBuffer

from app.logger import Logger

logger = Logger().get_logger(__name__)


class AudioRaw:
    def __init__(
        self, raw_data, _format="raw", sample_width=16000, channels=1, frame_rate=16
    ):
        self.audio_args = {
            "format": _format,
            "sample_width": sample_width,
            "frame_rate": frame_rate,
            "channels": channels,
        }
        self.raw_data = raw_data
        return self

    def get(self, start, duration):
        return AudioSegment.from_file(
            io.BytesIO(self.raw_data),
            start_second=start,
            duration=duration,
            **self.convert_args,
        )


class AudioConverter:
    def __init__(self, audio):
        self.audio = audio

    def convert(self, out_format):
        return self.audio.export(format=out_format).read()

    def convert_to_opus(self):
        return self.convert(out_format="opus")


AUDIO_FILE_PREFIX = "output"


class AudioFile:
    file_path: str
    time_length: int

    def __init__(self, file_path, time_lenght):
        self.file_path = file_path
        self.time_length = time_lenght

    @staticmethod
    def from_bot_id(bot_id, num):
        return AudioFile(file_path=f"{AUDIO_FILE_PREFIX}/{num}_{bot_id}", time_lenght=0)


class AudioFileManager:
    def __init__(self, bot_id):
        self.audio_file = AudioFile.from_bot_id(bot_id, 0)
        self.bot_id = bot_id
        self.mutex = Lock()

    def save_segment(self, audio):
        with self.mutex:
            with open(self.audio_file.file_path, "ab") as f:
                f.write(audio)
                logger.info(f"audio_handler message: wrote {len(audio)} bytes")

    # add range of first and last ts
    def get_file(self):
        with self.mutex:
            with open(self.audio_file.file_path, "rb") as file:
                data = file.read()

        return data


"""
class AuidoManager:
    def __init__(self, bot_id):
        self.audio_files: list[AudioFile] = [AudioFile.from_bot_id(bot_id, 0)]
        self.bot_id = bot_id

    def save_segment(self, audio: ReadableBuffer):
        last_file = self.audio_files[len(self.audio_files) - 1]

        with open(last_file.file_path, "ab") as f:
            f.write(audio)
            logger.info(f"audio_handler message: wrote {len(audio)} bytes")

    def rotate(self):

        self.audio_files.append(
            AudioFile.from_bot_id(self.bot_id, len(self.audio_files))
        )
"""
