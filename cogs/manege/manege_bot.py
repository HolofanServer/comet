import discord
from discord.ext import commands

import sys
import subprocess
import platform
import time
import os
import asyncio
import json

from dotenv import load_dotenv

from utils import api
from utils.spam_blocker import SpamBlocker
from utils.logging import setup_logging
from utils.commands_help import is_owner, log_commnads

logger = setup_logging()

load_dotenv()
SERVICE_NAME = os.getenv("SERVICE_NAME")

with open('config/bot.json', 'r') as f:
    bot_config = json.load(f)
with open('config/version.json', 'r') as f:
    version_config = json.load(f)

class ManagementBotCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.spam_blocker = SpamBlocker(bot=bot)

    async def rstart_bot(self):
        try:
            if platform.system() == "Linux":
                subprocess.Popen(["sudo", "systemctl", "stop", f"{SERVICE_NAME}.service"])
                await asyncio.sleep(5)
                subprocess.Popen(["sudo", "systemctl", "start", f"{SERVICE_NAME}.service"])
            elif platform.system() == "Darwin":
                subprocess.Popen(["/bin/sh", "-c", "sleep 1; exec python3 " + " ".join(sys.argv)])
            else:
                logger.error("このOSはサポートされていません。")
                return
            await self.bot.close()
        except Exception as e:
            logger.error(f"再起動中にエラーが発生しました: {e}")

    @commands.hybrid_command(name='ping', hidden=True)
    @log_commnads()
    async def ping(self, ctx):
        """BotのPingを表示します"""
        self.spam_blocker.is_not_blacklisted()
        start_time = time.monotonic()
        api_ping = await api.measure_api_ping()

        if not api_ping:
            color = discord.Color.red()
        else:
            color = discord.Color.green()

        e = discord.Embed(title="Pong!", color=color)
        e.add_field(name="API Ping", value=f"{round(api_ping)}ms" if api_ping else "測定失敗", inline=True)
        e.add_field(name="WebSocket Ping", value=f"{round(self.bot.latency * 1000)}ms", inline=True)
        e.set_footer(text=f"Bot Version: {version_config['version']}")
        sent_message = await ctx.send(embed=e)
        end_time = time.monotonic()

        bot_ping = round((end_time - start_time) * 1000)

        e.add_field(name="Bot Ping", value=f"{bot_ping}ms", inline=True)
        await sent_message.edit(embed=e)

    @commands.command(name='restart')
    @is_owner()
    async def restart(self, ctx):
        """Botを再起動します"""
        await ctx.send("Botを再起動します...")
        await self.bot.close()

    @commands.hybrid_group(name='debug')
    async def debug(self, ctx):
        """Botの管理コマンド"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @debug.command(name='tree')
    @is_owner()
    async def tree(self, ctx):
        """Botのディレクトリ構成を表示します"""
        tree = subprocess.check_output('tree --prune -I "iphone3g" -I "config" -I "data" -I "logs" -I "__pycache__" -I ".DS_Store"', shell=True)
        tree = tree.decode('utf-8')
        tree = f"```sh\n{tree}```"
        await ctx.send(tree)

async def setup(bot):
    await bot.add_cog(ManagementBotCog(bot))