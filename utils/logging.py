import json
import os
import shutil
import uuid

from logging import getLogger, StreamHandler, Formatter, INFO, DEBUG, WARNING, ERROR, CRITICAL, FileHandler
from typing import Optional
from discord.ext.prometheus import PrometheusLoggingHandler

from datetime import datetime

logger = getLogger(__name__)
handler = StreamHandler()
handler.setLevel(DEBUG)
logger.setLevel(DEBUG)
logger.addHandler(handler)
logger.propagate = False

logger_gf = getLogger(__name__)
handler_gf = PrometheusLoggingHandler()
handler_gf.setLevel(DEBUG)
logger_gf.setLevel(DEBUG)
logger_gf.addHandler(handler_gf)
logger_gf.propagate = False

class CustomFormatter(Formatter):
    green = "\x1b[38;20m"
    white = "\x1b[37;20m"
    black = "\x1b[30;20m"
    purple = "\x1b[35;20m"
    blue = "\x1b[34;20m"
    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"

    FORMATS = {
        DEBUG: blue + format + reset,
        INFO: white + format + reset,
        WARNING: yellow + format + reset,
        ERROR: red + format + reset,
        CRITICAL: bold_red + format + reset
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = Formatter(log_fmt)
        return formatter.format(record)

def save_log(log_data):
    logger.info('Saving log data...')
    
    date_str = datetime.now().strftime('%Y-%m-%d')
    time_str = datetime.now().strftime('%H-%M-%S')
    base_dir_path = 'data/logging'
    dir_path = f'{base_dir_path}/{date_str}/{time_str}'

    date_folders = [f for f in os.listdir(base_dir_path) if os.path.isdir(os.path.join(base_dir_path, f))]
    if len(date_folders) > 10:
        oldest_folder = sorted(date_folders)[0]
        archive_path = os.path.join(base_dir_path, 'archive', oldest_folder)
        shutil.move(os.path.join(base_dir_path, oldest_folder), archive_path)
        logger.debug(f'Archived oldest folder: {oldest_folder}')

    os.makedirs(dir_path, exist_ok=True)

    file_name = f'{uuid.uuid4()}.json'

    file_path = os.path.join(dir_path, file_name)

    with open(file_path, 'w', encoding='utf-8') as file:
        json.dump(log_data, file, ensure_ascii=False, indent=4)

    logger.info(f'Log saved to {file_path}')

def setup_logging(mode: Optional[str] = None):
    
    if logger.hasHandlers():
        logger.handlers.clear()

    level = INFO

    if mode == "debug" or mode == "D":
        level = DEBUG
    elif mode == "info" or mode == "I":
        level = INFO
    elif mode == "warning" or mode == "W":
        level = WARNING
    elif mode == "error" or mode == "E":
        level = ERROR
    elif mode == "critical" or mode == "C":
        level = CRITICAL
    elif mode == "gf" or mode == "GF":
        level = DEBUG
        logger_gf.setLevel(DEBUG)
        handler_gf.setLevel(DEBUG)
        handler_gf.setFormatter(CustomFormatter())
        logger_gf.addHandler(handler_gf)
        logger_gf.propagate = False
        
        return logger
    elif mode == "api" or mode == "API":
        path = "data/logging/api"
        if not os.path.exists(path):
            os.makedirs(path, exist_ok=True)
        api_logger = getLogger("API")
        api_logger.setLevel(DEBUG)
        
        api_stream_handler = StreamHandler()
        api_stream_handler.setLevel(DEBUG)
        api_stream_handler.setFormatter(CustomFormatter())
        api_logger.addHandler(api_stream_handler)
        
        api_file_handler = FileHandler(f'{path}/api.log')
        api_file_handler.setLevel(DEBUG)
        api_file_handler.setFormatter(CustomFormatter())
        api_logger.addHandler(api_file_handler)
        
        api_logger.propagate = False
        return api_logger
    else:
        level = INFO

    logger.setLevel(level)

    handler = StreamHandler()
    handler.setLevel(level)
    handler.setFormatter(CustomFormatter())
    logger.addHandler(handler)

    return logger
