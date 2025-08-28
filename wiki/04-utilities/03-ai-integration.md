# AI統合

## C.O.M.E.T.について

**C.O.M.E.T.**の名前は以下の頭文字から構成されています：

- **C**ommunity of
- **O**shilove
- **M**oderation &
- **E**njoyment
- **T**ogether

HFS - ホロライブ非公式ファンサーバーのコミュニティを支える、推し愛とモデレーション、そして楽しさを一緒に提供するボットです。

## 概要

C.O.M.E.T.ボットのAI統合機能について説明します。OpenAI APIを使用したテキスト生成、画像解析、自動応答システムなどの実装について詳しく解説します。

## OpenAI統合

### 基本設定

```python
import openai
import asyncio
from typing import Optional, Dict, Any

class OpenAIIntegration:
    def __init__(self, api_key: str):
        self.client = openai.AsyncOpenAI(api_key=api_key)
        self.model = "gpt-3.5-turbo"
        self.max_tokens = 1000
    
    async def generate_text(self, prompt: str, **kwargs) -> str:
        """テキスト生成"""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=self.max_tokens,
                **kwargs
            )
            return response.choices[0].message.content
        except Exception as e:
            raise AIIntegrationError(f"テキスト生成エラー: {e}")
```

### チャット機能

```python
class ChatBot:
    def __init__(self, openai_client: OpenAIIntegration):
        self.ai = openai_client
        self.conversation_history = {}
    
    async def chat_response(self, user_id: int, message: str) -> str:
        """チャット応答生成"""
        # 会話履歴の取得
        history = self.conversation_history.get(user_id, [])
        
        # システムプロンプト
        system_prompt = """
        あなたはHolofanServerのC.O.M.E.T.ボットです。
        ホロライブファンコミュニティの一員として、親しみやすく、
        役立つ情報を提供してください。
        """
        
        # メッセージ構築
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": message})
        
        try:
            response = await self.ai.client.chat.completions.create(
                model=self.ai.model,
                messages=messages,
                max_tokens=500,
                temperature=0.7
            )
            
            ai_response = response.choices[0].message.content
            
            # 会話履歴更新
            self.update_conversation_history(user_id, message, ai_response)
            
            return ai_response
        except Exception as e:
            return f"申し訳ありません。エラーが発生しました: {e}"
    
    def update_conversation_history(self, user_id: int, user_message: str, ai_response: str):
        """会話履歴更新"""
        if user_id not in self.conversation_history:
            self.conversation_history[user_id] = []
        
        history = self.conversation_history[user_id]
        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": ai_response})
        
        # 履歴制限（最新10件）
        if len(history) > 20:
            self.conversation_history[user_id] = history[-20:]
```

## 画像解析

### 画像認識

```python
import base64
import aiohttp
from io import BytesIO

class ImageAnalyzer:
    def __init__(self, openai_client: OpenAIIntegration):
        self.ai = openai_client
    
    async def analyze_image(self, image_url: str, prompt: str = "この画像について説明してください") -> str:
        """画像解析"""
        try:
            response = await self.ai.client.chat.completions.create(
                model="gpt-4-vision-preview",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": image_url}}
                        ]
                    }
                ],
                max_tokens=300
            )
            return response.choices[0].message.content
        except Exception as e:
            raise AIIntegrationError(f"画像解析エラー: {e}")
    
    async def analyze_attachment(self, attachment_data: bytes, prompt: str) -> str:
        """添付ファイル解析"""
        # Base64エンコード
        base64_image = base64.b64encode(attachment_data).decode('utf-8')
        image_url = f"data:image/jpeg;base64,{base64_image}"
        
        return await self.analyze_image(image_url, prompt)
```

## 自動モデレーション

### コンテンツフィルタリング

```python
class ContentModerator:
    def __init__(self, openai_client: OpenAIIntegration):
        self.ai = openai_client
    
    async def check_content(self, text: str) -> Dict[str, Any]:
        """コンテンツチェック"""
        prompt = f"""
        以下のテキストを分析し、以下の観点で評価してください：
        1. 不適切な言語の使用
        2. ハラスメントや攻撃的な内容
        3. スパムの可能性
        4. ホロライブコミュニティに適さない内容
        
        テキスト: "{text}"
        
        JSON形式で回答してください：
        {{
            "is_appropriate": true/false,
            "confidence": 0.0-1.0,
            "reason": "理由",
            "suggested_action": "推奨アクション"
        }}
        """
        
        try:
            response = await self.ai.generate_text(prompt)
            import json
            return json.loads(response)
        except Exception as e:
            return {
                "is_appropriate": True,
                "confidence": 0.0,
                "reason": f"分析エラー: {e}",
                "suggested_action": "manual_review"
            }
```

## 翻訳機能

### 多言語対応

```python
class Translator:
    def __init__(self, openai_client: OpenAIIntegration):
        self.ai = openai_client
        self.supported_languages = {
            'ja': '日本語',
            'en': '英語',
            'ko': '韓国語',
            'zh': '中国語'
        }
    
    async def translate(self, text: str, target_language: str) -> str:
        """翻訳"""
        if target_language not in self.supported_languages:
            raise ValueError(f"サポートされていない言語: {target_language}")
        
        target_lang_name = self.supported_languages[target_language]
        prompt = f"""
        以下のテキストを{target_lang_name}に翻訳してください。
        自然で読みやすい翻訳を心がけてください。
        
        テキスト: "{text}"
        """
        
        return await self.ai.generate_text(prompt)
    
    async def detect_language(self, text: str) -> str:
        """言語検出"""
        prompt = f"""
        以下のテキストの言語を検出してください。
        言語コード（ja, en, ko, zh）のみを回答してください。
        
        テキスト: "{text}"
        """
        
        response = await self.ai.generate_text(prompt)
        return response.strip().lower()
```

## エラーハンドリング

### カスタム例外

```python
class AIIntegrationError(Exception):
    """AI統合関連のエラー"""
    pass

class RateLimitError(AIIntegrationError):
    """レート制限エラー"""
    pass

class APIKeyError(AIIntegrationError):
    """APIキーエラー"""
    pass
```

### レート制限対応

```python
import asyncio
from datetime import datetime, timedelta

class RateLimiter:
    def __init__(self, max_requests: int = 60, time_window: int = 60):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = []
    
    async def acquire(self):
        """レート制限チェック"""
        now = datetime.now()
        
        # 古いリクエストを削除
        self.requests = [req_time for req_time in self.requests 
                        if now - req_time < timedelta(seconds=self.time_window)]
        
        if len(self.requests) >= self.max_requests:
            wait_time = self.time_window - (now - self.requests[0]).total_seconds()
            await asyncio.sleep(wait_time)
            return await self.acquire()
        
        self.requests.append(now)
        return True
```

## 設定管理

### 環境変数

```python
import os
from typing import Optional

class AIConfig:
    def __init__(self):
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        self.model = os.getenv('OPENAI_MODEL', 'gpt-3.5-turbo')
        self.max_tokens = int(os.getenv('OPENAI_MAX_TOKENS', '1000'))
        self.temperature = float(os.getenv('OPENAI_TEMPERATURE', '0.7'))
        
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY環境変数が設定されていません")
    
    def validate(self) -> bool:
        """設定検証"""
        return all([
            self.openai_api_key,
            0 <= self.temperature <= 2,
            self.max_tokens > 0
        ])
```

## 関連ドキュメント

- [API統合](02-api-integration.md)
- [エラーハンドリング](../02-core/04-error-handling.md)
- [設定管理](../01-architecture/04-configuration-management.md)
- [ツールCogs](../03-cogs/05-tool-cogs.md)
