# ログシステム

## 概要

HFS専属ボットは、カラーコンソール出力、ファイルログ、構造化ログデータ管理を備えた包括的なログシステムを実装しています。

## ログアーキテクチャ

### コアコンポーネント

#### 1. カスタムフォーマッター (`CustomFormatter`)
異なるログレベルに対してカラーコンソール出力を提供します:

```python
class CustomFormatter(Formatter):
    FORMATS = {
        DEBUG: blue + format + reset,
        INFO: white + format + reset,
        WARNING: yellow + format + reset,
        ERROR: red + format + reset,
        CRITICAL: bold_red + format + reset
    }
```

**カラースキーム**:
- **DEBUG**: 青
- **INFO**: 白  
- **WARNING**: 黄
- **ERROR**: 赤
- **CRITICAL**: 太字赤

#### 2. セットアップ関数 (`setup_logging`)
複数のモードを持つ設定可能なログセットアップ:

```python
def setup_logging(mode: Optional[str] = None):
    # Supports: "debug", "info", "warning", "error", "critical", "api"
```

**利用可能なモード**:
- `"debug"` または `"D"`: デバッグレベルログ
- `"info"` または `"I"`: 情報レベルログ  
- `"warning"` または `"W"`: 警告レベルログ
- `"error"` または `"E"`: エラーレベルログ
- `"critical"` または `"C"`: 重要レベルログ
- `"api"` または `"API"`: ファイル出力付き特別APIログ

### ログデータ管理

#### 構造化ログストレージ (`save_log`)
自動アーカイブ機能付きでJSONファイルとして構造化ログデータを保存します:

```python
def save_log(log_data):
    # Creates timestamped directories: data/logging/YYYY-MM-DD/HH-MM-SS/
    # Generates UUID-based filenames
    # Automatically archives old logs (keeps 10 most recent days)
```

**ディレクトリ構造**:
```
data/
└── logging/
    ├── 2024-01-01/
    │   ├── 12-30-45/
    │   │   └── uuid-filename.json
    │   └── 14-15-30/
    └── archive/
        └── older-logs/
```

**ログデータ形式**:
```json
{
  "event": "BotReady",
  "description": "Bot has successfully connected to Discord",
  "timestamp": "2024-01-01 12:00:00",
  "session_id": "session_123",
  "additional_data": {}
}
```

### ログモード

#### 1. 標準コンソールログ
カラー出力付きのデフォルトコンソールログ:
```python
logger = setup_logging("info")
logger.info("Bot started successfully")
```

#### 2. APIログモード
コンソールとファイル出力の両方を持つAPI操作用の特別なログモード:
```python
api_logger = setup_logging("api")
# Logs to both console and data/logging/api/api.log
```

#### 3. デバッグモード
開発用の拡張ログ:
```python
debug_logger = setup_logging("debug")
# Shows detailed debug information
```

## 使用パターン

### Cogs内での使用
```python
from utils.logging import setup_logging

logger = setup_logging(__name__)

class MyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        logger.info(f"{self.__class__.__name__} initialized")
    
    async def some_method(self):
        try:
            # Operation
            logger.info("Operation completed successfully")
        except Exception as e:
            logger.error(f"Operation failed: {e}")
```

### 構造化イベントログ
```python
from utils.logging import save_log

# Log important events
log_data = {
    "event": "UserJoin",
    "description": f"User {user.name} joined the server",
    "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    "user_id": user.id,
    "guild_id": guild.id
}
save_log(log_data)
```

### エラー追跡
```python
try:
    await risky_operation()
except Exception as e:
    logger.error(f"Risky operation failed: {e}")
    logger.error(traceback.format_exc())  # Full stack trace
    
    # Structured error logging
    error_data = {
        "event": "Error",
        "error_type": type(e).__name__,
        "error_message": str(e),
        "stack_trace": traceback.format_exc(),
        "timestamp": datetime.now().isoformat()
    }
    save_log(error_data)
```

## ログ管理

### 自動アーカイブ
システムは自動的にログストレージを管理します:
- 最新10日間のログを保持
- 古いログを`archive/`ディレクトリにアーカイブ
- ログ蓄積によるディスク容量問題を防止

### ファイル構成
```
data/logging/
├── 2024-01-15/          # Today's logs
│   ├── 09-30-15/        # Morning session
│   ├── 14-45-30/        # Afternoon session
│   └── 20-15-45/        # Evening session
├── 2024-01-14/          # Yesterday's logs
├── archive/             # Archived logs
│   └── 2024-01-01/      # Older archived logs
└── api/                 # API-specific logs
    └── api.log
```

### ログローテーション
- 日次ログディレクトリ
- セッションベースのサブディレクトリ
- UUIDベースの個別ログファイル
- 古いログの自動クリーンアップ

## ボットシステムとの統合

### メインボットログ
```python
# In main.py
from utils.logging import setup_logging, save_log

logger = setup_logging(__name__)

async def on_ready(self):
    log_data = {
        "event": "BotReady",
        "description": f"{self.user} has successfully connected to Discord",
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "session_id": session_id
    }
    save_log(log_data)
```

### エラーハンドラー統合
```python
async def on_command_error(self, ctx, error):
    logger.error(f"Command error: {error}")
    
    error_log = {
        "event": "CommandError",
        "command": ctx.command.name if ctx.command else "unknown",
        "error": str(error),
        "user_id": ctx.author.id,
        "guild_id": ctx.guild.id if ctx.guild else None,
        "timestamp": datetime.now().isoformat()
    }
    save_log(error_log)
```

## パフォーマンス考慮事項

### 効率的なログ
- 遅延文字列フォーマット: `logger.info("User %s joined", user.name)`
- 条件付きデバッグログ: `if logger.isEnabledFor(DEBUG):`
- 非同期セーフなログ操作

### ストレージ管理
- 自動ログローテーションによりディスク容量問題を防止
- JSON形式により簡単な解析と分析が可能
- UUIDファイル名により命名競合を防止

---

## 関連ドキュメント

- [エラーハンドリング](../02-core/04-error-handling.md)
- [設定管理](../01-architecture/04-configuration-management.md)
- [開発セットアップ](../05-development/01-development-setup.md)
- [監視とデバッグ](../05-development/02-monitoring-debugging.md)
