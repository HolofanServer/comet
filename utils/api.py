import time

import httpx

from config.setting import get_settings
from utils.logging import setup_logging

logger = setup_logging("API")
settings = get_settings()

async def measure_api_ping():
    url = 'https://discord.com/api/v10/gateway'
    headers = {
        'Authorization': f'Bot {settings.bot_token}',
        'User-Agent': 'DiscordBot/0.1'
    }
    async with httpx.AsyncClient(headers=headers) as client:
        start_time = time.monotonic()
        try:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                websocket_url = data.get("url")
                end_time = time.monotonic()
                ping_time = (end_time - start_time) * 1000
                return websocket_url, ping_time
            else:
                logger.error(f"Error: Received status code {resp.status_code}")
                return None, None
        except httpx.RequestError as e:
            logger.error(f"Request failed: {e}")
            return None, None
