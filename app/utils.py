import os
import requests


def get_sum_GPT(
    input_text: str,
    model_uri: str,
    api_key: str,
) -> str:
    prompt = {
        "modelUri": model_uri,
        "completionOptions": {
            "stream": False,
            "temperature": 0.1,
            "maxTokens": "2000"
        },
        "messages": [
            {
                "role": "user",
                "text": f"{input_text}",
            },
        ]
    }

    url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
    headers = {
        "Content-Type": "application/json",
        "Authorization": api_key,
    }

    response = requests.post(url, headers=headers, json=prompt)
    return response.json()['result']['alternatives'][0]['message']['text']


def get_mindmap_GPT(
    input_text: str,
    model_uri: str,
    api_key: str,
) -> str:
    prompt = {
        "modelUri": model_uri,
        "completionOptions": {
            "stream": False,
            "temperature": 0.1,
            "maxTokens": "2000"
        },
        "messages": [
            {
                "role": "system",
                "text": "Ты  опытный редактор. Декопозируй указанный текст на 3 темы, выведи только темы через запятую"
            },
            {
                "role": "user",
                "text": f"{input_text}",
            },
        ]
    }

    url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
    headers = {
        "Content-Type": "application/json",
        "Authorization": api_key,
    }

    response = requests.post(url, headers=headers, json=prompt)
    result = response.json()['result']['alternatives'][0]['message']['text'].split('\n')[2:]
    return result
