import discord
from discord.ext import commands
import sys
import subprocess
import platform
import asyncio
import time
import os

from utils import api

class ManagementBotCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name='ping', hidden=True)
    async def ping(self, ctx):
        """BotのPingを表示します"""
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

    @commands.hybrid_command(name='embedtetst', hidden=True)
    async def embedtest(self, ctx):
        """Embedのテスト"""

        e1 = discord.Embed(title="Botのバージョン", color=discord.Color.blue())
        e1.add_field(name="Bot", value=f"{self.bot.user.name} {self.bot.user.id}")
        e1.add_field(name="Python", value=f"{platform.python_version()}")
        e1.add_field(name="discord.py", value=f"{discord.__version__}")

        e2 = discord.Embed(title="システム情報", color=discord.Color.blue())
        e2.add_field(name="OS", value=f"{platform.system()} {platform.release()}")
        e2.add_field(name="CPU", value=f"{platform.processor()}")

        e3 = discord.Embed(title="プロセス情報", color=discord.Color.blue())
        e3.add_field(name="プロセスID", value=f"{os.getpid()}")

        embed = [e1, e2, e3]

        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(ManagementBotCog(bot))