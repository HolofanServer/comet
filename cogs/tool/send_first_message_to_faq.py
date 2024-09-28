import discord
from discord.ext import commands
import asyncio


class SendFirstMessageToFaqCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_thread_create(self, thread):
        if isinstance(thread.parent, discord.ForumChannel) and thread.parent.id == 1230368803746218034:
            await asyncio.sleep(5)
            auther_mention = thread.owner.mention
            embed = discord.Embed(
                title="質問フォーラムへようこそ！",
                description=(
                    "----------------------------------------\n"
                    f"{thread.owner.display_name} さん、質問フォーラムへようこそ！\n\n"
                    "このフォーラムでは**以下の項目**を守って頂けると、メンバーが解決しやすくなりますのでご協力お願いします。\n"
                    "- 問題等は詳しく内容を書いてください。\n"
                    " - PCの不具合であればOSや機種名も\n"
                    " - 問題の内容やどのような状況なのか等画像や動画を添付してもいいかも\n"
                    "- 質問してる側という意識を大切に\n"
                    " - メッセージをくれるメンバーはあなたの問題を解決しようとしてくださっている方々です。リスペクトをもって接しましょう。\n"
                    "----------------------------------------"
                ),
                color=discord.Color.blue()
            )
            await thread.send(content=auther_mention, embed=embed)

async def setup(bot):
    await bot.add_cog(SendFirstMessageToFaqCog(bot))