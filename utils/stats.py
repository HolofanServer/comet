import json
import os

from config.setting import get_settings

settings = get_settings()

stats_json_path = "data/stats/stats.json"

async def get_stats():
    if not os.path.exists(stats_json_path):
        return {}
    with open(stats_json_path) as f:
        return json.load(f)

async def save_stats(stats):
    os.makedirs(os.path.dirname(stats_json_path), exist_ok=True)
    with open(stats_json_path, "w") as f:
        json.dump(stats, f, indent=4)

async def update_stats(category: str, key: str, value):
    stats = await get_stats()
    if category not in stats:
        stats[category] = {}
    stats[category][key] = value
    await save_stats(stats)
