import requests
from typing import Optional
from .logger import Logger

from .db import ClickClient


logger = Logger().get_logger(__name__)

STOP_RESPONSES = [
    "простите",
    "я не понимаю о чем вы",
    "я не могу ничего сказать об этом",
    "давайте сменим тему",
    "сложно выделить конкретные основные мысли",
    "сложно выделить основные мысли",
    "диалог не содержит чётко выраженной основной мысли",
]


def gpt_req_sender(
    model_uri: str,
    system_prompt: str,
    api_key: str,
    temperature: float,
    max_tokens=2000,
):
    def inner(
        input_text: str,
    ) -> str:
        return send_request_to_gpt(
            input_text, model_uri, system_prompt, api_key, temperature, max_tokens
        )

    return inner


click_client = ClickClient()


def send_request_to_gpt(
    input_text: str,
    model_uri: str,
    system_prompt: str,
    api_key: str,
    temperature: float,
    max_tokens=2000,
) -> Optional[str]:
    prompt = {
        "modelUri": model_uri,
        "completionOptions": {
            "stream": False,
            "temperature": temperature,
            "maxTokens": max_tokens,
        },
        "messages": [
            {
                "role": "system",
                "text": system_prompt,
            },
            {
                "role": "user",
                "text": input_text,
            },
        ],
    }

    url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
    headers = {
        "Content-Type": "application/json",
        "Authorization": api_key,
    }

    response = requests.post(url, headers=headers, json=prompt)
    logger.debug(f"send_request_to_gpt response: {response.json()}")

    try:
        resp_json = response.json()
        logger.info(resp_json)
        resp_res = resp_json["result"]["alternatives"][0]["message"]["text"]
    except Exception as e:
        logger.error(f"send_request_to_gpt: {e}")
        return None

    strs_to_clean = resp_res.split(".")
    strs = []
    for str_to_clean in strs_to_clean:
        clean = True

        for stop in STOP_RESPONSES:
            if stop in str_to_clean.lower():
                clean = False
                break

        if clean:
            strs.append(str_to_clean)

    resp_res = ".".join(strs)

    try:
        click_client.insert_new_summaraize(system_prompt, input_text, resp_res)
    except Exception as e:
        logger.error(f"failed to log into click: {e}")

    return resp_res
