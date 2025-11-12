# ログシステム

## C.O.M.E.T.について

**C.O.M.E.T.**の名前は以下の頭文字から構成されています：

- **C**ommunity of
- **O**shilove
- **M**oderation &
- **E**njoyment
- **T**ogether

HFS - ホロライブ非公式ファンサーバーのコミュニティを支える、推し愛とモデレーション、そして楽しさを一緒に提供するボットです。

## 概要

COMETボットのログシステムは、包括的なログ記録、構造化ログ、リアルタイム監視、ログ分析機能を提供します。開発、デバッグ、運用監視、セキュリティ監査のすべてのニーズに対応します。

## ログシステムアーキテクチャ

```
┌─────────────────────────────────────────────────────────────┐
│                    ログシステムアーキテクチャ                 │
├─────────────────────────────────────────────────────────────┤
│  ログ生成層 (Log Generation)                                 │
│  ├── アプリケーションログ                                    │
│  ├── セキュリティログ                                        │
│  ├── パフォーマンスログ                                      │
│  └── 監査ログ                                                │
├─────────────────────────────────────────────────────────────┤
│  ログ処理層 (Log Processing)                                 │
│  ├── ログフォーマッター                                      │
│  ├── ログフィルター                                          │
│  ├── ログエンリッチャー                                      │
│  └── ログバリデーター                                        │
├─────────────────────────────────────────────────────────────┤
│  ログ配信層 (Log Distribution)                               │
│  ├── ファイルハンドラー                                      │
│  ├── コンソールハンドラー                                    │
│  ├── Webhookハンドラー                                       │
│  └── データベースハンドラー                                  │
├─────────────────────────────────────────────────────────────┤
│  ログ保存層 (Log Storage)                                    │
│  ├── ローカルファイル                                        │
│  ├── データベース                                            │
│  ├── 外部ログサービス                                        │
│  └── アーカイブストレージ                                    │
└─────────────────────────────────────────────────────────────┘
```

## ログ設定とセットアップ

### 1. ログ設定クラス

**場所**: [`utils/logging.py`](../utils/logging.py)

```python
import logging
import logging.handlers
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional
import pytz

class COMETLogger:
    def __init__(self, name: str = "COMET", level: str = "INFO"):
        self.name = name
        self.level = getattr(logging, level.upper())
        self.logger = self._setup_logger()
        self.session_id = self._generate_session_id()
        
    def _setup_logger(self) -> logging.Logger:
        """ロガーの初期化"""
        logger = logging.getLogger(self.name)
        logger.setLevel(self.level)
        
        # 既存のハンドラーをクリア
        logger.handlers.clear()
        
        # フォーマッターの設定
        formatter = self._create_formatter()
        
        # コンソールハンドラー
        console_handler = logging.StreamHandler()
        console_handler.setLevel(self.level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # ファイルハンドラー
        file_handler = self._create_file_handler()
        file_handler.setLevel(self.level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        # エラー専用ハンドラー
        error_handler = self._create_error_handler()
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        logger.addHandler(error_handler)
        
        return logger
    
    def _create_formatter(self) -> logging.Formatter:
        """ログフォーマッターの作成"""
        format_string = (
            '%(asctime)s - %(name)s - %(levelname)s - '
            '[%(filename)s:%(lineno)d] - %(message)s'
        )
        
        formatter = logging.Formatter(
            format_string,
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # 日本時間の設定
        formatter.converter = lambda *args: datetime.now(
            pytz.timezone('Asia/Tokyo')
        ).timetuple()
        
        return formatter
    
    def _create_file_handler(self) -> logging.handlers.RotatingFileHandler:
        """ファイルハンドラーの作成"""
        log_dir = "logs"
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = os.path.join(log_dir, f"{self.name.lower()}.log")
        
        handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        
        return handler
    
    def _create_error_handler(self) -> logging.handlers.RotatingFileHandler:
        """エラー専用ハンドラーの作成"""
        log_dir = "logs"
        error_file = os.path.join(log_dir, f"{self.name.lower()}_error.log")
        
        handler = logging.handlers.RotatingFileHandler(
            error_file,
            maxBytes=5 * 1024 * 1024,  # 5MB
            backupCount=10,
            encoding='utf-8'
        )
        
        return handler
    
    def _generate_session_id(self) -> str:
        """セッションIDの生成"""
        import uuid
        return str(uuid.uuid4())[:8]
```

### 2. 構造化ログ

```python
class StructuredLogger:
    def __init__(self, base_logger: logging.Logger):
        self.base_logger = base_logger
        self.default_fields = {
            "service": "COMET",
            "version": "2.1.0",
            "environment": os.getenv("ENVIRONMENT", "development")
        }
    
    def log_structured(self, level: str, message: str, **kwargs) -> None:
        """構造化ログの出力"""
        log_data = {
            "timestamp": datetime.now(pytz.timezone('Asia/Tokyo')).isoformat(),
            "level": level.upper(),
            "message": message,
            **self.default_fields,
            **kwargs
        }
        
        # JSONとして出力
        json_message = json.dumps(log_data, ensure_ascii=False, separators=(',', ':'))
        
        log_level = getattr(logging, level.upper())
        self.base_logger.log(log_level, json_message)
    
    def info(self, message: str, **kwargs) -> None:
        self.log_structured("info", message, **kwargs)
    
    def warning(self, message: str, **kwargs) -> None:
        self.log_structured("warning", message, **kwargs)
    
    def error(self, message: str, **kwargs) -> None:
        self.log_structured("error", message, **kwargs)
    
    def debug(self, message: str, **kwargs) -> None:
        self.log_structured("debug", message, **kwargs)
    
    def critical(self, message: str, **kwargs) -> None:
        self.log_structured("critical", message, **kwargs)
```

### 3. イベントログ

```python
class EventLogger:
    def __init__(self, structured_logger: StructuredLogger):
        self.logger = structured_logger
    
    async def log_command_execution(self, ctx, command_name: str, success: bool, duration: float = None) -> None:
        """コマンド実行ログ"""
        event_data = {
            "event_type": "command_execution",
            "command": command_name,
            "user_id": ctx.author.id,
            "user_name": str(ctx.author),
            "guild_id": ctx.guild.id if ctx.guild else None,
            "guild_name": ctx.guild.name if ctx.guild else None,
            "channel_id": ctx.channel.id,
            "success": success,
            "duration_ms": duration * 1000 if duration else None
        }
        
        if success:
            self.logger.info("Command executed successfully", **event_data)
        else:
            self.logger.warning("Command execution failed", **event_data)
    
    async def log_user_action(self, action: str, user_id: int, guild_id: int = None, **metadata) -> None:
        """ユーザーアクションログ"""
        event_data = {
            "event_type": "user_action",
            "action": action,
            "user_id": user_id,
            "guild_id": guild_id,
            "metadata": metadata
        }
        
        self.logger.info("User action logged", **event_data)
    
    async def log_system_event(self, event: str, severity: str = "info", **details) -> None:
        """システムイベントログ"""
        event_data = {
            "event_type": "system_event",
            "event": event,
            "severity": severity,
            "details": details
        }
        
        log_method = getattr(self.logger, severity.lower(), self.logger.info)
        log_method("System event occurred", **event_data)
    
    async def log_error_event(self, error: Exception, context: Dict[str, Any] = None) -> None:
        """エラーイベントログ"""
        import traceback
        
        event_data = {
            "event_type": "error_event",
            "error_type": type(error).__name__,
            "error_message": str(error),
            "traceback": traceback.format_exc(),
            "context": context or {}
        }
        
        self.logger.error("Error occurred", **event_data)
```

## 専用ログハンドラー

### 1. Webhookハンドラー

```python
import aiohttp
import asyncio
from logging import Handler, LogRecord

class WebhookHandler(Handler):
    def __init__(self, webhook_url: str, level: int = logging.ERROR):
        super().__init__(level)
        self.webhook_url = webhook_url
        self.session = None
        
    async def emit_async(self, record: LogRecord) -> None:
        """非同期でWebhookにログを送信"""
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            # ログレコードをフォーマット
            message = self.format(record)
            
            # Discord Webhook形式
            payload = {
                "content": f"```\n{message}\n```",
                "embeds": [{
                    "title": f"{record.levelname} - {record.name}",
                    "description": record.getMessage(),
                    "color": self._get_color_for_level(record.levelno),
                    "timestamp": datetime.fromtimestamp(record.created).isoformat(),
                    "fields": [
                        {
                            "name": "ファイル",
                            "value": f"{record.filename}:{record.lineno}",
                            "inline": True
                        },
                        {
                            "name": "関数",
                            "value": record.funcName,
                            "inline": True
                        }
                    ]
                }]
            }
            
            async with self.session.post(
                self.webhook_url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status != 204:
                    print(f"Webhook送信失敗: {response.status}")
                    
        except Exception as e:
            print(f"Webhook送信エラー: {e}")
    
    def emit(self, record: LogRecord) -> None:
        """同期インターフェース"""
        try:
            loop = asyncio.get_event_loop()
            loop.create_task(self.emit_async(record))
        except RuntimeError:
            # イベントループが存在しない場合
            asyncio.run(self.emit_async(record))
    
    def _get_color_for_level(self, level: int) -> int:
        """ログレベルに応じた色を取得"""
        colors = {
            logging.DEBUG: 0x808080,    # グレー
            logging.INFO: 0x0099FF,     # 青
            logging.WARNING: 0xFF9900,  # オレンジ
            logging.ERROR: 0xFF0000,    # 赤
            logging.CRITICAL: 0x990000  # 暗赤
        }
        return colors.get(level, 0x000000)
    
    async def close(self) -> None:
        """セッションのクリーンアップ"""
        if self.session:
            await self.session.close()
```

### 2. データベースハンドラー

```python
class DatabaseHandler(Handler):
    def __init__(self, db_service, level: int = logging.INFO):
        super().__init__(level)
        self.db_service = db_service
        
    async def emit_async(self, record: LogRecord) -> None:
        """データベースにログを保存"""
        try:
            log_data = {
                "timestamp": datetime.fromtimestamp(record.created).isoformat(),
                "level": record.levelname,
                "logger_name": record.name,
                "message": record.getMessage(),
                "filename": record.filename,
                "line_number": record.lineno,
                "function_name": record.funcName,
                "thread_id": record.thread,
                "process_id": record.process
            }
            
            # 例外情報がある場合は追加
            if record.exc_info:
                import traceback
                log_data["exception"] = traceback.format_exception(*record.exc_info)
            
            query = """
            INSERT INTO logs (
                timestamp, level, logger_name, message, filename, 
                line_number, function_name, thread_id, process_id, 
                exception, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            await self.db_service.execute_query(
                query,
                (
                    log_data["timestamp"],
                    log_data["level"],
                    log_data["logger_name"],
                    log_data["message"],
                    log_data["filename"],
                    log_data["line_number"],
                    log_data["function_name"],
                    log_data["thread_id"],
                    log_data["process_id"],
                    json.dumps(log_data.get("exception")),
                    datetime.now().isoformat()
                )
            )
            
        except Exception as e:
            print(f"データベースログ保存エラー: {e}")
    
    def emit(self, record: LogRecord) -> None:
        """同期インターフェース"""
        try:
            loop = asyncio.get_event_loop()
            loop.create_task(self.emit_async(record))
        except RuntimeError:
            asyncio.run(self.emit_async(record))
```

## ログ分析とモニタリング

### 1. ログ分析器

```python
class LogAnalyzer:
    def __init__(self, db_service):
        self.db_service = db_service
    
    async def get_error_summary(self, hours: int = 24) -> Dict[str, Any]:
        """エラーサマリーの取得"""
        query = """
        SELECT 
            level,
            COUNT(*) as count,
            logger_name,
            filename
        FROM logs 
        WHERE 
            timestamp > datetime('now', '-{} hours')
            AND level IN ('ERROR', 'CRITICAL')
        GROUP BY level, logger_name, filename
        ORDER BY count DESC
        """.format(hours)
        
        results = await self.db_service.fetch_all(query, ())
        
        summary = {
            "total_errors": sum(row["count"] for row in results),
            "error_breakdown": results,
            "top_error_sources": results[:5]
        }
        
        return summary
    
    async def get_command_usage_stats(self, days: int = 7) -> Dict[str, Any]:
        """コマンド使用統計の取得"""
        query = """
        SELECT 
            JSON_EXTRACT(message, '$.command') as command,
            COUNT(*) as usage_count,
            AVG(CAST(JSON_EXTRACT(message, '$.duration_ms') AS REAL)) as avg_duration_ms
        FROM logs 
        WHERE 
            timestamp > datetime('now', '-{} days')
            AND JSON_EXTRACT(message, '$.event_type') = 'command_execution'
            AND JSON_EXTRACT(message, '$.success') = 1
        GROUP BY command
        ORDER BY usage_count DESC
        """.format(days)
        
        results = await self.db_service.fetch_all(query, ())
        
        return {
            "total_commands": sum(row["usage_count"] for row in results),
            "command_stats": results,
            "most_used_commands": results[:10]
        }
    
    async def detect_anomalies(self) -> List[Dict[str, Any]]:
        """異常の検出"""
        anomalies = []
        
        # エラー率の急増
        error_rate = await self._calculate_error_rate()
        if error_rate > 0.1:  # 10%以上
            anomalies.append({
                "type": "high_error_rate",
                "value": error_rate,
                "threshold": 0.1,
                "description": "エラー率が異常に高くなっています"
            })
        
        # 応答時間の増加
        avg_response_time = await self._calculate_avg_response_time()
        if avg_response_time > 5000:  # 5秒以上
            anomalies.append({
                "type": "slow_response_time",
                "value": avg_response_time,
                "threshold": 5000,
                "description": "平均応答時間が異常に長くなっています"
            })
        
        return anomalies
    
    async def _calculate_error_rate(self) -> float:
        """エラー率の計算"""
        query = """
        SELECT 
            COUNT(CASE WHEN level IN ('ERROR', 'CRITICAL') THEN 1 END) * 1.0 / COUNT(*) as error_rate
        FROM logs 
        WHERE timestamp > datetime('now', '-1 hour')
        """
        
        result = await self.db_service.fetch_one(query, ())
        return result["error_rate"] if result else 0.0
    
    async def _calculate_avg_response_time(self) -> float:
        """平均応答時間の計算"""
        query = """
        SELECT AVG(CAST(JSON_EXTRACT(message, '$.duration_ms') AS REAL)) as avg_duration
        FROM logs 
        WHERE 
            timestamp > datetime('now', '-1 hour')
            AND JSON_EXTRACT(message, '$.event_type') = 'command_execution'
            AND JSON_EXTRACT(message, '$.duration_ms') IS NOT NULL
        """
        
        result = await self.db_service.fetch_one(query, ())
        return result["avg_duration"] if result else 0.0
```

### 2. リアルタイム監視

```python
class LogMonitor:
    def __init__(self, log_analyzer: LogAnalyzer, notification_service):
        self.log_analyzer = log_analyzer
        self.notification_service = notification_service
        self.monitoring_active = False
        
    async def start_monitoring(self, interval: int = 300) -> None:
        """監視の開始（5分間隔）"""
        self.monitoring_active = True
        
        while self.monitoring_active:
            try:
                await self._check_system_health()
                await asyncio.sleep(interval)
            except Exception as e:
                logger.error(f"監視エラー: {e}")
                await asyncio.sleep(60)  # エラー時は1分後に再試行
    
    def stop_monitoring(self) -> None:
        """監視の停止"""
        self.monitoring_active = False
    
    async def _check_system_health(self) -> None:
        """システムヘルスチェック"""
        # 異常検出
        anomalies = await self.log_analyzer.detect_anomalies()
        
        if anomalies:
            await self._handle_anomalies(anomalies)
        
        # エラーサマリー
        error_summary = await self.log_analyzer.get_error_summary(hours=1)
        
        if error_summary["total_errors"] > 10:  # 1時間で10個以上のエラー
            await self._handle_high_error_count(error_summary)
    
    async def _handle_anomalies(self, anomalies: List[Dict[str, Any]]) -> None:
        """異常への対応"""
        for anomaly in anomalies:
            message = f"🚨 異常検出: {anomaly['description']}\n"
            message += f"値: {anomaly['value']}\n"
            message += f"閾値: {anomaly['threshold']}"
            
            await self.notification_service.send_alert(
                title="システム異常検出",
                message=message,
                severity="HIGH"
            )
    
    async def _handle_high_error_count(self, error_summary: Dict[str, Any]) -> None:
        """高エラー数への対応"""
        message = f"⚠️ 高エラー数検出\n"
        message += f"過去1時間のエラー数: {error_summary['total_errors']}\n"
        message += f"主なエラー源:\n"
        
        for error in error_summary["top_error_sources"][:3]:
            message += f"- {error['filename']}: {error['count']}件\n"
        
        await self.notification_service.send_alert(
            title="高エラー数検出",
            message=message,
            severity="MEDIUM"
        )
```

## ログ設定の初期化

### setup_logging 関数

```python
def setup_logging(name: str = "COMET", level: str = None) -> logging.Logger:
    """ログシステムの初期化"""
    if level is None:
        level = os.getenv("LOG_LEVEL", "INFO")
    
    # COMETLoggerの初期化
    comet_logger = COMETLogger(name, level)
    base_logger = comet_logger.logger
    
    # 構造化ログの追加
    structured_logger = StructuredLogger(base_logger)
    
    # イベントログの追加
    event_logger = EventLogger(structured_logger)
    
    # Webhookハンドラーの追加（エラー時のみ）
    webhook_url = os.getenv("ERROR_WEBHOOK_URL")
    if webhook_url:
        webhook_handler = WebhookHandler(webhook_url, logging.ERROR)
        base_logger.addHandler(webhook_handler)
    
    # カスタム属性の追加
    base_logger.structured = structured_logger
    base_logger.events = event_logger
    base_logger.session_id = comet_logger.session_id
    
    return base_logger

# グローバルロガーの初期化
logger = setup_logging()
```

## ログ使用例

### 1. 基本的な使用方法

```python
from utils.logging import setup_logging

logger = setup_logging("MyCog")

# 基本ログ
logger.info("Cog initialized successfully")
logger.warning("Configuration value missing, using default")
logger.error("Failed to connect to external service")

# 構造化ログ
logger.structured.info(
    "User command executed",
    user_id=123456789,
    command="ping",
    guild_id=987654321,
    duration_ms=150
)

# イベントログ
await logger.events.log_command_execution(ctx, "ping", True, 0.15)
await logger.events.log_user_action("role_assigned", user_id=123456789, role="moderator")
```

### 2. エラーハンドリングでの使用

```python
try:
    result = await some_operation()
    logger.structured.info("Operation completed", operation="some_operation", result=result)
except Exception as e:
    await logger.events.log_error_event(
        e, 
        context={
            "operation": "some_operation",
            "user_id": ctx.author.id,
            "guild_id": ctx.guild.id
        }
    )
    raise
```

---

## 関連ドキュメント

- [エラーハンドリング](04-error-handling.md)
- [メインボットクラス](01-main-bot-class.md)
- [データベース管理](../04-utilities/01-database-management.md)
- [監視システム](../03-cogs/08-monitoring-cogs.md)
