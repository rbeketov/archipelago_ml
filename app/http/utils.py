from flask import jsonify

from ..logger import Logger
from ..utils import HTTPStatusException

logger = Logger().get_logger(__name__)


def json_error(status_code, description=None):
    if description is None:
        response = jsonify({"error": "Error"})
    else:
        response = jsonify({"error": description})

    response.status_code = status_code
    logger.debug(response)
    return response


class HttpException400:
    def __init__(self, logger):
        self.logger = logger

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        if exc_type is not None:
            self.log_err(exc_type=exc_type, exc_value=exc_value)
            return json_error(400)

    def log_err(self, exc_type, exc_value):
        if self.logger is not None:
            if exc_type is HTTPStatusException:
                logger.error(f"Error: http status: {exc_value.res.json()}")
            else:
                logger.error(f"Error: {exc_value}")
