import json
import os
import sys

from enum import Enum
from flask import Flask, request, jsonify, abort
from dotenv import load_dotenv

from utils import get_sum_GPT, get_mindmap_GPT

from zoom_bot_api import ZoomBot, ZoomBotNet, ZoomBotConfig, Transcription

from logger import Logger

load_dotenv()

API_KEY = os.environ.get("API_KEY")
MODEL_URI_SUMM = os.environ.get("MODEL_URI_SUMM")
MODEL_URI_MINDMAP = os.environ.get("MODEL_URI_MINDMAP")
TOKEN = os.environ.get("TOKEN")

logger = Logger().get_logger(__name__)


def json_error(status_code, description=None):
    if description is None:
        response = jsonify({'error': 'Error'})
    else:
        response = jsonify({'error': description})

    response.status_code = status_code
    logger.debug(response)
    return response



class RequestFields(Enum):
    TOKEN_VALUE = "token"
    TEXT_VALUE = "text"


app = Flask(__name__)

@app.route('/get-summarize', methods=['POST'])
def get_summarize():
    try:
        token = request.json[RequestFields.TOKEN_VALUE.value]
        if token != TOKEN:
            return json_error(403)

        text = request.json[RequestFields.TEXT_VALUE.value]
        logger.info(f"Принят запрос {text}")

        summ_text = get_sum_GPT(text, MODEL_URI_SUMM, API_KEY)
        logger.info(f"Суммаризированный текст {summ_text}")

        json_data = {"summ_text": summ_text}
        return jsonify(json_data)

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return json_error(400)



@app.route('/get-mindmap', methods=['POST'])
def get_mindmap():
    try:
        token = request.json[RequestFields.TOKEN_VALUE.value]
        if token != TOKEN:
            return json_error(403)


        text = request.json[RequestFields.TEXT_VALUE.value]
        logger.info(f"Принят запрос {text}")

        mindmap_text = get_mindmap_GPT(text, MODEL_URI_MINDMAP, API_KEY)
        logger.info(f"Ответ майндмапы {mindmap_text}")

        json_data = {"mindmap_text": mindmap_text}
        return jsonify(json_data)

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return json_error(400)


# ---- recall zoom
    
ZOOM_BOT_CONFIG: ZoomBotConfig = {
    "RECALL_API_TOKEN": os.environ.get("RECALL_API_TOKEN"),
    "WEBHOOK_URL": "http://185.241.194.125:8080/transcription",
    "NAME": "Dmitry Kotegov",
}     

zoom_bot_net = ZoomBotNet(ZOOM_BOT_CONFIG)

@app.route('/start_recording', methods=['POST'])
def start_recording():

    class RequestFields(Enum):
        USER_ID = "user_id"
        MEETING_URL = "url"
        TOKEN_VALUE = "token"

    try:
        logger.info(f"get req: {request.json}")
        if not request.is_json:
            return json_error(400, description="Request body must be JSON")

        # validate
        token = request.json[RequestFields.TOKEN_VALUE.value]
        if token != TOKEN:
            return json_error(403)
        
        meeting_url = request.get_json().get(RequestFields.MEETING_URL.value)
        if not meeting_url:
            return json_error(400, description="meeting_url is required")
        
        user_id = request.get_json().get(RequestFields.USER_ID.value)
        if not user_id:
            return json_error(400, description="user_id is required")
        
        #
        bot = zoom_bot_net.new_bot(user_id)
        bot.join_and_start_recording(meeting_url=meeting_url)

        return jsonify("OK")

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return json_error(400)


@app.route('/stop_recording', methods=['POST'])
def stop_recording():

    class RequestFields(Enum):
        USER_ID = "user_id"
        TOKEN_VALUE = "token"

    try:
        logger.info(f"get req: {request.json}")
        if not request.is_json:
            return json_error(400, description="Request body must be JSON")

        # validate
        token = request.json[RequestFields.TOKEN_VALUE.value]
        if token != TOKEN:
            return json_error(403)
        
        user_id = request.get_json().get(RequestFields.USER_ID.value)
        if not user_id:
            return json_error(400, description="user_id is required")

        bot = zoom_bot_net.get_by_user_id(user_id=user_id)
        if bot is None:
            return json_error(400, description="No such bot")
        
        bot.leave()

        return jsonify("OK")

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return json_error(400)
    
@app.route('/bot_state', methods=['POST'])
def bot_state():

    class RequestFields(Enum):
        USER_ID = "user_id"
        TOKEN_VALUE = "token"

    try:
        logger.info(f"get req: {request.json}")
        if not request.is_json:
            return json_error(400, description="Request body must be JSON")

        # validate
        token = request.json[RequestFields.TOKEN_VALUE.value]
        if token != TOKEN:
            return json_error(403)
        
        user_id = request.get_json().get(RequestFields.USER_ID.value)
        if not user_id:
            return json_error(400, description="user_id is required")

        bot = zoom_bot_net.get_by_user_id(user_id=user_id)
        if bot is None:
            return json_error(400, description="No such bot")

        state = bot.recording_state()

        if isinstance(state, str):
            return json_error(400, description=state)

        return jsonify("OK")

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return json_error(400)

@app.route('/transcription', methods=['POST'])
def get_trascription():
    try:
        logger.info(f"webhook /transcription: {request.json}")

        bot_id = request.json['data']['bot_id']
        transcript = request.json['transcipt']

        bot = zoom_bot_net.get_by_bot_id(bot_id=bot_id)
        if bot is None:
            logger.error("No such bot")
        else:
            bot.add_transcription(Transcription.from_recall_resp(transcript))

        return jsonify({"success": True})

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return json_error(400)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
