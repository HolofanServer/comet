import os
import json

class JSONManager:
    def __init__(self, filepath, default_data=None):
        self.filepath = filepath
        self.default_data = default_data or {}

    def load(self):
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.save(self.default_data)
            return self.default_data

    def save(self, data):
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
