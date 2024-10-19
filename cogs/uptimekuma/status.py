import discord
from discord.ext import commands, tasks

import httpx
import os
from dotenv import load_dotenv

from utils.logging import setup_logging
from utils.commands_help import is_guild

logger = setup_logging()

load_dotenv()

puth_url = os.getenv("PUSH_URL")
status_url = os.getenv("STATUS_URL")

class UptimeKumaStatus(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.push_status.start()
        
    @commands.hybrid_group(name="status", description="ステータス感れのコマンドです。")
    async def status(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @status.command(name="link", description="ステータスページのURLを送信します。")
    @is_guild()
    async def link(self, ctx: commands.Context):
        await ctx.defer()
        
        file = discord.File("resource/images/status_pages.png", filename="status_pages.png")
        e = discord.Embed(
            title="Gizmodo Woods Status",
            description="-# gizmodo woodsで運用しているサービスのステータスを確認できます。\n-# もしサービスが正常に動作していないときはステータスが黄色か赤色になっているので、その場合はメンテナンスを行っているか、サーバーが正常に動作していない可能性があります。\n\n-# 🟢正常に動作中\n-# 🟡メンテナンス中\n-# 🔴正常に動作していない",
            color=discord.Color.green(),
            url="https://status.frwi.net/status/gw"
        )
        e.set_image(url="attachment://status_pages.png")
        e.set_footer(text="Powerd by Uptime Kuma")
        e.set_author(name="https://status.frwi.net/status/gw")
        massage = "ステータスページは[こちら](https://status.frwi.net/status/gw)で確認できます。"
        await ctx.send(embed=e, content=massage, file=file)
        
    @tasks.loop(seconds=60)
    async def push_status(self):
        url = f"{push_url}"
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url)
                if response.status_code == 200:
                    pass
                else:
                    pass
            except Exception as e:
                logger.error(f"Error pushing status: {e}")
                pass

async def setup(bot):
    await bot.add_cog(UptimeKumaStatus(bot))
