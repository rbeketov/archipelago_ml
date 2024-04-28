from strenum import StrEnum
from flask import Blueprint
from flask import request, jsonify

from ..config import Config
from ..gpt_utils import send_request_to_gpt
from .utils import HttpException400, json_error
from ..logger import Logger

from enum import auto

logger = Logger().get_logger(__name__)


class EndPoint(StrEnum):
    SUMMARAIZE = auto()
    MIND_MAP = auto()
    CORRECT_DIALOG = auto()


class RequestFields(StrEnum):
    TOKEN_VALUE = "token"
    TEXT_VALUE = "text"
    TEMPERATURE = "temperature"
    SUMMARY_DETAIL = "summary_detail"


def make_gpt_handler(config: Config):
    gpt_blueprint = Blueprint("gpt", __name__)

    def process_request(
        request: dict,
        model_uri: str,
        name_parent_endpoint: str,
        system_prompt: str,
        tokens_depends_on_req=False,
    ):
        token = request[RequestFields.TOKEN_VALUE]
        if token != config.env.TOKEN:
            return json_error(403)

        text = request[RequestFields.TEXT_VALUE]
        temperature = request[RequestFields.TEMPERATURE]
        logger.info(f"From {name_parent_endpoint}\nAccepted request {text}")

        mindmap_text = send_request_to_gpt(
            input_text=text,
            model_uri=model_uri,
            system_prompt=system_prompt,
            api_key=config.env.API_KEY,
            temperature=temperature,
            max_tokens=(len(text) + 10 if tokens_depends_on_req else 2000),
        )

        logger.info(f"Response from {name_parent_endpoint}: {mindmap_text}")

        json_data = {"result": mindmap_text}
        return jsonify(json_data)

    @gpt_blueprint.route("/gpt/get-summarize", methods=["POST"])
    def get_summarize():
        print(request)
        with HttpException400(logger=logger):
            summary_detail_prompt = config.prompts.SUMMARAIZE_WITH_DETAIL(
                request.get_json().get(RequestFields.SUMMARY_DETAIL)
            )
            if summary_detail_prompt is None:
                json_error(400, description="summary_detail is invalid")

            return process_request(
                request=request.json,
                model_uri=config.env.MODEL_URI_SUMM,
                name_parent_endpoint=EndPoint.SUMMARAIZE,
                system_prompt=summary_detail_prompt,
                tokens_depends_on_req=True,
            )

    @gpt_blueprint.route("/gpt/get-mindmap", methods=["POST"])
    def get_mindmap():
        with HttpException400(logger=logger):
            return process_request(
                request=request.json,
                model_uri=config.env.MODEL_URI_GPT,
                name_parent_endpoint=EndPoint.MIND_MAP,
                system_prompt=config.prompts.MIND_MAP,
            )

    @gpt_blueprint.route("/gpt/get-correcting-dialog", methods=["POST"])
    def get_correcting_dialog():
        with HttpException400(logger=logger):
            logger.info(f"get req: {request.json}")
            return process_request(
                request=request.json,
                model_uri=config.prompts.MODEL_URI_GPT,
                name_parent_endpoint=EndPoint.CORRECT_DIALOG,
                system_prompt=config.prompts.CORRECT_DIALOG,
            )

    return gpt_blueprint
