import aiohttp
import time

async def measure_api_ping():
    url = 'https://discord.com/api/v9/gateway'
    async with aiohttp.ClientSession() as session:
        start_time = time.monotonic()
        async with session.get(url) as resp:
            if resp.status == 200:
                end_time = time.monotonic()
                return (end_time - start_time) * 1000
            else:
                return None