import logging
import os
import sys
import json
import colorlog

LOGS_DIR = "logs/"


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class Logger(metaclass=Singleton):
    handlers = []

    def __init__(self):
        if not os.path.exists(LOGS_DIR):
            os.makedirs(LOGS_DIR)

        formatter = colorlog.ColoredFormatter(
            "%(light_blue)s%(asctime)s%(reset)s - %(log_color)s%(levelname)s%(reset)s - %(blue)s[%(filename)s:%(module)s:%(funcName)s:%(lineno)d]%(reset)s - %(message)s\n"
        )

        handlerFile = logging.FileHandler(f"{LOGS_DIR}/server.log")
        handlerFile.setFormatter(formatter)

        handlerStdout = logging.StreamHandler(sys.stdout)
        handlerStdout.setFormatter(formatter)

        Logger.handlers = [handlerFile, handlerStdout]

    @classmethod
    def get_logger(
        cls,
        package,
        level=logging.DEBUG,
        dict_prettier=True,
        stack_trace_err_by_default=True,
    ):
        logger = logging.getLogger(package)

        logger = _Logger.from_parent(logger, dict_prettier, stack_trace_err_by_default)

        logger.setLevel(level)

        for handler in cls.handlers:
            logger.addHandler(handler)

        return logger


class DictPrettierFormat(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def __str__(self):
        return json.dumps(dict(self), indent=4, ensure_ascii=False)


class _Logger(logging.Logger):
    def __init__(
        self, dict_prettier=False, stack_trace_err_by_default=False, *args, **kwargs
    ):
        self.dict_prettier = dict_prettier
        self.stack_trace_err_by_default = stack_trace_err_by_default
        super().__init__(*args, **kwargs)

    def error(self, msg, *args, **kwargs):
        if self.stack_trace_err_by_default:
            # super().exception(msg, *args, **kwargs)

            super().error(msg, *args, exc_info=True, **kwargs)

        else:
            super().error(msg, *args, **kwargs)

    def makeRecord(
        self,
        name,
        level,
        fn,
        lno,
        msg,
        args,
        exc_info,
        func=None,
        extra=None,
        sinfo=None,
    ):
        msg = DictPrettierFormat(msg) if isinstance(msg, dict) else msg
        new_record_args = (
            [DictPrettierFormat(arg) if isinstance(arg, dict) else arg for arg in args]
            if self.dict_prettier
            else args
        )
        super_args = (
            name,
            level,
            fn,
            lno,
            msg,
            new_record_args,
            exc_info,
            func,
            extra,
            sinfo,
        )
        return super().makeRecord(*super_args)

    @classmethod
    def from_parent(
        cls,
        parent_logger_instance: logging.Logger,
        dict_prettier=False,
        stack_trace_err_by_default=False,
    ):
        return cls(
            dict_prettier=dict_prettier,
            stack_trace_err_by_default=stack_trace_err_by_default,
            name=parent_logger_instance.name,
            level=parent_logger_instance.level,
        )


if __name__ == "__main__":
    logger = Logger().get_logger(__name__)
    logger.debug("aaaa")
