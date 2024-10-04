import discord
from discord.ext import commands

import json
import os

from utils.spam_blocker import SpamBlocker

class SpamBlockerCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.spam_blocker = SpamBlocker(bot)


    @commands.command(name="set_spam_limit", aliases=["ssl"])
    @commands.is_owner()
    async def set_spam_limit(self, ctx: commands.Context, limit: int):
        """スパムリミットを設定"""
        self.spam_blocker.config['spam_limit'] = limit
        self.spam_blocker.save_config(self.spam_blocker.config)
        self.spam_blocker.spam_control = commands.CooldownMapping.from_cooldown(
            self.spam_blocker.config['spam_limit'],
            self.spam_blocker.config['cooldown_period'],
            commands.BucketType.user
        )
        await ctx.send(f"Spam limit set to {limit}")

    @commands.command(name="set_cooldown_period", aliases=["scp"])
    @commands.is_owner()
    async def set_cooldown_period(self, ctx: commands.Context, period: float):
        """スパムのクールダウン期間を設定"""
        self.spam_blocker.config['cooldown_period'] = period
        self.spam_blocker.save_config(self.spam_blocker.config)
        self.spam_blocker.spam_control = commands.CooldownMapping.from_cooldown(
            self.spam_blocker.config['spam_limit'],
            self.spam_blocker.config['cooldown_period'],
            commands.BucketType.user
        )
        await ctx.send(f"Cooldown period set to {period} seconds")

    @commands.command(name="set_auto_blacklist_limit", aliases=["sabl"])
    @commands.is_owner()
    async def set_auto_blacklist_limit(self, ctx: commands.Context, limit: int):
        """自動ブラックリストのトリガー回数を設定"""
        self.spam_blocker.config['auto_blacklist_limit'] = limit
        self.spam_blocker.save_config(self.spam_blocker.config)
        await ctx.send(f"Auto blacklist limit set to {limit}")

    @commands.command(name="show_spam_config", aliases=["ss"])
    @commands.is_owner()
    async def show_spam_config(self, ctx: commands.Context):
        """現在のスパム管理の設定を表示"""
        config = json.dumps(self.spam_blocker.config, indent=4)
        await ctx.send(f"Current spam blocker config:\n```json\n{config}\n```")

async def setup(bot: commands.Bot):
    await bot.add_cog(SpamBlockerCog(bot))
