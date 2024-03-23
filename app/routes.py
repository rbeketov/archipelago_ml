import json
import os
import logging
import requests

from enum import Enum
from flask import Flask, request, jsonify, abort
from dotenv import load_dotenv

from utils import get_sum_GPT, get_mindmap_GPT

load_dotenv()

API_KEY = os.environ.get("API_KEY")
MODEL_URI_SUMM = os.environ.get("MODEL_URI_SUMM")
MODEL_URI_MINDMAP = os.environ.get("MODEL_URI_MINDMAP")
TOKEN = os.environ.get("TOKEN")

LOGS_DIR = "logs/"


logger = logging.getLogger(__name__)
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)
handler = logging.FileHandler(f"{LOGS_DIR}/server.log")
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s') 
handler.setFormatter(formatter)
logger.setLevel(logging.INFO)
logger.addHandler(handler)


class RequestFields(Enum):
    TOKEN_VALUE = "token"
    TEXT_VALUE = "text"


app = Flask(__name__)


def send_to_speech_kit(audio_data):
    # The URL you're sending the POST request to
    url = 'https://stt.api.cloud.yandex.net/speech/v1/stt:recognize?topic=general'

    # Headers, if needed (e.g., for setting Content-Type)
    headers = {
        'Authorization': 'Api-Key AQVNwCGJU5ig_17yfiOwJrhKojbesdqV2UEx1ho2',
        'Content-Type': 'audio/ogg',
    }

    # Make the POST request
    response = requests.post(url, data=audio_data, headers=headers)

    # Check the status code and print the response
    if response.status_code == 200:
        return response.json()
    else:
        return None


@app.route('/api/get-convert', methods=['POST'])
def get_convert():
    try:
        body = request.data        
        return jsonify(send_to_speech_kit(body))

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return abort(400)


@app.route('/api/get-summarize', methods=['POST'])
def get_summarize():
    try:
        token = request.json[RequestFields.TOKEN_VALUE.value]
        if token != TOKEN:
            return abort(403)

        text = request.json[RequestFields.TEXT_VALUE.value]
        logger.info(f"Принят запрос {text}")

        summ_text = get_sum_GPT(text, MODEL_URI_SUMM, API_KEY)
        logger.info(f"Суммаризированный текст {summ_text}")

        json_data = {"summ_text": summ_text}
        return jsonify(json_data)

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return abort(400)



@app.route('/api/get-mindmap', methods=['POST'])
def get_mindmap():
    try:
        token = request.json[RequestFields.TOKEN_VALUE.value]
        if token != TOKEN:
            return abort(403)


        text = request.json[RequestFields.TEXT_VALUE.value]
        logger.info(f"Принят запрос {text}")

        mindmap_text = get_mindmap_GPT(text, MODEL_URI_MINDMAP, API_KEY)
        logger.info(f"Ответ майндмапы {mindmap_text}")

        json_data = {"mindmap_text": mindmap_text}
        return jsonify(json_data)

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return abort(400)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
