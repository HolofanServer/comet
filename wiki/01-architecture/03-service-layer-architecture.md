# サービス層アーキテクチャ

## C.O.M.E.T.について

**C.O.M.E.T.**の名前は以下の頭文字から構成されています：

- **C**ommunity of
- **O**shilove
- **M**oderation &
- **E**njoyment
- **T**ogether

HFS - ホロライブ非公式ファンサーバーのコミュニティを支える、推し愛とモデレーション、そして楽しさを一緒に提供するボットです。

## 概要

COMETボットのサービス層は、ビジネスロジックとデータアクセス層の間の抽象化レイヤーを提供します。依存性注入パターンとサービス指向アーキテクチャを採用し、モジュラーで拡張可能な設計を実現しています。

## サービス層アーキテクチャ図

```
┌─────────────────────────────────────────────────────────────┐
│                    サービス層アーキテクチャ                   │
├─────────────────────────────────────────────────────────────┤
│  プレゼンテーション層 (Cogs)                                  │
│  ├── Events Cogs                                            │
│  ├── Management Cogs                                        │
│  ├── Tool Cogs                                              │
│  └── Homepage Cogs                                          │
├─────────────────────────────────────────────────────────────┤
│  サービス層 (Business Logic)                                 │
│  ├── 認証サービス (AuthService)                              │
│  ├── ログサービス (LoggingService)                           │
│  ├── データベースサービス (DatabaseService)                  │
│  ├── 通知サービス (NotificationService)                      │
│  ├── 分析サービス (AnalyticsService)                         │
│  └── 設定サービス (ConfigurationService)                     │
├─────────────────────────────────────────────────────────────┤
│  データアクセス層 (Data Access)                              │
│  ├── JSONファイルストレージ                                  │
│  ├── SQLiteデータベース                                      │
│  ├── 外部API統合                                             │
│  └── ファイルシステム                                        │
├─────────────────────────────────────────────────────────────┤
│  外部サービス                                                │
│  ├── Discord API                                            │
│  ├── Webhook サービス                                       │
│  ├── 監視サービス (UptimeKuma)                               │
│  └── サードパーティAPI                                       │
└─────────────────────────────────────────────────────────────┘
```

## コアサービス

### 1. 認証サービス (AuthService)

**場所**: [`utils/auth.py`](../utils/auth.py)

**責任**:
- ボット認証の管理
- 権限検証
- セキュアな認証情報の処理

**主要メソッド**:
```python
class AuthService:
    async def authenticate(self) -> bool
    async def verify_permissions(self, user_id: int, permission: str) -> bool
    async def get_auth_token(self) -> str
    async def refresh_credentials(self) -> None
```

**使用例**:
```python
auth_service = AuthService()
if await auth_service.authenticate():
    logger.info("認証成功")
else:
    logger.error("認証失敗")
```

### 2. ログサービス (LoggingService)

**場所**: [`utils/logging.py`](../utils/logging.py)

**責任**:
- 構造化ログの管理
- ログレベルの制御
- ログの永続化と配信

**主要メソッド**:
```python
class LoggingService:
    def setup_logging(self, level: str = "INFO") -> logging.Logger
    def log_event(self, event_data: dict) -> None
    def save_log(self, log_data: dict) -> None
    def get_logs(self, filter_criteria: dict) -> List[dict]
```

**ログ構造**:
```python
log_data = {
    "event": "UserAction",
    "description": "User performed action",
    "timestamp": datetime.now().isoformat(),
    "user_id": 123456789,
    "guild_id": 987654321,
    "session_id": session_id,
    "metadata": {
        "command": "example_command",
        "parameters": {"param1": "value1"}
    }
}
```

### 3. データベースサービス (DatabaseService)

**場所**: [`utils/db_manager.py`](../utils/db_manager.py)

**責任**:
- データベース接続の管理
- CRUD操作の抽象化
- データマイグレーション

**主要メソッド**:
```python
class DatabaseService:
    async def connect(self) -> None
    async def execute_query(self, query: str, params: tuple) -> Any
    async def fetch_one(self, query: str, params: tuple) -> dict
    async def fetch_all(self, query: str, params: tuple) -> List[dict]
    async def migrate(self, migration_file: str) -> None
```

**使用例**:
```python
db_service = DatabaseService()
await db_service.connect()
result = await db_service.fetch_one(
    "SELECT * FROM users WHERE id = ?", 
    (user_id,)
)
```

### 4. 通知サービス (NotificationService)

**場所**: [`utils/webhook.py`](../utils/webhook.py)

**責任**:
- Webhook通知の送信
- 通知テンプレートの管理
- 配信失敗時の再試行

**主要メソッド**:
```python
class NotificationService:
    async def send_webhook(self, url: str, data: dict) -> bool
    async def send_startup_notification(self, bot: commands.Bot) -> None
    async def send_error_notification(self, error: Exception) -> None
    async def send_custom_notification(self, template: str, data: dict) -> None
```

### 5. 分析サービス (AnalyticsService)

**場所**: [`utils/analytics.py`](../utils/analytics.py)

**責任**:
- ユーザー行動の分析
- サーバー統計の収集
- パフォーマンスメトリクスの追跡

**主要メソッド**:
```python
class AnalyticsService:
    async def track_command_usage(self, command: str, user_id: int) -> None
    async def collect_server_stats(self, guild_id: int) -> dict
    async def generate_report(self, period: str) -> dict
    async def get_user_activity(self, user_id: int) -> dict
```

### 6. 設定サービス (ConfigurationService)

**場所**: [`config/setting.py`](../config/setting.py)

**責任**:
- 設定の読み込みと管理
- 環境変数の処理
- 動的設定更新

**主要メソッド**:
```python
class ConfigurationService:
    def load_config(self, config_name: str) -> dict
    def save_config(self, config_name: str, data: dict) -> None
    def get_env_var(self, key: str, default: Any = None) -> Any
    def update_runtime_config(self, key: str, value: Any) -> None
```

## 依存性注入パターン

### サービスコンテナ

```python
class ServiceContainer:
    def __init__(self):
        self._services = {}
        self._singletons = {}
    
    def register(self, service_type: type, implementation: type, singleton: bool = True):
        self._services[service_type] = {
            'implementation': implementation,
            'singleton': singleton
        }
    
    def get(self, service_type: type):
        if service_type not in self._services:
            raise ValueError(f"Service {service_type} not registered")
        
        service_info = self._services[service_type]
        
        if service_info['singleton']:
            if service_type not in self._singletons:
                self._singletons[service_type] = service_info['implementation']()
            return self._singletons[service_type]
        else:
            return service_info['implementation']()
```

### サービス登録

```python
# サービスコンテナの初期化
container = ServiceContainer()

# サービスの登録
container.register(AuthService, AuthService, singleton=True)
container.register(LoggingService, LoggingService, singleton=True)
container.register(DatabaseService, DatabaseService, singleton=True)
container.register(NotificationService, NotificationService, singleton=True)
```

### Cogでの依存性注入

```python
class ExampleCog(commands.Cog):
    def __init__(self, bot: commands.Bot, container: ServiceContainer):
        self.bot = bot
        self.auth_service = container.get(AuthService)
        self.db_service = container.get(DatabaseService)
        self.notification_service = container.get(NotificationService)
    
    @commands.command()
    async def example_command(self, ctx):
        if not await self.auth_service.verify_permissions(ctx.author.id, "example"):
            await ctx.send("権限がありません")
            return
        
        data = await self.db_service.fetch_one(
            "SELECT * FROM examples WHERE user_id = ?",
            (ctx.author.id,)
        )
        
        await self.notification_service.send_custom_notification(
            "command_executed",
            {"user": ctx.author.name, "command": "example"}
        )
```

## サービス間通信

### イベントバス

```python
class EventBus:
    def __init__(self):
        self._subscribers = {}
    
    def subscribe(self, event_type: str, handler: callable):
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)
    
    async def publish(self, event_type: str, data: dict):
        if event_type in self._subscribers:
            for handler in self._subscribers[event_type]:
                await handler(data)
```

### 使用例

```python
# イベントバスの初期化
event_bus = EventBus()

# イベントハンドラーの登録
async def handle_user_join(data):
    user_id = data['user_id']
    guild_id = data['guild_id']
    # ウェルカムメッセージの送信
    await send_welcome_message(user_id, guild_id)

event_bus.subscribe('user_joined', handle_user_join)

# イベントの発行
await event_bus.publish('user_joined', {
    'user_id': 123456789,
    'guild_id': 987654321
})
```

## サービス設定

### 設定ファイル構造

```json
{
    "services": {
        "auth": {
            "token_refresh_interval": 3600,
            "max_retry_attempts": 3
        },
        "database": {
            "connection_pool_size": 10,
            "query_timeout": 30
        },
        "logging": {
            "level": "INFO",
            "max_file_size": "10MB",
            "backup_count": 5
        },
        "notifications": {
            "webhook_timeout": 10,
            "retry_delay": 5
        }
    }
}
```

### 環境固有設定

```python
class EnvironmentConfig:
    def __init__(self, environment: str):
        self.environment = environment
        self.config = self._load_environment_config()
    
    def _load_environment_config(self):
        if self.environment == "development":
            return {
                "logging_level": "DEBUG",
                "database_url": "sqlite:///dev.db",
                "webhook_enabled": False
            }
        elif self.environment == "production":
            return {
                "logging_level": "INFO",
                "database_url": "sqlite:///prod.db",
                "webhook_enabled": True
            }
```

## エラーハンドリングとリトライ

### サービスレベルエラーハンドリング

```python
class ServiceBase:
    def __init__(self, max_retries: int = 3, retry_delay: float = 1.0):
        self.max_retries = max_retries
        self.retry_delay = retry_delay
    
    async def execute_with_retry(self, operation: callable, *args, **kwargs):
        for attempt in range(self.max_retries):
            try:
                return await operation(*args, **kwargs)
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise e
                await asyncio.sleep(self.retry_delay * (2 ** attempt))
```

### 回路ブレーカーパターン

```python
class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    async def call(self, operation: callable, *args, **kwargs):
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.timeout:
                self.state = "HALF_OPEN"
            else:
                raise Exception("Circuit breaker is OPEN")
        
        try:
            result = await operation(*args, **kwargs)
            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"
            
            raise e
```

## パフォーマンス監視

### メトリクス収集

```python
class MetricsService:
    def __init__(self):
        self.metrics = {}
    
    def increment_counter(self, metric_name: str, value: int = 1):
        if metric_name not in self.metrics:
            self.metrics[metric_name] = 0
        self.metrics[metric_name] += value
    
    def record_timing(self, metric_name: str, duration: float):
        timing_key = f"{metric_name}_timing"
        if timing_key not in self.metrics:
            self.metrics[timing_key] = []
        self.metrics[timing_key].append(duration)
    
    def get_metrics(self) -> dict:
        return self.metrics.copy()
```

### パフォーマンスデコレータ

```python
def measure_performance(metric_name: str):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                metrics_service.increment_counter(f"{metric_name}_success")
                return result
            except Exception as e:
                metrics_service.increment_counter(f"{metric_name}_error")
                raise e
            finally:
                duration = time.time() - start_time
                metrics_service.record_timing(metric_name, duration)
        return wrapper
    return decorator
```

## テスト戦略

### サービスのユニットテスト

```python
import pytest
from unittest.mock import AsyncMock, Mock

class TestAuthService:
    @pytest.fixture
    def auth_service(self):
        return AuthService()
    
    @pytest.mark.asyncio
    async def test_authenticate_success(self, auth_service):
        # モックの設定
        auth_service._verify_token = AsyncMock(return_value=True)
        
        # テスト実行
        result = await auth_service.authenticate()
        
        # アサーション
        assert result is True
        auth_service._verify_token.assert_called_once()
```

### 統合テスト

```python
class TestServiceIntegration:
    @pytest.mark.asyncio
    async def test_user_registration_flow(self):
        # サービスの初期化
        container = ServiceContainer()
        auth_service = container.get(AuthService)
        db_service = container.get(DatabaseService)
        notification_service = container.get(NotificationService)
        
        # テストデータ
        user_data = {"id": 123, "name": "test_user"}
        
        # フロー実行
        await auth_service.register_user(user_data)
        user = await db_service.get_user(123)
        await notification_service.send_welcome_notification(user)
        
        # 検証
        assert user["name"] == "test_user"
```

---

## 関連ドキュメント

- [ボットアーキテクチャ概要](01-bot-architecture-overview.md)
- [設定管理](04-configuration-management.md)
- [データベース管理](../04-utilities/01-database-management.md)
- [エラーハンドリング](../02-core/04-error-handling.md)
