"""
Checkpoint データモデル
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class MessageLog:
    """メッセージログ"""

    user_id: int
    guild_id: int
    channel_id: int
    message_id: int
    content: str = ""
    word_count: int = 0
    char_count: int = 0
    has_attachments: bool = False
    has_embeds: bool = False
    thread_id: int | None = None
    forum_id: int | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ReactionLog:
    """リアクションログ"""

    user_id: int
    guild_id: int
    message_id: int
    emoji_name: str
    emoji_id: int | None = None
    emoji_animated: bool = False
    is_add: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class VoiceLog:
    """VCログ"""

    user_id: int
    guild_id: int
    channel_id: int
    joined_at: datetime
    left_at: datetime | None = None
    duration_seconds: int = 0
    was_self_muted: bool = False
    was_self_deafened: bool = False
    was_streaming: bool = False
    was_video: bool = False
    peak_participants: int = 1


@dataclass
class MentionLog:
    """メンション・リプライログ"""

    from_user_id: int
    to_user_id: int
    guild_id: int
    message_id: int
    mention_type: str  # 'mention' / 'reply'
    channel_id: int
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class OmikujiLog:
    """おみくじログ"""

    user_id: int
    guild_id: int
    result: str
    result_detail: dict[str, Any] | None = None
    used_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class UserStats:
    """ユーザー統計"""

    user_id: int
    guild_id: int
    year: int
    total_messages: int = 0
    total_reactions: int = 0
    total_vc_seconds: int = 0
    total_mentions_sent: int = 0
    total_mentions_received: int = 0
    total_omikuji: int = 0
    active_days: int = 0
    top_emoji: dict[str, Any] | None = None
    top_reply_user: dict[str, Any] | None = None
    top_channels: list[dict[str, Any]] = field(default_factory=list)
    peak_hour: int = 0
    omikuji_distribution: dict[str, int] = field(default_factory=dict)
    message_rank: int = 0
    vc_rank: int = 0
    omikuji_rank: int = 0


@dataclass
class RankingEntry:
    """ランキングエントリ"""

    rank: int
    user_id: int
    value: int
    category: str
    username: str = ""
    avatar_url: str | None = None
    formatted_value: str = ""


@dataclass
class DailyStat:
    """日別統計"""

    user_id: int
    guild_id: int
    stat_date: str  # YYYY-MM-DD
    message_count: int = 0
    reaction_count: int = 0
    vc_seconds: int = 0
    mention_sent_count: int = 0
    mention_received_count: int = 0
    omikuji_count: int = 0
