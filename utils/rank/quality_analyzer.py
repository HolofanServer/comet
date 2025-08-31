"""
AI品質分析エンジン

GPT-5/GPT-5-miniを活用してメッセージの品質を多次元分析し、
XP倍率を動的に計算するシステム。
"""

import hashlib
import json
import time
from datetime import datetime, timedelta
from typing import Any, Optional

from openai import AsyncOpenAI
from pydantic import ValidationError

from config.setting import get_settings
from models.rank.quality_analysis import (
    AnalysisResult,
    MessageAnalysis,
    MessageCategory,
    QualityAnalysisConfig,
    QualityCache,
    QualityScore,
)
from utils.database import execute_query
from utils.logging import setup_logging

logger = setup_logging("QUALITY_ANALYZER")
settings = get_settings()

class MessageQualityAnalyzer:
    """メッセージ品質のAI分析クラス"""

    def __init__(self):
        """初期化"""
        api_key = settings.etc_api_openai_api_key
        if not api_key:
            logger.warning("OPENAI_API_KEY が設定されていません。品質分析機能は無効になります。")
            self.client = None
        else:
            self.client = AsyncOpenAI(api_key=api_key)

        self.config = QualityAnalysisConfig()
        self.cache: dict[str, QualityCache] = {}

        # システムプロンプト
        self.system_prompt = """あなたはDiscordコミュニティのメッセージ品質を評価するエキスパートです。

メッセージを以下の4つの次元で評価してください：

**1. コンテンツ価値 (content_value):** 0.0-1.0
- 情報の有用性・正確性
- 新しい知見や価値の提供
- 問題解決への貢献

**2. コミュニティ貢献 (community_contrib):** 0.0-1.0
- 他者への助言・サポート
- 建設的な議論への参加
- コミュニティの発展への寄与

**3. 言語品質 (language_quality):** 0.0-1.0
- 文法・表現の適切性
- 礼儀正しさ・敬語の使用
- 読みやすさ・理解しやすさ

**4. エンゲージメント (engagement):** 0.0-1.0
- 議論を促進する内容
- 他者の参加を促す質問
- 興味深いトピックの提起

**カテゴリ分類:**
- question: 質問・疑問
- answer: 回答・解決
- discussion: 議論・意見
- support: サポート・助言
- sharing: 情報共有・報告
- casual: 日常会話
- spam: スパム・低品質
- other: その他

**XP倍率計算:**
- 品質スコアに基づいて0.1-3.0倍の範囲で設定
- 高品質コンテンツ（0.8以上）にはボーナス
- スパムや低品質は大幅減額

日本語のコミュニティ文脈を考慮して評価してください。"""

    async def analyze_message_quality(
        self,
        content: str,
        channel_name: Optional[str] = None,
        guild_context: Optional[str] = None
    ) -> AnalysisResult:
        """
        メッセージ品質をAI分析

        Args:
            content: メッセージ内容
            channel_name: チャンネル名（コンテキスト用）
            guild_context: サーバーのコンテキスト情報

        Returns:
            AnalysisResult: 分析結果
        """
        if not self.client:
            return AnalysisResult(
                success=False,
                error_message="OpenAI APIが設定されていません。",
                fallback_used=True
            )

        start_time = time.time()

        # 長さチェック
        if len(content) < self.config.min_length_for_analysis:
            return self._create_default_result(content, "too_short")

        if len(content) > self.config.max_length_for_analysis:
            content = content[:self.config.max_length_for_analysis] + "..."

        # キャッシュチェック
        cache_key = self._get_cache_key(content)
        cached = await self._get_from_cache(cache_key)
        if cached:
            logger.debug(f"品質分析キャッシュヒット: {cache_key[:8]}")
            return AnalysisResult(
                success=True,
                analysis=cached.analysis,
                total_processing_time_ms=int((time.time() - start_time) * 1000)
            )

        try:
            # プライマリモデルで分析
            result = await self._analyze_with_model(
                content, self.config.primary_model, channel_name, guild_context
            )

            if not result.success or (result.analysis and result.analysis.confidence < self.config.confidence_threshold):
                logger.info(f"フォールバックモデルで再分析: confidence={result.analysis.confidence if result.analysis else 0}")
                fallback_result = await self._analyze_with_model(
                    content, self.config.fallback_model, channel_name, guild_context
                )
                if fallback_result.success:
                    fallback_result.fallback_used = True
                    result = fallback_result

            # キャッシュに保存
            if result.success and result.analysis:
                await self._save_to_cache(cache_key, result.analysis)

            # 処理時間記録
            result.total_processing_time_ms = int((time.time() - start_time) * 1000)

            return result

        except Exception as e:
            logger.error(f"品質分析エラー: {e}")
            return AnalysisResult(
                success=False,
                error_message=f"分析中にエラーが発生しました: {str(e)}",
                total_processing_time_ms=int((time.time() - start_time) * 1000)
            )

    async def _analyze_with_model(
        self,
        content: str,
        model: str,
        channel_name: Optional[str] = None,
        guild_context: Optional[str] = None
    ) -> AnalysisResult:
        """指定されたモデルで分析を実行"""

        try:
            # プロンプト構築
            user_prompt = self._build_analysis_prompt(content, channel_name, guild_context)

            # OpenAI API呼び出し
            response = await self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=1.0,  # gpt-5/miniモデルはtemperature=1のみサポート
                max_completion_tokens=1500
            )

            content_response = response.choices[0].message.content
            logger.debug(f"AI品質分析応答 ({model}): {content_response[:100]}...")

            # JSON解析
            analysis_data = json.loads(content_response)

            # Pydantic検証・構造化
            analysis = self._parse_analysis_response(analysis_data, content, model)

            return AnalysisResult(
                success=True,
                analysis=analysis,
                tokens_used=response.usage.total_tokens if response.usage else 0
            )

        except json.JSONDecodeError as e:
            logger.error(f"JSON解析エラー ({model}): {e}")
            return AnalysisResult(
                success=False,
                error_message=f"AI応答の解析に失敗しました ({model})"
            )

        except ValidationError as e:
            logger.error(f"Pydantic検証エラー ({model}): {e}")
            return AnalysisResult(
                success=False,
                error_message=f"分析結果の構造検証に失敗しました ({model})"
            )

        except Exception as e:
            logger.error(f"モデル分析エラー ({model}): {e}")
            return AnalysisResult(
                success=False,
                error_message=f"分析実行エラー ({model}): {str(e)}"
            )

    def _build_analysis_prompt(
        self,
        content: str,
        channel_name: Optional[str],
        guild_context: Optional[str]
    ) -> str:
        """分析用プロンプトを構築"""

        prompt = "以下のDiscordメッセージを品質分析してください:\n\n"
        prompt += f"**メッセージ:**\n{content}\n\n"

        if channel_name:
            prompt += f"**チャンネル:** #{channel_name}\n"

        if guild_context:
            prompt += f"**サーバー情報:** {guild_context}\n"

        prompt += """
**出力形式（JSON）:**
```json
{
  "category": "question|answer|discussion|support|sharing|casual|spam|other",
  "confidence": 0.85,
  "quality_scores": {
    "content_value": 0.7,
    "community_contrib": 0.6,
    "language_quality": 0.9,
    "engagement": 0.5
  },
  "ai_reasoning": "このメッセージの評価理由...",
  "key_phrases": ["重要語句1", "重要語句2"],
  "sentiment": "positive|neutral|negative",
  "xp_multiplier": 1.3,
  "bonus_reason": "高品質な技術解説"
}
```

必ずJSON形式で出力してください。"""

        return prompt

    def _parse_analysis_response(
        self,
        data: dict[str, Any],
        original_content: str,
        model: str
    ) -> MessageAnalysis:
        """AI応答をMessageAnalysisオブジェクトに変換"""

        # デフォルト値設定
        category = MessageCategory(data.get("category", "other"))
        confidence = max(0.0, min(1.0, data.get("confidence", 0.5)))

        # 品質スコア構築
        quality_data = data.get("quality_scores", {})
        quality_scores = QualityScore(
            content_value=max(0.0, min(1.0, quality_data.get("content_value", 0.5))),
            community_contrib=max(0.0, min(1.0, quality_data.get("community_contrib", 0.5))),
            language_quality=max(0.0, min(1.0, quality_data.get("language_quality", 0.7))),
            engagement=max(0.0, min(1.0, quality_data.get("engagement", 0.5)))
        )

        # XP倍率計算（品質とカテゴリに基づく）
        base_multiplier = self.config.category_multipliers.get(category, 1.0)
        quality_bonus = quality_scores.overall * 0.5  # 最大+50%

        xp_multiplier = data.get("xp_multiplier")
        if xp_multiplier is None:
            xp_multiplier = base_multiplier + quality_bonus

        # 高品質ボーナス
        bonus_reason = data.get("bonus_reason")
        if quality_scores.overall >= self.config.high_quality_threshold:
            xp_multiplier += self.config.high_quality_bonus
            if not bonus_reason:
                bonus_reason = "高品質コンテンツボーナス"

        # 上下限調整
        xp_multiplier = max(0.1, min(3.0, xp_multiplier))

        return MessageAnalysis(
            message_content=original_content,
            message_length=len(original_content),
            category=category,
            confidence=confidence,
            quality_scores=quality_scores,
            ai_reasoning=data.get("ai_reasoning", "分析理由が提供されませんでした"),
            key_phrases=data.get("key_phrases", []),
            sentiment=data.get("sentiment"),
            xp_multiplier=xp_multiplier,
            bonus_reason=bonus_reason,
            analysis_model=model
        )

    def _create_default_result(self, content: str, reason: str) -> AnalysisResult:
        """デフォルト分析結果を作成"""

        default_scores = QualityScore(
            content_value=0.5,
            community_contrib=0.5,
            language_quality=0.7,
            engagement=0.5
        )

        analysis = MessageAnalysis(
            message_content=content,
            message_length=len(content),
            category=MessageCategory.CASUAL,
            confidence=1.0,
            quality_scores=default_scores,
            ai_reasoning=f"デフォルト分析（理由: {reason}）",
            xp_multiplier=1.0,
            analysis_model="default"
        )

        return AnalysisResult(success=True, analysis=analysis)

    def _get_cache_key(self, content: str) -> str:
        """キャッシュキーを生成"""
        return hashlib.md5(content.encode('utf-8')).hexdigest()

    async def _get_from_cache(self, cache_key: str) -> Optional[QualityCache]:
        """キャッシュから結果を取得"""
        if not self.config.enable_cache:
            return None

        try:
            query = "SELECT analysis_data, cache_time FROM quality_cache WHERE message_hash = $1"
            result = await execute_query(query, cache_key)

            if result and len(result) > 0:
                cache_data = result[0]
                cache_time = cache_data["cache_time"]

                # TTLチェック
                if datetime.now() - cache_time < timedelta(seconds=self.config.cache_ttl_seconds):
                    analysis_data = json.loads(cache_data["analysis_data"])
                    analysis = MessageAnalysis.model_validate(analysis_data)

                    return QualityCache(
                        message_hash=cache_key,
                        analysis=analysis,
                        cache_time=cache_time
                    )
                else:
                    # 期限切れキャッシュを削除
                    await execute_query("DELETE FROM quality_cache WHERE message_hash = $1", cache_key)

        except Exception as e:
            logger.warning(f"キャッシュ読み込みエラー: {e}")

        return None

    async def _save_to_cache(self, cache_key: str, analysis: MessageAnalysis):
        """キャッシュに結果を保存"""
        if not self.config.enable_cache:
            return

        try:
            analysis_json = analysis.model_dump_json()

            query = """
            INSERT INTO quality_cache (message_hash, analysis_data, cache_time)
            VALUES ($1, $2, NOW())
            ON CONFLICT (message_hash)
            DO UPDATE SET analysis_data = EXCLUDED.analysis_data, cache_time = NOW()
            """

            await execute_query(query, cache_key, analysis_json)

        except Exception as e:
            logger.warning(f"キャッシュ保存エラー: {e}")

# モジュールレベルのインスタンス
quality_analyzer = MessageQualityAnalyzer()

async def analyze_message_quality(
    content: str,
    channel_name: Optional[str] = None,
    guild_context: Optional[str] = None
) -> AnalysisResult:
    """
    便利関数：メッセージ品質を分析

    Args:
        content: メッセージ内容
        channel_name: チャンネル名
        guild_context: サーバーコンテキスト

    Returns:
        AnalysisResult: 分析結果
    """
    return await quality_analyzer.analyze_message_quality(content, channel_name, guild_context)
