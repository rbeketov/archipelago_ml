import asyncio
import pathlib
import ssl
import threading
import time

import websockets

from app.logger import Logger

logger = Logger().get_logger(__name__)

ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
localhost_pem = pathlib.Path("/home/ubuntu").with_name("fullchain1.pem")
ssl_context.load_verify_locations(localhost_pem)


class WebSocketServer(threading.Thread):
    def __init__(self, ip, port, ws_serve: callable, reboot_time=None):
        self.ip = ip
        self.port = port
        self.ws_serve = ws_serve
        self.reboot_time = reboot_time

        self.ws_server_stop = None
        self.ws_server_task: asyncio.Task = None
        self.loop = None

        threading.Thread.__init__(self)

    async def _start_ws_server(self):
        server = await websockets.serve(
            self.ws_serve, self.ip, self.port, ssl=ssl_context
        )
        await self.ws_server_stop
        server.close()
        logger.info(f"Web Socket server (port={self.port}) is shutting down")
        await server.wait_closed()

    def run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        running = True
        while running:
            try:
                logger.info(f"Staring websocket server at {self.ip}:{self.port}")

                self.ws_server_stop = self.loop.create_future()
                self.ws_server_task = self.loop.create_task(self._start_ws_server())

                self.loop.run_until_complete(self.ws_server_task)
                break
            except Exception as ex:
                logger.error(
                    f"Web Socket server (port={self.port}) got exception: {ex}",
                    exc_info=True,
                )

                if self.reboot_time is None:
                    running = False

                time.sleep(self.reboot_time)

    def stop(self):
        if self.ws_server_task and not self.ws_server_task.done():
            logger.info(f"self.ws_server_stop: {self.ws_server_stop.done()}")
            self.loop.call_soon_threadsafe(self.ws_server_stop.set_result, None)
