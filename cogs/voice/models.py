"""
Voice Recording データモデル
"""

from dataclasses import dataclass
from datetime import datetime

from cogs.voice.db import voice_database
from utils.logging import setup_logging

logger = setup_logging(__name__)


@dataclass
class VoiceSession:
    """録音セッション"""

    id: int
    guild_id: int
    channel_id: int
    started_by: int
    started_at: datetime
    ended_at: datetime | None = None
    duration_seconds: int | None = None
    participant_count: int = 0
    status: str = "recording"


@dataclass
class VoiceRecording:
    """ユーザーごとの録音データ"""

    id: int
    session_id: int
    user_id: int
    duration_seconds: float
    file_size_bytes: int | None = None
    discord_message_id: int | None = None
    discord_attachment_url: str | None = None


@dataclass
class VoiceTranscript:
    """文字起こし結果"""

    id: int
    recording_id: int | None
    session_id: int | None
    user_id: int | None
    content: str
    language: str = "ja"
    word_count: int | None = None


@dataclass
class VoiceSummary:
    """要約結果"""

    id: int
    session_id: int
    summary: str
    key_points: str | None = None
    action_items: str | None = None
    model_used: str = "gpt-4o-mini"


class VoiceDB:
    """Voice Recording DB操作"""

    async def create_session(
        self,
        guild_id: int,
        channel_id: int,
        started_by: int,
        started_at: datetime,
    ) -> int | None:
        """セッションを作成"""
        if not voice_database._initialized:
            return None

        query = """
            INSERT INTO voice_sessions (guild_id, channel_id, started_by, started_at, status)
            VALUES ($1, $2, $3, $4, 'recording')
            RETURNING id
        """
        try:
            async with voice_database.pool.acquire() as conn:
                row = await conn.fetchrow(query, guild_id, channel_id, started_by, started_at)
                return row["id"] if row else None
        except Exception as e:
            logger.error(f"セッション作成エラー: {e}")
            return None

    async def end_session(
        self,
        session_id: int,
        ended_at: datetime,
        duration_seconds: int,
        participant_count: int,
        status: str = "completed",
    ) -> bool:
        """セッションを終了"""
        if not voice_database._initialized:
            return False

        query = """
            UPDATE voice_sessions
            SET ended_at = $2, duration_seconds = $3, participant_count = $4, status = $5
            WHERE id = $1
        """
        try:
            async with voice_database.pool.acquire() as conn:
                await conn.execute(query, session_id, ended_at, duration_seconds, participant_count, status)
            return True
        except Exception as e:
            logger.error(f"セッション終了エラー: {e}")
            return False

    async def add_recording(
        self,
        session_id: int,
        user_id: int,
        duration_seconds: float,
        file_size_bytes: int | None = None,
        discord_message_id: int | None = None,
        discord_attachment_url: str | None = None,
    ) -> int | None:
        """録音データを追加"""
        if not voice_database._initialized:
            return None

        query = """
            INSERT INTO voice_recordings
            (session_id, user_id, duration_seconds, file_size_bytes, discord_message_id, discord_attachment_url)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id
        """
        try:
            async with voice_database.pool.acquire() as conn:
                row = await conn.fetchrow(
                    query, session_id, user_id, duration_seconds,
                    file_size_bytes, discord_message_id, discord_attachment_url
                )
                return row["id"] if row else None
        except Exception as e:
            logger.error(f"録音データ追加エラー: {e}")
            return None

    async def add_transcript(
        self,
        content: str,
        recording_id: int | None = None,
        session_id: int | None = None,
        user_id: int | None = None,
        language: str = "ja",
    ) -> int | None:
        """文字起こし結果を保存"""
        if not voice_database._initialized:
            return None

        word_count = len(content)

        query = """
            INSERT INTO voice_transcripts
            (recording_id, session_id, user_id, content, language, word_count)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id
        """
        try:
            async with voice_database.pool.acquire() as conn:
                row = await conn.fetchrow(
                    query, recording_id, session_id, user_id, content, language, word_count
                )
                return row["id"] if row else None
        except Exception as e:
            logger.error(f"文字起こし保存エラー: {e}")
            return None

    async def add_summary(
        self,
        session_id: int,
        summary: str,
        key_points: str | None = None,
        action_items: str | None = None,
        model_used: str = "gpt-4o-mini",
    ) -> int | None:
        """要約結果を保存"""
        if not voice_database._initialized:
            return None

        query = """
            INSERT INTO voice_summaries
            (session_id, summary, key_points, action_items, model_used)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id
        """
        try:
            async with voice_database.pool.acquire() as conn:
                row = await conn.fetchrow(
                    query, session_id, summary, key_points, action_items, model_used
                )
                return row["id"] if row else None
        except Exception as e:
            logger.error(f"要約保存エラー: {e}")
            return None

    async def get_session(self, session_id: int) -> VoiceSession | None:
        """セッションを取得"""
        if not voice_database._initialized:
            return None

        query = "SELECT * FROM voice_sessions WHERE id = $1"
        try:
            async with voice_database.pool.acquire() as conn:
                row = await conn.fetchrow(query, session_id)
                if row:
                    return VoiceSession(
                        id=row["id"],
                        guild_id=row["guild_id"],
                        channel_id=row["channel_id"],
                        started_by=row["started_by"],
                        started_at=row["started_at"],
                        ended_at=row["ended_at"],
                        duration_seconds=row["duration_seconds"],
                        participant_count=row["participant_count"],
                        status=row["status"],
                    )
            return None
        except Exception as e:
            logger.error(f"セッション取得エラー: {e}")
            return None

    async def get_guild_sessions(
        self,
        guild_id: int,
        limit: int = 10,
    ) -> list[VoiceSession]:
        """サーバーのセッション履歴を取得"""
        if not voice_database._initialized:
            return []

        query = """
            SELECT * FROM voice_sessions
            WHERE guild_id = $1
            ORDER BY started_at DESC
            LIMIT $2
        """
        try:
            async with voice_database.pool.acquire() as conn:
                rows = await conn.fetch(query, guild_id, limit)
                return [
                    VoiceSession(
                        id=row["id"],
                        guild_id=row["guild_id"],
                        channel_id=row["channel_id"],
                        started_by=row["started_by"],
                        started_at=row["started_at"],
                        ended_at=row["ended_at"],
                        duration_seconds=row["duration_seconds"],
                        participant_count=row["participant_count"],
                        status=row["status"],
                    )
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"セッション履歴取得エラー: {e}")
            return []

    async def get_session_transcripts(self, session_id: int) -> list[VoiceTranscript]:
        """セッションの文字起こし結果を取得"""
        if not voice_database._initialized:
            return []

        query = """
            SELECT * FROM voice_transcripts
            WHERE session_id = $1
            ORDER BY created_at
        """
        try:
            async with voice_database.pool.acquire() as conn:
                rows = await conn.fetch(query, session_id)
                return [
                    VoiceTranscript(
                        id=row["id"],
                        recording_id=row["recording_id"],
                        session_id=row["session_id"],
                        user_id=row["user_id"],
                        content=row["content"],
                        language=row["language"],
                        word_count=row["word_count"],
                    )
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"文字起こし取得エラー: {e}")
            return []


# シングルトンインスタンス
voice_db = VoiceDB()


async def setup(bot):
    """ダミーsetup - このモジュールはCogではない"""
    pass
