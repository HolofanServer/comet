import json
import os
import shutil
import uuid

from logging import getLogger, StreamHandler, Formatter, INFO, DEBUG, WARNING, ERROR, CRITICAL
from typing import Optional

from datetime import datetime

logger = getLogger(__name__)
handler = StreamHandler()
handler.setLevel(DEBUG)
logger.setLevel(DEBUG)
logger.addHandler(handler)
logger.propagate = False

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
    else:
        level = INFO

    logger.setLevel(level)

    handler = StreamHandler()
    handler.setLevel(level)
    formatter = Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger
