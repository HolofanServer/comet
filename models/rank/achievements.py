"""
アチーブメント・スキルツリー・プレステージシステム用データモデル

Discord.pyレベリングシステムのゲーミフィケーション機能を支える
包括的なデータ構造とバリデーション。
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, List, Any, Union, Literal
from datetime import datetime
from enum import Enum

class AchievementType(str, Enum):
    """アチーブメントタイプ"""
    LEVEL = "level"                    # レベル到達
    XP_TOTAL = "xp_total"             # 総XP獲得
    XP_DAILY = "xp_daily"             # 日次XP獲得
    MESSAGE_COUNT = "message_count"    # メッセージ数
    VOICE_TIME = "voice_time"         # 音声チャンネル時間
    VOICE_XP = "voice_xp"             # 音声XP獲得
    STREAK_DAILY = "streak_daily"      # 日次連続記録
    STREAK_WEEKLY = "streak_weekly"    # 週次連続記録
    SOCIAL = "social"                  # ソーシャル活動
    SPECIAL = "special"                # 特別イベント
    CUSTOM = "custom"                  # カスタム条件

class AchievementRarity(str, Enum):
    """アチーブメント希少度"""
    COMMON = "common"       # よくある (白)
    UNCOMMON = "uncommon"   # 珍しい (緑)
    RARE = "rare"          # レア (青)
    EPIC = "epic"          # エピック (紫)
    LEGENDARY = "legendary" # レジェンダリー (オレンジ)
    MYTHIC = "mythic"      # ミシック (赤)

class SkillType(str, Enum):
    """スキルタイプ"""
    XP_BOOST = "xp_boost"           # XP獲得量アップ
    VOICE_BOOST = "voice_boost"     # 音声XP獲得量アップ
    COOLDOWN_REDUCE = "cooldown_reduce"  # クールダウン短縮
    QUALITY_BOOST = "quality_boost"  # 品質分析ボーナス
    STREAK_PROTECT = "streak_protect"  # ストリーク保護
    SOCIAL_BOOST = "social_boost"    # ソーシャルボーナス
    SPECIAL_ACCESS = "special_access"  # 特別機能アクセス

class PrestigeType(str, Enum):
    """プレステージタイプ"""
    STANDARD = "standard"    # 標準プレステージ
    VOICE = "voice"         # 音声特化
    SOCIAL = "social"       # ソーシャル特化
    STREAMER = "streamer"   # 配信者特化
    DEVELOPER = "developer" # 開発者特化

class AchievementCondition(BaseModel):
    """アチーブメント条件"""
    type: AchievementType
    target_value: int = Field(..., ge=1, description="目標値")
    current_value: int = Field(0, ge=0, description="現在値")
    additional_params: Optional[Dict[str, Any]] = Field(default=None, description="追加パラメータ")
    
    @property
    def progress_percentage(self) -> float:
        """進捗率を計算"""
        return min(100.0, (self.current_value / self.target_value) * 100.0)
    
    @property
    def is_completed(self) -> bool:
        """達成済みかチェック"""
        return self.current_value >= self.target_value

class Achievement(BaseModel):
    """アチーブメントデータ"""
    id: str = Field(..., description="アチーブメントID")
    name: str = Field(..., description="アチーブメント名")
    description: str = Field(..., description="説明")
    type: AchievementType
    rarity: AchievementRarity
    condition: AchievementCondition
    
    # 報酬
    xp_reward: int = Field(0, ge=0, description="XP報酬")
    skill_points_reward: int = Field(0, ge=0, description="スキルポイント報酬")
    title_reward: Optional[str] = Field(None, description="称号報酬")
    role_reward: Optional[str] = Field(None, description="ロール報酬")
    custom_rewards: Optional[Dict[str, Any]] = Field(default=None, description="カスタム報酬")
    
    # メタデータ
    icon: Optional[str] = Field(None, description="アイコン絵文字")
    color: Optional[int] = Field(None, description="色コード")
    hidden: bool = Field(False, description="隠しアチーブメント")
    one_time: bool = Field(True, description="一回限り")
    requires_achievements: Optional[List[str]] = Field(default=None, description="前提アチーブメント")
    
    created_at: datetime = Field(default_factory=datetime.now)
    
    @validator('color')
    def validate_color(cls, v):
        if v is not None and (v < 0 or v > 0xFFFFFF):
            raise ValueError('色コードは0x000000から0xFFFFFFの範囲である必要があります')
        return v

class UserAchievement(BaseModel):
    """ユーザーのアチーブメント進捗"""
    guild_id: int
    user_id: int
    achievement_id: str
    
    # 進捗
    current_progress: int = Field(0, ge=0)
    is_completed: bool = Field(False)
    completion_date: Optional[datetime] = Field(None)
    
    # メタデータ
    first_seen: datetime = Field(default_factory=datetime.now)
    last_updated: datetime = Field(default_factory=datetime.now)
    notification_sent: bool = Field(False)

class SkillNode(BaseModel):
    """スキルツリーノード"""
    id: str = Field(..., description="スキルID")
    name: str = Field(..., description="スキル名")
    description: str = Field(..., description="スキル説明")
    type: SkillType
    
    # ツリー構造
    tier: int = Field(..., ge=1, le=10, description="ティア（階層）")
    prerequisites: Optional[List[str]] = Field(default=None, description="前提スキル")
    
    # コスト・効果
    skill_points_cost: int = Field(..., ge=1, description="必要スキルポイント")
    max_level: int = Field(1, ge=1, le=10, description="最大レベル")
    effect_per_level: float = Field(..., description="レベル毎の効果量")
    
    # メタデータ
    icon: Optional[str] = Field(None, description="アイコン絵文字")
    color: Optional[int] = Field(None, description="色コード")
    category: str = Field("general", description="カテゴリ")

class UserSkill(BaseModel):
    """ユーザーのスキル習得状況"""
    guild_id: int
    user_id: int
    skill_id: str
    
    current_level: int = Field(0, ge=0, description="現在レベル")
    total_invested_points: int = Field(0, ge=0, description="投資済みポイント")
    unlocked_at: Optional[datetime] = Field(None)
    last_upgraded: Optional[datetime] = Field(None)

class PrestigeBenefit(BaseModel):
    """プレステージ特典"""
    xp_multiplier: float = Field(1.0, ge=0.1, le=10.0, description="XP倍率")
    voice_xp_multiplier: float = Field(1.0, ge=0.1, le=10.0, description="音声XP倍率")
    skill_point_multiplier: float = Field(1.0, ge=0.1, le=10.0, description="スキルポイント倍率")
    
    daily_xp_bonus: int = Field(0, ge=0, description="日次XPボーナス")
    exclusive_titles: Optional[List[str]] = Field(default=None, description="専用称号")
    exclusive_roles: Optional[List[str]] = Field(default=None, description="専用ロール")
    
    achievement_bonus: float = Field(1.0, ge=1.0, le=5.0, description="アチーブメント報酬倍率")
    special_features: Optional[Dict[str, bool]] = Field(default=None, description="特別機能")

class PrestigeTier(BaseModel):
    """プレステージティア"""
    tier: int = Field(..., ge=1, description="ティア番号")
    name: str = Field(..., description="ティア名")
    type: PrestigeType
    
    required_level: int = Field(..., ge=50, description="必要レベル")
    required_achievements: int = Field(0, ge=0, description="必要アチーブメント数")
    required_skill_points: int = Field(0, ge=0, description="必要スキルポイント")
    
    benefits: PrestigeBenefit
    reset_progress: bool = Field(True, description="進捗リセット")
    keep_skills: bool = Field(False, description="スキル保持")
    
    # 視覚効果
    icon: Optional[str] = Field(None, description="アイコン")
    color: Optional[int] = Field(None, description="色コード")
    badge: Optional[str] = Field(None, description="バッジ")

class UserPrestige(BaseModel):
    """ユーザーのプレステージ状況"""
    guild_id: int
    user_id: int
    
    current_tier: int = Field(0, ge=0, description="現在ティア")
    current_type: Optional[PrestigeType] = Field(None)
    total_prestiges: int = Field(0, ge=0, description="総プレステージ回数")
    
    # 履歴
    last_prestige_date: Optional[datetime] = Field(None)
    prestige_history: Optional[List[Dict[str, Any]]] = Field(default=None)
    
    # 統計
    total_levels_before_prestige: int = Field(0, ge=0, description="プレステージ前総レベル")
    total_xp_before_prestige: int = Field(0, ge=0, description="プレステージ前総XP")

class GamificationConfig(BaseModel):
    """ゲーミフィケーション設定"""
    guild_id: int
    
    # システム有効化
    achievements_enabled: bool = Field(True)
    skills_enabled: bool = Field(True)
    prestige_enabled: bool = Field(True)
    
    # 通知設定
    achievement_notifications: bool = Field(True)
    skill_unlock_notifications: bool = Field(True)
    prestige_notifications: bool = Field(True)
    
    # カスタム設定
    custom_achievements: Optional[List[Achievement]] = Field(default=None)
    skill_point_base_rate: float = Field(1.0, ge=0.1, le=10.0, description="スキルポイント基本レート")
    achievement_channel_id: Optional[int] = Field(None, description="アチーブメント通知チャンネル")
    
    # メタデータ
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    updated_by: Optional[int] = Field(None)

class GamificationStats(BaseModel):
    """ゲーミフィケーション統計"""
    guild_id: int
    user_id: int
    
    # アチーブメント統計
    total_achievements: int = Field(0, ge=0)
    completed_achievements: int = Field(0, ge=0)
    achievement_completion_rate: float = Field(0.0, ge=0.0, le=100.0)
    
    # スキル統計
    total_skill_points_earned: int = Field(0, ge=0)
    total_skill_points_spent: int = Field(0, ge=0)
    unlocked_skills_count: int = Field(0, ge=0)
    max_skill_tier: int = Field(0, ge=0)
    
    # プレステージ統計  
    prestige_level: int = Field(0, ge=0)
    total_prestiges: int = Field(0, ge=0)
    prestige_xp_bonus: float = Field(0.0, ge=0.0)
    
    # 全体統計
    gamification_score: float = Field(0.0, ge=0.0, description="ゲーミフィケーション総合スコア")
    last_updated: datetime = Field(default_factory=datetime.now)

# プリセット定義
class AchievementPresets:
    """アチーブメントプリセット定義"""
    
    @staticmethod
    def get_level_achievements() -> List[Achievement]:
        """レベル系アチーブメント"""
        achievements = []
        
        # レベル到達アチーブメント
        level_milestones = [
            (5, "初心者卒業", "レベル5に到達", AchievementRarity.COMMON, "🎯"),
            (10, "成長の道", "レベル10に到達", AchievementRarity.COMMON, "📈"),
            (25, "上級者への道", "レベル25に到達", AchievementRarity.UNCOMMON, "⭐"),
            (50, "熟練者", "レベル50に到達", AchievementRarity.RARE, "💎"),
            (75, "エキスパート", "レベル75に到達", AchievementRarity.EPIC, "🏆"),
            (100, "レジェンド", "レベル100に到達", AchievementRarity.LEGENDARY, "👑"),
        ]
        
        for level, name, desc, rarity, icon in level_milestones:
            achievements.append(Achievement(
                id=f"level_{level}",
                name=name,
                description=desc,
                type=AchievementType.LEVEL,
                rarity=rarity,
                condition=AchievementCondition(
                    type=AchievementType.LEVEL,
                    target_value=level
                ),
                xp_reward=level * 100,
                skill_points_reward=max(1, level // 10),
                icon=icon
            ))
        
        return achievements
    
    @staticmethod
    def get_xp_achievements() -> List[Achievement]:
        """XP系アチーブメント"""
        achievements = []
        
        # XP獲得アチーブメント
        xp_milestones = [
            (1000, "千の道のり", "総XP 1,000獲得", AchievementRarity.COMMON, "💫"),
            (10000, "万の実績", "総XP 10,000獲得", AchievementRarity.UNCOMMON, "⚡"),
            (50000, "経験豊富", "総XP 50,000獲得", AchievementRarity.RARE, "🌟"),
            (100000, "百戦練磨", "総XP 100,000獲得", AchievementRarity.EPIC, "✨"),
            (500000, "経験の王者", "総XP 500,000獲得", AchievementRarity.LEGENDARY, "🔥"),
        ]
        
        for xp, name, desc, rarity, icon in xp_milestones:
            achievements.append(Achievement(
                id=f"total_xp_{xp}",
                name=name,
                description=desc,
                type=AchievementType.XP_TOTAL,
                rarity=rarity,
                condition=AchievementCondition(
                    type=AchievementType.XP_TOTAL,
                    target_value=xp
                ),
                xp_reward=xp // 10,
                skill_points_reward=max(1, xp // 25000),
                icon=icon
            ))
        
        return achievements

class SkillTreePresets:
    """スキルツリープリセット定義"""
    
    @staticmethod
    def get_general_skills() -> List[SkillNode]:
        """汎用スキル"""
        return [
            # ティア1: 基本スキル
            SkillNode(
                id="xp_boost_basic",
                name="経験値アップ I",
                description="メッセージXP獲得量を5%増加",
                type=SkillType.XP_BOOST,
                tier=1,
                skill_points_cost=1,
                max_level=5,
                effect_per_level=0.05,
                icon="📚",
                category="基本"
            ),
            
            SkillNode(
                id="voice_boost_basic",
                name="音声経験値アップ I", 
                description="音声XP獲得量を3%増加",
                type=SkillType.VOICE_BOOST,
                tier=1,
                skill_points_cost=1,
                max_level=5,
                effect_per_level=0.03,
                icon="🎤",
                category="音声"
            ),
            
            # ティア2: 中級スキル
            SkillNode(
                id="cooldown_reduce_basic",
                name="クールダウン短縮 I",
                description="XPクールダウンを2秒短縮",
                type=SkillType.COOLDOWN_REDUCE,
                tier=2,
                prerequisites=["xp_boost_basic"],
                skill_points_cost=2,
                max_level=3,
                effect_per_level=2.0,
                icon="⏱️",
                category="効率"
            ),
            
            # ティア3: 上級スキル
            SkillNode(
                id="quality_boost_advanced",
                name="品質分析ボーナス",
                description="AI品質分析ボーナスを10%増加",
                type=SkillType.QUALITY_BOOST,
                tier=3,
                prerequisites=["xp_boost_basic", "cooldown_reduce_basic"],
                skill_points_cost=5,
                max_level=3,
                effect_per_level=0.10,
                icon="🧠",
                category="高度"
            ),
        ]

class PrestigePresets:
    """プレステージプリセット定義"""
    
    @staticmethod
    def get_standard_prestige_tiers() -> List[PrestigeTier]:
        """標準プレステージティア"""
        return [
            PrestigeTier(
                tier=1,
                name="新星",
                type=PrestigeType.STANDARD,
                required_level=100,
                required_achievements=10,
                required_skill_points=50,
                benefits=PrestigeBenefit(
                    xp_multiplier=1.1,
                    skill_point_multiplier=1.2,
                    daily_xp_bonus=500,
                    exclusive_titles=["新星の道"]
                ),
                icon="🌟",
                badge="⭐"
            ),
            
            PrestigeTier(
                tier=2,
                name="熟練者",
                type=PrestigeType.STANDARD,
                required_level=150,
                required_achievements=25,
                required_skill_points=100,
                benefits=PrestigeBenefit(
                    xp_multiplier=1.2,
                    skill_point_multiplier=1.4,
                    daily_xp_bonus=1000,
                    exclusive_titles=["熟練者の証"],
                    achievement_bonus=1.2
                ),
                icon="💎",
                badge="💎"
            ),
            
            PrestigeTier(
                tier=3,
                name="マスター",
                type=PrestigeType.STANDARD,
                required_level=200,
                required_achievements=50,
                required_skill_points=200,
                benefits=PrestigeBenefit(
                    xp_multiplier=1.5,
                    voice_xp_multiplier=1.3,
                    skill_point_multiplier=1.6,
                    daily_xp_bonus=2000,
                    exclusive_titles=["マスターの称号"],
                    achievement_bonus=1.5,
                    special_features={"custom_rank_card": True}
                ),
                icon="👑",
                badge="👑"
            ),
        ]
