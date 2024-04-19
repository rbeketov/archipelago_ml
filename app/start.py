import asyncio
import websockets
import json
import os
import sys
import logging
import threading
import requests

from enum import auto
from app.config import Config
from app.http import create_flask_app
from strenum import StrEnum

from app.meeting_bots import BotNet

from logger import Logger

import schedule
import time


logger = Logger().get_logger(__name__)
config = Config()

# ----- websocket

"""async def audio_ws_handler(websocket):
    async for message in websocket:
        if isinstance(message, str):
            logger.info(f"audio_handler message: {message}")
        else:
            participant_id = int.from_bytes(message[0:4], byteorder='little')
            with open(f'output/{participant_id}-output.raw', 'ab') as f:
                f.write(message[4:])
                logger.info(f"wrote message for {participant_id}")

async def speaker_ws_handler(websocket):
    async for message in websocket:
        if isinstance(message, str):
            json_message = json.loads(message)

            logger.info(f"speaker_handler: {json_message}")

        logger.error(f"speaker_handler: {message}")



def run_websocket_server(handler, port, ip = "0.0.0.0") -> threading.Thread:
    def websocket_runner():
        async def websocket_main():
            async with websockets.serve(handler, ip, port):
                await asyncio.Future()

        asyncio.run(websocket_main())

    return threading.Thread(target=websocket_runner)"""

# ----- scheduler


def run_scheduler() -> threading.Thread:
    def scheduler_runner():
        while True:
            schedule.run_pending()
            time.sleep(1)

    return threading.Thread(target=scheduler_runner)


# ------ threads


def start_all_threads(threads):
    for thread in threads:
        thread.start()


def join_all_threads(threads):
    for thread in threads:
        thread.join()


if __name__ == "__main__":
    try:
        bot_net = BotNet(config.bot_config)

        # shed_thr = run_scheduler()
        # shed_thr.start()

        # audio_ws_thr = run_websocket_server(audio_ws_handler, AUDIO_WS_PORT)
        # audio_ws_thr.start()

        # speaker_ws_thr = run_websocket_server(speaker_ws_handler, SPEAKER_WS_PORT)
        # speaker_ws_thr.start()

        threads = [
            run_scheduler(),
            # run_websocket_server(audio_ws_handler, AUDIO_WS_PORT),
            # run_websocket_server(speaker_ws_handler, SPEAKER_WS_PORT),
        ]

        start_all_threads(threads)

        flask_app = create_flask_app()
        flask_app.run(host="0.0.0.0", port=config.env.MYSELF_PORT, debug=True)

    except Exception as e:
        logger.error(f"Server has stopped with {e}")
    finally:
        join_all_threads(threads)
