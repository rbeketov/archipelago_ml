import json
import os
import sys
import logging
import threading
import requests

from enum import auto
from strenum import StrEnum
from flask import Flask, request, jsonify, abort
from flask_cors import CORS
from dotenv import load_dotenv


from bot_api import HTTPStatusException, Bot, BotNet, BotConfig, Transcription
from gpt_utils import send_request_to_gpt, gpt_req_sender

from logger import Logger

import schedule
import time

load_dotenv()


def env_or_panic(key: str):
    env = os.environ.get(key)
    if env == "":
        raise Exception(f"{key} not set")
    return env


API_KEY = env_or_panic("API_KEY")
MODEL_URI_SUMM = env_or_panic("MODEL_URI_SUMM")
MODEL_URI_GPT = env_or_panic("MODEL_URI_GPT")
TOKEN = env_or_panic("TOKEN")
MYSELF_IP_ADRESS = env_or_panic("MYSELF_IP_ADRESS")
MYSELF_PORT = int(env_or_panic("MYSELF_PORT"))
SUMMARY_INTERVAL = int(env_or_panic("SUMMARY_INTERVAL"))
RECALL_API_TOKEN = env_or_panic("RECALL_API_TOKEN")


logger = Logger().get_logger(__name__)


def json_error(status_code, description=None):
    if description is None:
        response = jsonify({'error': 'Error'})
    else:
        response = jsonify({'error': description})

    response.status_code = status_code
    logger.debug(response)
    return response


class RequestFields(StrEnum):
    TOKEN_VALUE = "token"
    TEXT_VALUE = "text"
    TEMPERATURE = "temperature"


class SystemPromts(StrEnum):
    SUMMARAIZE = "Выдели основные мысли из диалога."
    CLEAN_SUMMARIZATION = "Оставь только главное в тексте"
    STYLE = lambda role: f"Стилизуй текст в роли {role}"

    SUMMARAIZE_OLD = "Ты помогаешь суммаризировать разговор между людьми. Твоя задача - выделять ключевые мысли. Максимум 10 предложений. Если какие то предложения не несут смысла - пропускай их. В конечном тексте не должно быть 'Speaker'."
    MIND_MAP = "Ты опытный редактор. Декопозируй указанный текст на темы, выведи только темы через запятую"
    CORRECT_DIALOG = "Ты помогаешь улучшать расшифроку speach to text. Расшифрока каждого говорящиего начинается со 'Speaker'. Сам текст расшифровки находится после 'Text:'. Не придумывай ничего лишнего, поправь правописание и грамматику диалога. Оставь имена говорящих как есть."


class EndPoint(StrEnum):
    SUMMARAIZE = auto()
    MIND_MAP = auto()
    CORRECT_DIALOG = auto()

app = Flask(__name__)
CORS(app)


def process_request(
    request: dict,
    model_uri: str,
    name_parent_endpoint: str,
    system_prompt: str,
    tokens_depends_on_req=False,
):
    token = request[RequestFields.TOKEN_VALUE]
    if token != TOKEN:
        return json_error(403)

    text = request[RequestFields.TEXT_VALUE]
    temperature = request[RequestFields.TEMPERATURE]
    logger.info(f"From {name_parent_endpoint}\nAccepted request {text}")

    mindmap_text = send_request_to_gpt(
        input_text=text,
        model_uri=model_uri,
        system_prompt=system_prompt,
        api_key=API_KEY,
        temperature=temperature,
        max_tokens=(len(text) + 10 if tokens_depends_on_req else 2000),
    )

    logger.info(f"Response from {name_parent_endpoint}: {mindmap_text}")

    json_data = {"result": mindmap_text}
    return jsonify(json_data)


@app.route('/gpt/get-summarize', methods=['POST'])
def get_summarize():
    print(request)
    try:
        return process_request(
            request=request.json,
            model_uri=MODEL_URI_SUMM,
            name_parent_endpoint=EndPoint.SUMMARAIZE,
            system_prompt=SystemPromts.SUMMARAIZE,
            tokens_depends_on_req=True,
        )
    except Exception as e:
        logger.error(f"Error: {e}")
        return json_error(400)


@app.route('/gpt/get-mindmap', methods=['POST'])
def get_mindmap():
    try:
        return process_request(
            request=request.json,
            model_uri=MODEL_URI_GPT,
            name_parent_endpoint=EndPoint.MIND_MAP,
            system_prompt=SystemPromts.MIND_MAP,
        )
    except Exception as e:
        logger.error(f"Error: {e}")
        return json_error(400)


@app.route('/gpt/get-correcting-dialog', methods=['POST'])
def get_correcting_dialog():
    try:
        logger.info(f"get req: {request.json}")
        return process_request(
            request=request.json,
            model_uri=MODEL_URI_GPT,
            name_parent_endpoint=EndPoint.CORRECT_DIALOG,
            system_prompt=SystemPromts.CORRECT_DIALOG,
        )
    except Exception as e:
        logger.error(f"Error: {e}")
        return json_error(400)


# ---- recall

BOT_CONFIG: BotConfig = {
    "RECALL_API_TOKEN": RECALL_API_TOKEN,
    "WEBHOOK_URL": f"http://{MYSELF_IP_ADRESS}:8080/transcription",
    "NAME": "ArchipelagoSummer",
}

bot_net = BotNet(BOT_CONFIG)

@app.route('/start_recording', methods=['POST'])
def start_recording():

    class RequestFields(StrEnum):
        USER_ID = "user_id"
        MEETING_URL = "url"
        TOKEN_VALUE = "token"

    try:
        logger.info(f"get req: {request.json}")
        if not request.is_json:
            return json_error(400, description="Request body must be JSON")

        # validate
        token = request.json[RequestFields.TOKEN_VALUE]
        if token != TOKEN:
            return json_error(403)

        meeting_url = request.get_json().get(RequestFields.MEETING_URL)
        if not meeting_url:
            return json_error(400, description="meeting_url is required")

        user_id = request.get_json().get(RequestFields.USER_ID)
        if not user_id:
            return json_error(400, description="user_id is required")

        bot = bot_net.new_bot(
            user_id,
            gpt_req_sender(
                MODEL_URI_GPT,
                SystemPromts.SUMMARAIZE,
                API_KEY,
                0,
            ),
            gpt_req_sender(
                MODEL_URI_GPT,
                SystemPromts.CLEAN_SUMMARIZE,
                API_KEY,
                0,
            ),
            SUMMARY_INTERVAL,
        )
        if bot is None:
            return json_error(400, description="This user already have active bot")

        bot.join_and_start_recording(meeting_url=meeting_url)

        return jsonify("OK")

    except Exception as e:
        logger.error(f"Error: {e}")
        return json_error(400)


@app.route('/stop_recording', methods=['POST'])
def stop_recording():

    class RequestFields(StrEnum):
        USER_ID = "user_id"
        TOKEN_VALUE = "token"

    try:
        logger.info(f"get req: {request.json}")
        if not request.is_json:
            return json_error(400, description="Request body must be JSON")

        # validate
        token = request.json[RequestFields.TOKEN_VALUE]
        if token != TOKEN:
            return json_error(403)

        user_id = request.get_json().get(RequestFields.USER_ID)
        if not user_id:
            return json_error(400, description="user_id is required")

        bot = bot_net.get_by_user_id(user_id=user_id)
        if bot is None:
            return json_error(400, description="No such bot")

        bot.leave()

        return jsonify("OK")

    except Exception as e:
        logger.error(f"Error: {e}")
        return json_error(400)

@app.route('/bot_state', methods=['POST'])
def bot_state():

    class RequestFields(StrEnum):
        USER_ID = "user_id"
        TOKEN_VALUE = "token"

    try:
        logger.info(f"get req: {request.json}")
        if not request.is_json:
            return json_error(400, description="Request body must be JSON")

        # validate
        token = request.json[RequestFields.TOKEN_VALUE]
        if token != TOKEN:
            return json_error(403)

        user_id = request.get_json().get(RequestFields.USER_ID)
        if not user_id:
            return json_error(400, description="user_id is required")

        bot = bot_net.get_by_user_id(user_id=user_id)
        if bot is None:
            return json_error(400, description="No such bot")

        state = bot.recording_state()

        if isinstance(state, str):
            return jsonify({"state": state})

        return jsonify({"state": 'ok'})

    except Exception as e:
        logger.error(f"Error: {e}")
        return json_error(400)

@app.route('/transcription', methods=['POST'])
def get_trascription():
    try:
        logger.info(f"webhook /transcription: {request.json}")

        payload = request.json['data']
        bot_id = payload['bot_id']
        transcript = payload['transcript']

        bot = bot_net.get_by_bot_id(bot_id=bot_id)
        if bot is None:
            logger.error("No such bot")
        else:
            bot.add_transcription(Transcription.from_recall_resp(transcript))

        return jsonify({"success": True})

    except Exception as e:
        logger.error(f"Error: {e}")
        return json_error(400)

@app.route('/get_sum', methods=['POST'])
def get_sum():

    class RequestFields(StrEnum):
        USER_ID = "user_id"
        TOKEN_VALUE = "token"
        ROLE = "role"

    try:
        logger.info(f"get req: {request.json}")
        if not request.is_json:
            return json_error(400, description="Request body must be JSON")

        # validate
        token = request.json[RequestFields.TOKEN_VALUE]
        if token != TOKEN:
            return json_error(403)

        user_id = request.get_json().get(RequestFields.USER_ID)
        if not user_id:
            return json_error(400, description="user_id is required")

        role = request.get_json().get(RequestFields.ROLE, None)

        bot = bot_net.get_by_user_id(user_id=user_id)
        if bot is None:
            return json_error(400, description="No such bot")

        summ = bot.get_summary()
        if summ is None:
            return jsonify({"has_sum": False})

        if role is None or role == "dafault":
            summ = send_request_to_gpt(
                summ,
                MODEL_URI_GPT,
                SystemPromts.STYLE(role),
                API_KEY,
                0,
            )
            if summ is None:
                return jsonify({"has_sum": False})


        json_data = {"summ_text": summ, "has_sum": True}
        return jsonify(json_data)

    except HTTPStatusException as e:
        logger.error(f"Error: {e.res.json()}")
        return json_error(400)
    except Exception as e:
        logger.error(f"Error: {e}")
        return json_error(400)

# ----- scheduler

def run_scheduler() -> threading.Thread:
    def scheduler_runner():
        while True:
            schedule.run_pending()
            time.sleep(1)

    return threading.Thread(target=scheduler_runner)


if __name__ == '__main__':
    try:
        thr = run_scheduler()
        thr.start()
        app.run(host='0.0.0.0', port=MYSELF_PORT, debug=True)
    except Exception as e:
        logger.error(f"Server has stopped with {e}")
    finally:
        thr.join()
