"""
Voice Recording DB接続管理
"""

import asyncpg

from config.setting import get_settings
from utils.logging import setup_logging

logger = setup_logging(__name__)
settings = get_settings()


class VoiceDatabase:
    """Voice Recording専用DB接続"""

    def __init__(self):
        self.pool: asyncpg.Pool | None = None
        self._initialized = False

    async def initialize(self) -> bool:
        """DB接続を初期化"""
        if self._initialized:
            return True

        db_url = settings.voice_database_url
        if not db_url:
            logger.warning("VOICE_DATABASE_URL が設定されていません")
            return False

        try:
            self.pool = await asyncpg.create_pool(
                db_url,
                min_size=1,
                max_size=5,
                command_timeout=30,
            )
            self._initialized = True
            logger.info("Voice DB接続成功")
            return True
        except Exception as e:
            logger.error(f"Voice DB接続エラー: {e}")
            return False

    async def close(self):
        """DB接続を閉じる"""
        if self.pool:
            await self.pool.close()
            self._initialized = False
            logger.info("Voice DB接続を閉じました")


# シングルトンインスタンス
voice_database = VoiceDatabase()


async def setup(bot):
    """ダミーsetup - このモジュールはCogではない"""
    pass
