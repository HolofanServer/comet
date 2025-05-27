import discord
from discord.ext import commands
from discord import app_commands

import pytz
import json
import subprocess

from datetime import datetime
from typing import Callable

from utils.logging import setup_logging
from config.setting import get_settings
from utils.stats import update_stats, get_stats

settings = get_settings()

owner_id = settings.bot_owner_id
moderator_role_name = "Community Mod"
dev_guild_id = settings.admin_dev_guild_id
log_commands_channel_id = settings.admin_commands_log_channel_id

with open("config/bot.json", "r", encoding="utf-8") as f:
    bot_config = json.load(f)
with open("config/version.json", "r", encoding="utf-8") as f:
    version_config = json.load(f)

logger = setup_logging("D")

def is_guild():
    async def predicate(ctx: commands.Context):
        if ctx.guild is None:
            logger.warning(f"DMでコマンドが実行されました: {ctx.author}")
            await ctx.send("このコマンドはDMでは利用できません。")
            return False
        else:
            return True
    return commands.check(predicate)

def is_owner():
    async def predicate(ctx: commands.Context):
        logger.debug(f"{owner_id}/{ctx.author.id}")
        if ctx.author.id != owner_id:
            logger.warning(f"オーナー以外のユーザーがコマンドを実行しようとしました: {ctx.author}")
            await ctx.send("このコマンドはBotのオーナーのみが利用できます。")
            return False
        else:
            return True
    return commands.check(predicate)

def is_moderator():
    async def predicate(ctx: commands.Context):
        if ctx.guild.id == int(dev_guild_id):
            return True
        if not any(role.name == moderator_role_name for role in ctx.author.roles):
            logger.warning(f"モデレーター以外のユーザーがコマンドを実行しようとしました: {ctx.author}")
            await ctx.send("このコマンドは運営のみが利用できます。")
            return False
        else:
            return True
    return commands.check(predicate)

def is_booster():
    async def predicate(ctx: commands.Context):
        if not any(role.name == "Server Booster" for role in ctx.author.roles):
            logger.warning(f"サーバーブースター以外のユーザーがコマンドを実行しようとしました: {ctx.author}")
            await ctx.send("このコマンドはサーバーブースターのみが利用できます。")
            return False
        else:
            return True
    return commands.check(predicate)

def log_commands():
    async def predicate(ctx: commands.Context):
        jst_time = datetime.now(pytz.timezone('Asia/Tokyo'))
        guild = ctx.bot.get_guild(int(dev_guild_id))
        if guild is None:
            logger.warning(f"開発用サーバーが見つかりません: {dev_guild_id}")
            return True
        
        channel = guild.get_channel(int(log_commands_channel_id))
        if channel is None:
            logger.warning(f"ログチャンネルが見つかりません: {log_commands_channel_id}")
            return True
        
        e = discord.Embed(
            title="コマンド実行通知",
            description="",
            color=discord.Color.blurple(),
            timestamp=jst_time
        )
        if ctx.interaction:
            command_name = f"/{ctx.command.name}"
            e.add_field(name="使用コマンド", value=command_name)
        else:
            command_name = f"{bot_config['prefix']}{ctx.command.name}"
            e.add_field(name="使用コマンド", value=command_name)
            if ctx.args:
                e.add_field(name="コマンド引数", value=f"{ctx.args}")
            else:
                e.add_field(name="コマンド引数", value="なし")
        e.add_field(name="使用者", value=f"{ctx.author.display_name}/{ctx.author.id}")
        e.add_field(name="サーバー名", value=f"{ctx.guild.name}/{ctx.guild.id}")
        e.add_field(name="チャンネル名", value=f"{ctx.channel.name}/{ctx.channel.id}")
        e.set_footer(text=f"Bot Version: {version_config['version']}")
        #await channel.send(embed=e)

        stats = await get_stats()
        command_count = stats.get("commands", {}).get("total", 0)
        await update_stats("commands", "total", command_count + 1)

        return True
    return commands.check(predicate)

def is_guild_app():
    async def predicate(interaction: discord.Interaction):
        if interaction.guild is None:
            logger.warning(f"DMでアプリコマンドが実行されました: {interaction.user}")
            await interaction.response.send_message("このコマンドはDMでは利用できません。")
            return False
        else:
            return True
    return app_commands.check(predicate)

def is_owner_app():
    async def predicate(interaction: discord.Interaction):
        if interaction.user.id != owner_id:
            logger.warning(f"オーナー以外のユーザーがアプリコマンドを実行しようとしました: {interaction.user}")
            await interaction.response.send_message("このコマンドはBotのオーナーのみが利用できます。", ephemeral=True)
            return False
        else:
            return True
    return app_commands.check(predicate)

def is_moderator_app():
    async def predicate(interaction: discord.Interaction):
        if not any(role.name == moderator_role_name for role in interaction.user.roles):
            logger.warning(f"モデレーター以外のユーザーがアプリコマンドを実行しようとしました: {interaction.user}")
            await interaction.response.send_message("このコマンドは運営のみが利用できます。")
            return False
        else:
            return True
    return app_commands.check(predicate)

def user_install():
    def decorator(func: Callable):
        async def wrapper(self, ctx):
            interaction = ctx.interaction
            if interaction:
                await func(self, ctx)
        
        wrapper = app_commands.allowed_installs(guilds=False, users=True)(wrapper)
        wrapper = app_commands.allowed_contexts(guilds=False, dms=True, private_channels=True)(wrapper)
        return wrapper
    return decorator

def context_menu(name: str, type: app_commands.ContextMenu):
    def decorator(func: Callable):
        context_menu = app_commands.ContextMenu(
            name=name,
            callback=func,
            type=type
        )
        async def wrapper(self, interaction: discord.Interaction):
            await func(self, interaction)
        return context_menu
            
def is_dev():
    def decorator(func: Callable):
        async def wrapper(self, ctx, *args, **kwargs):
            try:
                result = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True, check=True)
                branch = result.stdout.strip()
                if branch != "dev":
                    await ctx.send("この機能は開発環境でのみ使用できます。")
                    return
                return await func(self, ctx, *args, **kwargs)
            except subprocess.CalledProcessError:
                await ctx.send("ブランチの取得に失敗しました。")
                return
        return wrapper
    return decorator

def is_main():
    def decorator(func: Callable):
        async def wrapper(self, ctx, *args, **kwargs):
            try:
                result = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True, check=True)
                branch = result.stdout.strip()
                if branch != "main":
                    await ctx.send("この機能は本番環境でのみ使用できます。")
                    return
                return await func(self, ctx, *args, **kwargs)
            except subprocess.CalledProcessError:
                await ctx.send("ブランチの取得に失敗しました。")
                return
        return wrapper
    return decorator