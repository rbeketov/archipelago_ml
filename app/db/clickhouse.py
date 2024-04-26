import os


import clickhouse_connect
from clickhouse_connect import common
from dotenv import load_dotenv


HOST = "HOST_CLICK"
PORT = "PORT_CLICK"
DATABASE = "DATABASE_CLICK"


class SingleTone(type):
    _instances: dict = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)

        return cls._instances[cls]


class ClickClient(metaclass=SingleTone):
    def __init__(self):
        load_dotenv()

        common.set_setting("autogenerate_session_id", False)

        self._host = os.environ.get(HOST)
        self._port = os.environ.get(PORT)
        self._database = os.environ.get(DATABASE)
        self._click_client = clickhouse_connect.get_client(
            host=self._host,
            port=self._port,
            username="default",
            database=self._database,
        )

    def insert_new_summaraize(
        self,
        prompt: str,
        request: str,
        response: str,
    ):
        data = [[prompt, request, response]]
        self._click_client.insert(
            "gpt_summarize", data, column_names=["prompt", "request", "response"]
        )
