from flask import Flask
from flask_cors import CORS

from app.meeting_bots import BotNet
from app.config import Config


def create_flask_app(bot_net: BotNet):
    app = Flask(__name__)
    CORS(app)
    config = Config()

    from app.http.gpt import make_gpt_handler
    from app.http.meeting_bot import make_bot_handler

    app.register_blueprint(make_gpt_handler(config))
    app.register_blueprint(make_bot_handler(config, bot_net))

    return app
