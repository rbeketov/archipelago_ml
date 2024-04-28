from strenum import StrEnum
import os
from .meeting_bots import BotConfig
from dotenv import load_dotenv


def summarization_with_detail(
    agree_detail: str = "Средняя",
):
    aggree_detail_conv: dict = {
        "Средняя": ".",
        "Краткая": " двумя или тремя предложениями",
        "Развёрнутая": " подробно",
    }

    aggree_detail_prompt = aggree_detail_conv.get(agree_detail, None)
    if aggree_detail_prompt is None:
        return None

    return f"Выдели основные мысли из диалога{aggree_detail_prompt}"


class SystemPromts(StrEnum):
    SUMMARAIZE = summarization_with_detail("Средняя")
    CLEAN_SUMMARIZATION = "Оставь только главное в тексте"
    STYLE = lambda role: f"Стилизуй текст в роли {role}"  # noqa: E731
    SUMMARAIZE_WITH_DETAIL = summarization_with_detail

    SUMMARAIZE_OLD = "Ты помогаешь суммаризировать разговор между людьми. Твоя задача - выделять ключевые мысли. Максимум 10 предложений. Если какие то предложения не несут смысла - пропускай их. В конечном тексте не должно быть 'Speaker'."
    MIND_MAP = "Ты опытный редактор. Декопозируй указанный текст на темы, выведи только темы через запятую"
    CORRECT_DIALOG = "Ты помогаешь улучшать расшифроку speach to text. Расшифрока каждого говорящиего начинается со 'Speaker'. Сам текст расшифровки находится после 'Text:'. Не придумывай ничего лишнего, поправь правописание и грамматику диалога. Оставь имена говорящих как есть."


class EnvConfig:
    def __init__(self):
        load_dotenv()

        self.API_KEY = self.__class__.env_or_panic("API_KEY")
        self.MODEL_URI_SUMM = self.__class__.env_or_panic("MODEL_URI_SUMM")
        self.MODEL_URI_GPT = self.__class__.env_or_panic("MODEL_URI_GPT")
        self.TOKEN = self.__class__.env_or_panic("TOKEN")
        self.MYSELF_IP_ADRESS = self.__class__.env_or_panic("MYSELF_IP_ADRESS")
        self.MYSELF_PORT = int(self.__class__.env_or_panic("MYSELF_PORT"))
        self.SUMMARY_INTERVAL = int(self.__class__.env_or_panic("SUMMARY_INTERVAL"))
        self.MIN_PROMPT_LEN = int(self.__class__.env_or_panic("MIN_PROMPT_LEN"))
        self.RECALL_API_TOKEN = self.__class__.env_or_panic("RECALL_API_TOKEN")
        self.API_KEY_SPEACH_KIT = self.__class__.env_or_panic("API_KEY_SPEACH_KIT")

        self.SERVER_NAME = "archipelago.team"  # TODO
        self.SSL_SERT_PATH = self.__class__.env_or_panic("SSL_SERT_PATH")
        self.SSL_KEY_PATH = self.__class__.env_or_panic("SSL_KEY_PATH")

        self.FFMPEG_PATH = self.__class__.env_or_panic("FFMPEG_PATH")  # /usr/bin/ffmpeg
        self.AUDIO_WS_PORT = int("8079")
        self.SPEAKER_WS_PORT = int("8078")
        self.NOTES_PORT = int("8899")

    def env_or_panic(key: str):
        env = os.environ.get(key)
        if env == "" or env is None:
            raise Exception(f"{key} not set")
        return env


def make_bot_config(
    recall_api_token,
    speaker_ws_port,
    audio_ws_port,
    notes_port,
    ip,
    server_name,
    port,
    min_prompt_len,
) -> BotConfig:
    return {
        "RECALL_API_TOKEN": recall_api_token,
        "NAME": "ArchipelagoSummer",
        "WEBHOOKS": {
            "speaker_ws_url": None,  # get_ws_url(server_name, speaker_ws_port),
            "audio_ws_url": None,  # get_ws_url(server_name, audio_ws_port),
            "transcription_url": f"http://{ip}:{port}/transcription",
        },
        "MIN_PROMPT_LEN": min_prompt_len,
        "SUMM_GETTER_ENDP": f"http://{ip}:{notes_port}/get",
        "SUMM_SAVER_ENDP": f"http://{ip}:{notes_port}/save",
        "SUMM_FINISHER_ENDP": f"http://{ip}:{notes_port}/finish",
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
                server_name=env.SERVER_NAME,
                port=env.MYSELF_PORT,
                min_prompt_len=env.MIN_PROMPT_LEN,
                notes_port=env.NOTES_PORT,
            )

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
    def prompts(self) -> SystemPromts:
        return SystemPromts
