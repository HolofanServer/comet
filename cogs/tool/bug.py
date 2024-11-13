import discord
from discord.ext import commands

import os

from utils.logging import setup_logging

from config.setting import get_settings

logger = setup_logging()

settings = get_settings()
main_dev_channel_id = settings.admin_bug_report_channel_id
main_dev_server_id = settings.admin_main_guild_id

class BugReportCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="bug_report")
    @commands.dm_only()
    async def bug_report(self, ctx, 内容: str, 画像: discord.Attachment = None):
        """バグを報告します。"""
        dev_channel = self.bot.get_channel(main_dev_channel_id)
        dev_server = self.bot.get_guild(main_dev_server_id)
        if dev_channel is None:
            await ctx.send("開発者チャンネルが見つかりません。")
            return
        if dev_server is None:
            await ctx.send("開発者サーバーが見つかりません。")
            return
        e = discord.Embed(title="バグ報告", description=内容, color=discord.Color.red())
        e.add_field(name="報告者", value=ctx.author.mention, inline=True)
        if ctx.guild:
            e.add_field(name="サーバー", value=ctx.guild.name, inline=True)
        else:
            e.add_field(name="サーバー", value="DM", inline=True)
        if isinstance(ctx.channel, discord.DMChannel):
            channel_mention = "DM"
        else:
            channel_mention = ctx.channel.mention
        e.add_field(name="チャンネル", value=channel_mention, inline=True)
        if 画像 is not None:
            e.set_image(url=画像.url)
        await dev_channel.send(embed=e)
        await ctx.send("バグを報告しました。", ephemeral=True)

async def setup(bot):
    await bot.add_cog(BugReportCog(bot))
