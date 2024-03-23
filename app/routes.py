import json
import os
import logging
import sys

from enum import Enum
from flask import Flask, request, jsonify, abort
from dotenv import load_dotenv

from utils import get_sum_GPT, get_mindmap_GPT

from zoom_bot_api import RecallApi

load_dotenv()

API_KEY = os.environ.get("API_KEY")
MODEL_URI_SUMM = os.environ.get("MODEL_URI_SUMM")
MODEL_URI_MINDMAP = os.environ.get("MODEL_URI_MINDMAP")
TOKEN = os.environ.get("TOKEN")

LOGS_DIR = "logs/"


logger = logging.getLogger(__name__)
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)
# handler = logging.FileHandler(f"{LOGS_DIR}/server.log")
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s') 
handler.setFormatter(formatter)
logger.setLevel(logging.INFO)
logger.addHandler(handler)


class RequestFields(Enum):
    TOKEN_VALUE = "token"
    TEXT_VALUE = "text"


app = Flask(__name__)


@app.route('/get-summarize', methods=['POST'])
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



@app.route('/get-mindmap', methods=['POST'])
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

# ---- recall
    

CONFIG = {
    "RECALL_API_TOKEN": os.environ.get("RECALL_API_TOKEN"),
    "DESTINATION_URL": "http://185.241.194.125:8080/transcription",
}    

logger.info(f"RECALL_API_TOKEN: {CONFIG['RECALL_API_TOKEN']}")
recall_api = RecallApi(CONFIG["RECALL_API_TOKEN"])    

class SRRequestFields(Enum):
    MEETING_URL = "url"

@app.route('/start_recording', methods=['POST'])
def start_recording():
    try:
        logger.info(f"get req: {request.json}")
        if not request.is_json:
            return abort(400, description="Request body must be JSON")

        meeting_url = request.get_json().get(SRRequestFields.MEETING_URL.value)
        if not meeting_url:
            return abort(400, description="Meeting URL is required")
        
        resp = recall_api.start_recording("Kotegov Dmitry", meeting_url, CONFIG["DESTINATION_URL"])

        logger.info(f"/start_recording: {resp.json()}")

        return jsonify("OK")

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return abort(400)


@app.route('/stop_recording', methods=['POST'])
def stop_recording():

    class RequestFields(Enum):
        BOT_ID = "bot_id"

    try:
        bot_id = request.json[RequestFields.BOT_ID.value]
        resp = recall_api.stop_recording(bot_id)

        logger.info(f"/stop_recording: {resp.json()}")

        return jsonify("OK")

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return abort(400)

@app.route('/transcription', methods=['POST'])
def get_trascription():
    try:
        logger.info(f"webhook /transcription: {request.json()}")
        return jsonify({"success": True})

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return abort(400)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
