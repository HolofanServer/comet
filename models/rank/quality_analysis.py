"""
メッセージ品質分析用Pydanticモデル

AI（GPT-5/GPT-5-mini）による多次元メッセージ品質評価の
構造化データモデル。
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, validator


class QualityDimension(str, Enum):
    """品質評価の次元"""
    CONTENT_VALUE = "content_value"        # コンテンツ価値
    COMMUNITY_CONTRIB = "community_contrib"  # コミュニティ貢献
    LANGUAGE_QUALITY = "language_quality"    # 言語品質
    ENGAGEMENT = "engagement"               # エンゲージメント促進

class MessageCategory(str, Enum):
    """メッセージカテゴリ"""
    QUESTION = "question"           # 質問
    ANSWER = "answer"              # 回答・解決
    DISCUSSION = "discussion"       # 議論・意見
    SUPPORT = "support"            # サポート・助言
    SHARING = "sharing"            # 情報共有・報告
    CASUAL = "casual"              # 日常会話
    SPAM = "spam"                  # スパム・低品質
    OTHER = "other"                # その他

class QualityScore(BaseModel):
    """品質スコア（0.0-1.0）"""
    content_value: float = Field(
        ge=0.0, le=1.0,
        description="コンテンツの情報価値・有用性"
    )
    community_contrib: float = Field(
        ge=0.0, le=1.0,
        description="コミュニティへの貢献度"
    )
    language_quality: float = Field(
        ge=0.0, le=1.0,
        description="言語の品質・適切性"
    )
    engagement: float = Field(
        ge=0.0, le=1.0,
        description="議論・交流の促進度"
    )

    @property
    def overall(self) -> float:
        """総合品質スコア"""
        return (
            self.content_value * 0.3 +
            self.community_contrib * 0.3 +
            self.language_quality * 0.2 +
            self.engagement * 0.2
        )

class MessageAnalysis(BaseModel):
    """メッセージ分析結果"""

    # 基本情報
    message_content: str = Field(description="分析対象メッセージ")
    message_length: int = Field(description="メッセージ長")

    # 分類結果
    category: MessageCategory = Field(description="メッセージカテゴリ")
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="分類の信頼度"
    )

    # 品質評価
    quality_scores: QualityScore = Field(description="多次元品質スコア")

    # AI分析結果
    ai_reasoning: str = Field(description="AI分析の根拠・理由")
    key_phrases: list[str] = Field(
        default_factory=list,
        description="重要なキーフレーズ"
    )
    sentiment: Optional[str] = Field(
        default=None,
        description="感情分析結果（positive/neutral/negative）"
    )

    # XP計算関連
    xp_multiplier: float = Field(
        ge=0.0, le=5.0,
        description="品質に基づくXP倍率"
    )
    bonus_reason: Optional[str] = Field(
        default=None,
        description="ボーナス付与理由"
    )

    # メタ情報
    analysis_model: str = Field(description="使用したAIモデル")
    analysis_time: datetime = Field(default_factory=datetime.now)
    processing_time_ms: Optional[int] = Field(default=None)

    @validator('xp_multiplier')
    def validate_xp_multiplier(cls, v, values):
        # 品質スコアに基づいて適切な倍率かチェック
        if 'quality_scores' in values:
            overall_score = values['quality_scores'].overall
            if v > (1.0 + overall_score * 2.0):  # 最大3倍まで
                raise ValueError('XP倍率が品質スコアに対して過大です')
        return v

class QualityAnalysisConfig(BaseModel):
    """品質分析の設定"""

    # モデル選択
    primary_model: str = Field(default="gpt-5-mini")
    fallback_model: str = Field(default="gpt-5")

    # 分析閾値
    min_length_for_analysis: int = Field(default=10, description="分析対象最小文字数")
    max_length_for_analysis: int = Field(default=2000, description="分析対象最大文字数")

    # フォールバック条件
    confidence_threshold: float = Field(
        default=0.7,
        ge=0.0, le=1.0,
        description="低信頼度でのフォールバック閾値"
    )

    # キャッシュ設定
    enable_cache: bool = Field(default=True)
    cache_ttl_seconds: int = Field(default=3600)  # 1時間

    # XP倍率設定
    category_multipliers: dict[MessageCategory, float] = Field(
        default_factory=lambda: {
            MessageCategory.ANSWER: 1.8,
            MessageCategory.SUPPORT: 1.6,
            MessageCategory.SHARING: 1.4,
            MessageCategory.DISCUSSION: 1.3,
            MessageCategory.QUESTION: 1.2,
            MessageCategory.CASUAL: 1.0,
            MessageCategory.SPAM: 0.1,
            MessageCategory.OTHER: 1.0
        }
    )

    # 品質ボーナス
    high_quality_threshold: float = Field(default=0.8, description="高品質判定閾値")
    high_quality_bonus: float = Field(default=0.5, description="高品質ボーナス倍率")

class AnalysisResult(BaseModel):
    """分析結果の統合レスポンス"""
    success: bool = Field(description="分析成功フラグ")
    analysis: Optional[MessageAnalysis] = Field(default=None)
    error_message: Optional[str] = Field(default=None)
    fallback_used: bool = Field(default=False, description="フォールバックモデル使用")

    # パフォーマンス指標
    total_processing_time_ms: int = Field(default=0)
    tokens_used: int = Field(default=0)
    cost_estimate: Optional[float] = Field(default=None, description="推定コスト（USD）")

class QualityCache(BaseModel):
    """品質分析結果のキャッシュ"""
    message_hash: str = Field(description="メッセージのハッシュ値")
    analysis: MessageAnalysis = Field(description="分析結果")
    cache_time: datetime = Field(default_factory=datetime.now)
    hit_count: int = Field(default=1, description="キャッシュヒット回数")
