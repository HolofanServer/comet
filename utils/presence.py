import asyncio
import datetime

import discord
import pytz

from config.setting import get_settings
from utils.logging import setup_logging

logger = setup_logging()
settings = get_settings()

main_guild_id = settings.admin_main_guild_id

presences = [
    {"type": "Playing", "name": "HFS Manager", "state": "つながる絆、ひろがる推し活"}
]

def get_greeting():
    # 現在のJST時間を取得
    jst_now = datetime.datetime.now(pytz.timezone('Asia/Tokyo'))
    hour = jst_now.hour

    # 時間帯によって挨拶を変更
    if 5 <= hour < 10:
        return "おはようございます！"
    elif 10 <= hour < 18:
        return "こんにちは！"
    else:
        return "こんばんは！"

async def update_presence(bot):
    index = 0
    while not bot.is_closed():
        try:
            guild = bot.get_guild(main_guild_id)
            if guild is None:
                logger.error("Guild not found (waiting for guild cache to be ready)")
                await asyncio.sleep(30)  # ギルドキャッシュが準備できるまで長めに待機
                continue

            # サーバーメンバー数を取得
            member_count = sum(1 for _ in guild.members)

            # 現在のJST時間を取得
            jst_now = datetime.datetime.now(pytz.timezone('Asia/Tokyo'))
            jst_time_str = jst_now.strftime('%H:%M')

            # 時間帯に応じた挨拶
            greeting = get_greeting()

            # 動的なプレゼンスリスト
            dynamic_presences = [
                {"type": "Playing", "name": f"{member_count}人が参加中...", "state": "とまらないホロライブ！"},
                {"type": "Playing", "name": f"{jst_time_str} JST", "state": greeting}
            ]

            # すべてのプレゼンスを結合
            all_presences = dynamic_presences + presences

            # 現在のインデックスのプレゼンスを選択
            presence = all_presences[index % len(all_presences)]

            # アクティビティの種類を設定
            activity_type = getattr(discord.ActivityType, presence["type"].lower(), discord.ActivityType.playing)
            activity = discord.Activity(type=activity_type, name=presence["name"], state=presence.get("state", None), status=discord.Status.online)

            await bot.change_presence(activity=activity)

            await asyncio.sleep(60)

            # 次のプレゼンスに進む
            index = (index + 1) % len(all_presences)

        except discord.ConnectionClosed as e:
            logger.error(f"Connection closed: {e}")
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            await asyncio.sleep(5)
