"""
HFS Rank XP サービス

XP計算・付与ロジックを管理
"""
import re
from datetime import datetime, timezone

from utils.logging import setup_logging

from .models import RankConfig, RankUser, rank_db

logger = setup_logging(__name__)


class RankService:
    """Rankサービスクラス"""

    def __init__(self):
        # メッセージXPクールダウン: {user_id: last_xp_time}
        self._message_cooldowns: dict[int, datetime] = {}

    # ========== XP計算ロジック ==========

    def _calculate_streak_multiplier(self, streak: int) -> float:
        """
        ストリーク（連続ログイン日数）に応じた倍率を計算
        - 1-6日: 1.0x
        - 7-13日: 1.1x
        - 14-29日: 1.2x
        - 30-59日: 1.5x
        - 60日以上: 2.0x（最大）
        """
        if streak < 7:
            return 1.0
        elif streak < 14:
            return 1.1
        elif streak < 30:
            return 1.2
        elif streak < 60:
            return 1.5
        else:
            return 2.0

    def _calculate_quality_bonus(self, content: str) -> int:
        """
        メッセージ品質に応じたボーナスXPを計算
        - 長文（100文字以上）: +2 XP
        - 絵文字/カスタム絵文字: +1 XP
        - URL含む: +1 XP
        - 画像/ファイル添付: 別途処理
        """
        bonus = 0

        # 長文ボーナス
        if len(content) >= 100:
            bonus += 2
        elif len(content) >= 50:
            bonus += 1

        # 絵文字ボーナス（カスタム絵文字も含む）
        emoji_pattern = re.compile(r'<a?:\w+:\d+>|[\U0001F300-\U0001F9FF]')
        if emoji_pattern.search(content):
            bonus += 1

        # URL共有ボーナス
        url_pattern = re.compile(r'https?://\S+')
        if url_pattern.search(content):
            bonus += 1

        return min(bonus, 5)  # 最大5XPまで

    def _get_channel_multiplier(self, channel_id: int, config: RankConfig) -> float:
        """チャンネルごとのXP倍率を取得"""
        if config.channel_multipliers:
            return config.channel_multipliers.get(channel_id, 1.0)
        return 1.0

    def calculate_final_xp(
        self,
        base_xp: int,
        content: str,
        channel_id: int,
        streak: int,
        config: RankConfig,
    ) -> int:
        """
        最終的なXPを計算（全ての倍率・ボーナスを適用）
        """
        # 品質ボーナス
        quality_bonus = 0
        if config.quality_bonus_enabled:
            quality_bonus = self._calculate_quality_bonus(content)

        # ストリーク倍率
        streak_multiplier = 1.0
        if config.streak_bonus_enabled:
            streak_multiplier = self._calculate_streak_multiplier(streak)

        # チャンネル倍率
        channel_multiplier = self._get_channel_multiplier(channel_id, config)

        # グローバル倍率（イベント用）
        global_multiplier = config.global_multiplier

        # 最終XP計算
        final_xp = (base_xp + quality_bonus) * streak_multiplier * channel_multiplier * global_multiplier

        return int(final_xp)

    async def add_message_xp(
        self,
        user_id: int,
        guild_id: int,
        content: str = "",
        channel_id: int = 0,
    ) -> tuple[RankUser | None, dict]:
        """
        メッセージXPを付与（クールダウン付き）

        Returns:
            (RankUser | None, xp_details): ユーザー情報とXP詳細
        """
        config = await rank_db.get_config(guild_id)
        xp_details = {"base": 0, "quality": 0, "streak_mult": 1.0, "channel_mult": 1.0, "total": 0}

        if not config.is_enabled:
            return None, xp_details

        # クールダウンチェック
        now = datetime.now(timezone.utc)
        last_xp = self._message_cooldowns.get(user_id)
        if last_xp:
            elapsed = (now - last_xp).total_seconds()
            if elapsed < config.message_cooldown_seconds:
                return None, xp_details

        # ユーザーのストリーク取得
        user = await rank_db.get_user(user_id, guild_id)
        streak = user.current_streak if user else 0

        # XP計算
        base_xp = config.message_xp
        quality_bonus = self._calculate_quality_bonus(content) if config.quality_bonus_enabled else 0
        streak_mult = self._calculate_streak_multiplier(streak) if config.streak_bonus_enabled else 1.0
        channel_mult = self._get_channel_multiplier(channel_id, config)
        global_mult = config.global_multiplier

        final_xp = int((base_xp + quality_bonus) * streak_mult * channel_mult * global_mult)

        xp_details = {
            "base": base_xp,
            "quality": quality_bonus,
            "streak_mult": streak_mult,
            "channel_mult": channel_mult,
            "global_mult": global_mult,
            "total": final_xp,
        }

        # XP付与（アクティブ日数・ストリークも同時更新）
        result = await rank_db.add_xp(user_id, guild_id, final_xp, "message", update_active=True)
        if result:
            self._message_cooldowns[user_id] = now

        return result, xp_details

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

        # XP付与（アクティブ日数・ストリークも同時更新）
        result = await rank_db.add_xp(user_id, guild_id, config.omikuji_xp, "omikuji", update_active=True)

        return result

    async def add_reaction_xp(
        self,
        user_id: int,
        guild_id: int,
        reactor_id: int,
    ) -> RankUser | None:
        """
        リアクションをもらったときにXPを付与
        - 自分自身のリアクションは除外
        - 同一ユーザーからのリアクションはクールダウン
        """
        # 自分自身のリアクションは除外
        if user_id == reactor_id:
            return None

        config = await rank_db.get_config(guild_id)

        if not config.is_enabled:
            return None

        # クールダウン: 同一ユーザーからは5分に1回
        cooldown_key = f"reaction_{user_id}_{reactor_id}"
        now = datetime.now(timezone.utc)
        last_xp = self._message_cooldowns.get(cooldown_key)
        if last_xp:
            elapsed = (now - last_xp).total_seconds()
            if elapsed < 300:  # 5分
                return None

        # リアクションXP（基本2XP）
        reaction_xp = 2

        # ストリーク・グローバル倍率を適用
        user = await rank_db.get_user(user_id, guild_id)
        streak = user.current_streak if user else 0
        streak_mult = self._calculate_streak_multiplier(streak) if config.streak_bonus_enabled else 1.0
        final_xp = int(reaction_xp * streak_mult * config.global_multiplier)

        result = await rank_db.add_xp(user_id, guild_id, final_xp, "reaction")
        if result:
            self._message_cooldowns[cooldown_key] = now

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
        # XP付与（アクティブ日数・ストリークも同時更新）
        result = await rank_db.add_xp(user_id, guild_id, xp, "vc", update_active=True)

        return result

    def is_channel_excluded(self, channel_id: int, config) -> bool:
        """除外チャンネルかチェック"""
        if config.excluded_channels:
            return channel_id in config.excluded_channels
        return False


# シングルトンインスタンス
rank_service = RankService()
