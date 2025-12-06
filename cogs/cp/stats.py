"""
Checkpoint 統計集計

ユーザー統計・ランキング・キャッシュを管理
"""
import json
from datetime import date, datetime, timedelta, timezone
from typing import Any

from utils.logging import setup_logging

from .db import checkpoint_db
from .models import RankingEntry, UserStats

logger = setup_logging(__name__)

# キャッシュ有効期限（秒）
CACHE_TTL = 300  # 5分


class CheckpointStats:
    """統計集計クラス"""

    def __init__(self):
        self._local_cache: dict[str, tuple[datetime, Any]] = {}

    def _is_cache_valid(self, key: str) -> bool:
        """ローカルキャッシュが有効か"""
        if key not in self._local_cache:
            return False
        cached_at, _ = self._local_cache[key]
        return (datetime.now(timezone.utc) - cached_at).total_seconds() < CACHE_TTL

    def _get_cache(self, key: str) -> Any | None:
        """ローカルキャッシュから取得"""
        if self._is_cache_valid(key):
            return self._local_cache[key][1]
        return None

    def _set_cache(self, key: str, value: Any):
        """ローカルキャッシュに保存"""
        self._local_cache[key] = (datetime.now(timezone.utc), value)

    async def get_user_stats(
        self, user_id: int, guild_id: int, year: int | None = None
    ) -> UserStats | None:
        """ユーザー統計を取得"""
        if not checkpoint_db._initialized:
            return None

        target_year = year or date.today().year
        cache_key = f"user_stats:{user_id}:{guild_id}:{target_year}"

        # キャッシュチェック
        cached = self._get_cache(cache_key)
        if cached:
            return cached

        query = """
            SELECT
                $1::BIGINT as user_id,
                $2::BIGINT as guild_id,
                COALESCE(SUM(message_count), 0) as total_messages,
                COALESCE(SUM(reaction_count), 0) as total_reactions,
                COALESCE(SUM(vc_seconds), 0) as total_vc_seconds,
                COALESCE(SUM(mention_sent_count), 0) as total_mentions_sent,
                COALESCE(SUM(mention_received_count), 0) as total_mentions_received,
                COALESCE(SUM(omikuji_count), 0) as total_omikuji
            FROM cp_daily_stats
            WHERE user_id = $1 AND guild_id = $2
              AND EXTRACT(YEAR FROM stat_date) = $3
        """

        try:
            async with checkpoint_db.pool.acquire() as conn:
                row = await conn.fetchrow(query, user_id, guild_id, target_year)

            if not row:
                return None

            stats = UserStats(
                user_id=user_id,
                guild_id=guild_id,
                year=target_year,
                total_messages=row["total_messages"],
                total_reactions=row["total_reactions"],
                total_vc_seconds=row["total_vc_seconds"],
                total_mentions_sent=row["total_mentions_sent"],
                total_mentions_received=row["total_mentions_received"],
                total_omikuji=row["total_omikuji"],
            )

            self._set_cache(cache_key, stats)
            return stats

        except Exception as e:
            logger.error(f"ユーザー統計取得エラー: {e}")
            return None

    async def get_rankings(
        self,
        guild_id: int,
        category: str,
        year: int | None = None,
        limit: int = 10,
    ) -> list[RankingEntry]:
        """ランキングを取得"""
        if not checkpoint_db._initialized:
            return []

        target_year = year or date.today().year
        cache_key = f"ranking:{guild_id}:{category}:{target_year}:{limit}"

        cached = self._get_cache(cache_key)
        if cached:
            return cached

        # カテゴリに応じたカラム
        column_map = {
            "messages": "message_count",
            "reactions": "reaction_count",
            "vc": "vc_seconds",
            "mentions_sent": "mention_sent_count",
            "mentions_received": "mention_received_count",
            "omikuji": "omikuji_count",
        }

        column = column_map.get(category)
        if not column:
            return []

        query = f"""
            SELECT
                user_id,
                SUM({column}) as total
            FROM cp_daily_stats
            WHERE guild_id = $1
              AND EXTRACT(YEAR FROM stat_date) = $2
            GROUP BY user_id
            HAVING SUM({column}) > 0
            ORDER BY total DESC
            LIMIT $3
        """

        try:
            async with checkpoint_db.pool.acquire() as conn:
                rows = await conn.fetch(query, guild_id, target_year, limit)

            rankings = [
                RankingEntry(
                    rank=i + 1,
                    user_id=row["user_id"],
                    value=int(row["total"]),
                    category=category,
                )
                for i, row in enumerate(rows)
            ]

            self._set_cache(cache_key, rankings)
            return rankings

        except Exception as e:
            logger.error(f"ランキング取得エラー: {e}")
            return []

    async def get_top_emojis(
        self, user_id: int, guild_id: int, limit: int = 5
    ) -> list[dict[str, Any]]:
        """よく使う絵文字を取得"""
        if not checkpoint_db._initialized:
            return []

        query = """
            SELECT emoji_name, emoji_id, emoji_animated, use_count
            FROM cp_reaction_counts
            WHERE user_id = $1 AND guild_id = $2
            ORDER BY use_count DESC
            LIMIT $3
        """

        try:
            async with checkpoint_db.pool.acquire() as conn:
                rows = await conn.fetch(query, user_id, guild_id, limit)

            return [
                {
                    "name": row["emoji_name"],
                    "id": row["emoji_id"],
                    "animated": row["emoji_animated"],
                    "count": row["use_count"],
                }
                for row in rows
            ]
        except Exception as e:
            logger.error(f"絵文字統計取得エラー: {e}")
            return []

    async def get_mention_network(
        self, user_id: int, guild_id: int, limit: int = 5
    ) -> dict[str, list[dict[str, Any]]]:
        """メンション相関を取得"""
        if not checkpoint_db._initialized:
            return {"sent_to": [], "received_from": []}

        # 送信先
        sent_query = """
            SELECT to_user_id, COUNT(*) as count
            FROM cp_mention_logs
            WHERE from_user_id = $1 AND guild_id = $2
            GROUP BY to_user_id
            ORDER BY count DESC
            LIMIT $3
        """

        # 受信元
        received_query = """
            SELECT from_user_id, COUNT(*) as count
            FROM cp_mention_logs
            WHERE to_user_id = $1 AND guild_id = $2
            GROUP BY from_user_id
            ORDER BY count DESC
            LIMIT $3
        """

        try:
            async with checkpoint_db.pool.acquire() as conn:
                sent_rows = await conn.fetch(sent_query, user_id, guild_id, limit)
                received_rows = await conn.fetch(
                    received_query, user_id, guild_id, limit
                )

            return {
                "sent_to": [
                    {"user_id": row["to_user_id"], "count": row["count"]}
                    for row in sent_rows
                ],
                "received_from": [
                    {"user_id": row["from_user_id"], "count": row["count"]}
                    for row in received_rows
                ],
            }
        except Exception as e:
            logger.error(f"メンション相関取得エラー: {e}")
            return {"sent_to": [], "received_from": []}

    async def aggregate_monthly_stats(self, guild_id: int, year: int, month: int):
        """月別統計を集計してDBに保存"""
        if not checkpoint_db._initialized:
            return

        query = """
            INSERT INTO cp_monthly_stats
                (user_id, guild_id, year, month, message_count, reaction_count,
                 vc_seconds, mention_sent_count, mention_received_count, omikuji_count)
            SELECT
                user_id, guild_id, $3, $4,
                SUM(message_count), SUM(reaction_count), SUM(vc_seconds),
                SUM(mention_sent_count), SUM(mention_received_count), SUM(omikuji_count)
            FROM cp_daily_stats
            WHERE guild_id = $1
              AND EXTRACT(YEAR FROM stat_date) = $3
              AND EXTRACT(MONTH FROM stat_date) = $4
            GROUP BY user_id, guild_id
            ON CONFLICT (user_id, guild_id, year, month) DO UPDATE
            SET message_count = EXCLUDED.message_count,
                reaction_count = EXCLUDED.reaction_count,
                vc_seconds = EXCLUDED.vc_seconds,
                mention_sent_count = EXCLUDED.mention_sent_count,
                mention_received_count = EXCLUDED.mention_received_count,
                omikuji_count = EXCLUDED.omikuji_count,
                updated_at = CURRENT_TIMESTAMP
        """

        try:
            async with checkpoint_db.pool.acquire() as conn:
                await conn.execute(query, guild_id, guild_id, year, month)
            logger.info(f"月別統計集計完了: {year}/{month}")
        except Exception as e:
            logger.error(f"月別統計集計エラー: {e}")

    async def save_to_db_cache(
        self, user_id: int, guild_id: int, cache_key: str, data: dict
    ):
        """DBキャッシュに保存"""
        if not checkpoint_db._initialized:
            return

        query = """
            INSERT INTO cp_stats_cache (user_id, guild_id, cache_key, cache_value, expires_at)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (user_id, guild_id, cache_key) DO UPDATE
            SET cache_value = $4, expires_at = $5, updated_at = CURRENT_TIMESTAMP
        """

        expires_at = datetime.now(timezone.utc) + timedelta(seconds=CACHE_TTL)

        try:
            async with checkpoint_db.pool.acquire() as conn:
                await conn.execute(
                    query, user_id, guild_id, cache_key, json.dumps(data), expires_at
                )
        except Exception as e:
            logger.warning(f"キャッシュ保存エラー: {e}")


# シングルトンインスタンス
checkpoint_stats = CheckpointStats()
