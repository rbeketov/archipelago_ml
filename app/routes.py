import json
import os
import logging

from enum import Enum
from flask import Flask, request, jsonify
from dotenv import load_dotenv

from utils import get_sum_GPT

load_dotenv()

API_KEY = os.environ.get("API_KEY")
MODEL_URI = os.environ.get("MODEL_URI")

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
    TEXT_VALUE = "text"


app = Flask(__name__)


@app.route('/get-summarize', methods=['POST'])
def get_summarize():
    try:
        text = request.json[RequestFields.TEXT_VALUE.value]
        logger.info(f"Принят запрос {text}")

        summ_text = get_sum_GPT(text, MODEL_URI, API_KEY)
        logger.info(f"Суммаризированный текст {summ_text}")

        json_data = {"summ_text": summ_text}
        return jsonify(json_data)

    except Exception as e:
        logger.error(f"Ошибка: {e}")


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
