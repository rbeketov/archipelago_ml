import os
import io
import requests
from typing import Optional

from dotenv import load_dotenv
from pydub import AudioSegment


load_dotenv()
os.environ["FFMPEG_PATH"] = "/opt/homebrew/bin/ffmpeg"
API_KEY_SPEACH_KIT = os.environ.get("API_KEY_SPEACH_KIT")


def _convert_audio_mp3_to_opus(mp3_data) -> bytes:
    audio = AudioSegment.from_file(io.BytesIO(mp3_data), format="mp3")
    opus_data = audio.export(format="opus").read()
    return opus_data

def get_speach_to_text(audio_data: bytes) -> Optional[str]:
    opus_audio_data = _convert_audio_mp3_to_opus(audio_data)
    url = 'https://stt.api.cloud.yandex.net/speech/v1/stt:recognize?topic=general'

    headers = {
        'Authorization': API_KEY_SPEACH_KIT,
        'Content-Type': 'audio/ogg',
    }

    response = requests.post(url, data=opus_audio_data, headers=headers)
    if response.status_code == 200:
        return response.json()['result']
    return response.json()


if __name__ == "__main__":
    with open("audio_data/audio1424368168.mp3", "rb") as file:
        data = file.read()
    print(get_speach_to_text(data))
