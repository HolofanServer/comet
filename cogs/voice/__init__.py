"""Voice recording cog"""

from .db import voice_database
from .recording import VoiceRecording


async def setup(bot):
    """Cog setup"""
    # Voice DB初期化
    await voice_database.initialize()
    await bot.add_cog(VoiceRecording(bot))
