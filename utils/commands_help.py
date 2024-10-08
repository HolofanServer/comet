import discord
from discord.ext import commands
from discord import app_commands

import os

from typing import Callable

from utils.logging import setup_logging

owner_id = [int(os.environ["BOT_OWNER_ID"])]
moderator_role_name = os.environ.get("MODERATOR_ROLE_NAME", "moderator")
log_commnads_channel_id = os.environ.get("COMANNDS_LOG_CHANNEL_ID")


logger = setup_logging()

def is_guild():
    async def predicate(ctx: commands.Context):
        if ctx.guild is None:
            logger.warning(f"DMでコマンドが実行されました: {ctx.author}")
            await ctx.send("このコマンドはDMでは利用できません。")
            return False
        return True
    return commands.check(predicate)

def is_owner():
    async def predicate(ctx: commands.Context):
        if ctx.author.id not in owner_id:
            logger.warning(f"オーナー以外のユーザーがコマンドを実行しようとしました: {ctx.author}")
            await ctx.send("このコマンドはBotのオーナーのみが利用できます。")
            return False
        return True
    return commands.check(predicate)

def is_moderator():
    async def predicate(ctx: commands.Context):
        if not any(role.name == moderator_role_name for role in ctx.author.roles):
            logger.warning(f"モデレーター以外のユーザーがコマンドを実行しようとしました: {ctx.author}")
            await ctx.send("このコマンドは運営のみが利用できます。")
            return False
        return True
    return commands.check(predicate)

def log_commnads():
    async def predicate(ctx: commands.Context):
        e = discord.Embed(
            title=ctx.author.display_name,
            description="",
            color=discord.Color.blurple()
        )
        e.add_field(name="使用コマンド", value=f"{ctx.bot.commnad.name}")
        for command in ctx.bot.commands:
            e.description += f"{command.name}\n"
        await ctx.send(embed=e)
        return False
    return commands.check(predicate)

def is_guild_app():
    async def predicate(interaction: discord.Interaction):
        if interaction.guild is None:
            logger.warning(f"DMでアプリコマンドが実行されました: {interaction.user}")
            await interaction.response.send_message("このコマンドはDMでは利用できません。")
            return False
        return True
    return app_commands.check(predicate)

def is_owner_app():
    async def predicate(interaction: discord.Interaction):
        if interaction.user.id not in owner_id:
            logger.warning(f"オーナー以外のユーザーがアプリコマンドを実行しようとしました: {interaction.user}")
            await interaction.response.send_message("このコマンドはBotのオーナーのみが利用できます。", ephemeral=True)
            return False
        return True
    return app_commands.check(predicate)

def is_moderator_app():
    async def predicate(interaction: discord.Interaction):
        if not any(role.name == moderator_role_name for role in interaction.user.roles):
            logger.warning(f"モデレーター以外のユーザーがアプリコマンドを実行しようとしました: {interaction.user}")
            await interaction.response.send_message("このコマンドは運営のみが利用できます。")
            return False
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

def user_install_context_menu(name: str, type: app_commands.ContextMenu):
    def decorator(func: Callable):
        context_menu = app_commands.ContextMenu(
            name=name,
            callback=func,
            type=type
        )
        async def wrapper(self, interaction: discord.Interaction):
            await func(self, interaction)
        
        return context_menu
    return decorator
