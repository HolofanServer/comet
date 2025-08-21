"""
OpenAI API統合による自然言語→設定JSON変換ユーティリティ

GPT-5/GPT-5-miniとStructured Outputsを活用して、
自然言語の設定指示を厳密なJSON構造に変換する。
"""

import json
from typing import Optional, Dict, Any
from openai import AsyncOpenAI
from pydantic import ValidationError

from models.rank.level_config import LevelConfig, ConfigParseResult
from utils.logging import setup_logging
from config.setting import get_settings

logger = setup_logging("AI_CONFIG")
settings = get_settings()

class AIConfigParser:
    """OpenAI APIを使用した自然言語設定解析クラス"""
    
    def __init__(self):
        """初期化 - APIキーの設定"""
        api_key = settings.etc_api_openai_api_key
        if not api_key:
            logger.warning("OPENAI_API_KEY が設定されていません。AI設定機能は無効になります。")
            self.client = None
        else:
            self.client = AsyncOpenAI(api_key=api_key)
        
        # システムプロンプト
        self.system_prompt = """あなたはDiscordレベリングシステムの設定を管理するエキスパートです。

ユーザーの自然言語による設定指示を、LevelConfig JSONスキーマに正確に変換してください。

**重要な変換ルール:**
1. 曜日の日本語対応：
   - "平日" → "weekday"
   - "週末" → "weekend" 
   - "月曜" → "monday"
   - "火曜" → "tuesday"
   - etc.

2. 時刻表記の正規化：
   - "20時" → "20:00"
   - "午後8時" → "20:00"
   - "8pm" → "20:00"

3. チャンネル指定：
   - "#qa" → channel_name: "qa"
   - "全般チャンネル" → channel_name: "全般"

4. 倍率の解釈：
   - "2倍" → multiplier: 2.0
   - "半分" → multiplier: 0.5
   - "無効" → multiplier: 0.0

5. 安全性の原則：
   - 不明確な場合は保守的な値を使用
   - 極端な値（10倍以上等）は制限内に収める
   - 必須でない項目は省略

**出力形式:** 必ずJSON形式で、LevelConfigスキーマに従って出力してください。"""

    async def parse_natural_language(
        self, 
        natural_input: str,
        use_gpt5: bool = True,
        context: Optional[Dict[str, Any]] = None
    ) -> ConfigParseResult:
        """
        自然言語をLevelConfig JSONに変換
        
        Args:
            natural_input: 自然言語の設定指示
            use_gpt5: True=GPT-5使用、False=GPT-5-mini使用
            context: 追加コンテキスト（チャンネル情報など）
        
        Returns:
            ConfigParseResult: 解析結果
        """
        if not self.client:
            return ConfigParseResult(
                success=False,
                error_message="OpenAI APIが設定されていません。",
                original_input=natural_input,
                confidence=0.0
            )
        
        try:
            # モデル選択
            model = "gpt-5" if use_gpt5 else "gpt-5-mini"
            
            # プロンプト構築
            user_prompt = self._build_user_prompt(natural_input, context)
            
            # OpenAI API呼び出し
            response = await self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},  # Structured Outputs
                temperature=1.0,  # gpt-5/miniモデルはtemperature=1のみサポート
                max_completion_tokens=4000
            )
            
            # レスポンス解析
            content = response.choices[0].message.content
            logger.info(f"AI応答: {content[:200]}...")
            
            # JSON解析
            config_dict = json.loads(content)
            
            # Pydantic検証
            level_config = LevelConfig.model_validate(config_dict)
            
            # 成功
            return ConfigParseResult(
                success=True,
                config=level_config,
                confidence=0.9,  # GPTの出力は一般的に高信頼度
                original_input=natural_input
            )
            
        except ValidationError as e:
            logger.error(f"Pydantic検証エラー: {e}")
            return ConfigParseResult(
                success=False,
                error_message=f"設定の検証に失敗しました: {str(e)}",
                original_input=natural_input,
                confidence=0.0
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析エラー: {e}")
            # GPT-5-miniでリトライ
            if use_gpt5:
                logger.info("GPT-5-miniでリトライします...")
                return await self.parse_natural_language(
                    natural_input, 
                    use_gpt5=False, 
                    context=context
                )
            
            return ConfigParseResult(
                success=False,
                error_message="AIの応答を解析できませんでした。",
                original_input=natural_input,
                confidence=0.0
            )
            
        except Exception as e:
            logger.error(f"予期しないエラー: {e}")
            return ConfigParseResult(
                success=False,
                error_message=f"処理中にエラーが発生しました: {str(e)}",
                original_input=natural_input,
                confidence=0.0
            )

    def _build_user_prompt(
        self, 
        natural_input: str, 
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """ユーザープロンプトの構築"""
        
        prompt = f"以下の自然言語設定をLevelConfig JSONに変換してください:\n\n{natural_input}\n\n"
        
        # コンテキスト情報の追加
        if context:
            prompt += "**利用可能な情報:**\n"
            
            if "channels" in context:
                channels = context["channels"]
                prompt += f"サーバーのチャンネル: {', '.join(channels)}\n"
            
            if "roles" in context:
                roles = context["roles"]
                prompt += f"サーバーのロール: {', '.join(roles)}\n"
            
            prompt += "\n"
        
        prompt += """**出力要件:**
- 必ずLevelConfigスキーマに準拠したJSONで出力
- 不明確な場合は安全な初期値を使用  
- 日本語の曜日・時刻表記を正確に変換
- チャンネル名やロール名は正確にマッピング

JSON:"""
        
        return prompt

    async def explain_config(self, config: LevelConfig) -> str:
        """
        設定内容を日本語で説明
        
        Args:
            config: 設定オブジェクト
            
        Returns:
            str: 日本語説明文
        """
        if not self.client:
            return "AI説明機能が利用できません。"
        
        try:
            config_json = config.model_dump_json(indent=2, ensure_ascii=False)
            
            prompt = f"""以下のDiscordレベリングシステム設定を、ユーザーフレンドリーな日本語で説明してください:

{config_json}

**説明要件:**
- 簡潔で分かりやすい日本語
- 設定の要点を整理して表示
- 特別な倍率や時間帯設定がある場合は強調
- 箇条書きやセクション分けで読みやすく

説明:"""

            response = await self.client.chat.completions.create(
                model="gpt-5-mini",  # 説明はminiで十分
                messages=[{"role": "user", "content": prompt}],
                temperature=1.0,  # gpt-5/miniモデルはtemperature=1のみサポート
                max_completion_tokens=1000
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"設定説明生成エラー: {e}")
            return "設定の説明生成に失敗しました。"

# モジュールレベルのインスタンス
ai_parser = AIConfigParser()

async def parse_config_natural_language(
    natural_input: str,
    context: Optional[Dict[str, Any]] = None
) -> ConfigParseResult:
    """
    便利関数：自然言語設定を解析
    
    Args:
        natural_input: 自然言語入力
        context: コンテキスト情報
        
    Returns:
        ConfigParseResult: 解析結果
    """
    return await ai_parser.parse_natural_language(natural_input, context=context)

async def explain_config_japanese(config: LevelConfig) -> str:
    """
    便利関数：設定を日本語で説明
    
    Args:
        config: 設定オブジェクト
        
    Returns:
        str: 日本語説明
    """
    return await ai_parser.explain_config(config)
