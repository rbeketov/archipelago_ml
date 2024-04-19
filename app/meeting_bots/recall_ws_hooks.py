import json
from app.logger import Logger


logger = Logger().get_logger(__name__)


class RecallWsHooks:
    @staticmethod
    async def audio_ws_handler(websocket, path):
        async for message in websocket:
            if isinstance(message, str):
                logger.info(f"audio_handler message: {message}")
            else:
                participant_id = int.from_bytes(message[0:4], byteorder="little")
                with open(f"output/{participant_id}-output.raw", "ab") as f:
                    f.write(message[4:])
                    logger.info(f"wrote message for {participant_id}")

    @staticmethod
    async def speaker_ws_handler(websocket, path):
        async for message in websocket:
            if isinstance(message, str):
                json_message = json.loads(message)

                logger.info(f"speaker_handler: {json_message}")

            logger.error(f"speaker_handler: {message}")


def get_all_recall_ws_hooks():
    return [
        m.__func__ for m in vars(RecallWsHooks).values() if isinstance(m, staticmethod)
    ]
