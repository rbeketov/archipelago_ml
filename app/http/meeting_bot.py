from strenum import StrEnum
from flask import Blueprint
from flask import request, jsonify

from ..config import Config
from ..gpt_utils import gpt_req_sender, send_request_to_gpt
from .utils import json_error, HttpException400
from ..logger import Logger

from ..meeting_bots import BotNet, Transcription

logger = Logger().get_logger(__name__)


def make_bot_handler(config: Config, bot_net: BotNet) -> Blueprint:
    bot_blueprint = Blueprint("meeting_bot", __name__)

    @bot_blueprint.route("/start_recording", methods=["POST"])
    def start_recording():
        class RequestFields(StrEnum):
            USER_ID = "user_id"
            MEETING_URL = "url"
            TOKEN_VALUE = "token"
            SUMMARY_DETAIL = "summary_detail"

        with HttpException400(logger=logger):
            logger.info(f"get req: {request.json}")
            if not request.is_json:
                return json_error(400, description="Request body must be JSON")

            # validate
            token = request.json[RequestFields.TOKEN_VALUE]
            if token != config.env.TOKEN:
                return json_error(403)

            summary_detail_prompt = config.prompts.SUMMARAIZE_WITH_DETAIL(
                request.get_json().get(RequestFields.SUMMARY_DETAIL)
            )
            if summary_detail_prompt is None:
                json_error(400, description="summary_detail is invalid")

            meeting_url = request.get_json().get(RequestFields.MEETING_URL)
            if not meeting_url:
                return json_error(400, description="meeting_url is required")

            user_id = request.get_json().get(RequestFields.USER_ID)
            if not user_id:
                return json_error(400, description="user_id is required")

            bot = bot_net.new_bot(
                user_id,
                gpt_req_sender(
                    config.env.MODEL_URI_GPT,
                    summary_detail_prompt,
                    config.env.API_KEY,
                    0,
                ),
                config.env.SUMMARY_INTERVAL,
                gpt_req_sender(
                    config.env.MODEL_URI_GPT,
                    config.prompts.CLEAN_SUMMARIZATION,
                    config.env.API_KEY,
                    0,
                ),
            )
            if bot is None:
                return json_error(400, description="This user already have active bot")

            bot.join_and_start_recording(meeting_url=meeting_url)

            return jsonify(
                {
                    "summ_id": bot.bot_id,
                }
            )

    @bot_blueprint.route("/stop_recording", methods=["POST"])
    def stop_recording():
        class RequestFields(StrEnum):
            USER_ID = "user_id"
            TOKEN_VALUE = "token"

        with HttpException400(logger=logger):
            logger.info(f"get req: {request.json}")
            if not request.is_json:
                return json_error(400, description="Request body must be JSON")

            # validate
            token = request.json[RequestFields.TOKEN_VALUE]
            if token != config.env.TOKEN:
                return json_error(403)

            user_id = request.get_json().get(RequestFields.USER_ID)
            if not user_id:
                return json_error(400, description="user_id is required")

            bot = bot_net.get_by_user_id(user_id=user_id)
            if bot is None:
                return json_error(400, description="No such bot")

            bot.leave()

            return jsonify("OK")

    @bot_blueprint.route("/bot_state", methods=["POST"])
    def bot_state():
        class RequestFields(StrEnum):
            USER_ID = "user_id"
            TOKEN_VALUE = "token"

        with HttpException400(logger=logger):
            logger.info(f"get req: {request.json}")
            if not request.is_json:
                return json_error(400, description="Request body must be JSON")

            # validate
            token = request.json[RequestFields.TOKEN_VALUE]
            if token != config.env.TOKEN:
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

            return jsonify({"state": "ok"})

    @bot_blueprint.route("/transcription", methods=["POST"])
    def get_trascription():
        with HttpException400(logger=logger):
            logger.info(f"webhook /transcription: {request.json}")

            payload = request.json["data"]
            bot_id = payload["bot_id"]
            transcript = payload["transcript"]

            bot = bot_net.get_by_bot_id(bot_id=bot_id)
            if bot is None:
                logger.error("No such bot")
            else:
                bot.add_transcription(Transcription.from_recall_resp(transcript))

            return jsonify({"success": True})

    @bot_blueprint.route("/get_sum", methods=["POST"])
    def get_sum():
        class RequestFields(StrEnum):
            # USER_ID = "user_id"
            SUMM_ID = "summ_id"
            TOKEN_VALUE = "token"
            ROLE = "role"

        with HttpException400(logger=logger):
            logger.info(f"get req: {request.json}")
            if not request.is_json:
                return json_error(400, description="Request body must be JSON")

            # validate
            token = request.json[RequestFields.TOKEN_VALUE]
            if token != config.env.TOKEN:
                return json_error(403)

            bot_id = request.get_json().get(RequestFields.SUMM_ID)
            if not bot_id:
                return json_error(400, description="summ_id is required")

            role = request.get_json().get(RequestFields.ROLE, None)

            logger.info(f"bot net: {bot_net}")

            # TODO: make sure bot existed
            summ = bot_net.summary_repo.get(bot_id=bot_id)

            if summ is None:
                return jsonify({"has_sum": False})

            if role is not None and role != "default":
                summ = send_request_to_gpt(
                    summ,
                    config.env.MODEL_URI_GPT,
                    config.prompts.SystemPromts.STYLE(role),
                    config.env.API_KEY,
                    0,
                )
                if summ is None:
                    return jsonify({"has_sum": False})

            json_data = {"summ_text": summ, "has_sum": True}
            return jsonify(json_data)

    return bot_blueprint
