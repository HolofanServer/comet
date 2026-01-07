import asyncio

import discord
from discord.ext import commands

from config.setting import get_settings
from utils.logging import setup_logging

logger = setup_logging()
settings = get_settings()

# 設定から取得
HOLOPITTAN_FORUM_CHANNEL_ID = settings.holopittan_forum_channel_id
HFS_GUILD_ID = settings.hfs_main_guild_id
HOLOPITTAN_GUIDE_CHANNEL_ID = settings.holopittan_guide_channel_id
HOLOPITTAN_FEEDBACK_CHANNEL_ID = settings.holopittan_feedback_channel_id


class SendFirstMessageToHolopittanCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_thread_create(self, thread):
        if isinstance(thread.parent, discord.ForumChannel) and thread.parent.id == HOLOPITTAN_FORUM_CHANNEL_ID:
            await asyncio.sleep(5)
            auther_mention = thread.owner.mention
            embed = discord.Embed(
                title="🎮 ホロぴったん - ゲームを始める準備！",
                description=(
                    f"{thread.owner.display_name} さん、このスレッドでゲームを開始できます！\n\n"
                    "🧩 **このスレッドは「ホロぴったん」専用のゲームルームです！**\n"
                    "以下の手順に沿って、みんなで協力して答えを一致させましょう！\n\n"
                    f"初心者向けの説明：https://discord.com/channels/{HFS_GUILD_ID}/{HOLOPITTAN_GUIDE_CHANNEL_ID}\n\n"
                    "1. </matchgame:1378608353152077824> を実行してゲームを開始\n"
                    "2. 参加者を集める（ボタンを押して参加）\n"
                    "3. 主催者が「ゲーム開始」を押すとスタート！\n"
                    "4. 出題された質問に回答\n"
                    "5. 全員の答えが一致するまで続行！\n\n"
                    "📌 このスレッド内でプレイしてね！途中参加もOKです。\n"
                    "🛠 不具合やバグがあれば </bug_report:1378723645081387210> コマンドで報告してくれると助かります！\n"
                    f"フィードバックや要望などは https://discord.com/channels/{HFS_GUILD_ID}/{HOLOPITTAN_FEEDBACK_CHANNEL_ID} で報告してください。"
                ),
                color=discord.Color.teal()
            )
            await thread.send(content=auther_mention, embed=embed)

async def setup(bot):
    await bot.add_cog(SendFirstMessageToHolopittanCog(bot))
