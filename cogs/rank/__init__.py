"""
HFS Rank システム

XP・ランク・常連ロールを管理するレベリングシステム
"""
from discord.ext import commands

from .logging import RankLogging
from .ranking import RankCommands


async def setup(bot: commands.Bot):
    """Rank Cogをロード"""
    await bot.add_cog(RankLogging(bot))
    await bot.add_cog(RankCommands(bot))
