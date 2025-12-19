"""
Checkpoint モデル テスト
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from cogs.cp.models import (
    DailyStat,
    MentionLog,
    MessageLog,
    OmikujiLog,
    RankingEntry,
    ReactionLog,
    UserStats,
    VoiceLog,
)


class TestMessageLog:
    """MessageLogのテスト"""

    def test_create_message_log(self):
        """MessageLogの生成テスト"""
        now = datetime.now(timezone.utc)
        log = MessageLog(
            user_id=123456789,
            guild_id=987654321,
            channel_id=111222333,
            message_id=444555666,
            content="テストメッセージ",
            word_count=1,
            char_count=8,
            has_attachments=False,
            has_embeds=False,
            created_at=now,
        )

        assert log.user_id == 123456789
        assert log.guild_id == 987654321
        assert log.content == "テストメッセージ"
        assert log.word_count == 1
        assert log.char_count == 8

    def test_message_log_with_thread(self):
        """スレッド付きMessageLogのテスト"""
        now = datetime.now(timezone.utc)
        log = MessageLog(
            user_id=123456789,
            guild_id=987654321,
            channel_id=111222333,
            message_id=444555666,
            content="スレッドメッセージ",
            word_count=1,
            char_count=9,
            has_attachments=False,
            has_embeds=False,
            thread_id=777888999,
            forum_id=None,
            created_at=now,
        )

        assert log.thread_id == 777888999
        assert log.forum_id is None


class TestReactionLog:
    """ReactionLogのテスト"""

    def test_create_reaction_log(self):
        """ReactionLogの生成テスト"""
        now = datetime.now(timezone.utc)
        log = ReactionLog(
            user_id=123456789,
            guild_id=987654321,
            message_id=444555666,
            emoji_name="👍",
            emoji_id=None,
            emoji_animated=False,
            is_add=True,
            created_at=now,
        )

        assert log.emoji_name == "👍"
        assert log.is_add is True

    def test_custom_emoji_reaction(self):
        """カスタム絵文字リアクションのテスト"""
        now = datetime.now(timezone.utc)
        log = ReactionLog(
            user_id=123456789,
            guild_id=987654321,
            message_id=444555666,
            emoji_name="custom_emoji",
            emoji_id=999888777,
            emoji_animated=True,
            is_add=True,
            created_at=now,
        )

        assert log.emoji_id == 999888777
        assert log.emoji_animated is True


class TestVoiceLog:
    """VoiceLogのテスト"""

    def test_create_voice_log(self):
        """VoiceLogの生成テスト"""
        now = datetime.now(timezone.utc)
        log = VoiceLog(
            user_id=123456789,
            guild_id=987654321,
            channel_id=111222333,
            joined_at=now,
            was_self_muted=False,
            was_self_deafened=False,
        )

        assert log.user_id == 123456789
        assert log.left_at is None
        assert log.duration_seconds is None


class TestMentionLog:
    """MentionLogのテスト"""

    def test_create_mention_log(self):
        """MentionLogの生成テスト"""
        now = datetime.now(timezone.utc)
        log = MentionLog(
            from_user_id=123456789,
            to_user_id=987654321,
            guild_id=111222333,
            message_id=444555666,
            mention_type="mention",
            channel_id=777888999,
            created_at=now,
        )

        assert log.from_user_id == 123456789
        assert log.to_user_id == 987654321
        assert log.mention_type == "mention"

    def test_reply_mention(self):
        """リプライメンションのテスト"""
        now = datetime.now(timezone.utc)
        log = MentionLog(
            from_user_id=123456789,
            to_user_id=987654321,
            guild_id=111222333,
            message_id=444555666,
            mention_type="reply",
            channel_id=777888999,
            created_at=now,
        )

        assert log.mention_type == "reply"


class TestOmikujiLog:
    """OmikujiLogのテスト"""

    def test_create_omikuji_log(self):
        """OmikujiLogの生成テスト"""
        now = datetime.now(timezone.utc)
        log = OmikujiLog(
            user_id=123456789,
            guild_id=987654321,
            result="大吉",
            result_detail={"luck": 100},
            used_at=now,
        )

        assert log.result == "大吉"
        assert log.result_detail["luck"] == 100


class TestUserStats:
    """UserStatsのテスト"""

    def test_create_user_stats(self):
        """UserStatsの生成テスト"""
        stats = UserStats(
            user_id=123456789,
            guild_id=987654321,
            year=2025,
            total_messages=100,
            total_reactions=50,
            total_vc_seconds=3600,
            total_mentions_sent=10,
            total_mentions_received=20,
            total_omikuji=5,
        )

        assert stats.total_messages == 100
        assert stats.total_vc_seconds == 3600


class TestRankingEntry:
    """RankingEntryのテスト"""

    def test_create_ranking_entry(self):
        """RankingEntryの生成テスト"""
        entry = RankingEntry(
            rank=1,
            user_id=123456789,
            value=1000,
            category="messages",
        )

        assert entry.rank == 1
        assert entry.value == 1000
        assert entry.category == "messages"


class TestDailyStat:
    """DailyStatのテスト"""

    def test_create_daily_stat(self):
        """DailyStatの生成テスト"""
        stat = DailyStat(
            user_id=123456789,
            guild_id=987654321,
            stat_date="2025-12-01",
            message_count=50,
            reaction_count=25,
            vc_seconds=1800,
            mention_sent_count=5,
            mention_received_count=10,
            omikuji_count=2,
        )

        assert stat.stat_date == "2025-12-01"
        assert stat.message_count == 50
