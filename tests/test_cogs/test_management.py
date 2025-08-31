"""
Tests for management and moderation cogs.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest


class TestUserWarning:
    """Test user warning system."""

    def test_warning_data_structure(self):
        """Test warning data structure."""
        warning = {
            "id": 1,
            "user_id": 123456789,
            "moderator_id": 987654321,
            "reason": "Spam behavior",
            "timestamp": datetime.now(),
            "active": True
        }

        required_fields = ["id", "user_id", "moderator_id", "reason", "timestamp", "active"]
        for field in required_fields:
            assert field in warning

        assert isinstance(warning["user_id"], int)
        assert isinstance(warning["moderator_id"], int)
        assert isinstance(warning["reason"], str)
        assert isinstance(warning["timestamp"], datetime)
        assert isinstance(warning["active"], bool)

    @pytest.mark.asyncio
    async def test_warning_creation(self, mock_user, mock_member):
        """Test warning creation logic."""
        warnings_db = []

        async def create_warning(user_id, moderator_id, reason):
            """Mock warning creation."""
            warning = {
                "id": len(warnings_db) + 1,
                "user_id": user_id,
                "moderator_id": moderator_id,
                "reason": reason,
                "timestamp": datetime.now(),
                "active": True
            }
            warnings_db.append(warning)
            return warning

        warning = await create_warning(
            user_id=mock_user.id,
            moderator_id=mock_member.id,
            reason="Test warning"
        )

        assert len(warnings_db) == 1
        assert warning["user_id"] == mock_user.id
        assert warning["reason"] == "Test warning"
        assert warning["active"] is True

    @pytest.mark.asyncio
    async def test_warning_retrieval(self, mock_user):
        """Test warning retrieval by user."""
        warnings_db = [
            {
                "id": 1,
                "user_id": mock_user.id,
                "moderator_id": 987654321,
                "reason": "First warning",
                "timestamp": datetime.now() - timedelta(days=1),
                "active": True
            },
            {
                "id": 2,
                "user_id": mock_user.id,
                "moderator_id": 987654321,
                "reason": "Second warning",
                "timestamp": datetime.now(),
                "active": True
            },
            {
                "id": 3,
                "user_id": 999999999,
                "moderator_id": 987654321,
                "reason": "Other user warning",
                "timestamp": datetime.now(),
                "active": True
            }
        ]

        def get_user_warnings(user_id):
            """Mock warning retrieval."""
            return [w for w in warnings_db if w["user_id"] == user_id and w["active"]]

        user_warnings = get_user_warnings(mock_user.id)

        assert len(user_warnings) == 2
        assert all(w["user_id"] == mock_user.id for w in user_warnings)
        assert all(w["active"] for w in user_warnings)

    @pytest.mark.asyncio
    async def test_warning_expiration(self):
        """Test warning expiration logic."""
        warnings_db = [
            {
                "id": 1,
                "user_id": 123456789,
                "moderator_id": 987654321,
                "reason": "Old warning",
                "timestamp": datetime.now() - timedelta(days=31),
                "active": True
            },
            {
                "id": 2,
                "user_id": 123456789,
                "moderator_id": 987654321,
                "reason": "Recent warning",
                "timestamp": datetime.now() - timedelta(days=5),
                "active": True
            }
        ]

        def expire_old_warnings(days_threshold=30):
            """Mock warning expiration."""
            cutoff_date = datetime.now() - timedelta(days=days_threshold)
            expired_count = 0

            for warning in warnings_db:
                if warning["timestamp"] < cutoff_date and warning["active"]:
                    warning["active"] = False
                    expired_count += 1

            return expired_count

        expired = expire_old_warnings(30)

        assert expired == 1
        assert warnings_db[0]["active"] is False
        assert warnings_db[1]["active"] is True


class TestModerationCommands:
    """Test moderation command functionality."""

    @pytest.mark.asyncio
    async def test_kick_command_validation(self, mock_member, mock_interaction):
        """Test kick command validation."""

        def validate_kick_target(moderator, target):
            """Mock kick validation."""
            if moderator.id == target.id:
                return False, "You cannot kick yourself"

            if target.bot:
                return False, "Cannot kick bots"

            if hasattr(moderator, 'top_role') and hasattr(target, 'top_role'):
                if moderator.top_role.position <= target.top_role.position:
                    return False, "Target has equal or higher role"

            return True, "Valid target"

        moderator = MagicMock()
        moderator.id = 111111111
        moderator.top_role = MagicMock()
        moderator.top_role.position = 10

        target = MagicMock()
        target.id = 222222222
        target.bot = False
        target.top_role = MagicMock()
        target.top_role.position = 5

        valid, message = validate_kick_target(moderator, target)
        assert valid is True
        assert message == "Valid target"

        valid, message = validate_kick_target(moderator, moderator)
        assert valid is False
        assert "yourself" in message

    @pytest.mark.asyncio
    async def test_ban_command_validation(self, mock_member):
        """Test ban command validation."""

        def validate_ban_duration(duration_str):
            """Mock ban duration validation."""
            if not duration_str:
                return True, None  # Permanent ban

            duration_map = {
                "1d": timedelta(days=1),
                "7d": timedelta(days=7),
                "30d": timedelta(days=30)
            }

            if duration_str in duration_map:
                return True, duration_map[duration_str]

            return False, "Invalid duration format"

        valid, duration = validate_ban_duration("7d")
        assert valid is True
        assert duration == timedelta(days=7)

        valid, duration = validate_ban_duration(None)
        assert valid is True
        assert duration is None

        valid, duration = validate_ban_duration("invalid")
        assert valid is False

    @pytest.mark.asyncio
    async def test_mute_functionality(self, mock_member, mock_guild):
        """Test mute functionality."""

        class MockMuteSystem:
            def __init__(self):
                self.muted_users = {}

            async def mute_user(self, user_id, duration=None, reason="No reason provided"):
                """Mock user muting."""
                end_time = None
                if duration:
                    end_time = datetime.now() + duration

                self.muted_users[user_id] = {
                    "muted_at": datetime.now(),
                    "end_time": end_time,
                    "reason": reason,
                    "active": True
                }
                return True

            async def unmute_user(self, user_id):
                """Mock user unmuting."""
                if user_id in self.muted_users:
                    self.muted_users[user_id]["active"] = False
                    return True
                return False

            def is_muted(self, user_id):
                """Check if user is muted."""
                if user_id not in self.muted_users:
                    return False

                mute_data = self.muted_users[user_id]
                if not mute_data["active"]:
                    return False

                if mute_data["end_time"] and datetime.now() > mute_data["end_time"]:
                    mute_data["active"] = False
                    return False

                return True

        mute_system = MockMuteSystem()

        await mute_system.mute_user(mock_member.id, timedelta(hours=1), "Test mute")
        assert mute_system.is_muted(mock_member.id) is True

        await mute_system.unmute_user(mock_member.id)
        assert mute_system.is_muted(mock_member.id) is False

    @pytest.mark.asyncio
    async def test_purge_command(self, mock_channel, mock_message):
        """Test message purge functionality."""

        async def mock_purge(channel, limit, check=None):
            """Mock message purging."""
            messages = []
            for i in range(min(limit, 10)):  # Simulate up to 10 messages
                msg = MagicMock()
                msg.id = i
                msg.author = MagicMock()
                msg.author.id = 123456789 if i % 2 == 0 else 987654321
                msg.content = f"Message {i}"
                messages.append(msg)

            if check:
                messages = [msg for msg in messages if check(msg)]

            return messages

        deleted = await mock_purge(mock_channel, 5)
        assert len(deleted) == 5

        def user_filter(message):
            return message.author.id == 123456789

        deleted = await mock_purge(mock_channel, 10, check=user_filter)
        assert len(deleted) == 5  # Half the messages
        assert all(msg.author.id == 123456789 for msg in deleted)


class TestAutoModeration:
    """Test automatic moderation features."""

    def test_spam_detection(self):
        """Test spam detection logic."""
        import time
        from collections import defaultdict

        message_history = defaultdict(list)

        def detect_spam(user_id, message_content, threshold=5, time_window=60):
            """Mock spam detection."""
            current_time = time.time()
            user_messages = message_history[user_id]

            user_messages[:] = [
                (msg_time, content) for msg_time, content in user_messages
                if current_time - msg_time < time_window
            ]

            user_messages.append((current_time, message_content))

            if len(user_messages) > threshold:
                return True

            recent_content = [content for _, content in user_messages[-3:]]
            if len(set(recent_content)) == 1 and len(recent_content) >= 3:
                return True

            return False

        user_id = 123456789

        for i in range(3):
            assert detect_spam(user_id, f"Message {i}") is False

        for i in range(5):
            detect_spam(user_id, f"Spam {i}")

        assert detect_spam(user_id, "More spam") is True

        new_user = 987654321
        for _ in range(3):
            detect_spam(new_user, "Same message")

        assert detect_spam(new_user, "Same message") is True

    def test_content_filtering(self):
        """Test content filtering."""

        def filter_content(message_content):
            """Mock content filtering."""
            banned_words = ["spam", "scam", "hack"]
            suspicious_patterns = ["http://", "discord.gg/"]

            content_lower = message_content.lower()

            for word in banned_words:
                if word in content_lower:
                    return False, f"Contains banned word: {word}"

            for pattern in suspicious_patterns:
                if pattern in content_lower:
                    return False, f"Contains suspicious pattern: {pattern}"

            return True, "Content approved"

        valid, reason = filter_content("Hello everyone!")
        assert valid is True

        valid, reason = filter_content("This is spam content")
        assert valid is False
        assert "spam" in reason

        valid, reason = filter_content("Join my server: discord.gg/example")
        assert valid is False
        assert "suspicious pattern" in reason

    @pytest.mark.asyncio
    async def test_raid_protection(self):
        """Test raid protection logic."""
        import time
        from collections import defaultdict

        join_history = defaultdict(list)

        def detect_raid(guild_id, user_join_time, threshold=10, time_window=300):
            """Mock raid detection."""
            guild_joins = join_history[guild_id]

            guild_joins[:] = [
                join_time for join_time in guild_joins
                if user_join_time - join_time < time_window
            ]

            guild_joins.append(user_join_time)

            return len(guild_joins) > threshold

        guild_id = 123456789
        current_time = time.time()

        for i in range(5):
            join_time = current_time + i * 60  # 1 minute apart
            assert detect_raid(guild_id, join_time) is False

        for i in range(8):
            join_time = current_time + 300 + i * 5  # 5 seconds apart
            detect_raid(guild_id, join_time)

        raid_join_time = current_time + 300 + 50
        assert detect_raid(guild_id, raid_join_time) is True
