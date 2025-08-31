# セキュリティガイドライン

## C.O.M.E.T.について

**C.O.M.E.T.**の名前は以下の頭文字から構成されています：

- **C**ommunity of
- **O**shilove
- **M**oderation &
- **E**njoyment
- **T**ogether

HFS - ホロライブ非公式ファンサーバーのコミュニティを支える、推し愛とモデレーション、そして楽しさを一緒に提供するボットです。

## 概要

C.O.M.E.T.ボットの開発・運用におけるセキュリティガイドラインについて説明します。セキュアなコーディング、認証・認可、データ保護、脆弱性対策などについて詳しく解説します。

## セキュアコーディング

### 入力検証

```python
import re
from typing import Any, Optional
import html

class InputValidator:
    def __init__(self):
        self.max_string_length = 2000
        self.allowed_chars_pattern = re.compile(r'^[a-zA-Z0-9\s\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF\u3000-\u303F]*$')
    
    def validate_user_input(self, input_data: str) -> str:
        """ユーザー入力検証"""
        if not isinstance(input_data, str):
            raise ValueError("入力は文字列である必要があります")
        
        # 長さチェック
        if len(input_data) > self.max_string_length:
            raise ValueError(f"入力が長すぎます（最大{self.max_string_length}文字）")
        
        # 文字種チェック
        if not self.allowed_chars_pattern.match(input_data):
            raise ValueError("許可されていない文字が含まれています")
        
        # HTMLエスケープ
        return html.escape(input_data.strip())
    
    def validate_discord_id(self, discord_id: str) -> int:
        """Discord ID検証"""
        try:
            id_int = int(discord_id)
            if id_int <= 0 or id_int > 2**63 - 1:
                raise ValueError("無効なDiscord IDです")
            return id_int
        except ValueError:
            raise ValueError("Discord IDは数値である必要があります")
    
    def sanitize_filename(self, filename: str) -> str:
        """ファイル名サニタイズ"""
        # 危険な文字を除去
        dangerous_chars = ['..', '/', '\\', ':', '*', '?', '"', '<', '>', '|', '\0']
        sanitized = filename
        for char in dangerous_chars:
            sanitized = sanitized.replace(char, '_')
        
        # 長さ制限
        if len(sanitized) > 255:
            name, ext = os.path.splitext(sanitized)
            sanitized = name[:255-len(ext)] + ext
        
        return sanitized
```

### SQLインジェクション対策

```python
import sqlite3
from typing import List, Tuple, Any

class SecureDatabase:
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    async def execute_query(self, query: str, params: Tuple[Any, ...] = ()) -> List[Tuple]:
        """安全なクエリ実行"""
        # プリペアドステートメントを使用
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                return cursor.fetchall()
        except sqlite3.Error as e:
            logger.error(f"データベースエラー: {e}")
            raise DatabaseSecurityError("データベース操作に失敗しました")
    
    async def insert_user_data(self, user_id: int, username: str, data: str) -> bool:
        """ユーザーデータ安全挿入"""
        query = "INSERT INTO users (user_id, username, data) VALUES (?, ?, ?)"
        try:
            await self.execute_query(query, (user_id, username, data))
            return True
        except Exception as e:
            logger.error(f"ユーザーデータ挿入エラー: {e}")
            return False
```

## 認証・認可

### 権限管理

```python
from enum import Enum
from functools import wraps
import discord
from discord.ext import commands

class PermissionLevel(Enum):
    USER = 1
    MODERATOR = 2
    ADMIN = 3
    OWNER = 4

class PermissionManager:
    def __init__(self):
        self.admin_roles = ["管理者", "Admin", "Moderator"]
        self.owner_ids = [123456789012345678]  # オーナーのDiscord ID
    
    def get_permission_level(self, member: discord.Member) -> PermissionLevel:
        """権限レベル取得"""
        if member.id in self.owner_ids:
            return PermissionLevel.OWNER
        
        if member.guild_permissions.administrator:
            return PermissionLevel.ADMIN
        
        for role in member.roles:
            if role.name in self.admin_roles:
                return PermissionLevel.MODERATOR
        
        return PermissionLevel.USER
    
    def require_permission(self, required_level: PermissionLevel):
        """権限チェックデコレータ"""
        def decorator(func):
            @wraps(func)
            async def wrapper(ctx, *args, **kwargs):
                if isinstance(ctx, commands.Context):
                    user_level = self.get_permission_level(ctx.author)
                elif hasattr(ctx, 'user'):  # Interaction
                    user_level = self.get_permission_level(ctx.user)
                else:
                    raise SecurityError("権限チェックに失敗しました")
                
                if user_level.value < required_level.value:
                    raise InsufficientPermissionError("この操作を実行する権限がありません")
                
                return await func(ctx, *args, **kwargs)
            return wrapper
        return decorator
```

### セッション管理

```python
import secrets
import time
from typing import Dict, Optional

class SessionManager:
    def __init__(self, session_timeout: int = 3600):
        self.sessions: Dict[str, dict] = {}
        self.session_timeout = session_timeout
    
    def create_session(self, user_id: int) -> str:
        """セッション作成"""
        session_id = secrets.token_urlsafe(32)
        self.sessions[session_id] = {
            'user_id': user_id,
            'created_at': time.time(),
            'last_activity': time.time()
        }
        return session_id
    
    def validate_session(self, session_id: str) -> Optional[int]:
        """セッション検証"""
        if session_id not in self.sessions:
            return None
        
        session = self.sessions[session_id]
        current_time = time.time()
        
        # タイムアウトチェック
        if current_time - session['last_activity'] > self.session_timeout:
            del self.sessions[session_id]
            return None
        
        # 最終活動時刻更新
        session['last_activity'] = current_time
        return session['user_id']
    
    def invalidate_session(self, session_id: str) -> bool:
        """セッション無効化"""
        if session_id in self.sessions:
            del self.sessions[session_id]
            return True
        return False
```

## データ保護

### 暗号化

```python
from cryptography.fernet import Fernet
import base64
import os

class DataEncryption:
    def __init__(self, key: bytes = None):
        if key is None:
            key = os.environ.get('ENCRYPTION_KEY')
            if key:
                key = base64.urlsafe_b64decode(key.encode())
            else:
                key = Fernet.generate_key()
        
        self.cipher = Fernet(key)
    
    def encrypt_data(self, data: str) -> str:
        """データ暗号化"""
        try:
            encrypted = self.cipher.encrypt(data.encode())
            return base64.urlsafe_b64encode(encrypted).decode()
        except Exception as e:
            raise EncryptionError(f"暗号化に失敗しました: {e}")
    
    def decrypt_data(self, encrypted_data: str) -> str:
        """データ復号化"""
        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted = self.cipher.decrypt(encrypted_bytes)
            return decrypted.decode()
        except Exception as e:
            raise DecryptionError(f"復号化に失敗しました: {e}")
    
    @staticmethod
    def generate_key() -> str:
        """暗号化キー生成"""
        key = Fernet.generate_key()
        return base64.urlsafe_b64encode(key).decode()
```

### 個人情報保護

```python
import hashlib
import re
from typing import Optional

class PrivacyProtection:
    def __init__(self):
        self.pii_patterns = {
            'email': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
            'phone': re.compile(r'\b\d{3}-\d{4}-\d{4}\b'),
            'credit_card': re.compile(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b')
        }
    
    def anonymize_user_id(self, user_id: int, salt: str = "") -> str:
        """ユーザーID匿名化"""
        data = f"{user_id}{salt}".encode()
        return hashlib.sha256(data).hexdigest()[:16]
    
    def detect_pii(self, text: str) -> dict:
        """個人情報検出"""
        detected = {}
        for pii_type, pattern in self.pii_patterns.items():
            matches = pattern.findall(text)
            if matches:
                detected[pii_type] = len(matches)
        return detected
    
    def mask_sensitive_data(self, text: str) -> str:
        """機密データマスク"""
        masked_text = text
        for pii_type, pattern in self.pii_patterns.items():
            masked_text = pattern.sub('[REDACTED]', masked_text)
        return masked_text
```

## レート制限・DDoS対策

### レート制限

```python
import time
from collections import defaultdict, deque
from typing import Dict

class RateLimiter:
    def __init__(self, max_requests: int = 10, time_window: int = 60):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests: Dict[int, deque] = defaultdict(deque)
    
    def is_rate_limited(self, user_id: int) -> bool:
        """レート制限チェック"""
        current_time = time.time()
        user_requests = self.requests[user_id]
        
        # 古いリクエストを削除
        while user_requests and current_time - user_requests[0] > self.time_window:
            user_requests.popleft()
        
        # リクエスト数チェック
        if len(user_requests) >= self.max_requests:
            return True
        
        # 新しいリクエストを記録
        user_requests.append(current_time)
        return False
    
    def get_remaining_requests(self, user_id: int) -> int:
        """残りリクエスト数取得"""
        current_time = time.time()
        user_requests = self.requests[user_id]
        
        # 古いリクエストを削除
        while user_requests and current_time - user_requests[0] > self.time_window:
            user_requests.popleft()
        
        return max(0, self.max_requests - len(user_requests))
```

## ログ・監査

### セキュリティログ

```python
import logging
import json
from datetime import datetime
from typing import Dict, Any

class SecurityLogger:
    def __init__(self, log_file: str = "security.log"):
        self.logger = logging.getLogger("security")
        self.logger.setLevel(logging.INFO)
        
        handler = logging.FileHandler(log_file)
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
    
    def log_security_event(self, event_type: str, user_id: int, details: Dict[str, Any]):
        """セキュリティイベントログ"""
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'event_type': event_type,
            'user_id': user_id,
            'details': details
        }
        
        self.logger.info(json.dumps(log_data, ensure_ascii=False))
    
    def log_failed_authentication(self, user_id: int, reason: str):
        """認証失敗ログ"""
        self.log_security_event(
            'authentication_failed',
            user_id,
            {'reason': reason}
        )
    
    def log_permission_violation(self, user_id: int, attempted_action: str):
        """権限違反ログ"""
        self.log_security_event(
            'permission_violation',
            user_id,
            {'attempted_action': attempted_action}
        )
    
    def log_suspicious_activity(self, user_id: int, activity: str, risk_level: str):
        """不審な活動ログ"""
        self.log_security_event(
            'suspicious_activity',
            user_id,
            {'activity': activity, 'risk_level': risk_level}
        )
```

## 脆弱性対策

### 依存関係管理

```python
import subprocess
import json
from typing import List, Dict

class VulnerabilityScanner:
    def __init__(self):
        pass
    
    def scan_dependencies(self) -> Dict[str, Any]:
        """依存関係脆弱性スキャン"""
        try:
            # safety check実行
            result = subprocess.run(
                ['safety', 'check', '--json'],
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode == 0:
                return {'status': 'safe', 'vulnerabilities': []}
            else:
                vulnerabilities = json.loads(result.stdout)
                return {
                    'status': 'vulnerable',
                    'vulnerabilities': vulnerabilities
                }
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    def check_outdated_packages(self) -> List[Dict[str, str]]:
        """古いパッケージチェック"""
        try:
            result = subprocess.run(
                ['pip', 'list', '--outdated', '--format=json'],
                capture_output=True,
                text=True,
                check=True
            )
            return json.loads(result.stdout)
        except Exception as e:
            logger.error(f"パッケージチェックエラー: {e}")
            return []
```

## エラーハンドリング

### セキュリティ例外

```python
class SecurityError(Exception):
    """セキュリティ関連のエラー"""
    pass

class InsufficientPermissionError(SecurityError):
    """権限不足エラー"""
    pass

class AuthenticationError(SecurityError):
    """認証エラー"""
    pass

class EncryptionError(SecurityError):
    """暗号化エラー"""
    pass

class DecryptionError(SecurityError):
    """復号化エラー"""
    pass

class DatabaseSecurityError(SecurityError):
    """データベースセキュリティエラー"""
    pass

class RateLimitExceededError(SecurityError):
    """レート制限超過エラー"""
    pass
```

## セキュリティチェックリスト

### 開発時チェック項目

- [ ] 全ての入力データを検証・サニタイズしている
- [ ] SQLインジェクション対策を実装している
- [ ] 適切な権限チェックを行っている
- [ ] 機密データを暗号化している
- [ ] レート制限を実装している
- [ ] セキュリティログを記録している
- [ ] 依存関係の脆弱性をチェックしている
- [ ] エラーメッセージで機密情報を漏洩していない

### 運用時チェック項目

- [ ] 定期的なセキュリティスキャンを実施している
- [ ] ログを監視している
- [ ] 依存関係を最新に保っている
- [ ] バックアップを暗号化している
- [ ] アクセス制御を適切に設定している

## 関連ドキュメント

- [認証システム](../02-core/02-authentication-system.md)
- [エラーハンドリング](../02-core/04-error-handling.md)
- [データベース管理](../04-utilities/01-database-management.md)
- [監視とデバッグ](02-monitoring-debugging.md)
