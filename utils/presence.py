import discord

import asyncio
import os

from dotenv import load_dotenv

from utils.logging import setup_logging

load_dotenv()

logger = setup_logging()

main_guild_id = int(os.getenv("MAIN_GUILD_ID"))

presences = [
    {"type": "Playing", "name": "/omikuji", "state": "1日一回運試し！"},
    {"type": "Playing", "name": "サーバーブースター限定コマンドで画像を生成しよう！", "state": "DellE3を使ったAI画像生成コマンド"},
    {"type": "Playing", "name": "/help", "state": "わからないことがあれば使ってみてね！"},
]

async def update_presence(bot):
    index = 0
    while not bot.is_closed():
        try:
            member_count = sum(1 for _ in bot.get_guild(main_guild_id).members)
            
            custom_presence = {"type": "Playing", "name": f"{member_count}人が参加中...", "state": "iPhoneだけだよ！"}
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