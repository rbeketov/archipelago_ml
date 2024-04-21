from app.config import Config
from app.http import create_flask_app
from app.utils import stop_all_threads, start_all_threads

from app.meeting_bots import BotNet
from app.scheduler import Scheduler

from app.websocket import WebSocketServer

from app.logger import Logger

logger = Logger().get_logger(__name__)
config = Config()


if __name__ == "__main__":
    try:
        bot_net = BotNet(config.bot_config)

        scheduler = Scheduler()

        ws_server_1 = WebSocketServer(
            "0.0.0.0",
            config.env.AUDIO_WS_PORT,
            bot_net.ws_hooks.audio_ws_handler_combined,
            reboot_time=None,
        )

        ws_server_2 = WebSocketServer(
            "0.0.0.0",
            config.env.SPEAKER_WS_PORT,
            bot_net.ws_hooks.speaker_ws_handler,
            reboot_time=None,
        )

        threads = [
            scheduler,
            ws_server_1,
            ws_server_2,
        ]

        start_all_threads(threads)

        flask_app = create_flask_app(bot_net=bot_net)
        flask_app.run(host="0.0.0.0", port=config.env.MYSELF_PORT, debug=False)

    except Exception as e:
        logger.error(f"Server has stopped with: {e}")
    finally:
        if "threads" in locals():
            stop_all_threads(threads)
