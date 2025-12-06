"""
Checkpoint DB クライアント

専用PostgreSQLへの非同期接続とログ記録を管理
"""
import json
from datetime import date, datetime, timedelta
from typing import Any

import asyncpg

from config.setting import get_settings
from utils.logging import setup_logging

from .models import (
    DailyStat,
    MentionLog,
    MessageLog,
    OmikujiLog,
    ReactionLog,
    VoiceLog,
)

logger = setup_logging(__name__)


class CheckpointDB:
    """Checkpoint専用DBクライアント"""

    def __init__(self):
        self.pool: asyncpg.Pool | None = None
        self._initialized = False

    async def initialize(self) -> bool:
        """DB接続プールを初期化"""
        if self._initialized:
            return True

        settings = get_settings()
        if not settings.cp_database_url:
            logger.warning("CP_DATABASE_URL が設定されていません")
            return False

        try:
            self.pool = await asyncpg.create_pool(
                settings.cp_database_url,
                min_size=3,
                max_size=15,
                command_timeout=30,
            )
            self._initialized = True
            logger.info("✅ Checkpoint DB 接続プール初期化完了")
            return True
        except Exception as e:
            logger.error(f"❌ Checkpoint DB 接続失敗: {e}")
            return False

    async def close(self):
        """接続プールを閉じる"""
        if self.pool:
            await self.pool.close()
            self._initialized = False
            logger.info("Checkpoint DB 接続プールを閉じました")

    # ==================== ログ記録 ====================

    async def log_message(self, log: MessageLog) -> bool:
        """メッセージをログ記録"""
        if not self._initialized:
            return False

        query = """
            INSERT INTO cp_message_logs
            (user_id, guild_id, channel_id, thread_id, forum_id, message_id,
             content, word_count, char_count, has_attachments, has_embeds, created_at, created_year)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            ON CONFLICT (message_id) DO NOTHING
        """
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    query,
                    log.user_id,
                    log.guild_id,
                    log.channel_id,
                    log.thread_id,
                    log.forum_id,
                    log.message_id,
                    log.content[:2000] if log.content else "",
                    log.word_count,
                    log.char_count,
                    log.has_attachments,
                    log.has_embeds,
                    log.created_at,
                    log.created_at.year,
                )

            # 日別統計を更新
            await self._increment_daily_stat(
                log.user_id, log.guild_id, "message_count", 1
            )
            return True
        except Exception as e:
            logger.error(f"メッセージログ記録エラー: {e}")
            await self._log_error("log_message", str(e), {"user_id": log.user_id})
            return False

    async def log_reaction(self, log: ReactionLog) -> bool:
        """リアクションをログ記録"""
        if not self._initialized:
            return False

        # ログ記録
        log_query = """
            INSERT INTO cp_reaction_logs
            (user_id, guild_id, message_id, emoji_name, emoji_id, emoji_animated, is_add, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """
        # カウント更新
        count_query = """
            INSERT INTO cp_reaction_counts
            (user_id, guild_id, emoji_name, emoji_id, emoji_animated, use_count, last_used_at)
            VALUES ($1, $2, $3, $4, $5, 1, $6)
            ON CONFLICT (user_id, guild_id, emoji_name) DO UPDATE
            SET use_count = cp_reaction_counts.use_count + 1, last_used_at = $6
        """
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    log_query,
                    log.user_id,
                    log.guild_id,
                    log.message_id,
                    log.emoji_name,
                    log.emoji_id,
                    log.emoji_animated,
                    log.is_add,
                    log.created_at,
                )

                if log.is_add:
                    await conn.execute(
                        count_query,
                        log.user_id,
                        log.guild_id,
                        log.emoji_name,
                        log.emoji_id,
                        log.emoji_animated,
                        log.created_at,
                    )

            if log.is_add:
                await self._increment_daily_stat(
                    log.user_id, log.guild_id, "reaction_count", 1
                )
            return True
        except Exception as e:
            logger.error(f"リアクションログ記録エラー: {e}")
            await self._log_error("log_reaction", str(e), {"user_id": log.user_id})
            return False

    async def log_voice_join(self, log: VoiceLog) -> int | None:
        """VC参加をログ記録"""
        if not self._initialized:
            return None

        query = """
            INSERT INTO cp_voice_logs
            (user_id, guild_id, channel_id, joined_at, was_self_muted, was_self_deafened, joined_year)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id
        """
        try:
            async with self.pool.acquire() as conn:
                session_id = await conn.fetchval(
                    query,
                    log.user_id,
                    log.guild_id,
                    log.channel_id,
                    log.joined_at,
                    log.was_self_muted,
                    log.was_self_deafened,
                    log.joined_at.year,
                )
            return session_id
        except Exception as e:
            logger.error(f"VC参加ログ記録エラー: {e}")
            await self._log_error("log_voice_join", str(e), {"user_id": log.user_id})
            return None

    async def log_voice_leave(
        self, user_id: int, guild_id: int, channel_id: int, left_at: datetime
    ) -> int | None:
        """VC退出をログ記録"""
        if not self._initialized:
            return None

        query = """
            UPDATE cp_voice_logs
            SET left_at = $1,
                duration_seconds = EXTRACT(EPOCH FROM ($1 - joined_at))::INT
            WHERE user_id = $2 AND guild_id = $3 AND channel_id = $4 AND left_at IS NULL
            ORDER BY joined_at DESC
            LIMIT 1
            RETURNING duration_seconds
        """
        try:
            async with self.pool.acquire() as conn:
                duration = await conn.fetchval(
                    query, left_at, user_id, guild_id, channel_id
                )

            if duration and duration > 0:
                await self._increment_daily_stat(
                    user_id, guild_id, "vc_seconds", int(duration)
                )
            return duration
        except Exception as e:
            logger.error(f"VC退出ログ記録エラー: {e}")
            await self._log_error("log_voice_leave", str(e), {"user_id": user_id})
            return None

    async def log_mention(self, log: MentionLog) -> bool:
        """メンション・リプライをログ記録"""
        if not self._initialized:
            return False

        query = """
            INSERT INTO cp_mention_logs
            (from_user_id, to_user_id, guild_id, message_id, mention_type, channel_id, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
        """
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    query,
                    log.from_user_id,
                    log.to_user_id,
                    log.guild_id,
                    log.message_id,
                    log.mention_type,
                    log.channel_id,
                    log.created_at,
                )

            await self._increment_daily_stat(
                log.from_user_id, log.guild_id, "mention_sent_count", 1
            )
            await self._increment_daily_stat(
                log.to_user_id, log.guild_id, "mention_received_count", 1
            )
            return True
        except Exception as e:
            logger.error(f"メンションログ記録エラー: {e}")
            await self._log_error(
                "log_mention", str(e), {"from_user_id": log.from_user_id}
            )
            return False

    async def log_omikuji(self, log: OmikujiLog) -> bool:
        """おみくじをログ記録"""
        if not self._initialized:
            return False

        query = """
            INSERT INTO cp_omikuji_logs
            (user_id, guild_id, result, result_detail, used_at, used_year)
            VALUES ($1, $2, $3, $4, $5, $6)
        """
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    query,
                    log.user_id,
                    log.guild_id,
                    log.result,
                    json.dumps(log.result_detail) if log.result_detail else None,
                    log.used_at,
                    log.used_at.year,
                )

            await self._increment_daily_stat(
                log.user_id, log.guild_id, "omikuji_count", 1
            )
            return True
        except Exception as e:
            logger.error(f"おみくじログ記録エラー: {e}")
            await self._log_error("log_omikuji", str(e), {"user_id": log.user_id})
            return False

    # ==================== ユーザーメタデータ ====================

    async def update_user_metadata(
        self,
        user_id: int,
        guild_id: int,
        username: str,
        display_name: str,
        avatar_url: str | None,
        is_bot: bool = False,
    ) -> bool:
        """ユーザーメタデータを更新"""
        if not self._initialized:
            return False

        query = """
            INSERT INTO cp_user_metadata
            (user_id, guild_id, username, display_name, avatar_url, is_bot, last_active_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT (user_id) DO UPDATE
            SET username = $3, display_name = $4, avatar_url = $5,
                last_active_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
        """
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    query, user_id, guild_id, username, display_name, avatar_url, is_bot
                )
            return True
        except Exception as e:
            logger.warning(f"ユーザーメタデータ更新エラー: {e}")
            return False

    # ==================== 日別統計 ====================

    async def _increment_daily_stat(
        self, user_id: int, guild_id: int, field: str, value: int
    ):
        """日別統計をインクリメント"""
        if not self._initialized:
            return

        today = date.today()
        query = f"""
            INSERT INTO cp_daily_stats (user_id, guild_id, stat_date, {field})
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (user_id, guild_id, stat_date) DO UPDATE
            SET {field} = cp_daily_stats.{field} + $4, updated_at = CURRENT_TIMESTAMP
        """
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(query, user_id, guild_id, today, value)
        except Exception as e:
            logger.error(f"日別統計更新エラー: {e}")

    async def get_daily_stats(
        self, user_id: int, guild_id: int, days: int = 30
    ) -> list[DailyStat]:
        """日別統計を取得"""
        if not self._initialized:
            return []

        query = """
            SELECT * FROM cp_daily_stats
            WHERE user_id = $1 AND guild_id = $2 AND stat_date >= $3
            ORDER BY stat_date DESC
        """
        start_date = date.today() - timedelta(days=days)
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(query, user_id, guild_id, start_date)
            return [
                DailyStat(
                    user_id=row["user_id"],
                    guild_id=row["guild_id"],
                    stat_date=str(row["stat_date"]),
                    message_count=row["message_count"],
                    reaction_count=row["reaction_count"],
                    vc_seconds=row["vc_seconds"],
                    mention_sent_count=row["mention_sent_count"],
                    mention_received_count=row["mention_received_count"],
                    omikuji_count=row["omikuji_count"],
                )
                for row in rows
            ]
        except Exception as e:
            logger.error(f"日別統計取得エラー: {e}")
            return []

    # ==================== エラーログ ====================

    async def _log_error(
        self, error_type: str, error_message: str, context: dict[str, Any]
    ):
        """エラーをログ記録"""
        if not self._initialized:
            return

        query = """
            INSERT INTO cp_error_logs (error_type, error_message, context, severity)
            VALUES ($1, $2, $3, 'error')
        """
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    query, error_type, error_message, json.dumps(context)
                )
        except Exception as e:
            logger.critical(f"エラーログ記録失敗: {e}")

    # ==================== 設定 ====================

    async def is_logging_enabled(self, guild_id: int) -> bool:
        """ギルドでログ収集が有効か"""
        if not self._initialized:
            return False

        query = "SELECT is_enabled FROM cp_config WHERE guild_id = $1"
        try:
            async with self.pool.acquire() as conn:
                result = await conn.fetchval(query, guild_id)
            return result if result is not None else True  # デフォルトは有効
        except Exception:
            return True

    async def get_excluded_channels(self, guild_id: int) -> set[int]:
        """除外チャンネルIDを取得"""
        if not self._initialized:
            return set()

        query = "SELECT excluded_channels FROM cp_config WHERE guild_id = $1"
        try:
            async with self.pool.acquire() as conn:
                result = await conn.fetchval(query, guild_id)
            return set(result) if result else set()
        except Exception:
            return set()


# シングルトンインスタンス
checkpoint_db = CheckpointDB()
