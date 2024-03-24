import logging
import os
import sys

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

        formatter = logging.Formatter('%(asctime)s - [%(filename)s:%(module)s:%(funcName)s:%(lineno)d] - %(levelname)s - %(message)s') 

        handlerFile = logging.FileHandler(f"{LOGS_DIR}/server.log")
        handlerFile.setFormatter(formatter)

        handlerStdout = logging.StreamHandler(sys.stdout)
        handlerStdout.setFormatter(formatter)
        
        Logger.handlers = [handlerFile, handlerStdout]

    @classmethod
    def get_logger(cls, package, level=logging.DEBUG):
        logger = logging.getLogger(package)
        logger.setLevel(level)

        for handler in cls.handlers:
            logger.addHandler(handler)
        
        return logger   
    
if __name__ == '__main__':
    logger = Logger().get_logger(__name__)
    logger.debug('aaaa')
