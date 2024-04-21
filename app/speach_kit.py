import os
import requests
from typing import Optional
from app.audio import AudioConverter

from app.logger import Logger
from dotenv import load_dotenv

logger = Logger().get_logger(__name__)


YA_SPEECH_TO_TEXT_URL = (
    "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize?topic=general"
)


class YaSpeechToText:
    def __init__(self, api_key, ffmpeg_path):
        self.api_key = api_key

        load_dotenv()
        os.environ["FFMPEG_PATH"] = ffmpeg_path

    def get(self, opus_audio_data: bytes) -> Optional[str]:
        headers = {
            "Authorization": self.api_key,
            "Content-Type": "audio/ogg",
        }

        try:
            response = requests.post(
                YA_SPEECH_TO_TEXT_URL, data=opus_audio_data, headers=headers
            )
        except Exception as e:
            logger.error("failed to get tr from YaSpeechKit: %s", e)
            return None

        if response.status_code == 200:
            return response.json()["result"]

        logger.error("failed to get tr from YaSpeechKit: response: %s", response.json())
        return None
