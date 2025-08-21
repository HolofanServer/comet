"""
レベリングシステムのAI設定用Pydanticモデル

OpenAI Structured Outputsと連携して、自然言語の設定を
厳密なJSON構造に変換・検証するためのデータモデル。
"""

from pydantic import BaseModel, Field, validator
from typing import List, Optional, Union
from enum import Enum

class DayOfWeek(str, Enum):
    """曜日の定義"""
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"
    
    # 日本語対応
    WEEKDAY = "weekday"  # 平日
    WEEKEND = "weekend"  # 週末

class TimeWindow(BaseModel):
    """時間帯設定"""
    day: Union[DayOfWeek, List[DayOfWeek]] = Field(
        description="対象曜日（単体または複数）"
    )
    start_time: str = Field(
        description="開始時刻（HH:MM形式）",
        pattern=r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$"
    )
    end_time: str = Field(
        description="終了時刻（HH:MM形式）", 
        pattern=r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$"
    )
    multiplier: float = Field(
        default=1.0,
        ge=0.0,
        le=10.0,
        description="XP倍率（0.0-10.0）"
    )

class ChannelConfig(BaseModel):
    """チャンネル別設定"""
    channel_id: Optional[str] = Field(default=None, description="チャンネルID")
    channel_name: Optional[str] = Field(default=None, description="チャンネル名")
    multiplier: float = Field(
        default=1.0,
        ge=0.0, 
        le=10.0,
        description="XP倍率"
    )
    base_xp: Optional[int] = Field(
        default=None,
        ge=0,
        le=1000,
        description="ベースXP（nullの場合は全体設定を使用）"
    )
    cooldown_seconds: Optional[int] = Field(
        default=None,
        ge=0,
        le=3600,
        description="クールダウン秒数"
    )

class RoleConfig(BaseModel):
    """ロール別設定"""
    role_id: Optional[str] = Field(default=None, description="ロールID")
    role_name: Optional[str] = Field(default=None, description="ロール名")
    multiplier: float = Field(
        default=1.0,
        ge=0.0,
        le=10.0,
        description="XP倍率"
    )
    bonus_xp: int = Field(
        default=0,
        ge=0,
        le=1000,
        description="ボーナスXP"
    )

class SpamFilter(BaseModel):
    """スパムフィルタ設定"""
    banned_words: List[str] = Field(
        default_factory=list,
        description="禁止単語リスト"
    )
    min_length: int = Field(
        default=1,
        ge=1,
        le=2000,
        description="最小文字数"
    )
    max_length: int = Field(
        default=2000,
        ge=1,
        le=2000,
        description="最大文字数"  
    )
    repetition_threshold: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="繰り返し閾値（0.0-1.0）"
    )

class LevelConfig(BaseModel):
    """メインレベリング設定"""
    
    # 基本設定
    base_xp: int = Field(
        default=10,
        ge=1,
        le=1000,
        description="基本XP付与量"
    )
    base_cooldown: int = Field(
        default=60,
        ge=0,
        le=3600,
        description="基本クールダウン（秒）"
    )
    
    # 倍率・ボーナス設定
    global_multiplier: float = Field(
        default=1.0,
        ge=0.0,
        le=10.0,
        description="全体XP倍率"
    )
    
    # チャンネル設定
    channels: List[ChannelConfig] = Field(
        default_factory=list,
        description="チャンネル別設定"
    )
    
    # ロール設定
    roles: List[RoleConfig] = Field(
        default_factory=list,
        description="ロール別設定"
    )
    
    # 時間帯設定
    time_windows: List[TimeWindow] = Field(
        default_factory=list,
        description="時間帯別設定"
    )
    
    # スパムフィルタ
    spam_filter: SpamFilter = Field(
        default_factory=SpamFilter,
        description="スパムフィルタ設定"
    )
    
    # 有効/無効
    enabled: bool = Field(
        default=True,
        description="設定の有効/無効"
    )
    
    @validator('base_xp')
    def validate_base_xp(cls, v):
        if v <= 0:
            raise ValueError('base_xpは1以上である必要があります')
        return v
    
    @validator('channels')
    def validate_channels(cls, v):
        # チャンネル名/IDの重複チェック
        channel_ids = [c.channel_id for c in v if c.channel_id]
        channel_names = [c.channel_name for c in v if c.channel_name]
        
        if len(channel_ids) != len(set(channel_ids)):
            raise ValueError('チャンネルIDが重複しています')
        if len(channel_names) != len(set(channel_names)):
            raise ValueError('チャンネル名が重複しています')
            
        return v

class ConfigParseResult(BaseModel):
    """自然言語解析結果"""
    success: bool = Field(description="解析成功フラグ")
    config: Optional[LevelConfig] = Field(default=None, description="解析済み設定")
    error_message: Optional[str] = Field(default=None, description="エラーメッセージ")
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="解析信頼度（0.0-1.0）"
    )
    original_input: str = Field(description="元の自然言語入力")
