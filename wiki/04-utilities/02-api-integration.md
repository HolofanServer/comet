# API統合

## C.O.M.E.T.について

**C.O.M.E.T.**の名前は以下の頭文字から構成されています：

- **C**ommunity of
- **O**shilove
- **M**oderation &
- **E**njoyment
- **T**ogether

HFS - ホロライブ非公式ファンサーバーのコミュニティを支える、推し愛とモデレーション、そして楽しさを一緒に提供するボットです。

## 概要

COMETボットのAPI統合システムは、外部サービスとの連携を効率的に管理し、データの取得、送信、同期を行います。RESTful API、WebSocket、RSS フィード、Webhook統合を含む包括的なAPI管理機能を提供します。

## API統合アーキテクチャ

```
┌─────────────────────────────────────────────────────────────┐
│                    API統合アーキテクチャ                     │
├─────────────────────────────────────────────────────────────┤
│  API管理層 (API Management)                                 │
│  ├── APIクライアント管理                                     │
│  ├── 認証・認可                                              │
│  ├── レート制限管理                                          │
│  └── エラーハンドリング                                      │
├─────────────────────────────────────────────────────────────┤
│  プロトコル層 (Protocol Layer)                              │
│  ├── HTTP/HTTPS クライアント                                │
│  ├── WebSocket クライアント                                 │
│  ├── RSS/Atom フィードリーダー                              │
│  └── Webhook サーバー                                       │
├─────────────────────────────────────────────────────────────┤
│  データ処理層 (Data Processing)                             │
│  ├── レスポンス解析                                          │
│  ├── データ変換                                              │
│  ├── キャッシュ管理                                          │
│  └── データ検証                                              │
├─────────────────────────────────────────────────────────────┤
│  外部サービス (External Services)                           │
│  ├── Discord API                                            │
│  ├── note.com API                                           │
│  ├── UptimeKuma API                                         │
│  ├── OpenAI API                                             │
│  └── その他のサードパーティAPI                              │
└─────────────────────────────────────────────────────────────┘
```

## HTTPクライアント管理

### 1. 基本HTTPクライアント

```python
import aiohttp
import asyncio
import json
from typing import Dict, Any, Optional, Union
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class HTTPClient:
    def __init__(self, base_url: str = None, timeout: int = 30):
        self.base_url = base_url
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.session: Optional[aiohttp.ClientSession] = None
        self.headers = {
            'User-Agent': 'COMET-Bot/2.1.0',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
    
    async def __aenter__(self):
        await self.create_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close_session()
    
    async def create_session(self):
        """HTTPセッションの作成"""
        if not self.session or self.session.closed:
            connector = aiohttp.TCPConnector(
                limit=100,
                limit_per_host=30,
                ttl_dns_cache=300,
                use_dns_cache=True
            )
            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=self.timeout,
                headers=self.headers
            )
    
    async def close_session(self):
        """HTTPセッションのクローズ"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    def _build_url(self, endpoint: str) -> str:
        """URLの構築"""
        if self.base_url:
            return f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        return endpoint
    
    async def get(self, endpoint: str, params: Dict[str, Any] = None, headers: Dict[str, str] = None) -> Dict[str, Any]:
        """GET リクエスト"""
        url = self._build_url(endpoint)
        request_headers = {**self.headers}
        if headers:
            request_headers.update(headers)
        
        try:
            async with self.session.get(url, params=params, headers=request_headers) as response:
                await self._check_response_status(response)
                return await self._parse_response(response)
        except Exception as e:
            logger.error(f"GET request failed: {url} - {e}")
            raise
    
    async def post(self, endpoint: str, data: Dict[str, Any] = None, headers: Dict[str, str] = None) -> Dict[str, Any]:
        """POST リクエスト"""
        url = self._build_url(endpoint)
        request_headers = {**self.headers}
        if headers:
            request_headers.update(headers)
        
        try:
            json_data = json.dumps(data) if data else None
            async with self.session.post(url, data=json_data, headers=request_headers) as response:
                await self._check_response_status(response)
                return await self._parse_response(response)
        except Exception as e:
            logger.error(f"POST request failed: {url} - {e}")
            raise
    
    async def put(self, endpoint: str, data: Dict[str, Any] = None, headers: Dict[str, str] = None) -> Dict[str, Any]:
        """PUT リクエスト"""
        url = self._build_url(endpoint)
        request_headers = {**self.headers}
        if headers:
            request_headers.update(headers)
        
        try:
            json_data = json.dumps(data) if data else None
            async with self.session.put(url, data=json_data, headers=request_headers) as response:
                await self._check_response_status(response)
                return await self._parse_response(response)
        except Exception as e:
            logger.error(f"PUT request failed: {url} - {e}")
            raise
    
    async def delete(self, endpoint: str, headers: Dict[str, str] = None) -> Dict[str, Any]:
        """DELETE リクエスト"""
        url = self._build_url(endpoint)
        request_headers = {**self.headers}
        if headers:
            request_headers.update(headers)
        
        try:
            async with self.session.delete(url, headers=request_headers) as response:
                await self._check_response_status(response)
                return await self._parse_response(response)
        except Exception as e:
            logger.error(f"DELETE request failed: {url} - {e}")
            raise
    
    async def _check_response_status(self, response: aiohttp.ClientResponse):
        """レスポンスステータスのチェック"""
        if response.status >= 400:
            error_text = await response.text()
            raise aiohttp.ClientResponseError(
                request_info=response.request_info,
                history=response.history,
                status=response.status,
                message=f"HTTP {response.status}: {error_text}"
            )
    
    async def _parse_response(self, response: aiohttp.ClientResponse) -> Dict[str, Any]:
        """レスポンスの解析"""
        content_type = response.headers.get('Content-Type', '')
        
        if 'application/json' in content_type:
            return await response.json()
        elif 'text/' in content_type:
            text = await response.text()
            return {"text": text}
        else:
            data = await response.read()
            return {"data": data}
```

### 2. 認証付きAPIクライアント

```python
class AuthenticatedAPIClient(HTTPClient):
    def __init__(self, base_url: str, api_key: str = None, token: str = None, timeout: int = 30):
        super().__init__(base_url, timeout)
        self.api_key = api_key
        self.token = token
        self.refresh_token = None
        self.token_expires_at = None
        
        # 認証ヘッダーの設定
        if self.api_key:
            self.headers['X-API-Key'] = self.api_key
        elif self.token:
            self.headers['Authorization'] = f'Bearer {self.token}'
    
    async def refresh_access_token(self):
        """アクセストークンの更新"""
        if not self.refresh_token:
            raise ValueError("Refresh token not available")
        
        try:
            data = {
                'grant_type': 'refresh_token',
                'refresh_token': self.refresh_token
            }
            
            response = await self.post('/auth/refresh', data=data)
            
            self.token = response['access_token']
            self.refresh_token = response.get('refresh_token', self.refresh_token)
            
            # トークンの有効期限を設定
            expires_in = response.get('expires_in', 3600)
            self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)
            
            # ヘッダーの更新
            self.headers['Authorization'] = f'Bearer {self.token}'
            
            logger.info("Access token refreshed successfully")
            
        except Exception as e:
            logger.error(f"Failed to refresh access token: {e}")
            raise
    
    async def _check_token_expiry(self):
        """トークンの有効期限チェック"""
        if self.token_expires_at and datetime.now() >= self.token_expires_at:
            await self.refresh_access_token()
    
    async def get(self, endpoint: str, params: Dict[str, Any] = None, headers: Dict[str, str] = None) -> Dict[str, Any]:
        """認証付きGETリクエスト"""
        await self._check_token_expiry()
        return await super().get(endpoint, params, headers)
    
    async def post(self, endpoint: str, data: Dict[str, Any] = None, headers: Dict[str, str] = None) -> Dict[str, Any]:
        """認証付きPOSTリクエスト"""
        await self._check_token_expiry()
        return await super().post(endpoint, data, headers)
```

## レート制限管理

### 1. レート制限ハンドラー

```python
import time
from collections import defaultdict, deque
from typing import Dict, Tuple

class RateLimiter:
    def __init__(self):
        self.limits = {}  # endpoint -> (requests, window_seconds)
        self.requests = defaultdict(deque)  # endpoint -> deque of timestamps
        self.reset_times = {}  # endpoint -> reset_timestamp
    
    def set_limit(self, endpoint: str, requests: int, window_seconds: int):
        """エンドポイントのレート制限を設定"""
        self.limits[endpoint] = (requests, window_seconds)
    
    async def wait_if_needed(self, endpoint: str):
        """必要に応じてレート制限の待機"""
        if endpoint not in self.limits:
            return
        
        max_requests, window_seconds = self.limits[endpoint]
        now = time.time()
        
        # 古いリクエストを削除
        request_times = self.requests[endpoint]
        while request_times and request_times[0] <= now - window_seconds:
            request_times.popleft()
        
        # レート制限チェック
        if len(request_times) >= max_requests:
            # 最も古いリクエストから計算した待機時間
            wait_time = window_seconds - (now - request_times[0])
            if wait_time > 0:
                logger.info(f"Rate limit reached for {endpoint}, waiting {wait_time:.2f} seconds")
                await asyncio.sleep(wait_time)
        
        # 現在のリクエストを記録
        request_times.append(now)
    
    def get_remaining_requests(self, endpoint: str) -> int:
        """残りリクエスト数を取得"""
        if endpoint not in self.limits:
            return float('inf')
        
        max_requests, window_seconds = self.limits[endpoint]
        now = time.time()
        
        # 古いリクエストを削除
        request_times = self.requests[endpoint]
        while request_times and request_times[0] <= now - window_seconds:
            request_times.popleft()
        
        return max(0, max_requests - len(request_times))

class RateLimitedAPIClient(AuthenticatedAPIClient):
    def __init__(self, base_url: str, api_key: str = None, token: str = None, timeout: int = 30):
        super().__init__(base_url, api_key, token, timeout)
        self.rate_limiter = RateLimiter()
    
    def set_rate_limit(self, endpoint: str, requests: int, window_seconds: int):
        """レート制限の設定"""
        self.rate_limiter.set_limit(endpoint, requests, window_seconds)
    
    async def get(self, endpoint: str, params: Dict[str, Any] = None, headers: Dict[str, str] = None) -> Dict[str, Any]:
        """レート制限付きGETリクエスト"""
        await self.rate_limiter.wait_if_needed(endpoint)
        return await super().get(endpoint, params, headers)
    
    async def post(self, endpoint: str, data: Dict[str, Any] = None, headers: Dict[str, str] = None) -> Dict[str, Any]:
        """レート制限付きPOSTリクエスト"""
        await self.rate_limiter.wait_if_needed(endpoint)
        return await super().post(endpoint, data, headers)
```

## 外部サービス統合

### 1. OpenAI API統合

```python
class OpenAIClient(RateLimitedAPIClient):
    def __init__(self, api_key: str):
        super().__init__("https://api.openai.com/v1", token=api_key)
        
        # OpenAI APIのレート制限設定
        self.set_rate_limit("/chat/completions", 3500, 60)  # 3500 requests per minute
        self.set_rate_limit("/completions", 3500, 60)
        self.set_rate_limit("/embeddings", 3500, 60)
    
    async def chat_completion(self, messages: list, model: str = "gpt-3.5-turbo", **kwargs) -> Dict[str, Any]:
        """チャット補完API"""
        data = {
            "model": model,
            "messages": messages,
            **kwargs
        }
        
        try:
            response = await self.post("/chat/completions", data=data)
            return response
        except Exception as e:
            logger.error(f"OpenAI chat completion failed: {e}")
            raise
    
    async def create_embedding(self, text: str, model: str = "text-embedding-ada-002") -> Dict[str, Any]:
        """テキスト埋め込み生成"""
        data = {
            "model": model,
            "input": text
        }
        
        try:
            response = await self.post("/embeddings", data=data)
            return response
        except Exception as e:
            logger.error(f"OpenAI embedding creation failed: {e}")
            raise
    
    async def moderate_content(self, text: str) -> Dict[str, Any]:
        """コンテンツモデレーション"""
        data = {"input": text}
        
        try:
            response = await self.post("/moderations", data=data)
            return response
        except Exception as e:
            logger.error(f"OpenAI moderation failed: {e}")
            raise
```

### 2. note.com API統合

```python
import feedparser
from typing import List

class NoteAPIClient(HTTPClient):
    def __init__(self):
        super().__init__("https://note.com")
    
    async def get_user_feed(self, username: str) -> List[Dict[str, Any]]:
        """ユーザーのRSSフィードを取得"""
        feed_url = f"/{username}/rss"
        
        try:
            # RSSフィードの取得
            response = await self.get(feed_url)
            
            if 'text' in response:
                # feedparserでRSSを解析
                feed = feedparser.parse(response['text'])
                
                posts = []
                for entry in feed.entries:
                    post_data = {
                        'id': entry.get('id', entry.get('link', '')),
                        'title': entry.get('title', ''),
                        'link': entry.get('link', ''),
                        'summary': entry.get('summary', ''),
                        'author': entry.get('author', username),
                        'published': entry.get('published_parsed'),
                        'tags': [tag.term for tag in entry.get('tags', [])],
                        'thumbnail': self._extract_thumbnail(entry)
                    }
                    posts.append(post_data)
                
                return posts
            
            return []
            
        except Exception as e:
            logger.error(f"Failed to fetch note feed for {username}: {e}")
            return []
    
    def _extract_thumbnail(self, entry) -> Optional[str]:
        """サムネイル画像URLの抽出"""
        if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
            return entry.media_thumbnail[0].get('url')
        
        # summaryからimg tagを探す
        import re
        summary = entry.get('summary', '')
        img_match = re.search(r'<img[^>]+src="([^"]+)"', summary)
        if img_match:
            return img_match.group(1)
        
        return None
    
    async def search_posts(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """投稿検索"""
        params = {
            'q': query,
            'limit': limit
        }
        
        try:
            # note.comの検索APIは公開されていないため、
            # 実際の実装では別の方法を使用する必要がある
            response = await self.get("/api/v1/search", params=params)
            return response.get('posts', [])
        except Exception as e:
            logger.error(f"Note search failed: {e}")
            return []
```

### 3. UptimeKuma API統合

```python
class UptimeKumaClient(AuthenticatedAPIClient):
    def __init__(self, base_url: str, api_key: str):
        super().__init__(base_url, api_key=api_key)
    
    async def get_monitors(self) -> List[Dict[str, Any]]:
        """監視対象の取得"""
        try:
            response = await self.get("/api/monitors")
            return response.get('monitors', [])
        except Exception as e:
            logger.error(f"Failed to fetch monitors: {e}")
            return []
    
    async def get_monitor_status(self, monitor_id: int) -> Dict[str, Any]:
        """特定監視対象の状態取得"""
        try:
            response = await self.get(f"/api/monitors/{monitor_id}")
            return response
        except Exception as e:
            logger.error(f"Failed to fetch monitor {monitor_id} status: {e}")
            return {}
    
    async def get_heartbeats(self, monitor_id: int, hours: int = 24) -> List[Dict[str, Any]]:
        """ハートビート履歴の取得"""
        params = {'hours': hours}
        
        try:
            response = await self.get(f"/api/monitors/{monitor_id}/heartbeats", params=params)
            return response.get('heartbeats', [])
        except Exception as e:
            logger.error(f"Failed to fetch heartbeats for monitor {monitor_id}: {e}")
            return []
    
    async def create_monitor(self, monitor_data: Dict[str, Any]) -> Dict[str, Any]:
        """新しい監視対象の作成"""
        try:
            response = await self.post("/api/monitors", data=monitor_data)
            return response
        except Exception as e:
            logger.error(f"Failed to create monitor: {e}")
            raise
    
    async def update_monitor(self, monitor_id: int, monitor_data: Dict[str, Any]) -> Dict[str, Any]:
        """監視対象の更新"""
        try:
            response = await self.put(f"/api/monitors/{monitor_id}", data=monitor_data)
            return response
        except Exception as e:
            logger.error(f"Failed to update monitor {monitor_id}: {e}")
            raise
    
    async def delete_monitor(self, monitor_id: int) -> bool:
        """監視対象の削除"""
        try:
            await self.delete(f"/api/monitors/{monitor_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete monitor {monitor_id}: {e}")
            return False
```

## WebSocket統合

### 1. WebSocketクライアント

```python
import websockets
import json
from typing import Callable, Any

class WebSocketClient:
    def __init__(self, url: str, headers: Dict[str, str] = None):
        self.url = url
        self.headers = headers or {}
        self.websocket = None
        self.message_handlers = {}
        self.is_connected = False
    
    async def connect(self):
        """WebSocket接続の確立"""
        try:
            self.websocket = await websockets.connect(
                self.url,
                extra_headers=self.headers
            )
            self.is_connected = True
            logger.info(f"WebSocket connected to {self.url}")
        except Exception as e:
            logger.error(f"WebSocket connection failed: {e}")
            raise
    
    async def disconnect(self):
        """WebSocket接続の切断"""
        if self.websocket:
            await self.websocket.close()
            self.is_connected = False
            logger.info("WebSocket disconnected")
    
    async def send_message(self, message: Dict[str, Any]):
        """メッセージの送信"""
        if not self.is_connected or not self.websocket:
            raise ConnectionError("WebSocket not connected")
        
        try:
            await self.websocket.send(json.dumps(message))
        except Exception as e:
            logger.error(f"Failed to send WebSocket message: {e}")
            raise
    
    async def listen(self):
        """メッセージの受信ループ"""
        if not self.is_connected or not self.websocket:
            raise ConnectionError("WebSocket not connected")
        
        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    await self._handle_message(data)
                except json.JSONDecodeError:
                    logger.warning(f"Received invalid JSON: {message}")
                except Exception as e:
                    logger.error(f"Error handling WebSocket message: {e}")
        except websockets.exceptions.ConnectionClosed:
            logger.info("WebSocket connection closed")
            self.is_connected = False
        except Exception as e:
            logger.error(f"WebSocket listen error: {e}")
            self.is_connected = False
    
    def add_message_handler(self, message_type: str, handler: Callable):
        """メッセージハンドラーの追加"""
        if message_type not in self.message_handlers:
            self.message_handlers[message_type] = []
        self.message_handlers[message_type].append(handler)
    
    async def _handle_message(self, data: Dict[str, Any]):
        """受信メッセージの処理"""
        message_type = data.get('type', 'unknown')
        
        if message_type in self.message_handlers:
            for handler in self.message_handlers[message_type]:
                try:
                    await handler(data)
                except Exception as e:
                    logger.error(f"Message handler error: {e}")
```

## Webhook管理

### 1. Webhookサーバー

```python
from aiohttp import web
import hmac
import hashlib

class WebhookServer:
    def __init__(self, host: str = '0.0.0.0', port: int = 8080):
        self.host = host
        self.port = port
        self.app = web.Application()
        self.webhook_handlers = {}
        self.secret_keys = {}
        
        # ルートの設定
        self.app.router.add_post('/webhook/{service}', self.handle_webhook)
    
    def add_webhook_handler(self, service: str, handler: Callable, secret_key: str = None):
        """Webhookハンドラーの追加"""
        self.webhook_handlers[service] = handler
        if secret_key:
            self.secret_keys[service] = secret_key
    
    async def handle_webhook(self, request: web.Request) -> web.Response:
        """Webhookリクエストの処理"""
        service = request.match_info['service']
        
        if service not in self.webhook_handlers:
            return web.Response(status=404, text="Service not found")
        
        try:
            # リクエストボディの取得
            body = await request.read()
            
            # 署名検証
            if service in self.secret_keys:
                if not self._verify_signature(request, body, self.secret_keys[service]):
                    return web.Response(status=401, text="Invalid signature")
            
            # JSONデータの解析
            try:
                data = json.loads(body.decode('utf-8'))
            except json.JSONDecodeError:
                return web.Response(status=400, text="Invalid JSON")
            
            # ハンドラーの実行
            handler = self.webhook_handlers[service]
            await handler(data, request.headers)
            
            return web.Response(status=200, text="OK")
            
        except Exception as e:
            logger.error(f"Webhook handler error for {service}: {e}")
            return web.Response(status=500, text="Internal server error")
    
    def _verify_signature(self, request: web.Request, body: bytes, secret_key: str) -> bool:
        """署名の検証"""
        signature_header = request.headers.get('X-Hub-Signature-256')
        if not signature_header:
            return False
        
        expected_signature = hmac.new(
            secret_key.encode('utf-8'),
            body,
            hashlib.sha256
        ).hexdigest()
        
        received_signature = signature_header.replace('sha256=', '')
        
        return hmac.compare_digest(expected_signature, received_signature)
    
    async def start(self):
        """Webhookサーバーの開始"""
        runner = web.AppRunner(self.app)
        await runner.setup()
        
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()
        
        logger.info(f"Webhook server started on {self.host}:{self.port}")
    
    async def stop(self):
        """Webhookサーバーの停止"""
        await self.app.shutdown()
        await self.app.cleanup()
        logger.info("Webhook server stopped")
```

## キャッシュ管理

### 1. APIレスポンスキャッシュ

```python
import pickle
from typing import Optional
from datetime import datetime, timedelta

class APICache:
    def __init__(self, default_ttl: int = 300):
        self.cache = {}
        self.default_ttl = default_ttl
    
    def _generate_key(self, endpoint: str, params: Dict[str, Any] = None) -> str:
        """キャッシュキーの生成"""
        key = endpoint
        if params:
            sorted_params = sorted(params.items())
            key += "?" + "&".join([f"{k}={v}" for k, v in sorted_params])
        return key
    
    def get(self, endpoint: str, params: Dict[str, Any] = None) -> Optional[Any]:
        """キャッシュからデータを取得"""
        key = self._generate_key(endpoint, params)
        
        if key in self.cache:
            data, expires_at = self.cache[key]
            if datetime.now() < expires_at:
                return data
            else:
                # 期限切れのデータを削除
                del self.cache[key]
        
        return None
    
    def set(self, endpoint: str, data: Any, params: Dict[str, Any] = None, ttl: int = None) -> None:
        """データをキャッシュに保存"""
        key = self._generate_key(endpoint, params)
        ttl = ttl or self.default_ttl
        expires_at = datetime.now() + timedelta(seconds=ttl)
        
        self.cache[key] = (data, expires_at)
    
    def delete(self, endpoint: str, params: Dict[str, Any] = None) -> None:
        """キャッシュからデータを削除"""
        key = self._generate_key(endpoint, params)
        if key in self.cache:
            del self.cache[key]
    
    def clear(self) -> None:
        """全キャッシュをクリア"""
        self.cache.clear()
    
    def cleanup_expired(self) -> None:
        """期限切れキャッシュの削除"""
        now = datetime.now()
        expired_keys = [
            key for key, (_, expires_at) in self.cache.items()
            if now >= expires_at
        ]
        
        for key in expired_keys:
            del self.cache[key]

class CachedAPIClient(RateLimitedAPIClient):
    def __init__(self, base_url: str, api_key: str = None, token: str = None, timeout: int = 30, cache_ttl: int = 300):
        super().__init__(base_url, api_key, token, timeout)
        self.cache = APICache(cache_ttl)
    
    async def get(self, endpoint: str, params: Dict[str, Any] = None, headers: Dict[str, str] = None, use_cache: bool = True, cache_ttl: int = None) -> Dict[str, Any]:
        """キャッシュ付きGETリクエスト"""
        if use_cache:
            cached_data = self.cache.get(endpoint, params)
            if cached_data is not None:
                return cached_data
        
        # キャッシュにない場合はAPIを呼び出し
        response = await super().get(endpoint, params, headers)
        
        if use_cache:
            self.cache.set(endpoint, response, params, cache_ttl)
        
        return response
    
    def clear_cache(self, endpoint: str = None, params: Dict[str, Any] = None):
        """キャッシュのクリア"""
        if endpoint:
            self.cache.delete(endpoint, params)
        else:
            self.cache.clear()
```

## API統合の使用例

### 1. 統合APIマネージャー

```python
class APIManager:
    def __init__(self):
        self.clients = {}
        self.webhook_server = None
    
    def register_client(self, name: str, client: HTTPClient):
        """APIクライアントの登録"""
        self.clients[name] = client
    
    def get_client(self, name: str) -> HTTPClient:
        """APIクライアントの取得"""
        if name not in self.clients:
            raise ValueError(f"API client '{name}' not found")
        return self.clients[name]
    
    async def initialize_clients(self):
        """全クライアントの初期化"""
        for name, client in self.clients.items():
            try:
                await client.create_session()
                logger.info(f"Initialized API client: {name}")
            except Exception as e:
                logger.error(f"Failed to initialize API client {name}: {e}")
    
    async def cleanup_clients(self):
        """全クライアントのクリーンアップ"""
        for name, client in self.clients.items():
            try:
                await client.close_session()
                logger.info(f"Cleaned up API client: {name}")
            except Exception as e:
                logger.error(f"Failed to cleanup API client {name}: {e}")

# 使用例
async def setup_api_manager():
    manager = APIManager()
    
    # OpenAI クライアント
    openai_client = OpenAIClient(os.getenv("OPENAI_API_KEY"))
    manager.register_client("openai", openai_client)
    
    # note.com クライアント
    note_client = NoteAPIClient()
    manager.register_client("note", note_client)
    
    # UptimeKuma クライアント
    uptime_client = UptimeKumaClient(
        os.getenv("UPTIME_KUMA_URL"),
        os.getenv("UPTIME_KUMA_API_KEY")
    )
    manager.register_client("uptime", uptime_client)
    
    await manager.initialize_clients()
    return manager
```

---

## 関連ドキュメント

- [データベース管理](01-database-management.md)
- [ログシステム](../02-core/03-logging-system.md)
- [エラーハンドリング](../02-core/04-error-handling.md)
- [ノートCogs](../03-cogs/07-note-cogs.md)
- [監視Cogs](../03-cogs/08-monitoring-cogs.md)
