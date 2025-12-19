"""
HFS Checkpoint 2026 - Discord Bot Integration

2025年の活動ログを収集し、統計を提供するCog
"""
from discord.ext import commands

from .cp_commands import CheckpointCommands
from .event_logging import CheckpointLogging


async def setup(bot: commands.Bot):
    """Checkpoint Cogをロード"""
    await bot.add_cog(CheckpointLogging(bot))
    await bot.add_cog(CheckpointCommands(bot))
