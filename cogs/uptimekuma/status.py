import discord
from discord.ext import commands, tasks
from discord import app_commands

import httpx
import math
import asyncio
import traceback

from config.setting import get_settings

from utils.logging import setup_logging
from utils.commands_help import is_guild

logger = setup_logging()

settings = get_settings()

push_url = settings.uptimekuma_push_url
status_url = settings.uptimekuma_status_url
dev_guild_id = settings.admin_dev_guild_id
spam_logger_channel_id = settings.admin_commands_log_channel_id

class UptimeKumaStatus(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.push_status.start()
        
    @commands.hybrid_group(name="status", description="ステータス関連のコマンドです。")
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
        logger.info("push_statusが呼び出されました")
        ping = self.bot.latency
        if ping is None or math.isnan(ping):
            ping = 0
        else:
            ping = round(ping * 1000)
        url = f"{push_url}{ping}ms"
        logger.info(f"URL: {url}")
        max_retries = 3
        retry_delay = 5

        async with httpx.AsyncClient() as client:
            for attempt in range(1, max_retries + 1):
                try:
                    response = await client.get(url)
                    if response.status_code == 200:
                        logger.info(f"Status push successful on attempt {attempt}: {response.status_code}")
                        break
                    else:
                        logger.warning(f"Unexpected status code on attempt {attempt}: {response.status_code}")
                except httpx.RequestError as e:
                    await self.log_error(f"Request error on attempt {attempt}: {e}")
                except Exception as e:
                    await self.log_error(f"Unexpected error on attempt {attempt}: {e}")
                
                if attempt < max_retries:
                    await asyncio.sleep(retry_delay)
                else:
                    logger.error("Max retries reached. Failed to push status.")
                    await self.log_error("Max retries reached. Failed to push status.")

    async def log_error(self, message):
        logger.error(message, exc_info=True)
        error_traceback = traceback.format_exc()
        full_message = f"{message}\n```{error_traceback}```"
        
        dev_server = dev_guild_id
        if dev_server:
            spam_logger_channel = spam_logger_channel_id
            if spam_logger_channel:
                await spam_logger_channel.send(full_message)

async def setup(bot):
    await bot.add_cog(UptimeKumaStatus(bot))
