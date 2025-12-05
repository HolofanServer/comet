"""
HFS Rank XP サービス

XP計算・付与ロジックを管理
"""
from datetime import datetime, timezone

from utils.logging import setup_logging

from .models import RankUser, rank_db

logger = setup_logging(__name__)


class RankService:
    """Rankサービスクラス"""

    def __init__(self):
        # メッセージXPクールダウン: {user_id: last_xp_time}
        self._message_cooldowns: dict[int, datetime] = {}

    async def add_message_xp(self, user_id: int, guild_id: int) -> RankUser | None:
        """メッセージXPを付与（クールダウン付き）"""
        config = await rank_db.get_config(guild_id)

        if not config.is_enabled:
            return None

        # クールダウンチェック
        now = datetime.now(timezone.utc)
        last_xp = self._message_cooldowns.get(user_id)
        if last_xp:
            elapsed = (now - last_xp).total_seconds()
            if elapsed < config.message_cooldown_seconds:
                return None

        # XP付与
        result = await rank_db.add_xp(user_id, guild_id, config.message_xp, "message")
        if result:
            self._message_cooldowns[user_id] = now
            # アクティブ日数更新
            await rank_db.increment_active_days(user_id, guild_id)

        return result

    async def add_omikuji_xp(self, user_id: int, guild_id: int) -> RankUser | None:
        """おみくじXPを付与（1日1回）"""
        config = await rank_db.get_config(guild_id)

        if not config.is_enabled:
            return None

        # 今日すでにおみくじXPを取得したかチェック
        user = await rank_db.get_user(user_id, guild_id)
        if user and user.last_omikuji_xp_date:
            from datetime import date
            if user.last_omikuji_xp_date >= date.today():
                return None

        # XP付与
        result = await rank_db.add_xp(user_id, guild_id, config.omikuji_xp, "omikuji")
        if result:
            await rank_db.increment_active_days(user_id, guild_id)

        return result

    async def add_vc_xp(self, user_id: int, guild_id: int, minutes: int) -> RankUser | None:
        """VC XPを付与"""
        config = await rank_db.get_config(guild_id)

        if not config.is_enabled:
            return None

        # 10分ごとにXP
        xp_units = minutes // 10
        if xp_units <= 0:
            return None

        xp = xp_units * config.vc_xp_per_10min
        result = await rank_db.add_xp(user_id, guild_id, xp, "vc")
        if result:
            await rank_db.increment_active_days(user_id, guild_id)

        return result

    def is_channel_excluded(self, channel_id: int, config) -> bool:
        """除外チャンネルかチェック"""
        if config.excluded_channels:
            return channel_id in config.excluded_channels
        return False


# シングルトンインスタンス
rank_service = RankService()
