import json
from typing import Optional

import websockets
from app.logger import Logger
from .bot_net import BotNet, RealTimeAudio


logger = Logger().get_logger(__name__)


class RecallWsHooks:
    def __init__(self, bot_net: BotNet):
        self.bot_net = bot_net

    def get_real_time_audio_from_header(
        self, message, _handler_for_logs: str
    ) -> Optional[RealTimeAudio]:
        bot_id = None
        if isinstance(message, str):
            json_message = json.loads(message)
            logger.info("%s: first message: %s", _handler_for_logs, json_message)

            bot_id = json_message.get("bot_id", None)
            if bot_id is None:
                logger.error(
                    "%s: missing bot_id: %s",
                    _handler_for_logs,
                    json_message,
                )
        else:
            logger.error(
                "%s: first message is not string %s", _handler_for_logs, message
            )

        if bot_id is None:
            return None

        bot = self.bot_net.get_by_bot_id(bot_id)
        if bot is None:
            logger.error("%s: bot with %s doesnt exist", _handler_for_logs, bot_id)
            return None

        real_time_audio = bot.real_time_audio
        if real_time_audio is None:
            logger.error(
                "%s: real_time_audio not set for %s", _handler_for_logs, bot_id
            )
            return None

        return real_time_audio

    # TODO: Remove
    @property
    def audio_ws_handler_separate(self):
        async def _audio_ws_handler_separate(websocket, path):
            async for message in websocket:
                if isinstance(message, str):
                    logger.info(f"audio_handler message: {message}")
                else:
                    participant_id = int.from_bytes(message[0:4], byteorder="little")
                    with open(f"output/{participant_id}-output.raw", "ab") as f:
                        f.write(message[4:])
                        logger.info(f"wrote message for {participant_id}")

        return _audio_ws_handler_separate

    @property
    def audio_ws_handler_combined(self):
        async def _audio_ws_handler_combined(
            websocket, path
        ):  # audio_handler message: {"protocol_version":1,"bot_id":"a45c0d94-5822-41c5-8794-9be38e359412","recording_id":"c
            # 333ff7f-dcab-4ec1-b39f-00a259488bb5","separate_streams":false,"offset":0.0}

            first_message = await websocket.recv()

            real_time_audio = self.get_real_time_audio_from_header(
                first_message, "audio_ws_handler_combined"
            )
            if real_time_audio is None:
                await websocket.close()
                return

            # TODO: handle not json and not string
            while True:
                try:
                    message = await websocket.recv()

                    real_time_audio.save_segment(message)

                except websockets.ConnectionClosedOK:
                    break
                except Exception as e:
                    logger.error("audio_ws_handler got exceptiong: %s", e)

        return _audio_ws_handler_combined

    @property
    def speaker_ws_handler(self):
        async def _speaker_ws_handler(websocket, path):  #
            # speaker_handler: {'protocol_version': 1, 'bot_id': 'a45c0d94-5822-41c5-8794-9be38e359412', 'recording_id': 'c333ff7f-
            # dcab-4ec1-b39f-00a259488bb5'}
            first_message = await websocket.recv()

            real_time_audio = self.get_real_time_audio_from_header(
                first_message, "speaker_ws_handler"
            )
            if real_time_audio is None:
                await websocket.close()
                return

            # TODO: handle not json and not string
            while True:
                try:
                    # speaker_handler: {'user_id': 16778240, 'name': 'Степан Попов ИУ5', 'timestamp': 94.797325}
                    message = await websocket.recv()
                    json_message = json.loads(message)
                    logger.info("speaker_ws_handler: message: %s", json_message)

                    speaker = json_message["name"]
                    ts = json_message["timestamp"]

                    real_time_audio.add_speaker_event(speaker=speaker, unmute_ts=ts)

                except websockets.ConnectionClosedOK:
                    break
                except Exception as e:
                    logger.error("speaker_ws_handler got exceptiong: %s", e)

        return _speaker_ws_handler


"""def get_all_recall_ws_hooks():
    return [
        m.__func__ for m in vars(RecallWsHooks).values() if isinstance(m, staticmethod)
    ]
"""
