"""
AUS Database Manager
データベース接続とクエリ管理
"""

from typing import Any, Optional

import asyncpg

from config.setting import get_settings
from utils.logging import setup_logging

logger = setup_logging()
settings = get_settings()


class DatabaseManager:
    """AUSシステムのデータベース管理クラス"""

    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None

    async def initialize(self):
        """データベース接続プールを初期化"""
        database_url = settings.aus_database_url
        if not database_url:
            raise ValueError("AUS_DATABASE_URL環境変数が設定されていません")

        # Railway の postgres:// を postgresql:// に変換
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)

        self.pool = await asyncpg.create_pool(
            database_url,
            min_size=2,
            max_size=10,
            command_timeout=60
        )

        logger.info("✅ AUS Database pool created successfully")

    async def close(self):
        """データベース接続プールをクローズ"""
        if self.pool:
            await self.pool.close()
            logger.info("✅ AUS Database pool closed")

    # ==================== Verified Artists ====================

    async def is_verified_artist(self, user_id: int) -> bool:
        """ユーザーが認証済み絵師かどうか確認"""
        async with self.pool.acquire() as conn:
            result = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM verified_artists WHERE user_id = $1)",
                user_id
            )
            return result

    async def get_verified_artist(self, user_id: int) -> Optional[dict[str, Any]]:
        """認証済み絵師情報を取得"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT user_id, twitter_handle, twitter_url, verified_at,
                       verified_by, notes
                FROM verified_artists
                WHERE user_id = $1
                """,
                user_id
            )
            return dict(row) if row else None

    async def add_verified_artist(
        self,
        user_id: int,
        twitter_handle: str,
        twitter_url: str,
        verified_by: int,
        notes: Optional[str] = None
    ) -> bool:
        """認証済み絵師を追加"""
        async with self.pool.acquire() as conn:
            try:
                await conn.execute(
                    """
                    INSERT INTO verified_artists
                        (user_id, twitter_handle, twitter_url, verified_by, notes)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (user_id) DO UPDATE
                    SET twitter_handle = $2,
                        twitter_url = $3,
                        verified_at = NOW(),
                        verified_by = $4,
                        notes = $5
                    """,
                    user_id, twitter_handle, twitter_url, verified_by, notes
                )
                return True
            except Exception as e:
                logger.error(f"❌ Failed to add verified artist: {e}")
                return False

    async def remove_verified_artist(self, user_id: int) -> bool:
        """認証済み絵師を削除"""
        async with self.pool.acquire() as conn:
            try:
                result = await conn.execute(
                    "DELETE FROM verified_artists WHERE user_id = $1",
                    user_id
                )
                return result != "DELETE 0"
            except Exception as e:
                logger.error(f"❌ Failed to remove verified artist: {e}")
                return False

    async def get_all_verified_artists(self) -> list[dict[str, Any]]:
        """全ての認証済み絵師を取得"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT user_id, twitter_handle, twitter_url, verified_at,
                       verified_by, notes
                FROM verified_artists
                ORDER BY verified_at DESC
                """
            )
            return [dict(row) for row in rows]

    # ==================== Verification Tickets ====================

    async def create_ticket(
        self,
        user_id: int,
        twitter_handle: str,
        twitter_url: Optional[str],
        proof_description: str,
        channel_id: int
    ) -> int:
        """認証申請チケットを作成"""
        async with self.pool.acquire() as conn:
            ticket_id = await conn.fetchval(
                """
                INSERT INTO verification_tickets
                    (user_id, twitter_handle, twitter_url, proof_description, channel_id)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING ticket_id
                """,
                user_id, twitter_handle, twitter_url, proof_description, channel_id
            )
            return ticket_id

    async def get_ticket(self, ticket_id: int) -> Optional[dict[str, Any]]:
        """チケット情報を取得"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT ticket_id, user_id, twitter_handle, twitter_url,
                       proof_description, status, created_at, resolved_at,
                       resolved_by, channel_id, rejection_reason
                FROM verification_tickets
                WHERE ticket_id = $1
                """,
                ticket_id
            )
            return dict(row) if row else None

    async def get_user_pending_tickets(self, user_id: int) -> list[dict[str, Any]]:
        """ユーザーの未解決チケットを取得"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT ticket_id, user_id, twitter_handle, twitter_url,
                       proof_description, status, created_at, channel_id
                FROM verification_tickets
                WHERE user_id = $1 AND status = 'pending'
                ORDER BY created_at DESC
                """,
                user_id
            )
            return [dict(row) for row in rows]

    async def approve_ticket(
        self,
        ticket_id: int,
        verified_by: int,
        twitter_handle: str,
        twitter_url: str
    ) -> bool:
        """チケットを承認し、認証済み絵師に追加"""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                try:
                    # チケット情報取得
                    ticket = await conn.fetchrow(
                        "SELECT user_id FROM verification_tickets WHERE ticket_id = $1",
                        ticket_id
                    )
                    if not ticket:
                        return False

                    # チケットステータスを更新
                    await conn.execute(
                        """
                        UPDATE verification_tickets
                        SET status = 'approved',
                            resolved_at = NOW(),
                            resolved_by = $2
                        WHERE ticket_id = $1
                        """,
                        ticket_id, verified_by
                    )

                    # 認証済み絵師に追加
                    await conn.execute(
                        """
                        INSERT INTO verified_artists
                            (user_id, twitter_handle, twitter_url, verified_by)
                        VALUES ($1, $2, $3, $4)
                        ON CONFLICT (user_id) DO UPDATE
                        SET twitter_handle = $2,
                            twitter_url = $3,
                            verified_at = NOW(),
                            verified_by = $4
                        """,
                        ticket['user_id'], twitter_handle, twitter_url, verified_by
                    )

                    return True
                except Exception as e:
                    logger.error(f"❌ Failed to approve ticket: {e}")
                    return False

    async def reject_ticket(
        self,
        ticket_id: int,
        rejected_by: int,
        rejection_reason: str
    ) -> bool:
        """チケットを却下"""
        async with self.pool.acquire() as conn:
            try:
                result = await conn.execute(
                    """
                    UPDATE verification_tickets
                    SET status = 'rejected',
                        resolved_at = NOW(),
                        resolved_by = $2,
                        rejection_reason = $3
                    WHERE ticket_id = $1
                    """,
                    ticket_id, rejected_by, rejection_reason
                )
                return result != "UPDATE 0"
            except Exception as e:
                logger.error(f"❌ Failed to reject ticket: {e}")
                return False

    async def get_all_pending_tickets(self) -> list[dict[str, Any]]:
        """全ての未解決チケットを取得"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT ticket_id, user_id, twitter_handle, twitter_url,
                       proof_description, status, created_at, channel_id
                FROM verification_tickets
                WHERE status = 'pending'
                ORDER BY created_at ASC
                """
            )
            return [dict(row) for row in rows]

    async def get_ticket_stats(self) -> dict[str, int]:
        """チケット統計を取得"""
        async with self.pool.acquire() as conn:
            stats = await conn.fetchrow(
                """
                SELECT
                    COUNT(*) FILTER (WHERE status = 'pending') as pending,
                    COUNT(*) FILTER (WHERE status = 'approved') as approved,
                    COUNT(*) FILTER (WHERE status = 'rejected') as rejected,
                    COUNT(*) as total
                FROM verification_tickets
                """
            )
            return dict(stats) if stats else {
                'pending': 0, 'approved': 0, 'rejected': 0, 'total': 0
            }
