import discord

import asyncio

from utils.logging import setup_logging
from config.setting import get_settings

logger = setup_logging()
settings = get_settings()

main_guild_id = settings.admin_main_guild_id

presences = [
    {"type": "Playing", "name": "hfs", "state": ""}
]

async def update_presence(bot):
    index = 0
    while not bot.is_closed():
        try:
            guild = bot.get_guild(main_guild_id)
            if guild is None:
                logger.error("Guild not found")
                await asyncio.sleep(5)
                continue

            member_count = sum(1 for _ in guild.members)
            
            custom_presence = {"type": "Playing", "name": f"{member_count}人が参加中...", "state": "とまらないホロライブ！"}
            presences.insert(0, custom_presence)
            
            presence = presences[index]
            if presence["type"] == "Playing":
                activity_type = getattr(discord.ActivityType, presence["type"].lower(), discord.ActivityType.playing)
                activity = discord.Activity(type=activity_type, name=presence["name"], state=presence.get("state", None), status=discord.Status.online)

            await bot.change_presence(activity=activity)
            
            await asyncio.sleep(60)

            index = (index + 1) % len(presences)
            presences.pop(0)

        except discord.ConnectionClosed as e:
            logger.error(f"Connection closed: {e}")
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            await asyncio.sleep(5)