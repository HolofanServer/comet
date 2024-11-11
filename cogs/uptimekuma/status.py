import discord
from discord.ext import commands, tasks
from discord import app_commands

import httpx
import os
from dotenv import load_dotenv

from utils.logging import setup_logging
from utils.commands_help import is_guild

logger = setup_logging()

load_dotenv()

push_url = os.getenv("PUSH_URL")
status_url = os.getenv("STATUS_URL")

class UptimeKumaStatus(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.push_status.start()
        
    @commands.hybrid_group(name="status", description="ステータス感れのコマンドです。")
    @is_guild()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.user_install()
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def status(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @status.command(name="link", description="ステータスページのURLを送信します。")
    @is_guild()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.user_install()
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def link(self, ctx: commands.Context):
        await ctx.defer()
        
        file = discord.File("resource/images/new_status_pages.png", filename="status_pages.png")
        file2 = discord.File("resource/images/original.png", filename="original.png")
        file_list = [file, file2]
        
        e = discord.Embed(
            title="Gizmodo Woods Status",
            description="-# gizmodo woodsで運用しているサービスのステータスを確認できます。\n-# もしサービスが正常に動作していないときはサービスが動作していない可能性があります。\n\n-# 🟢正常に動作中\n-# 🟡動作していない可能性あり\n-# 🔴正常に動作していない",
            color=discord.Color.green(),
            url="https://status.frwi.net/status/gw"
        )
        e.set_image(url="attachment://status_pages.png")
        e.set_thumbnail(url="attachment://original.png")
        e.set_footer(text="Powerd by Uptime Kuma")
        e.set_author(name="https://status.frwi.net/status/gw")
        massage = "ステータスページは[こちら](https://status.frwi.net/status/gw)で確認できます。"
        await ctx.send(embed=e, content=massage, files=file_list)

    @tasks.loop(seconds=60)
    async def push_status(self):
        #logger.info("push_statusが呼び出されました")
        ping = self.bot.latency
        #logger.info(f"ping: {ping}")
        if ping is None or ping != ping:
            ping = 0
        else:
            ping = round(ping * 1000)
        url = f"{push_url}{ping}ms"
        #logger.info(f"URL: {url}")
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url)
                #logger.info(f"response: {response}")
                if response.status_code == 200:
                    #logger.info(f"response.status_code: {response.status_code}")
                    pass
                else:
                    #logger.info(f"response.status_code: {response.status_code}")
                    pass
            except Exception as e:
                logger.error(f"Error pushing status: {e}")
                pass

async def setup(bot):
    await bot.add_cog(UptimeKumaStatus(bot))
