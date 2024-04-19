from enum import StrEnum
import os
from app.meeting_bots import BotConfig
from app.utils import get_ws_url
from dotenv import load_dotenv


class SystemPromts(StrEnum):
    SUMMARAIZE = "Выдели основные мысли из диалога."
    CLEAN_SUMMARIZATION = "Оставь только главное в тексте"
    STYLE = lambda role: f"Стилизуй текст в роли {role}"  # noqa: E731

    SUMMARAIZE_OLD = "Ты помогаешь суммаризировать разговор между людьми. Твоя задача - выделять ключевые мысли. Максимум 10 предложений. Если какие то предложения не несут смысла - пропускай их. В конечном тексте не должно быть 'Speaker'."
    MIND_MAP = "Ты опытный редактор. Декопозируй указанный текст на темы, выведи только темы через запятую"
    CORRECT_DIALOG = "Ты помогаешь улучшать расшифроку speach to text. Расшифрока каждого говорящиего начинается со 'Speaker'. Сам текст расшифровки находится после 'Text:'. Не придумывай ничего лишнего, поправь правописание и грамматику диалога. Оставь имена говорящих как есть."


class EnvConfig:
    def __init__(self):
        load_dotenv()

        self.API_KEY = self.env_or_panic("API_KEY")
        self.MODEL_URI_SUMM = self.env_or_panic("MODEL_URI_SUMM")
        self.MODEL_URI_GPT = self.env_or_panic("MODEL_URI_GPT")
        self.TOKEN = self.env_or_panic("TOKEN")
        self.MYSELF_IP_ADRESS = self.env_or_panic("MYSELF_IP_ADRESS")
        self.MYSELF_PORT = int(self.env_or_panic("MYSELF_PORT"))
        self.SUMMARY_INTERVAL = int(self.env_or_panic("SUMMARY_INTERVAL"))
        self.MIN_PROMPT_LEN = int(self.env_or_panic("MIN_PROMPT_LEN"))
        self.RECALL_API_TOKEN = self.env_or_panic("RECALL_API_TOKEN")
        self.AUDIO_WS_PORT = int("5723")
        self.SPEAKER_WS_PORT = int("5724")

    def env_or_panic(key: str):
        env = os.environ.get(key)
        if env == "":
            raise Exception(f"{key} not set")
        return env


def make_bot_config(
    recall_api_token, speaker_ws_port, audio_ws_port, ip, port, min_prompt_len
) -> BotConfig:
    return {
        "RECALL_API_TOKEN": recall_api_token,
        "NAME": "ArchipelagoSummer",
        "WEBHOOKS": {
            "speaker_ws_url": get_ws_url("0.0.0.0", speaker_ws_port),
            "audio_ws_url": get_ws_url("0.0.0.0", audio_ws_port),
            "transcription_url": f"http://{ip}:{port}/transcription",
        },
        "MIN_PROMPT_LEN": min_prompt_len,
    }


class Config:
    _instance = None

    _env_config: EnvConfig = None
    _bot_config: BotConfig = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(Config, cls).__new__(cls, *args, **kwargs)

            env = EnvConfig()
            cls._env_config = env
            cls._bot_config = make_bot_config(
                recall_api_token=env.RECALL_API_TOKEN,
                speaker_ws_port=env.SPEAKER_WS_PORT,
                audio_ws_port=env.AUDIO_WS_PORT,
                ip=env.MYSELF_IP_ADRESS,
                port=env.MYSELF_PORT,
                min_prompt_len=env.MIN_PROMPT_LEN,
            )
            cls._prompts = SystemPromts()

        return cls._instance

    def __init__(self):
        pass

    @property
    def env(self) -> EnvConfig:
        return self._env_config

    @property
    def bot_config(self) -> BotConfig:
        return self._bot_config

    @property
    def prompts() -> SystemPromts:
        return SystemPromts
