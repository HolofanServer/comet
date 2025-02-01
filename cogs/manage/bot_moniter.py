import discord
from discord.ext import commands, tasks

import psutil
import platform
import datetime
import pytz
import json
import os

from utils.logging import setup_logging
from utils.commands_help import is_guild
from config.setting import get_settings

logger = setup_logging()
settings = get_settings()

STATUS_FILE = "data/sentry/status.json"

TOKEN = settings.sentry_token

class BotMonitor(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.monitor_channel_id = settings.admin_monitor_channel_id
        self.last_message = None
        self.monitor_status.start()

    def cog_unload(self):
        self.monitor_status.cancel()

    async def load_last_message_id(self):
        """保存されたメッセージIDを読み込む"""
        if os.path.exists(STATUS_FILE):
            with open(STATUS_FILE, "r") as f:
                data = json.load(f)
            return data.get("last_message_id")
        return None

    async def save_last_message_id(self, message_id):
        """メッセージIDを保存する"""
        os.makedirs(os.path.dirname(STATUS_FILE), exist_ok=True)
        with open(STATUS_FILE, "w") as f:
            json.dump({"last_message_id": message_id}, f)

    async def fetch_last_message(self):
        """保存されたメッセージIDからメッセージを取得"""
        last_message_id = await self.load_last_message_id()
        if last_message_id:
            try:
                channel = self.bot.get_channel(self.monitor_channel_id)
                if channel:
                    return await channel.fetch_message(last_message_id)
            except discord.NotFound:
                logger.warning(f"メッセージID {last_message_id} が見つかりませんでした。")
        return None

    @tasks.loop(minutes=5.0)
    async def monitor_status(self):
        try:
            channel = self.bot.get_channel(self.monitor_channel_id)
            if not channel:
                logger.error(f"Monitor channel not found: {self.monitor_channel_id}")
                return

            # Get system metrics
            cpu_percent = psutil.cpu_percent()
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Get bot metrics
            latency = round(self.bot.latency * 1000)  # Convert to ms
            guild_count = len(self.bot.guilds)
            user_count = sum(guild.member_count for guild in self.bot.guilds)
            
            # Create embed
            jst = pytz.timezone('Asia/Tokyo')
            now = datetime.datetime.now(jst)
            
            embed = discord.Embed(
                title="BOTステータスモニター",
                description=f"最終更新: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}",
                color=discord.Color.blue()
            )
            
            # System metrics
            embed.add_field(
                name="システム情報",
                value=f"```\nOS: {platform.system()} {platform.release()}\n"
                      f"CPU使用率: {cpu_percent}%\n"
                      f"メモリ使用率: {memory.percent}%\n"
                      f"ディスク使用率: {disk.percent}%```",
                inline=False
            )
            
            # Bot metrics
            embed.add_field(
                name="BOT情報",
                value=f"```\nPing: {latency}ms\n"
                      f"サーバー数: {guild_count}\n"
                      f"ユーザー数: {user_count}```",
                inline=False
            )
            
            # Update or send new message
            if self.last_message:
                try:
                    await self.last_message.edit(embed=embed)
                except discord.NotFound:
                    self.last_message = await channel.send(embed=embed)
                    await self.save_last_message_id(self.last_message.id)
            else:
                self.last_message = await channel.send(embed=embed)
                await self.save_last_message_id(self.last_message.id)

        except Exception as e:
            logger.error(f"Error in monitor_status: {e}", exc_info=True)

    @monitor_status.before_loop
    async def before_monitor_status(self):
        await self.bot.wait_until_ready()
        self.last_message = await self.fetch_last_message()

    @commands.hybrid_group(name="monitor")
    @is_guild()
    async def monitor(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @monitor.command(name="status")
    @is_guild()
    async def status(self, ctx: commands.Context):
        """現在のBOTステータスを表示します。"""
        await ctx.defer()
        
        cpu_percent = psutil.cpu_percent()
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        latency = round(self.bot.latency * 1000)
        
        jst = pytz.timezone('Asia/Tokyo')
        now = datetime.datetime.now(jst)
        
        embed = discord.Embed(
            title="現在のBOTステータス",
            description=f"取得時刻: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="システム情報",
            value=f"```\nOS: {platform.system()} {platform.release()}\n"
                  f"CPU使用率: {cpu_percent}%\n"
                  f"メモリ使用率: {memory.percent}%\n"
                  f"ディスク使用率: {disk.percent}%```",
            inline=False
        )
        
        embed.add_field(
            name="BOT情報",
            value=f"```\nPing: {latency}ms\n"
                  f"サーバー数: {len(self.bot.guilds)}\n"
                  f"ユーザー数: {sum(g.member_count for g in self.bot.guilds)}```",
            inline=False
        )
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(BotMonitor(bot))
