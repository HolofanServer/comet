import discord
from discord.ext import commands

import sys
import subprocess
import platform
import time
import os
from dotenv import load_dotenv

from utils import api
from utils.spam_blocker import SpamBlocker

load_dotenv()
SERVICE_NAME = os.getenv("SERVICE_NAME")

class ManagementBotCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.spam_blocker = SpamBlocker(bot=bot)

    async def rstart_bot(self):
        try:
            if platform.system() == "Linux":
                subprocess.Popen(["sudo", "systemctl", "restart", f"{SERVICE_NAME}.service"])
            elif platform.system() == "Darwin":
                subprocess.Popen(["/bin/sh", "-c", "sleep 1; exec python3 " + " ".join(sys.argv)])
            else:
                print("このOSはサポートされていません。")
                return
            await self.bot.close()
        except Exception as e:
            print(f"再起動中にエラーが発生しました: {e}")

    @commands.hybrid_command(name='ping', hidden=True)
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
        sent_message = await ctx.send(embed=e)
        end_time = time.monotonic()

        bot_ping = round((end_time - start_time) * 1000)

        e.add_field(name="Bot Ping", value=f"{bot_ping}ms", inline=True)
        await sent_message.edit(embed=e)

    @commands.command(name='restart')
    async def restart(self, ctx):
        """Botを再起動します"""
        await ctx.send("Botを再起動します...")
        await self.bot.close()

async def setup(bot):
    await bot.add_cog(ManagementBotCog(bot))