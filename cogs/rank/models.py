"""
HFS Rank データモデル・DBアクセス
"""
from dataclasses import dataclass
from datetime import date, datetime, timezone

from cogs.cp.db import checkpoint_db
from utils.logging import setup_logging

logger = setup_logging(__name__)


@dataclass
class RankUser:
    """ユーザーランク情報"""

    user_id: int
    guild_id: int
    yearly_xp: int = 0
    lifetime_xp: int = 0
    active_days: int = 0
    current_level: int = 1
    is_regular: bool = False
    last_message_xp_at: datetime | None = None
    last_omikuji_xp_date: date | None = None
    last_active_date: date | None = None


@dataclass
class RankConfig:
    """ランク設定"""

    guild_id: int
    message_xp: int = 5
    message_cooldown_seconds: int = 60
    omikuji_xp: int = 15
    vc_xp_per_10min: int = 5
    regular_xp_threshold: int = 10000
    regular_days_threshold: int = 50
    regular_role_id: int | None = None
    excluded_channels: list[int] | None = None
    excluded_roles: list[int] | None = None
    is_enabled: bool = True


class RankDB:
    """Rank DBアクセスクラス"""

    def __init__(self):
        self._config_cache: dict[int, RankConfig] = {}
        self._level_thresholds: list[tuple[int, int]] = []

    async def initialize(self):
        """レベル閾値をロード"""
        if not checkpoint_db._initialized:
            return

        query = "SELECT level, required_xp FROM rank_levels ORDER BY level"
        try:
            async with checkpoint_db.pool.acquire() as conn:
                rows = await conn.fetch(query)
            self._level_thresholds = [(row["level"], row["required_xp"]) for row in rows]
            logger.info(f"✅ レベル閾値ロード完了: {len(self._level_thresholds)}段階")
        except Exception as e:
            logger.error(f"レベル閾値ロードエラー: {e}")
            # デフォルト閾値
            self._level_thresholds = [(i, i * i * 10) for i in range(1, 51)]

    def calculate_level(self, xp: int) -> int:
        """XPからレベルを計算"""
        level = 1
        for lv, required in self._level_thresholds:
            if xp >= required:
                level = lv
            else:
                break
        return level

    async def get_config(self, guild_id: int) -> RankConfig:
        """ギルド設定を取得"""
        if guild_id in self._config_cache:
            return self._config_cache[guild_id]

        if not checkpoint_db._initialized:
            return RankConfig(guild_id=guild_id)

        query = "SELECT * FROM rank_config WHERE guild_id = $1"
        try:
            async with checkpoint_db.pool.acquire() as conn:
                row = await conn.fetchrow(query, guild_id)

            if row:
                config = RankConfig(
                    guild_id=guild_id,
                    message_xp=row["message_xp"],
                    message_cooldown_seconds=row["message_cooldown_seconds"],
                    omikuji_xp=row["omikuji_xp"],
                    vc_xp_per_10min=row["vc_xp_per_10min"],
                    regular_xp_threshold=row["regular_xp_threshold"],
                    regular_days_threshold=row["regular_days_threshold"],
                    regular_role_id=row["regular_role_id"],
                    excluded_channels=list(row["excluded_channels"]) if row["excluded_channels"] else [],
                    excluded_roles=list(row["excluded_roles"]) if row["excluded_roles"] else [],
                    is_enabled=row["is_enabled"],
                )
            else:
                config = RankConfig(guild_id=guild_id)

            self._config_cache[guild_id] = config
            return config
        except Exception as e:
            logger.error(f"設定取得エラー: {e}")
            return RankConfig(guild_id=guild_id)

    async def get_user(self, user_id: int, guild_id: int) -> RankUser | None:
        """ユーザー情報を取得"""
        if not checkpoint_db._initialized:
            return None

        query = "SELECT * FROM rank_users WHERE user_id = $1 AND guild_id = $2"
        try:
            async with checkpoint_db.pool.acquire() as conn:
                row = await conn.fetchrow(query, user_id, guild_id)

            if not row:
                return None

            return RankUser(
                user_id=row["user_id"],
                guild_id=row["guild_id"],
                yearly_xp=row["yearly_xp"],
                lifetime_xp=row["lifetime_xp"],
                active_days=row["active_days"],
                current_level=row["current_level"],
                is_regular=row["is_regular"],
                last_message_xp_at=row["last_message_xp_at"],
                last_omikuji_xp_date=row["last_omikuji_xp_date"],
                last_active_date=row["last_active_date"],
            )
        except Exception as e:
            logger.error(f"ユーザー取得エラー: {e}")
            return None

    async def add_xp(
        self,
        user_id: int,
        guild_id: int,
        xp: int,
        xp_type: str = "message",
    ) -> RankUser | None:
        """XPを追加"""
        if not checkpoint_db._initialized:
            return None

        now = datetime.now(timezone.utc)
        today = date.today()

        # XPタイプに応じたカラム更新
        extra_set = ""
        if xp_type == "message":
            extra_set = ", last_message_xp_at = $5"
        elif xp_type == "omikuji":
            extra_set = ", last_omikuji_xp_date = $6"

        query = f"""
            INSERT INTO rank_users (user_id, guild_id, yearly_xp, lifetime_xp, last_active_date, updated_at
                {', last_message_xp_at' if xp_type == 'message' else ''}
                {', last_omikuji_xp_date' if xp_type == 'omikuji' else ''})
            VALUES ($1, $2, $3, $3, $4, $5
                {', $5' if xp_type == 'message' else ''}
                {', $6' if xp_type == 'omikuji' else ''})
            ON CONFLICT (user_id, guild_id) DO UPDATE
            SET yearly_xp = rank_users.yearly_xp + $3,
                lifetime_xp = rank_users.lifetime_xp + $3,
                last_active_date = $4,
                updated_at = $5
                {extra_set}
            RETURNING *
        """

        try:
            async with checkpoint_db.pool.acquire() as conn:
                if xp_type == "message":
                    row = await conn.fetchrow(query, user_id, guild_id, xp, today, now)
                elif xp_type == "omikuji":
                    row = await conn.fetchrow(query, user_id, guild_id, xp, today, now, today)
                else:
                    row = await conn.fetchrow(query, user_id, guild_id, xp, today, now)

            if row:
                # レベル再計算
                new_level = self.calculate_level(row["yearly_xp"])
                if new_level != row["current_level"]:
                    await self._update_level(user_id, guild_id, new_level)

                return RankUser(
                    user_id=row["user_id"],
                    guild_id=row["guild_id"],
                    yearly_xp=row["yearly_xp"],
                    lifetime_xp=row["lifetime_xp"],
                    active_days=row["active_days"],
                    current_level=new_level,
                    is_regular=row["is_regular"],
                )
            return None
        except Exception as e:
            logger.error(f"XP追加エラー: {e}")
            return None

    async def _update_level(self, user_id: int, guild_id: int, level: int):
        """レベルを更新"""
        query = """
            UPDATE rank_users SET current_level = $3, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = $1 AND guild_id = $2
        """
        try:
            async with checkpoint_db.pool.acquire() as conn:
                await conn.execute(query, user_id, guild_id, level)
        except Exception as e:
            logger.error(f"レベル更新エラー: {e}")

    async def increment_active_days(self, user_id: int, guild_id: int) -> bool:
        """アクティブ日数をインクリメント"""
        if not checkpoint_db._initialized:
            return False

        today = date.today()
        query = """
            UPDATE rank_users
            SET active_days = active_days + 1,
                last_active_date = $3,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = $1 AND guild_id = $2
              AND (last_active_date IS NULL OR last_active_date < $3)
            RETURNING active_days
        """
        try:
            async with checkpoint_db.pool.acquire() as conn:
                result = await conn.fetchval(query, user_id, guild_id, today)
            return result is not None
        except Exception as e:
            logger.error(f"アクティブ日数更新エラー: {e}")
            return False

    async def get_rankings(
        self, guild_id: int, limit: int = 10, order_by: str = "yearly_xp"
    ) -> list[RankUser]:
        """ランキングを取得"""
        if not checkpoint_db._initialized:
            return []

        if order_by not in ("yearly_xp", "lifetime_xp", "active_days"):
            order_by = "yearly_xp"

        query = f"""
            SELECT * FROM rank_users
            WHERE guild_id = $1
            ORDER BY {order_by} DESC
            LIMIT $2
        """
        try:
            async with checkpoint_db.pool.acquire() as conn:
                rows = await conn.fetch(query, guild_id, limit)

            return [
                RankUser(
                    user_id=row["user_id"],
                    guild_id=row["guild_id"],
                    yearly_xp=row["yearly_xp"],
                    lifetime_xp=row["lifetime_xp"],
                    active_days=row["active_days"],
                    current_level=row["current_level"],
                    is_regular=row["is_regular"],
                )
                for row in rows
            ]
        except Exception as e:
            logger.error(f"ランキング取得エラー: {e}")
            return []

    async def get_user_rank(self, user_id: int, guild_id: int) -> int | None:
        """ユーザーの順位を取得"""
        if not checkpoint_db._initialized:
            return None

        query = """
            SELECT COUNT(*) + 1 as rank
            FROM rank_users
            WHERE guild_id = $1 AND yearly_xp > (
                SELECT yearly_xp FROM rank_users WHERE user_id = $2 AND guild_id = $1
            )
        """
        try:
            async with checkpoint_db.pool.acquire() as conn:
                result = await conn.fetchval(query, guild_id, user_id)
            return result
        except Exception:
            return None

    async def update_excluded_roles(self, guild_id: int, role_ids: list[int]) -> bool:
        """除外ロールを更新"""
        if not checkpoint_db._initialized:
            return False

        query = """
            INSERT INTO rank_config (guild_id, excluded_roles)
            VALUES ($1, $2)
            ON CONFLICT (guild_id) DO UPDATE
            SET excluded_roles = $2, updated_at = CURRENT_TIMESTAMP
        """
        try:
            async with checkpoint_db.pool.acquire() as conn:
                await conn.execute(query, guild_id, role_ids)
            # キャッシュ更新
            if guild_id in self._config_cache:
                self._config_cache[guild_id].excluded_roles = role_ids
            return True
        except Exception as e:
            logger.error(f"除外ロール更新エラー: {e}")
            return False

    async def update_excluded_channels(self, guild_id: int, channel_ids: list[int]) -> bool:
        """除外チャンネルを更新"""
        if not checkpoint_db._initialized:
            return False

        query = """
            INSERT INTO rank_config (guild_id, excluded_channels)
            VALUES ($1, $2)
            ON CONFLICT (guild_id) DO UPDATE
            SET excluded_channels = $2, updated_at = CURRENT_TIMESTAMP
        """
        try:
            async with checkpoint_db.pool.acquire() as conn:
                await conn.execute(query, guild_id, channel_ids)
            # キャッシュ更新
            if guild_id in self._config_cache:
                self._config_cache[guild_id].excluded_channels = channel_ids
            return True
        except Exception as e:
            logger.error(f"除外チャンネル更新エラー: {e}")
            return False

    async def update_enabled(self, guild_id: int, enabled: bool) -> bool:
        """有効/無効を更新"""
        if not checkpoint_db._initialized:
            return False

        query = """
            INSERT INTO rank_config (guild_id, is_enabled)
            VALUES ($1, $2)
            ON CONFLICT (guild_id) DO UPDATE
            SET is_enabled = $2, updated_at = CURRENT_TIMESTAMP
        """
        try:
            async with checkpoint_db.pool.acquire() as conn:
                await conn.execute(query, guild_id, enabled)
            # キャッシュ更新
            if guild_id in self._config_cache:
                self._config_cache[guild_id].is_enabled = enabled
            return True
        except Exception as e:
            logger.error(f"有効設定更新エラー: {e}")
            return False

    async def update_xp_settings(
        self,
        guild_id: int,
        message_xp: int | None = None,
        omikuji_xp: int | None = None,
        vc_xp: int | None = None,
        cooldown: int | None = None,
    ) -> bool:
        """XP設定を更新"""
        if not checkpoint_db._initialized:
            return False

        updates = []
        values = [guild_id]
        idx = 2

        if message_xp is not None:
            updates.append(f"message_xp = ${idx}")
            values.append(message_xp)
            idx += 1
        if omikuji_xp is not None:
            updates.append(f"omikuji_xp = ${idx}")
            values.append(omikuji_xp)
            idx += 1
        if vc_xp is not None:
            updates.append(f"vc_xp_per_10min = ${idx}")
            values.append(vc_xp)
            idx += 1
        if cooldown is not None:
            updates.append(f"message_cooldown_seconds = ${idx}")
            values.append(cooldown)
            idx += 1

        if not updates:
            return False

        query = f"""
            INSERT INTO rank_config (guild_id) VALUES ($1)
            ON CONFLICT (guild_id) DO UPDATE
            SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP
        """
        try:
            async with checkpoint_db.pool.acquire() as conn:
                await conn.execute(query, *values)
            # キャッシュクリア
            self._config_cache.pop(guild_id, None)
            return True
        except Exception as e:
            logger.error(f"XP設定更新エラー: {e}")
            return False

    async def update_regular_settings(
        self,
        guild_id: int,
        role_id: int | None = None,
        xp_threshold: int | None = None,
        days_threshold: int | None = None,
    ) -> bool:
        """常連ロール設定を更新"""
        if not checkpoint_db._initialized:
            return False

        updates = []
        values = [guild_id]
        idx = 2

        if role_id is not None:
            updates.append(f"regular_role_id = ${idx}")
            values.append(role_id if role_id > 0 else None)
            idx += 1
        if xp_threshold is not None:
            updates.append(f"regular_xp_threshold = ${idx}")
            values.append(xp_threshold)
            idx += 1
        if days_threshold is not None:
            updates.append(f"regular_days_threshold = ${idx}")
            values.append(days_threshold)
            idx += 1

        if not updates:
            return False

        query = f"""
            INSERT INTO rank_config (guild_id) VALUES ($1)
            ON CONFLICT (guild_id) DO UPDATE
            SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP
        """
        try:
            async with checkpoint_db.pool.acquire() as conn:
                await conn.execute(query, *values)
            # キャッシュクリア
            self._config_cache.pop(guild_id, None)
            return True
        except Exception as e:
            logger.error(f"常連設定更新エラー: {e}")
            return False


# シングルトンインスタンス
rank_db = RankDB()
