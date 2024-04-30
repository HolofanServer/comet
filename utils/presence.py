import discord
import random
import asyncio
from dotenv import load_dotenv
import os

load_dotenv()

main_guild_id = int(os.getenv("DQ_GUILD_ID"))
print(main_guild_id)

presences = [
    {"type": "Playing", "name": "サーバー人数を更新中..."},
    {"type": "Playing", "name": "/募集", "state": "冒険者を募集しよう！"},
    {"type": "Playing", "name": "みんなの意見をとりいれています", "state": "使い方は/helpで確認できます"},
]

async def update_presence(bot):
    index = 0
    while not bot.is_closed():
        member_count = sum(1 for _ in bot.get_guild(main_guild_id).members)
        
        custom_presence = {"type": "Playing", "name": f"{member_count}人の仲間たちと冒険中...", "state": "みんなで冒険を楽しもう！"}
        presences[-1] = custom_presence
        
        presence = presences[index]
        if index != 0:
            if presence["type"] == "Playing":
                activity_type = getattr(discord.ActivityType, presence["type"].lower(), discord.ActivityType.playing)
                activity = discord.Activity(type=activity_type, name=presence["name"], state=presence.get("state", None))
                print(presence["name"])

            await bot.change_presence(activity=activity)
        
        await asyncio.sleep(60)

        print(index)
        index = (index + 1) % len(presences)
        print(index)

