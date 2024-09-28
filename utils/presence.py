import discord
import asyncio
from dotenv import load_dotenv
import os

load_dotenv()

main_guild_id = int(os.getenv("DEV_GUILD_ID"))

presences = [
    {"type": "Playing", "name": "サーバー人数を更新中..."},
    {"type": "Playing", "name": "/omikuji", "state": "1日一回運試し！"},
]

async def update_presence(bot):
    index = 0
    while not bot.is_closed():
        member_count = sum(1 for _ in bot.get_guild(main_guild_id).members)
        
        custom_presence = {"type": "Playing", "name": f"{member_count}人が参加中...", "state": "iPhoneだけだよ！"}
        presences[-1] = custom_presence
        
        presence = presences[index]
        if index != 0:
            if presence["type"] == "Playing":
                activity_type = getattr(discord.ActivityType, presence["type"].lower(), discord.ActivityType.playing)
                activity = discord.Activity(type=activity_type, name=presence["name"], state=presence.get("state", None), status=discord.Status.online)

            await bot.change_presence(activity=activity)
        
        await asyncio.sleep(60)

        index = (index + 1) % len(presences)