import json
import os
import shutil
import uuid
import logging

from datetime import datetime

def save_log(log_data):
    date_str = datetime.now().strftime('%Y-%m-%d')
    time_str = datetime.now().strftime('%H-%M-%S')
    base_dir_path = 'data/logging'
    dir_path = f'{base_dir_path}/{date_str}/{time_str}'

    date_folders = [f for f in os.listdir(base_dir_path) if os.path.isdir(os.path.join(base_dir_path, f))]
    if len(date_folders) > 10:
        oldest_folder = sorted(date_folders)[0]
        archive_path = os.path.join(base_dir_path, 'archive', oldest_folder)
        shutil.move(os.path.join(base_dir_path, oldest_folder), archive_path)

    os.makedirs(dir_path, exist_ok=True)

    file_name = f'{uuid.uuid4()}.json'

    file_path = os.path.join(dir_path, file_name)

    with open(file_path, 'w', encoding='utf-8') as file:
        json.dump(log_data, file, ensure_ascii=False, indent=4)

    print(f'Log saved to {file_path}')

def setup_logging():
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    return logger

