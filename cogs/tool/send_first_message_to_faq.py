import asyncio

import discord
from discord.ext import commands

from utils.logging import setup_logging

logger = setup_logging()

class SendFirstMessageToHolopittanCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_thread_create(self, thread):
        if isinstance(thread.parent, discord.ForumChannel) and thread.parent.id == 1378760737027260466:
            await asyncio.sleep(5)
            auther_mention = thread.owner.mention
            embed = discord.Embed(
                title="🎮 ホロぴったん - ゲームを始める準備！",
                description=(
                    f"{thread.owner.display_name} さん、このスレッドでゲームを開始できます！\n\n"
                    "🧩 **このスレッドは「ホロぴったん」専用のゲームルームです！**\n"
                    "以下の手順に沿って、みんなで協力して答えを一致させましょう！\n\n"
                    "初心者向けの説明：https://discord.com/channels/1092138492173242430/1378761943531126937\n\n"
                    "1. </matchgame:1378608353152077824> を実行してゲームを開始\n"
                    "2. 参加者を集める（ボタンを押して参加）\n"
                    "3. 主催者が「ゲーム開始」を押すとスタート！\n"
                    "4. 出題された質問に回答\n"
                    "5. 全員の答えが一致するまで続行！\n\n"
                    "📌 このスレッド内でプレイしてね！途中参加もOKです。\n"
                    "🛠 不具合やバグがあれば </bug_report:1378723645081387210> コマンドで報告してくれると助かります！\n"
                    "フィードバックや要望などは https://discord.com/channels/1092138492173242430/1378761627280867498 で報告してください。"
                ),
                color=discord.Color.teal()
            )
            await thread.send(content=auther_mention, embed=embed)

async def setup(bot):
    await bot.add_cog(SendFirstMessageToHolopittanCog(bot))
