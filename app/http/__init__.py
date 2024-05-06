import logging
from flask import Flask
import flask.cli
from flask_cors import CORS

from ..meeting_bots import BotNet
from ..config import Config


def create_flask_app(bot_net: BotNet):
    app = Flask(__name__)
    app.config["JSON_AS_ASCII"] = False
    CORS(app)
    config = Config()

    from app.http.gpt import make_gpt_handler
    from app.http.meeting_bot import make_bot_handler

    app.register_blueprint(make_gpt_handler(config))
    app.register_blueprint(make_bot_handler(config, bot_net))

    app.logger.setLevel(logging.ERROR)

    flask.cli.show_server_banner = lambda *args: None

    return app
