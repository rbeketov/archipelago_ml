from typing import Optional
from strenum import StrEnum
from flask import Blueprint
from flask import request, jsonify, Response

from ..config import Config
from ..gpt_utils import gpt_req_sender, send_request_to_gpt
from .utils import json_error, HttpException400, error_resp, resp, test_mode
from ..logger import Logger

from ..meeting_bots import BotNet

from ..utils import none_unpack

logger = Logger().get_logger(__name__)


# TODO: make method to tranform from summary_model
def make_summ_response(
    id, has_summ, platform, date, summ_text, is_active, role, detalization
):
    return {
        "id": id,
        "has_summ": has_summ,
        "platform": platform,
        "date": date,
        "summ_text": summ_text,
        "is_active": is_active,
        "role": role,
        "detalization": detalization,
    }


def make_bot_handler(config: Config, bot_net: BotNet) -> Blueprint:
    bot_blueprint = Blueprint("meeting_bot", __name__)

    @bot_blueprint.route("/start_recording", methods=["POST"])
    def start_recording():
        class RequestFields(StrEnum):
            USER_ID = "user_id"
            MEETING_URL = "url"
            SUMMARY_DETAIL = "summary_detail"

        with HttpException400(logger=logger) as http_e:
            logger.info(f"get req: {request.json}")
            if not request.is_json:
                return json_error(400, description="Request body must be JSON")

            detalization = request.get_json().get(
                RequestFields.SUMMARY_DETAIL, "Средняя"
            )

            meeting_url = request.get_json().get(RequestFields.MEETING_URL)
            if not meeting_url:
                return json_error(400, description="meeting_url is required")

            bot = bot_net.join_meeting(
                meetring_url=meeting_url,
                detalization=detalization,
            )

            return jsonify(
                {
                    "summ_id": bot.bot_id,
                }
            )
        return http_e.response

    @bot_blueprint.route("/stop_recording", methods=["POST"])
    def stop_recording():
        class RequestFields(StrEnum):
            SUMM_ID = "summ_id"

        with HttpException400(logger=logger) as http_e:
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
        return http_e.response

    @bot_blueprint.route("/bot_state", methods=["POST"])
    def bot_state():
        class RequestFields(StrEnum):
            SUMM_ID = "summ_id"

        with HttpException400(logger=logger) as http_e:
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
        return http_e.response

    @bot_blueprint.route("/transcription", methods=["POST"])
    def get_trascription():
        with HttpException400(logger=logger) as http_e:
            logger.info(f"webhook /transcription: {request.json}")

            payload = request.json["data"]
            bot_id = payload["bot_id"]
            transcript = payload["transcript"]

            from ..meeting_bots.bot import Transcription  # maybe cyclic

            bot = bot_net.get_by_bot_id(bot_id=bot_id)
            if bot is not None:
                bot.add_transcription(Transcription.from_recall_resp(transcript))
                return jsonify({"success": True})

            bot = bot_net.try_restore_bot(
                bot_id=bot_id,
            )

            if bot is None:
                logger.error("No such bot")
            else:
                bot.add_transcription(Transcription.from_recall_resp(transcript))

            return jsonify({"success": True})
        return http_e.response

    @bot_blueprint.route("/get_sum", methods=["POST"])
    @test_mode
    def get_sum():
        class RequestFields(StrEnum):
            SUMM_ID = "summ_id"
            ROLE = "role"

        with HttpException400(logger=logger) as http_e:
            logger.info(f"get req: {request.json}")
            if not request.is_json:
                return json_error(400, description="Request body must be JSON")

            bot_id = request.get_json().get(RequestFields.SUMM_ID)
            if not bot_id:
                return json_error(400, description="summ_id is required")

            role = request.get_json().get(RequestFields.ROLE)
            if not role or role == "":
                return json_error(400, description="role is required")

            return resp(
                *get_summ_helper(
                    bot_net=bot_net, bot_id=bot_id, role=role, config=config
                )
            )
        return http_e.response

    @bot_blueprint.route("/batch_get_sum", methods=["POST"])
    @test_mode
    def batch_get_sum():
        with HttpException400(logger=logger) as http_e:
            logger.info(f"get req: {request.json}")
            if not request.is_json:
                return json_error(400, description="Request body must be JSON")

            summaries = request.json["summarizations"]
            batch_resp: list[dict] = []

            for summary in summaries:
                logger.info("for summary in summaries: %s", summary)
                bot_id = summary["summ_id"]
                if not bot_id:
                    return json_error(400, description="summ_id is required")

                role = summary["role"]
                if not role or role == "":
                    return json_error(400, description="role is required")

                r, status = get_summ_helper(
                    bot_net=bot_net, bot_id=bot_id, role=role, config=config
                )

                if status != 200:
                    return resp(r, status)

                batch_resp.append(r)

            logger.info("batch_resp: %s", batch_resp)

            return resp({"summarizations": batch_resp}, 200)
        return http_e.response

    return bot_blueprint


# returns dict or status code
def get_summ_helper(bot_net: BotNet, config: Config, bot_id, role) -> tuple[dict, int]:
    # TODO: make sure bot existed
    summary_model = bot_net.summary_repo.get_summary(bot_id=bot_id)
    if summary_model is None:
        return (error_resp(description="summary not exists"), 400)

    logger.info("summary_model %s", summary_model)
    if summary_model["role"] == role and summary_model["text_with_role"] != "":
        return (
            make_summ_response(
                id=bot_id,
                has_summ=True,
                summ_text=summary_model["text_with_role"],
                platform=summary_model["platform"],
                date=summary_model["started_at"],
                is_active=summary_model["active"],
                role=summary_model["role"],
                detalization=summary_model["detalization"],
            ),
            200,
        )

    summ = summary_model["text"]
    if summ is None or summ == "":
        return (
            make_summ_response(
                id=bot_id,
                has_summ=False,
                summ_text="",
                platform=summary_model["platform"],
                date=summary_model["started_at"],
                is_active=summary_model["active"],
                role=summary_model["role"],
                detalization=summary_model["detalization"],
            ),
            200,
        )

    if role != "default" and role != "обычный":
        summ = send_request_to_gpt(
            summ,
            config.env.MODEL_URI_GPT,
            config.prompts.STYLE(role),
            config.env.API_KEY,
            0,
        )
        if summ is None or summ == "":
            return (
                make_summ_response(
                    id=bot_id,
                    has_summ=False,
                    summ_text="",
                    platform=summary_model["platform"],
                    date=summary_model["started_at"],
                    is_active=summary_model["active"],
                    role=summary_model["role"],
                    detalization=summary_model["detalization"],
                ),
                200,
            )

    # TODO:
    # make async (after response)
    # dont dublicate input if role is default
    # handle update_res == False
    update_res = bot_net.summary_repo.update_role_text(
        bot_id=bot_id, summary_with_role=summ, role=role
    )

    return (
        make_summ_response(
            id=bot_id,
            has_summ=True,
            summ_text=summ,
            platform=summary_model["platform"],
            date=summary_model["started_at"],
            is_active=summary_model["active"],
            role=summary_model["role"],
            detalization=summary_model["detalization"],
        ),
        200,
    )
