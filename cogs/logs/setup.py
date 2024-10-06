import discord
from discord.ext import commands

import json
import os

from utils.logging import setup_logging

logger = setup_logging()

class LogSetupCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def toggle_logging(self, ctx, log_type: str, setting: bool, channel: discord.TextChannel = None, members=None, form: discord.Thread = None):
        guild_id = ctx.guild.id
        setting_bool = setting
        config_dir = f"data/logs/{guild_id}/config"
        config_file_path = f"{config_dir}/{log_type}.json"
        
        if not os.path.exists(config_dir):
            os.makedirs(config_dir, exist_ok=True)
        
        if not os.path.exists(config_file_path):
            with open(config_file_path, 'w') as f:
                json.dump({}, f)

        with open(config_file_path, 'r+') as f:
            config = json.load(f)
            config["log_" + log_type] = setting_bool
            if channel:
                config["log_channel"] = channel.id
            else:
                config.pop("log_channel", None)
            if members:
                config["members"] = [member.id for member in members if member]
            else:
                config.pop("members", None)
            if form:
                config["form"] = form.id
            else:
                config.pop("form", None)
            f.seek(0)
            json.dump(config, f, indent=4)
            f.truncate()

        if form:
            channel_info = f"in {channel.mention}" if channel else "in the current channel"
        else:
            channel_info = f"in {form.mention}" if form else "in the current channel"
        status = 'オン' if setting_bool else 'オフ'
        await ctx.send(f"{log_type.replace('_', ' ')}のログは{status}になりました。ログは{channel_info}に送信されます。")

    @commands.hybrid_group(name="logs")
    async def logs_group(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send("ログの設定を行います。")

    @logs_group.command(name='role')
    @commands.guild_only()
    @discord.app_commands.describe(setting="有効か無効か", channel="チャンネルに送信する場合はこれを使用", form="フォーラムに送信する場合はこれを使用")
    async def logs_role(self, ctx, setting: bool, channel: discord.TextChannel = None, form: discord.Thread = None):
        """ロールログの設定を行います。"""
        await self.toggle_logging(ctx, 'role', setting, channel=channel, form=form)

    @logs_group.command(name='message_edit')
    @commands.guild_only()
    @discord.app_commands.describe(setting="有効か無効か", channel="チャンネルに送信する場合はこれを使用", form="フォーラムに送信する場合はこれを使用")
    async def logs_message_edit(self, ctx, setting: bool, channel: discord.TextChannel = None, form: discord.Thread = None):
        """メッセージログの設定を行います。"""
        await self.toggle_logging(ctx, 'message_edit', setting, channel=channel, form=form)

    @logs_group.command(name='message_delete')
    @commands.guild_only()
    @discord.app_commands.describe(setting="有効か無効か", channel="チャンネルに送信する場合はこれを使用", form="フォーラムに送信する場合はこれを使用")
    async def logs_message_delete(self, ctx, setting: bool, channel: discord.TextChannel = None, form: discord.Thread = None):
        """メッセージ削除ログの設定を行います。"""
        await self.toggle_logging(ctx, 'message_delete', setting, channel=channel, form=form)

    @logs_group.command(name='join_remove')
    @commands.guild_only()
    @discord.app_commands.describe(setting="有効か無効か", channel="チャンネルに送信する場合はこれを使用", form="フォーラムに送信する場合はこれを使用")
    async def logs_join_remove(self, ctx, setting: bool, channel: discord.TextChannel = None, form: discord.Thread = None):
        """参加・退出ログの設定を行います。"""
        await self.toggle_logging(ctx, 'join_remove', setting, channel=channel, form=form)

    @logs_group.command(name='voice')
    @commands.guild_only()
    @discord.app_commands.describe(setting="有効か無効か", channel="チャンネルに送信する場合はこれを使用", form="フォーラムに送信する場合はこれを使用")
    async def logs_voice(self, ctx, setting: bool, channel: discord.TextChannel = None, form: discord.Thread = None):
        """ボイスチャンネルログの設定を行います。"""
        await self.toggle_logging(ctx, 'voice', setting, channel=channel, form=form)

    @logs_group.command(name='kick')
    @commands.guild_only()
    @discord.app_commands.describe(setting="有効か無効か", channel="チャンネルに送信する場合はこれを使用", form="フォーラムに送信する場合はこれを使用")
    async def logs_kick(self, ctx, setting: bool, channel: discord.TextChannel = None, form: discord.Thread = None):
        """キックログの設定を行います。"""
        await self.toggle_logging(ctx, 'kick', setting, channel=channel, form=form)

    @logs_group.command(name='ban')
    @commands.guild_only()
    @discord.app_commands.describe(setting="有効か無効か", channel="チャンネルに送信する場合はこれを使用", form="フォーラムに送信する場合はこれを使用")
    async def logs_ban(self, ctx, setting: bool, channel: discord.TextChannel = None, form: discord.Thread = None):
        """Banログの設定を行います。"""
        await self.toggle_logging(ctx, 'ban', setting, channel=channel, form=form)

    @logs_group.command(name='timeout')
    @commands.guild_only()
    @discord.app_commands.describe(setting="有効か無効か", channel="チャンネルに送信する場合はこれを使用", form="フォーラムに送信する場合はこれを使用")
    async def logs_timeout(self, ctx, setting: bool, channel: discord.TextChannel = None, form: discord.Thread = None):
        """タイムアウトログの設定を行います。"""
        await self.toggle_logging(ctx, 'timeout', setting, channel=channel, form=form)

    @logs_group.command(name='nickname')
    @commands.guild_only()
    @discord.app_commands.describe(setting="有効か無効か", channel="チャンネルに送信する場合はこれを使用", form="フォーラムに送信する場合はこれを使用")
    async def logs_nickname(self, ctx, setting: bool, channel: discord.TextChannel = None, form: discord.Thread = None):
        """ニックネームログの設定を行います。"""
        await self.toggle_logging(ctx, 'nickname', setting, channel=channel, form=form)

    @logs_group.command(name='channel')
    @commands.guild_only()
    @discord.app_commands.describe(setting="有効か無効か", channel="チャンネルに送信する場合はこれを使用", form="フォーラムに送信する場合はこれを使用")
    async def logs_channel(self, ctx, setting: bool, channel: discord.TextChannel = None, form: discord.Thread = None):
        """チャンネルログの設定を行います。"""
        await self.toggle_logging(ctx, 'channellog', setting, channel=channel, form=form)

    @logs_group.command(name="automod")
    @commands.guild_only()
    @discord.app_commands.describe(setting="有効か無効か", channel="チャンネルに送信する場合はこれを使用", form="フォーラムに送信する場合はこれを使用")
    async def logs_automod(self, ctx, setting: bool, channel: discord.TextChannel = None, form: discord.Thread = None):
        """オートモデレーションログの設定を行います。"""
        await self.toggle_logging(ctx, 'automod', setting, channel=channel, form=form)

    @logs_group.command(name="whitelist")
    @commands.guild_only()
    async def logs_whitelist(self, ctx, setting: bool, member1: discord.Member, member2: discord.Member = None, member3: discord.Member = None, member4: discord.Member = None, member5: discord.Member = None):
        """ホワイトリストログの設定を行います。"""
        await self.toggle_logging(ctx, 'whitelist', setting, members=[member1, member2, member3, member4, member5])
        
async def setup(bot):
    await bot.add_cog(LogSetupCog(bot))