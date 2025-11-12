"""
音声チャンネルXP・複数トラックシステム用データモデル

時間ベース音声XP、チャンネル別トラック管理、AFK/ミュート検出、
複数の音声活動トラックによる柔軟なXP付与システム。
"""

from datetime import datetime
from enum import Enum
from typing import Optional, Union

from pydantic import BaseModel, Field, validator


class VoiceActivityType(str, Enum):
    """音声活動タイプ"""
    SPEAKING = "speaking"       # 発言中
    LISTENING = "listening"     # 聞いている（非AFK）
    AFK = "afk"                # AFK状態
    MUTED = "muted"            # ミュート状態
    DEAFENED = "deafened"      # スピーカーオフ状態

class VoiceTrackType(str, Enum):
    """音声トラックタイプ"""
    GENERAL = "general"         # 一般音声XP
    STUDY = "study"            # 勉強・作業部屋
    GAMING = "gaming"          # ゲーム部屋
    MUSIC = "music"           # 音楽・雑談部屋
    EVENT = "event"           # イベント・会議部屋
    CUSTOM = "custom"         # カスタムトラック

class VoiceXPMultiplier(BaseModel):
    """音声XP倍率設定"""
    activity_type: VoiceActivityType
    multiplier: float = Field(ge=0.0, le=10.0)
    description: Optional[str] = None

class VoiceChannelConfig(BaseModel):
    """音声チャンネル設定"""
    channel_id: Optional[int] = Field(default=None, gt=0)
    channel_name: Optional[str] = None
    track_type: VoiceTrackType = VoiceTrackType.GENERAL
    base_xp_per_minute: int = Field(ge=0, le=1000, default=5)

    # 活動タイプ別倍率
    activity_multipliers: list[VoiceXPMultiplier] = Field(default_factory=lambda: [
        VoiceXPMultiplier(activity_type=VoiceActivityType.SPEAKING, multiplier=2.0, description="発言中ボーナス"),
        VoiceXPMultiplier(activity_type=VoiceActivityType.LISTENING, multiplier=1.0, description="通常XP"),
        VoiceXPMultiplier(activity_type=VoiceActivityType.AFK, multiplier=0.1, description="AFK時減少"),
        VoiceXPMultiplier(activity_type=VoiceActivityType.MUTED, multiplier=0.7, description="ミュート時減少"),
        VoiceXPMultiplier(activity_type=VoiceActivityType.DEAFENED, multiplier=0.3, description="スピーカーオフ時大幅減少"),
    ])

    # 時間帯別設定
    time_multipliers: dict[str, float] = Field(default_factory=lambda: {
        "morning": 1.0,    # 06:00-12:00
        "afternoon": 1.2,  # 12:00-18:00
        "evening": 1.5,    # 18:00-22:00
        "night": 0.8       # 22:00-06:00
    })

    # 最小・最大滞在時間（分）
    min_duration_minutes: int = Field(ge=1, le=60, default=2)  # 最低2分は必要
    max_xp_per_hour: int = Field(ge=10, le=10000, default=300)  # 1時間あたり最大XP制限

    # 人数ボーナス
    participant_bonus: dict[str, float] = Field(default_factory=lambda: {
        "solo": 0.5,       # 1人: 半減
        "small": 1.0,      # 2-4人: 通常
        "medium": 1.3,     # 5-8人: 1.3倍
        "large": 1.5,      # 9-15人: 1.5倍
        "huge": 1.2        # 16人以上: 1.2倍（混雑ペナルティ）
    })

    is_enabled: bool = True

class VoiceTrackConfig(BaseModel):
    """音声トラック設定"""
    track_type: VoiceTrackType
    track_name: str = Field(min_length=1, max_length=50)
    description: Optional[str] = None

    # グローバル倍率（このトラック全体への倍率）
    global_multiplier: float = Field(ge=0.1, le=5.0, default=1.0)

    # デフォルトチャンネル設定（新規チャンネル用）
    default_channel_config: VoiceChannelConfig = Field(default_factory=VoiceChannelConfig)

    # 特別ボーナス条件
    bonus_conditions: dict[str, Union[float, int]] = Field(default_factory=dict)

    is_active: bool = True

    @validator('track_name')
    def validate_track_name(cls, v):
        if not v.strip():
            raise ValueError('トラック名は空にできません')
        return v.strip()

class VoiceConfig(BaseModel):
    """サーバー全体の音声XP設定"""
    # 基本設定
    voice_xp_enabled: bool = True
    global_voice_multiplier: float = Field(ge=0.0, le=10.0, default=1.0)

    # チャンネル設定
    channels: dict[int, VoiceChannelConfig] = Field(default_factory=dict)  # channel_id -> config

    # トラック設定
    tracks: dict[VoiceTrackType, VoiceTrackConfig] = Field(default_factory=lambda: {
        VoiceTrackType.GENERAL: VoiceTrackConfig(
            track_type=VoiceTrackType.GENERAL,
            track_name="一般音声",
            description="通常の音声チャット活動"
        ),
        VoiceTrackType.STUDY: VoiceTrackConfig(
            track_type=VoiceTrackType.STUDY,
            track_name="勉強・作業",
            description="集中作業・勉強部屋での活動",
            global_multiplier=1.5
        ),
        VoiceTrackType.GAMING: VoiceTrackConfig(
            track_type=VoiceTrackType.GAMING,
            track_name="ゲーム",
            description="ゲーム中の音声チャット",
            global_multiplier=1.2
        ),
        VoiceTrackType.MUSIC: VoiceTrackConfig(
            track_type=VoiceTrackType.MUSIC,
            track_name="音楽・雑談",
            description="音楽鑑賞・雑談部屋",
            global_multiplier=0.9
        ),
        VoiceTrackType.EVENT: VoiceTrackConfig(
            track_type=VoiceTrackType.EVENT,
            track_name="イベント・会議",
            description="特別イベントや会議での参加",
            global_multiplier=2.0
        ),
    })

    # 制限・制約設定
    daily_voice_xp_limit: int = Field(ge=0, le=100000, default=1000)  # 1日の音声XP上限
    afk_detection_minutes: int = Field(ge=1, le=60, default=10)  # AFK判定時間（分）
    speaking_detection_window: int = Field(ge=5, le=300, default=30)  # 発言検出ウィンドウ（秒）

    # レート制限
    xp_calculation_interval: int = Field(ge=30, le=3600, default=60)  # XP計算間隔（秒）
    min_voice_session_seconds: int = Field(ge=10, le=600, default=120)  # 最小セッション時間

    # ボット・除外設定
    exclude_bot_channels: bool = True
    exclude_afk_channels: bool = True
    excluded_channel_ids: list[int] = Field(default_factory=list)
    excluded_user_ids: list[int] = Field(default_factory=list)

    def get_channel_config(self, channel_id: int) -> VoiceChannelConfig:
        """チャンネル設定を取得（デフォルトで汎用設定）"""
        if channel_id in self.channels:
            return self.channels[channel_id]

        # デフォルト設定を返す
        default_config = VoiceChannelConfig(channel_id=channel_id)
        self.channels[channel_id] = default_config
        return default_config

    def get_activity_multiplier(self, channel_id: int, activity_type: VoiceActivityType) -> float:
        """活動タイプ別倍率を取得"""
        channel_config = self.get_channel_config(channel_id)

        for multiplier in channel_config.activity_multipliers:
            if multiplier.activity_type == activity_type:
                return multiplier.multiplier

        # デフォルト倍率
        return 1.0 if activity_type == VoiceActivityType.LISTENING else 0.5

class VoiceSession(BaseModel):
    """音声セッション記録"""
    guild_id: int = Field(gt=0)
    user_id: int = Field(gt=0)
    channel_id: int = Field(gt=0)
    session_id: str  # UUID形式のセッションID

    # 時間情報
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: int = 0

    # 活動状態
    activity_log: list[dict] = Field(default_factory=list)  # 活動履歴
    total_speaking_seconds: int = 0
    total_listening_seconds: int = 0
    total_afk_seconds: int = 0
    total_muted_seconds: int = 0

    # XP計算
    base_xp_earned: int = 0
    bonus_xp_earned: int = 0
    total_xp_earned: int = 0

    # セッション情報
    peak_participants: int = 1  # 同時最大参加者数
    track_type: VoiceTrackType = VoiceTrackType.GENERAL

    is_completed: bool = False

    def calculate_duration(self) -> int:
        """セッション時間を計算"""
        if self.end_time:
            return int((self.end_time - self.start_time).total_seconds())
        return 0

    def add_activity_record(self, activity_type: VoiceActivityType, timestamp: datetime, participants: int = 1):
        """活動記録を追加"""
        self.activity_log.append({
            "activity": activity_type.value,
            "timestamp": timestamp.isoformat(),
            "participants": participants
        })

class VoiceStats(BaseModel):
    """ユーザー音声統計"""
    guild_id: int = Field(gt=0)
    user_id: int = Field(gt=0)

    # 累計統計
    total_voice_time_seconds: int = 0
    total_voice_xp: int = 0
    total_sessions: int = 0

    # トラック別統計
    track_stats: dict[VoiceTrackType, dict[str, int]] = Field(default_factory=dict)

    # 日別統計（最近30日分）
    daily_stats: dict[str, dict[str, int]] = Field(default_factory=dict)  # YYYY-MM-DD -> stats

    # ベスト記録
    longest_session_seconds: int = 0
    highest_daily_xp: int = 0
    most_productive_hour: int = 12  # 24時間制

    # レート情報
    average_xp_per_minute: float = 0.0
    favorite_channels: list[int] = Field(default_factory=list)

    last_updated: datetime = Field(default_factory=datetime.now)

    def update_session_stats(self, session: VoiceSession):
        """セッション完了時の統計更新"""
        if not session.is_completed:
            return

        # 基本統計更新
        self.total_voice_time_seconds += session.duration_seconds
        self.total_voice_xp += session.total_xp_earned
        self.total_sessions += 1

        # 最長セッション更新
        if session.duration_seconds > self.longest_session_seconds:
            self.longest_session_seconds = session.duration_seconds

        # トラック別統計
        if session.track_type not in self.track_stats:
            self.track_stats[session.track_type] = {
                "time_seconds": 0,
                "xp_earned": 0,
                "sessions": 0
            }

        track_stat = self.track_stats[session.track_type]
        track_stat["time_seconds"] += session.duration_seconds
        track_stat["xp_earned"] += session.total_xp_earned
        track_stat["sessions"] += 1

        # 日別統計
        date_key = session.start_time.strftime("%Y-%m-%d")
        if date_key not in self.daily_stats:
            self.daily_stats[date_key] = {
                "time_seconds": 0,
                "xp_earned": 0,
                "sessions": 0
            }

        daily_stat = self.daily_stats[date_key]
        daily_stat["time_seconds"] += session.duration_seconds
        daily_stat["xp_earned"] += session.total_xp_earned
        daily_stat["sessions"] += 1

        # 最高日XP更新
        if daily_stat["xp_earned"] > self.highest_daily_xp:
            self.highest_daily_xp = daily_stat["xp_earned"]

        # 平均XP/分更新
        if self.total_voice_time_seconds > 0:
            self.average_xp_per_minute = self.total_voice_xp / (self.total_voice_time_seconds / 60)

        # チャンネル使用頻度
        if session.channel_id not in self.favorite_channels:
            self.favorite_channels.append(session.channel_id)

        # 最新の更新時間
        self.last_updated = datetime.now()

# プリセット設定
class VoicePresets:
    """音声XP設定プリセット"""

    @staticmethod
    def get_balanced() -> VoiceConfig:
        """バランス型設定"""
        return VoiceConfig(
            global_voice_multiplier=1.0,
            daily_voice_xp_limit=800,
            afk_detection_minutes=5,
            xp_calculation_interval=60
        )

    @staticmethod
    def get_high_reward() -> VoiceConfig:
        """高報酬型設定"""
        return VoiceConfig(
            global_voice_multiplier=1.5,
            daily_voice_xp_limit=1500,
            afk_detection_minutes=3,
            xp_calculation_interval=30
        )

    @staticmethod
    def get_casual() -> VoiceConfig:
        """カジュアル型設定"""
        return VoiceConfig(
            global_voice_multiplier=0.8,
            daily_voice_xp_limit=500,
            afk_detection_minutes=15,
            xp_calculation_interval=120
        )
