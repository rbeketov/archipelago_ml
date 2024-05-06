from flask import abort, jsonify, request
from functools import wraps

from ..logger import Logger
from ..utils import HTTPStatusException

logger = Logger().get_logger(__name__)


def resp(r, status_code):
    response = jsonify(r)
    response.status_code = status_code
    return response


def error_resp(description=None):
    if description is None:
        return {"error": "Error"}

    return {"error": description}


def json_error(status_code, description=None):
    response = None

    response = jsonify(error_resp(description=description))

    response.status_code = status_code
    logger.error("response in json_error: %s", response.json)
    return response


class HttpException400:
    def __init__(self, logger):
        self.logger = logger
        self.response = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        if exc_type is not None:
            self.log_err(exc_type=exc_type, exc_value=exc_value)
            self.response = json_error(400)
            return True

    def log_err(self, exc_type, exc_value):
        if self.logger is not None:
            if exc_type is HTTPStatusException:
                logger.error(f"Error: http status: {exc_value.res.json()}")
            else:
                logger.error(f"Error: {exc_value}")


def test_mode(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        test_header = "X-TEST"

        if test_header in request.headers and request.headers[test_header] == "true":
            return f(*args, **kwargs)

        abort(403)

    return decorated
