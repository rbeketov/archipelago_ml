from app.config import Config
from app.http import create_flask_app
from app.utils import join_all_threads, start_all_threads

from app.meeting_bots import BotNet
from app.scheduler import Scheduler

from app.websocket import WebSocketServer

from logger import Logger

logger = Logger().get_logger(__name__)
config = Config()


if __name__ == "__main__":
    try:
        bot_net = BotNet(config.bot_config)

        scheduler = Scheduler()

        ws_server_1 = WebSocketServer(
            config.env.MYSELF_IP_ADRESS,
            config.env.AUDIO_WS_PORT,
            bot_net.ws_hooks.audio_ws_handler,
        )

        ws_server_2 = WebSocketServer(
            config.env.MYSELF_IP_ADRESS,
            config.env.SPEAKER_WS_PORT,
            bot_net.ws_hooks.speaker_ws_handler,
        )

        threads = [
            scheduler,
            ws_server_1,
            ws_server_2,
        ]

        start_all_threads(threads)

        flask_app = create_flask_app()
        flask_app.run(host="0.0.0.0", port=config.env.MYSELF_PORT, debug=True)

    except Exception as e:
        logger.error(f"Server has stopped with {e}")
    finally:
        join_all_threads(threads)
