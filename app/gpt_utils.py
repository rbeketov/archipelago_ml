import os
from typing import Optional
import requests
from logger import Logger

logger = Logger().get_logger(__name__)

def gpt_req_sender(
    model_uri: str,
    system_prompt: str,
    api_key: str,
    temperature: float,
    max_tokens=2000,
):
    def inner(input_text: str,) -> str:
        return send_request_to_gpt(input_text, model_uri, system_prompt, api_key, temperature, max_tokens)

    return inner


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
            "maxTokens": max_tokens
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
        ]
    }

    url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
    headers = {
        "Content-Type": "application/json",
        "Authorization": api_key,
    }

    response = requests.post(url, headers=headers, json=prompt)
    logger.debug(f"send_request_to_gpt response: {response.json()}")

    try:
        return response.json()['result']['alternatives'][0]['message']['text']
    except Exception as e:
        logger.error(f"send_request_to_gpt: {e}")
        return None

