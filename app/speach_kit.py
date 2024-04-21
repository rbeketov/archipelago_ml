import os
import io
import requests
from typing import Optional

from dotenv import load_dotenv
from pydub import AudioSegment

YA_SPEECH_TO_TEXT_URL = (
    "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize?topic=general"
)


class AudioConverter:
    def __init__(self, _format="raw", sample_width=16000, channels=1, frame_rate=16):
        self.convert_args = {
            "format": _format,
            "sample_width": sample_width,
            "frame_rate": frame_rate,
            "channels": channels,
        }
        return self

    def convert(self, raw_data, out_format):
        return (
            AudioSegment.from_file(
                io.BytesIO(raw_data),
                **self.convert_args,
            )
            .export(format=out_format)
            .read()
        )

    def convert_to_opus(self, raw_data):
        return self.convert(raw_data, out_format="opus")


class YaSpeechToText:
    def __init__(self, api_key, ffmpeg_path):
        self.api_key = api_key

        load_dotenv()
        os.environ["FFMPEG_PATH"] = ffmpeg_path

    def get(
        self, audio_data: bytes, opus_converter: AudioConverter | None
    ) -> Optional[str]:
        opus_audio_data = (
            opus_converter.convert_to_opus(audio_data) if opus_converter else audio_data
        )

        headers = {
            "Authorization": self.api_key,
            "Content-Type": "audio/ogg",
        }

        response = requests.post(
            YA_SPEECH_TO_TEXT_URL, data=opus_audio_data, headers=headers
        )
        if response.status_code == 200:
            return response.json()["result"]
        return response.json()


if __name__ == "__main__":
    from app.config import Config

    config = Config()

    with open("audio_data/audio1424368168.mp3", "rb") as file:
        data = file.read()

    print(YaSpeechToText(config.env.API_KEY_SPEACH_KIT).get(data))
