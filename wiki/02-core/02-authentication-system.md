# 認証システム

## C.O.M.E.T.について

**C.O.M.E.T.**の名前は以下の頭文字から構成されています：

- **C**ommunity of
- **O**shilove
- **M**oderation &
- **E**njoyment
- **T**ogether

HFS - ホロライブ非公式ファンサーバーのコミュニティを支える、推し愛とモデレーション、そして楽しさを一緒に提供するボットです。

## 概要

COMETボットの認証システムは、セキュアなボット認証、権限管理、アクセス制御を提供します。多層防御アプローチを採用し、不正アクセスからボットとサーバーを保護します。

## 認証アーキテクチャ

```
┌─────────────────────────────────────────────────────────────┐
│                    認証システムアーキテクチャ                 │
├─────────────────────────────────────────────────────────────┤
│  認証層 (Authentication Layer)                              │
│  ├── Discord Bot Token 認証                                 │
│  ├── 外部API認証                                             │
│  ├── Webhook認証                                             │
│  └── セッション管理                                          │
├─────────────────────────────────────────────────────────────┤
│  認可層 (Authorization Layer)                               │
│  ├── ロールベースアクセス制御 (RBAC)                         │
│  ├── 権限チェック                                            │
│  ├── コマンド権限                                            │
│  └── リソースアクセス制御                                    │
├─────────────────────────────────────────────────────────────┤
│  セキュリティ層 (Security Layer)                            │
│  ├── レート制限                                              │
│  ├── 入力検証                                                │
│  ├── 監査ログ                                                │
│  └── 異常検知                                                │
├─────────────────────────────────────────────────────────────┤
│  暗号化・保護層 (Encryption & Protection)                   │
│  ├── 認証情報暗号化                                          │
│  ├── セキュアストレージ                                      │
│  ├── 通信暗号化                                              │
│  └── 秘密鍵管理                                              │
└─────────────────────────────────────────────────────────────┘
```

## 認証コンポーネント

### 1. Discord Bot Token 認証

**場所**: [`utils/auth.py`](../utils/auth.py)

```python
import os
import aiohttp
import logging
from typing import Optional, Dict, Any

class DiscordAuthenticator:
    def __init__(self, token: str):
        self.token = token
        self.session: Optional[aiohttp.ClientSession] = None
        self.bot_info: Optional[Dict[str, Any]] = None
        
    async def authenticate(self) -> bool:
        """Discord Bot Tokenの認証"""
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            headers = {
                'Authorization': f'Bot {self.token}',
                'Content-Type': 'application/json'
            }
            
            async with self.session.get(
                'https://discord.com/api/v10/users/@me',
                headers=headers
            ) as response:
                if response.status == 200:
                    self.bot_info = await response.json()
                    logger.info(f"認証成功: {self.bot_info['username']}#{self.bot_info['discriminator']}")
                    return True
                else:
                    logger.error(f"認証失敗: HTTP {response.status}")
                    return False
                    
        except Exception as e:
            logger.error(f"認証エラー: {e}")
            return False
    
    async def verify_permissions(self, guild_id: int, permissions: int) -> bool:
        """ギルドでの権限を確認"""
        try:
            headers = {
                'Authorization': f'Bot {self.token}',
                'Content-Type': 'application/json'
            }
            
            async with self.session.get(
                f'https://discord.com/api/v10/guilds/{guild_id}/members/@me',
                headers=headers
            ) as response:
                if response.status == 200:
                    member_data = await response.json()
                    # 権限計算ロジック
                    return self._calculate_permissions(member_data, permissions)
                return False
                
        except Exception as e:
            logger.error(f"権限確認エラー: {e}")
            return False
    
    def _calculate_permissions(self, member_data: Dict, required_permissions: int) -> bool:
        """権限の計算"""
        # Discord権限計算の実装
        pass
    
    async def close(self):
        """セッションのクリーンアップ"""
        if self.session:
            await self.session.close()
```

### 2. 外部API認証

```python
class ExternalAPIAuthenticator:
    def __init__(self, api_key: str, api_url: str):
        self.api_key = api_key
        self.api_url = api_url
        self.access_token: Optional[str] = None
        self.token_expires_at: Optional[datetime] = None
    
    async def get_access_token(self) -> Optional[str]:
        """アクセストークンを取得"""
        if self.access_token and self.token_expires_at:
            if datetime.now() < self.token_expires_at:
                return self.access_token
        
        # トークンの更新
        await self._refresh_token()
        return self.access_token
    
    async def _refresh_token(self) -> None:
        """トークンの更新"""
        try:
            async with aiohttp.ClientSession() as session:
                data = {
                    'api_key': self.api_key,
                    'grant_type': 'client_credentials'
                }
                
                async with session.post(
                    f'{self.api_url}/auth/token',
                    json=data
                ) as response:
                    if response.status == 200:
                        token_data = await response.json()
                        self.access_token = token_data['access_token']
                        expires_in = token_data.get('expires_in', 3600)
                        self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)
                    else:
                        logger.error(f"トークン更新失敗: HTTP {response.status}")
                        
        except Exception as e:
            logger.error(f"トークン更新エラー: {e}")
```

### 3. 権限管理システム

```python
from enum import Enum
from typing import Set, List

class Permission(Enum):
    # 基本権限
    VIEW_CHANNELS = "view_channels"
    SEND_MESSAGES = "send_messages"
    
    # モデレーション権限
    MANAGE_MESSAGES = "manage_messages"
    KICK_MEMBERS = "kick_members"
    BAN_MEMBERS = "ban_members"
    
    # 管理権限
    MANAGE_GUILD = "manage_guild"
    MANAGE_ROLES = "manage_roles"
    MANAGE_CHANNELS = "manage_channels"
    
    # ボット固有権限
    BOT_ADMIN = "bot_admin"
    BOT_MODERATOR = "bot_moderator"
    BOT_DEVELOPER = "bot_developer"

class Role:
    def __init__(self, name: str, permissions: Set[Permission]):
        self.name = name
        self.permissions = permissions
    
    def has_permission(self, permission: Permission) -> bool:
        return permission in self.permissions

class PermissionManager:
    def __init__(self):
        self.roles = self._initialize_roles()
        self.user_roles = {}  # user_id -> Set[Role]
    
    def _initialize_roles(self) -> Dict[str, Role]:
        """デフォルトロールの初期化"""
        return {
            'admin': Role('admin', {
                Permission.BOT_ADMIN,
                Permission.MANAGE_GUILD,
                Permission.MANAGE_ROLES,
                Permission.MANAGE_CHANNELS,
                Permission.BAN_MEMBERS,
                Permission.KICK_MEMBERS,
                Permission.MANAGE_MESSAGES
            }),
            'moderator': Role('moderator', {
                Permission.BOT_MODERATOR,
                Permission.KICK_MEMBERS,
                Permission.MANAGE_MESSAGES,
                Permission.VIEW_CHANNELS,
                Permission.SEND_MESSAGES
            }),
            'user': Role('user', {
                Permission.VIEW_CHANNELS,
                Permission.SEND_MESSAGES
            })
        }
    
    async def check_permission(self, user_id: int, guild_id: int, permission: Permission) -> bool:
        """ユーザーの権限をチェック"""
        # Discord権限の確認
        discord_perms = await self._get_discord_permissions(user_id, guild_id)
        if self._has_discord_permission(discord_perms, permission):
            return True
        
        # ボット固有権限の確認
        user_roles = await self._get_user_roles(user_id, guild_id)
        for role in user_roles:
            if role.has_permission(permission):
                return True
        
        return False
    
    async def _get_discord_permissions(self, user_id: int, guild_id: int) -> int:
        """Discordの権限を取得"""
        # Discord APIから権限を取得する実装
        pass
    
    def _has_discord_permission(self, permissions: int, required: Permission) -> bool:
        """Discord権限の確認"""
        permission_mapping = {
            Permission.MANAGE_MESSAGES: 0x00002000,
            Permission.KICK_MEMBERS: 0x00000002,
            Permission.BAN_MEMBERS: 0x00000004,
            Permission.MANAGE_GUILD: 0x00000020,
            Permission.MANAGE_ROLES: 0x10000000,
            Permission.MANAGE_CHANNELS: 0x00000010,
        }
        
        required_value = permission_mapping.get(required, 0)
        return (permissions & required_value) == required_value
    
    async def _get_user_roles(self, user_id: int, guild_id: int) -> Set[Role]:
        """ユーザーのボット固有ロールを取得"""
        # データベースからユーザーロールを取得
        pass
```

### 4. セキュリティミドルウェア

```python
import time
from collections import defaultdict
from typing import Dict, Tuple

class SecurityMiddleware:
    def __init__(self):
        self.rate_limits = defaultdict(list)  # user_id -> [timestamp, ...]
        self.failed_attempts = defaultdict(int)  # user_id -> count
        self.blocked_users = set()
    
    async def check_rate_limit(self, user_id: int, command: str, limit: int = 5, window: int = 60) -> bool:
        """レート制限のチェック"""
        now = time.time()
        user_requests = self.rate_limits[user_id]
        
        # 古いリクエストを削除
        user_requests[:] = [req_time for req_time in user_requests if now - req_time < window]
        
        if len(user_requests) >= limit:
            logger.warning(f"Rate limit exceeded for user {user_id} on command {command}")
            return False
        
        user_requests.append(now)
        return True
    
    async def validate_input(self, input_data: str) -> bool:
        """入力検証"""
        # SQLインジェクション対策
        if self._contains_sql_injection(input_data):
            return False
        
        # XSS対策
        if self._contains_xss(input_data):
            return False
        
        # 長さ制限
        if len(input_data) > 2000:
            return False
        
        return True
    
    def _contains_sql_injection(self, input_data: str) -> bool:
        """SQLインジェクションの検出"""
        sql_patterns = [
            r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER)\b)",
            r"(\b(UNION|OR|AND)\b.*\b(SELECT|INSERT|UPDATE|DELETE)\b)",
            r"(--|#|/\*|\*/)",
            r"(\b(EXEC|EXECUTE)\b)"
        ]
        
        for pattern in sql_patterns:
            if re.search(pattern, input_data, re.IGNORECASE):
                return True
        return False
    
    def _contains_xss(self, input_data: str) -> bool:
        """XSSの検出"""
        xss_patterns = [
            r"<script[^>]*>.*?</script>",
            r"javascript:",
            r"on\w+\s*=",
            r"<iframe[^>]*>.*?</iframe>"
        ]
        
        for pattern in xss_patterns:
            if re.search(pattern, input_data, re.IGNORECASE):
                return True
        return False
    
    async def log_security_event(self, event_type: str, user_id: int, details: Dict[str, Any]) -> None:
        """セキュリティイベントのログ"""
        security_log = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "user_id": user_id,
            "details": details,
            "severity": self._get_severity(event_type)
        }
        
        logger.warning(f"Security event: {security_log}")
        
        # 重要なイベントは管理者に通知
        if security_log["severity"] == "HIGH":
            await self._notify_admins(security_log)
    
    def _get_severity(self, event_type: str) -> str:
        """イベントの重要度を判定"""
        high_severity_events = [
            "sql_injection_attempt",
            "xss_attempt",
            "repeated_failed_auth",
            "privilege_escalation_attempt"
        ]
        
        if event_type in high_severity_events:
            return "HIGH"
        return "MEDIUM"
```

### 5. 監査ログシステム

```python
class AuditLogger:
    def __init__(self, db_service):
        self.db_service = db_service
    
    async def log_authentication(self, user_id: int, success: bool, method: str, ip_address: str = None) -> None:
        """認証ログの記録"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event_type": "authentication",
            "user_id": user_id,
            "success": success,
            "method": method,
            "ip_address": ip_address,
            "session_id": self._generate_session_id()
        }
        
        await self._save_audit_log(log_entry)
    
    async def log_permission_check(self, user_id: int, permission: str, granted: bool, resource: str = None) -> None:
        """権限チェックログの記録"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event_type": "permission_check",
            "user_id": user_id,
            "permission": permission,
            "granted": granted,
            "resource": resource
        }
        
        await self._save_audit_log(log_entry)
    
    async def log_command_execution(self, user_id: int, command: str, parameters: Dict, success: bool) -> None:
        """コマンド実行ログの記録"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event_type": "command_execution",
            "user_id": user_id,
            "command": command,
            "parameters": parameters,
            "success": success
        }
        
        await self._save_audit_log(log_entry)
    
    async def _save_audit_log(self, log_entry: Dict[str, Any]) -> None:
        """監査ログの保存"""
        query = """
        INSERT INTO audit_logs (
            timestamp, event_type, user_id, data, created_at
        ) VALUES (?, ?, ?, ?, ?)
        """
        
        await self.db_service.execute_query(
            query,
            (
                log_entry["timestamp"],
                log_entry["event_type"],
                log_entry.get("user_id"),
                json.dumps(log_entry),
                datetime.now().isoformat()
            )
        )
    
    def _generate_session_id(self) -> str:
        """セッションIDの生成"""
        import uuid
        return str(uuid.uuid4())
```

## 認証フロー

### 1. ボット起動時認証フロー

```
1. 環境変数からトークン読み込み
   ↓
2. Discord API認証
   ↓
3. ボット情報取得
   ↓
4. 権限確認
   ↓
5. セッション確立
   ↓
6. 認証成功ログ記録
```

### 2. コマンド実行時認証フロー

```
1. ユーザーコマンド受信
   ↓
2. レート制限チェック
   ↓
3. 入力検証
   ↓
4. 権限確認
   ↓
5. コマンド実行
   ↓
6. 実行ログ記録
```

## セキュリティベストプラクティス

### 1. 認証情報の保護

```python
class SecureCredentialManager:
    def __init__(self, encryption_key: bytes):
        self.cipher_suite = Fernet(encryption_key)
    
    def encrypt_credential(self, credential: str) -> str:
        """認証情報の暗号化"""
        encrypted = self.cipher_suite.encrypt(credential.encode())
        return base64.b64encode(encrypted).decode()
    
    def decrypt_credential(self, encrypted_credential: str) -> str:
        """認証情報の復号化"""
        encrypted_bytes = base64.b64decode(encrypted_credential.encode())
        decrypted = self.cipher_suite.decrypt(encrypted_bytes)
        return decrypted.decode()
    
    @staticmethod
    def generate_encryption_key() -> bytes:
        """暗号化キーの生成"""
        return Fernet.generate_key()
```

### 2. セキュアな設定管理

```python
class SecureConfigManager:
    def __init__(self):
        self.sensitive_keys = {
            'BOT_TOKEN',
            'AUTH_TOKEN',
            'API_KEY',
            'WEBHOOK_URL',
            'DATABASE_PASSWORD'
        }
    
    def load_secure_config(self) -> Dict[str, str]:
        """セキュアな設定の読み込み"""
        config = {}
        
        for key in self.sensitive_keys:
            value = os.getenv(key)
            if value:
                # 環境変数から直接読み込み（ログに出力しない）
                config[key] = value
            else:
                logger.warning(f"Missing sensitive configuration: {key}")
        
        return config
    
    def validate_token_format(self, token: str) -> bool:
        """トークン形式の検証"""
        # Discord Bot Tokenの形式チェック
        if not re.match(r'^[A-Za-z0-9._-]{50,}$', token):
            return False
        
        # 既知の無効なトークンパターンをチェック
        invalid_patterns = ['test', 'example', 'placeholder']
        for pattern in invalid_patterns:
            if pattern.lower() in token.lower():
                return False
        
        return True
```

### 3. 異常検知システム

```python
class AnomalyDetector:
    def __init__(self):
        self.baseline_metrics = {}
        self.alert_thresholds = {
            'failed_auth_rate': 0.1,  # 10%以上の認証失敗率
            'command_rate_spike': 5.0,  # 通常の5倍以上のコマンド実行
            'unusual_hours': (2, 6)  # 深夜2-6時の活動
        }
    
    async def detect_anomalies(self, metrics: Dict[str, float]) -> List[str]:
        """異常の検出"""
        anomalies = []
        
        # 認証失敗率の異常
        if metrics.get('failed_auth_rate', 0) > self.alert_thresholds['failed_auth_rate']:
            anomalies.append("High authentication failure rate detected")
        
        # コマンド実行率の急増
        baseline_rate = self.baseline_metrics.get('command_rate', 1.0)
        current_rate = metrics.get('command_rate', 0)
        if current_rate > baseline_rate * self.alert_thresholds['command_rate_spike']:
            anomalies.append("Unusual spike in command execution rate")
        
        # 異常な時間帯の活動
        current_hour = datetime.now().hour
        if self.alert_thresholds['unusual_hours'][0] <= current_hour <= self.alert_thresholds['unusual_hours'][1]:
            if metrics.get('activity_level', 0) > baseline_rate:
                anomalies.append("Unusual activity during off-hours")
        
        return anomalies
    
    async def update_baseline(self, metrics: Dict[str, float]) -> None:
        """ベースライン指標の更新"""
        for key, value in metrics.items():
            if key in self.baseline_metrics:
                # 移動平均でベースラインを更新
                self.baseline_metrics[key] = (self.baseline_metrics[key] * 0.9) + (value * 0.1)
            else:
                self.baseline_metrics[key] = value
```

---

## 関連ドキュメント

- [メインボットクラス](01-main-bot-class.md)
- [エラーハンドリング](04-error-handling.md)
- [設定管理](../01-architecture/04-configuration-management.md)
- [データベース管理](../04-utilities/01-database-management.md)
