import asyncio
import threading
import time

import websockets

from app.logger import Logger

logger = Logger().get_logger(__name__)


class WebSocketServer(threading.Thread):
    def __init__(self, ip, port, ws_serve: callable, reboot_time=5):
        self.ip = ip
        self.port = port
        self.ws_serve = ws_serve
        self.reboot_time = reboot_time

        threading.Thread.__init__(self)

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        while True:
            try:
                print("Starting VL WebSocket Server...")
                logger.info(f"Staring websocket server at {self.ip}:{self.port}")

                startWSServer = websockets.serve(self.ws_serve, self.ip, self.port)
                asyncio.get_event_loop().run_until_complete(startWSServer)
                asyncio.get_event_loop().run_forever()
            except Exception as ex:
                logger.error(
                    f"Web Socket server (port={self.port}) got exception: {ex}"
                )

            if self.reboot_time is None:
                break

            time.sleep(self.reboot_time)
