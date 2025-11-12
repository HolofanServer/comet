# 設定管理

## C.O.M.E.T.について

**C.O.M.E.T.**の名前は以下の頭文字から構成されています：

- **C**ommunity of
- **O**shilove
- **M**oderation &
- **E**njoyment
- **T**ogether

HFS - ホロライブ非公式ファンサーバーのコミュニティを支える、推し愛とモデレーション、そして楽しさを一緒に提供するボットです。

## 概要

COMETボットの設定管理システムは、環境変数、JSONファイル、データベース設定を統合的に管理し、開発環境と本番環境での柔軟な設定切り替えを可能にします。

## 設定管理アーキテクチャ

```
┌─────────────────────────────────────────────────────────────┐
│                    設定管理システム                          │
├─────────────────────────────────────────────────────────────┤
│  環境変数 (.env)                                             │
│  ├── BOT_TOKEN                                              │
│  ├── ADMIN_GUILD_IDS                                        │
│  ├── CHANNEL_IDS                                            │
│  └── API_KEYS                                               │
├─────────────────────────────────────────────────────────────┤
│  JSONファイル設定 (config/)                                  │
│  ├── bot.json - ボット基本設定                               │
│  ├── version.json - バージョン情報                           │
│  ├── database.json - データベース設定                        │
│  └── features.json - 機能フラグ                              │
├─────────────────────────────────────────────────────────────┤
│  動的設定 (データベース)                                      │
│  ├── ギルド固有設定                                          │
│  ├── ユーザー設定                                            │
│  ├── 機能設定                                                │
│  └── 一時的設定                                              │
├─────────────────────────────────────────────────────────────┤
│  設定管理サービス                                            │
│  ├── ConfigurationService                                   │
│  ├── EnvironmentManager                                     │
│  ├── SettingsValidator                                      │
│  └── ConfigurationWatcher                                   │
└─────────────────────────────────────────────────────────────┘
```

## 環境変数設定

### .env ファイル構造

**場所**: [`.env.example`](../.env.example)

```env
# Discord Bot Configuration
BOT_TOKEN=your_discord_bot_token_here
COMMAND_PREFIX=!

# Guild and Channel IDs
ADMIN_MAIN_GUILD_ID=123456789012345678
ADMIN_DEV_GUILD_ID=876543210987654321
ADMIN_STARTUP_CHANNEL_ID=111111111111111111
ADMIN_BUG_REPORT_CHANNEL_ID=222222222222222222
ADMIN_ERROR_LOG_CHANNEL_ID=333333333333333333

# Authentication
AUTH_TOKEN=your_auth_token_here
AUTH_URL=https://your-auth-endpoint.com/api

# External Services
SENTRY_DSN=your_sentry_dsn_here
WEBHOOK_URL=your_webhook_url_here

# Feature Flags
ENABLE_ANALYTICS=true
ENABLE_MONITORING=true
DEBUG_MODE=false

# Database Configuration
DATABASE_URL=sqlite:///config/bot.db
DATABASE_POOL_SIZE=10

# Monitoring
PROMETHEUS_ENABLED=false
PROMETHEUS_PORT=8001
UPTIME_KUMA_URL=your_uptime_kuma_url

# Development Settings
ENVIRONMENT=production
LOG_LEVEL=INFO
```

### 環境変数の読み込み

**場所**: [`config/setting.py`](../config/setting.py)

```python
import os
from dotenv import load_dotenv
from typing import Optional, Union

load_dotenv()

class EnvironmentConfig:
    @staticmethod
    def get_str(key: str, default: Optional[str] = None) -> str:
        value = os.getenv(key, default)
        if value is None:
            raise ValueError(f"Environment variable {key} is required")
        return value
    
    @staticmethod
    def get_int(key: str, default: Optional[int] = None) -> int:
        value = os.getenv(key)
        if value is None:
            if default is not None:
                return default
            raise ValueError(f"Environment variable {key} is required")
        return int(value)
    
    @staticmethod
    def get_bool(key: str, default: bool = False) -> bool:
        value = os.getenv(key, str(default)).lower()
        return value in ('true', '1', 'yes', 'on')
    
    @staticmethod
    def get_list(key: str, separator: str = ',', default: Optional[list] = None) -> list:
        value = os.getenv(key)
        if value is None:
            return default or []
        return [item.strip() for item in value.split(separator)]

# 基本設定
TOKEN = EnvironmentConfig.get_str('BOT_TOKEN')
command_prefix = EnvironmentConfig.get_str('COMMAND_PREFIX', '!')

# ギルドとチャンネルID
main_guild_id = EnvironmentConfig.get_int('ADMIN_MAIN_GUILD_ID')
dev_guild_id = EnvironmentConfig.get_int('ADMIN_DEV_GUILD_ID')
startup_channel_id = EnvironmentConfig.get_int('ADMIN_STARTUP_CHANNEL_ID')
error_log_channel_id = EnvironmentConfig.get_int('ADMIN_ERROR_LOG_CHANNEL_ID')

# 機能フラグ
ENABLE_ANALYTICS = EnvironmentConfig.get_bool('ENABLE_ANALYTICS')
ENABLE_MONITORING = EnvironmentConfig.get_bool('ENABLE_MONITORING')
DEBUG_MODE = EnvironmentConfig.get_bool('DEBUG_MODE')
```

## JSONファイル設定

### ボット基本設定 (bot.json)

**場所**: [`config/bot.json`](../config/bot.json)

```json
{
    "bot_info": {
        "name": "COMET",
        "version": "2.1.0",
        "description": "HFS専属BOT 総合ガイド",
        "author": "FreeWiFiTech",
        "support_server": "https://discord.gg/hfs"
    },
    "features": {
        "moderation": {
            "enabled": true,
            "auto_mod": true,
            "log_actions": true
        },
        "entertainment": {
            "enabled": true,
            "omikuji": true,
            "giveaway": true
        },
        "analytics": {
            "enabled": true,
            "user_tracking": true,
            "server_stats": true
        }
    },
    "limits": {
        "max_warnings": 3,
        "cooldown_duration": 300,
        "max_giveaway_entries": 1000
    },
    "default_settings": {
        "language": "ja",
        "timezone": "Asia/Tokyo",
        "date_format": "%Y-%m-%d %H:%M:%S"
    }
}
```

### バージョン管理 (version.json)

```json
{
    "version": "2.1.0",
    "build": "20250827",
    "release_date": "2025-08-27",
    "changelog": [
        {
            "version": "2.1.0",
            "date": "2025-08-27",
            "changes": [
                "Added comprehensive wiki documentation",
                "Improved error handling system",
                "Enhanced monitoring capabilities"
            ]
        }
    ],
    "compatibility": {
        "min_python_version": "3.8",
        "discord_py_version": "2.6.2",
        "required_intents": ["all"]
    }
}
```

### データベース設定 (database.json)

```json
{
    "connections": {
        "primary": {
            "type": "sqlite",
            "path": "config/bot.db",
            "pool_size": 10,
            "timeout": 30
        },
        "analytics": {
            "type": "sqlite",
            "path": "config/analytics.db",
            "pool_size": 5,
            "timeout": 15
        }
    },
    "migrations": {
        "auto_migrate": true,
        "backup_before_migration": true,
        "migration_path": "migrations/"
    },
    "maintenance": {
        "auto_vacuum": true,
        "vacuum_interval": 86400,
        "backup_interval": 604800
    }
}
```

## 設定管理サービス

### ConfigurationService クラス

```python
import json
import os
from typing import Any, Dict, Optional
from pathlib import Path

class ConfigurationService:
    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self.config_cache = {}
        self.watchers = {}
    
    def load_config(self, config_name: str) -> Dict[str, Any]:
        """JSONファイルから設定を読み込み"""
        if config_name in self.config_cache:
            return self.config_cache[config_name]
        
        config_path = self.config_dir / f"{config_name}.json"
        
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file {config_path} not found")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        self.config_cache[config_name] = config
        return config
    
    def save_config(self, config_name: str, data: Dict[str, Any]) -> None:
        """設定をJSONファイルに保存"""
        config_path = self.config_dir / f"{config_name}.json"
        
        # バックアップ作成
        if config_path.exists():
            backup_path = config_path.with_suffix('.json.bak')
            config_path.rename(backup_path)
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        
        # キャッシュ更新
        self.config_cache[config_name] = data
    
    def get_nested_value(self, config_name: str, key_path: str, default: Any = None) -> Any:
        """ネストされた設定値を取得"""
        config = self.load_config(config_name)
        keys = key_path.split('.')
        
        current = config
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
        
        return current
    
    def set_nested_value(self, config_name: str, key_path: str, value: Any) -> None:
        """ネストされた設定値を設定"""
        config = self.load_config(config_name)
        keys = key_path.split('.')
        
        current = config
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        current[keys[-1]] = value
        self.save_config(config_name, config)
    
    def reload_config(self, config_name: str) -> Dict[str, Any]:
        """設定を再読み込み"""
        if config_name in self.config_cache:
            del self.config_cache[config_name]
        return self.load_config(config_name)
```

### 環境管理

```python
class EnvironmentManager:
    def __init__(self):
        self.environment = os.getenv('ENVIRONMENT', 'development')
        self.config_service = ConfigurationService()
    
    def is_development(self) -> bool:
        return self.environment == 'development'
    
    def is_production(self) -> bool:
        return self.environment == 'production'
    
    def get_environment_config(self) -> Dict[str, Any]:
        """環境固有の設定を取得"""
        base_config = self.config_service.load_config('bot')
        env_config_path = f"bot_{self.environment}"
        
        try:
            env_config = self.config_service.load_config(env_config_path)
            return self._merge_configs(base_config, env_config)
        except FileNotFoundError:
            return base_config
    
    def _merge_configs(self, base: Dict, override: Dict) -> Dict:
        """設定をマージ"""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value
        return result
```

## 動的設定管理

### ギルド固有設定

```python
class GuildSettingsManager:
    def __init__(self, db_service):
        self.db_service = db_service
    
    async def get_guild_setting(self, guild_id: int, setting_key: str, default: Any = None) -> Any:
        """ギルド固有の設定を取得"""
        query = "SELECT setting_value FROM guild_settings WHERE guild_id = ? AND setting_key = ?"
        result = await self.db_service.fetch_one(query, (guild_id, setting_key))
        
        if result:
            return json.loads(result['setting_value'])
        return default
    
    async def set_guild_setting(self, guild_id: int, setting_key: str, value: Any) -> None:
        """ギルド固有の設定を保存"""
        query = """
        INSERT OR REPLACE INTO guild_settings (guild_id, setting_key, setting_value, updated_at)
        VALUES (?, ?, ?, ?)
        """
        await self.db_service.execute_query(
            query, 
            (guild_id, setting_key, json.dumps(value), datetime.now().isoformat())
        )
    
    async def get_all_guild_settings(self, guild_id: int) -> Dict[str, Any]:
        """ギルドの全設定を取得"""
        query = "SELECT setting_key, setting_value FROM guild_settings WHERE guild_id = ?"
        results = await self.db_service.fetch_all(query, (guild_id,))
        
        settings = {}
        for row in results:
            settings[row['setting_key']] = json.loads(row['setting_value'])
        
        return settings
```

### 機能フラグ管理

```python
class FeatureFlagManager:
    def __init__(self, config_service: ConfigurationService):
        self.config_service = config_service
        self.flags_cache = {}
    
    def is_feature_enabled(self, feature_name: str, guild_id: Optional[int] = None) -> bool:
        """機能フラグの状態を確認"""
        # グローバル設定を確認
        global_flag = self.config_service.get_nested_value(
            'bot', 
            f'features.{feature_name}.enabled', 
            False
        )
        
        if not global_flag:
            return False
        
        # ギルド固有の設定を確認（実装時）
        if guild_id:
            # ギルド固有の機能フラグロジック
            pass
        
        return True
    
    def set_feature_flag(self, feature_name: str, enabled: bool, guild_id: Optional[int] = None) -> None:
        """機能フラグを設定"""
        if guild_id:
            # ギルド固有の設定
            pass
        else:
            # グローバル設定
            self.config_service.set_nested_value(
                'bot',
                f'features.{feature_name}.enabled',
                enabled
            )
    
    def get_feature_config(self, feature_name: str) -> Dict[str, Any]:
        """機能の詳細設定を取得"""
        return self.config_service.get_nested_value(
            'bot',
            f'features.{feature_name}',
            {}
        )
```

## 設定検証

### SettingsValidator クラス

```python
from typing import List, Tuple
import re

class SettingsValidator:
    def __init__(self):
        self.validation_rules = {
            'BOT_TOKEN': self._validate_discord_token,
            'ADMIN_MAIN_GUILD_ID': self._validate_snowflake,
            'ADMIN_DEV_GUILD_ID': self._validate_snowflake,
            'WEBHOOK_URL': self._validate_url,
        }
    
    def validate_environment(self) -> List[Tuple[str, str]]:
        """環境変数を検証"""
        errors = []
        
        for key, validator in self.validation_rules.items():
            value = os.getenv(key)
            if value is None:
                errors.append((key, "Required environment variable is missing"))
                continue
            
            try:
                validator(value)
            except ValueError as e:
                errors.append((key, str(e)))
        
        return errors
    
    def _validate_discord_token(self, token: str) -> None:
        """Discordトークンの形式を検証"""
        if not re.match(r'^[A-Za-z0-9._-]+$', token):
            raise ValueError("Invalid Discord token format")
        
        if len(token) < 50:
            raise ValueError("Discord token too short")
    
    def _validate_snowflake(self, snowflake: str) -> None:
        """Discord Snowflakeの形式を検証"""
        try:
            value = int(snowflake)
            if value <= 0:
                raise ValueError("Snowflake must be positive")
        except ValueError:
            raise ValueError("Invalid snowflake format")
    
    def _validate_url(self, url: str) -> None:
        """URLの形式を検証"""
        if not re.match(r'^https?://', url):
            raise ValueError("URL must start with http:// or https://")
    
    def validate_config_file(self, config_name: str) -> List[str]:
        """設定ファイルを検証"""
        errors = []
        
        try:
            config = ConfigurationService().load_config(config_name)
            
            # 必須フィールドの確認
            required_fields = self._get_required_fields(config_name)
            for field in required_fields:
                if not self._has_nested_key(config, field):
                    errors.append(f"Missing required field: {field}")
            
        except Exception as e:
            errors.append(f"Failed to load config: {str(e)}")
        
        return errors
    
    def _get_required_fields(self, config_name: str) -> List[str]:
        """設定ファイルの必須フィールドを取得"""
        required_fields = {
            'bot': [
                'bot_info.name',
                'bot_info.version',
                'features',
                'limits'
            ],
            'database': [
                'connections.primary.type',
                'connections.primary.path'
            ]
        }
        return required_fields.get(config_name, [])
    
    def _has_nested_key(self, data: Dict, key_path: str) -> bool:
        """ネストされたキーの存在を確認"""
        keys = key_path.split('.')
        current = data
        
        for key in keys:
            if not isinstance(current, dict) or key not in current:
                return False
            current = current[key]
        
        return True
```

## 設定の監視と自動更新

### ConfigurationWatcher クラス

```python
import asyncio
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class ConfigurationWatcher(FileSystemEventHandler):
    def __init__(self, config_service: ConfigurationService, callback: callable):
        self.config_service = config_service
        self.callback = callback
        self.observer = Observer()
    
    def start_watching(self, config_dir: str) -> None:
        """設定ファイルの監視を開始"""
        self.observer.schedule(self, config_dir, recursive=False)
        self.observer.start()
    
    def stop_watching(self) -> None:
        """監視を停止"""
        self.observer.stop()
        self.observer.join()
    
    def on_modified(self, event):
        """ファイル変更時の処理"""
        if event.is_directory:
            return
        
        if event.src_path.endswith('.json'):
            config_name = Path(event.src_path).stem
            
            # 設定を再読み込み
            try:
                new_config = self.config_service.reload_config(config_name)
                asyncio.create_task(self.callback(config_name, new_config))
            except Exception as e:
                logger.error(f"Failed to reload config {config_name}: {e}")
```

## 設定のバックアップと復元

### ConfigurationBackup クラス

```python
import shutil
from datetime import datetime
import tarfile

class ConfigurationBackup:
    def __init__(self, config_dir: str = "config", backup_dir: str = "backups"):
        self.config_dir = Path(config_dir)
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(exist_ok=True)
    
    def create_backup(self, backup_name: Optional[str] = None) -> str:
        """設定のバックアップを作成"""
        if backup_name is None:
            backup_name = f"config_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        backup_path = self.backup_dir / f"{backup_name}.tar.gz"
        
        with tarfile.open(backup_path, 'w:gz') as tar:
            tar.add(self.config_dir, arcname='config')
        
        return str(backup_path)
    
    def restore_backup(self, backup_path: str) -> None:
        """バックアップから設定を復元"""
        backup_file = Path(backup_path)
        
        if not backup_file.exists():
            raise FileNotFoundError(f"Backup file {backup_path} not found")
        
        # 現在の設定をバックアップ
        current_backup = self.create_backup("pre_restore")
        
        try:
            # 設定ディレクトリを削除
            if self.config_dir.exists():
                shutil.rmtree(self.config_dir)
            
            # バックアップから復元
            with tarfile.open(backup_file, 'r:gz') as tar:
                tar.extractall(self.config_dir.parent)
            
        except Exception as e:
            # 復元に失敗した場合、元の設定を復元
            self.restore_backup(current_backup)
            raise e
    
    def list_backups(self) -> List[str]:
        """利用可能なバックアップのリストを取得"""
        backups = []
        for backup_file in self.backup_dir.glob("*.tar.gz"):
            backups.append(backup_file.name)
        return sorted(backups, reverse=True)
```

---

## 関連ドキュメント

- [ボットアーキテクチャ概要](01-bot-architecture-overview.md)
- [アプリケーション起動フロー](02-application-startup-flow.md)
- [サービス層アーキテクチャ](03-service-layer-architecture.md)
- [開発環境セットアップ](../05-development/01-development-setup.md)
