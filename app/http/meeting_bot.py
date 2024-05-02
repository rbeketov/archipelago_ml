from strenum import StrEnum
from flask import Blueprint
from flask import request, jsonify

from ..config import Config
from ..gpt_utils import gpt_req_sender, send_request_to_gpt
from .utils import json_error, HttpException400
from ..logger import Logger

from ..meeting_bots import BotNet

from ..utils import none_unpack

logger = Logger().get_logger(__name__)


def make_bot_handler(config: Config, bot_net: BotNet) -> Blueprint:
    bot_blueprint = Blueprint("meeting_bot", __name__)

    @bot_blueprint.route("/start_recording", methods=["POST"])
    def start_recording():
        class RequestFields(StrEnum):
            USER_ID = "user_id"
            MEETING_URL = "url"
            SUMMARY_DETAIL = "summary_detail"

        with HttpException400(logger=logger):
            logger.info(f"get req: {request.json}")
            if not request.is_json:
                return json_error(400, description="Request body must be JSON")

            detalization = request.get_json().get(
                RequestFields.SUMMARY_DETAIL, "Средняя"
            )
            summary_detail_prompt = config.prompts.SUMMARAIZE_WITH_DETAIL(detalization)

            meeting_url = request.get_json().get(RequestFields.MEETING_URL)
            if not meeting_url:
                return json_error(400, description="meeting_url is required")

            user_id = request.get_json().get(RequestFields.USER_ID)
            if not user_id:
                return json_error(400, description="user_id is required")

            bot = bot_net.join_meeting(
                meetring_url=meeting_url,
                detalization=detalization,
                summary_transf=gpt_req_sender(
                    config.env.MODEL_URI_GPT,
                    summary_detail_prompt,
                    config.env.API_KEY,
                    0,
                ),
                summary_interval_sec=config.env.SUMMARY_INTERVAL,
                summary_cleaner=gpt_req_sender(
                    config.env.MODEL_URI_GPT,
                    config.prompts.CLEAN_SUMMARIZATION,
                    config.env.API_KEY,
                    0,
                ),
            )

            return jsonify(
                {
                    "summ_id": bot.bot_id,
                }
            )

    @bot_blueprint.route("/stop_recording", methods=["POST"])
    def stop_recording():
        class RequestFields(StrEnum):
            SUMM_ID = "summ_id"

        with HttpException400(logger=logger):
            logger.info(f"get req: {request.json}")
            if not request.is_json:
                return json_error(400, description="Request body must be JSON")

            bot_id = request.get_json().get(RequestFields.SUMM_ID)
            if not bot_id:
                return json_error(400, description="summ_id is required")

            bot = bot_net.get_by_bot_id(bot_id=bot_id)
            if bot is not None:
                bot.leave()
                return jsonify("OK")

            bot_net.recall_api.stop_recording(bot_id)

            return jsonify("OK")

    @bot_blueprint.route("/bot_state", methods=["POST"])
    def bot_state():
        class RequestFields(StrEnum):
            SUMM_ID = "summ_id"

        with HttpException400(logger=logger):
            logger.info(f"get req: {request.json}")
            if not request.is_json:
                return json_error(400, description="Request body must be JSON")

            bot_id = request.get_json().get(RequestFields.SUMM_ID)
            if not bot_id:
                return json_error(400, description="summ_id is required")

            # TODO: may panic if bot not exists
            state = bot_net.recall_api.recording_state_crit(bot_id=bot_id)

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

            from ..meeting_bots.bot import Transcription  # maybe cyclic

            bot = bot_net.get_by_bot_id(bot_id=bot_id)
            if bot is not None:
                bot.add_transcription(Transcription.from_recall_resp(transcript))
                return jsonify({"success": True})

            # TODO:
            # move this inside bot
            summary_model = bot_net.summary_repo.get_summary(bot_id=bot_id)
            if summary_model is None:
                return jsonify({"success": True})

            detalization = summary_model["detalization"]
            summary_detail_prompt = config.prompts.SUMMARAIZE_WITH_DETAIL(detalization)

            bot = bot_net.try_restore_bot(
                bot_id=bot_id,
                summary_transf=gpt_req_sender(
                    config.env.MODEL_URI_GPT,
                    summary_detail_prompt,
                    config.env.API_KEY,
                    0,
                ),
                summary_interval_sec=config.env.SUMMARY_INTERVAL,
                summary_cleaner=gpt_req_sender(
                    config.env.MODEL_URI_GPT,
                    config.prompts.CLEAN_SUMMARIZATION,
                    config.env.API_KEY,
                    0,
                ),
            )

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
            ROLE = "role"

        with HttpException400(logger=logger):
            logger.info(f"get req: {request.json}")
            if not request.is_json:
                return json_error(400, description="Request body must be JSON")

            bot_id = request.get_json().get(RequestFields.SUMM_ID)
            if not bot_id:
                return json_error(400, description="summ_id is required")

            role = request.get_json().get(RequestFields.ROLE)
            if not role or role == "":
                return json_error(400, description="role is required")

            logger.info(f"bot net: {bot_net}")

            # TODO: make sure bot existed
            summ_with_role, summ_role, active = none_unpack(
                bot_net.summary_repo.get_summ_with_role(bot_id=bot_id), 3
            )
            if (
                summ_with_role is not None
                and summ_role == role
                and summ_with_role != ""
            ):
                json_data = {"summ_text": summ_with_role, "has_sum": True}

            summ, active = none_unpack(bot_net.summary_repo.get_summ(bot_id=bot_id), 2)
            if summ is None:
                return jsonify({"has_sum": False})

            if role != "default":
                summ = send_request_to_gpt(
                    summ,
                    config.env.MODEL_URI_GPT,
                    config.prompts.SystemPromts.STYLE(role),
                    config.env.API_KEY,
                    0,
                )
                if summ is None:
                    return jsonify({"has_sum": False})

            # TODO:
            # make async (after response)
            # dont dublicate input if role is default
            # handle update_res == False
            update_res = bot_net.summary_repo.update_role_text(
                bot_id=bot_id, summary_with_role=summ, role=role
            )

            json_data = {"summ_text": summ, "has_sum": True}
            return jsonify(json_data)

    return bot_blueprint
