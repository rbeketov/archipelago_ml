import os
import requests


def send_request_to_gpt(
    input_text: str,
    model_uri: str,
    system_prompt: str,
    api_key: str,
    temperature: float,
) -> str:
    prompt = {
        "modelUri": model_uri,
        "completionOptions": {
            "stream": False,
            "temperature": temperature,
            "maxTokens": "2000"
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
    return response.json()['result']['alternatives'][0]['message']['text']