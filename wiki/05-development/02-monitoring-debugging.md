# 監視とデバッグ

## C.O.M.E.T.について

**C.O.M.E.T.**の名前は以下の頭文字から構成されています：

- **C**ommunity of
- **O**shilove
- **M**oderation &
- **E**njoyment
- **T**ogether

HFS - ホロライブ非公式ファンサーバーのコミュニティを支える、推し愛とモデレーション、そして楽しさを一緒に提供するボットです。

## 概要

C.O.M.E.T.ボットの監視とデバッグシステムについて説明します。本ドキュメントでは、ボットの健全性監視、パフォーマンス分析、デバッグ手法について詳しく解説します。

## 監視システム

### リアルタイム監視

```python
import asyncio
import psutil
import time
from datetime import datetime

class BotMonitor:
    def __init__(self, bot):
        self.bot = bot
        self.start_time = time.time()
        self.metrics = {
            'commands_executed': 0,
            'errors_count': 0,
            'memory_usage': 0,
            'cpu_usage': 0
        }
    
    async def collect_metrics(self):
        """メトリクス収集"""
        process = psutil.Process()
        self.metrics['memory_usage'] = process.memory_info().rss / 1024 / 1024  # MB
        self.metrics['cpu_usage'] = process.cpu_percent()
        
        return self.metrics
    
    async def health_check(self):
        """ヘルスチェック"""
        return {
            'status': 'healthy' if self.bot.is_ready() else 'unhealthy',
            'uptime': time.time() - self.start_time,
            'latency': self.bot.latency,
            'guilds': len(self.bot.guilds)
        }
```

### パフォーマンス監視

```python
import functools
import time
import logging

def monitor_performance(func):
    """パフォーマンス監視デコレータ"""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            return result
        except Exception as e:
            logging.error(f"Error in {func.__name__}: {e}")
            raise
        finally:
            execution_time = time.time() - start_time
            if execution_time > 1.0:  # 1秒以上の場合
                logging.warning(
                    f"Slow execution: {func.__name__} took {execution_time:.2f}s"
                )
    return wrapper
```

## デバッグ手法

### ログベースデバッグ

```python
import logging
import sys
from pathlib import Path

def setup_debug_logging():
    """デバッグ用ログ設定"""
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # ファイルハンドラー
    file_handler = logging.FileHandler('debug.log')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(log_format))
    
    # コンソールハンドラー
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(log_format))
    
    # ルートロガー設定
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
```

### インタラクティブデバッグ

```python
import pdb
import traceback

class DebugCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command(name='debug')
    @commands.is_owner()
    async def debug_command(self, ctx, *, code: str):
        """デバッグコマンド実行"""
        try:
            # セキュリティ上の理由で本番環境では無効化
            if not self.bot.debug_mode:
                await ctx.send("デバッグモードが無効です")
                return
            
            result = eval(code)
            await ctx.send(f"結果: {result}")
        except Exception as e:
            await ctx.send(f"エラー: {e}")
            traceback.print_exc()
```

## トラブルシューティング

### 一般的な問題

#### メモリリーク

```python
import gc
import weakref

class MemoryTracker:
    def __init__(self):
        self.tracked_objects = weakref.WeakSet()
    
    def track(self, obj):
        """オブジェクト追跡"""
        self.tracked_objects.add(obj)
    
    def get_memory_usage(self):
        """メモリ使用量取得"""
        return {
            'tracked_objects': len(self.tracked_objects),
            'gc_objects': len(gc.get_objects())
        }
    
    def force_cleanup(self):
        """強制クリーンアップ"""
        gc.collect()
        return self.get_memory_usage()
```

#### レスポンス遅延

```python
import asyncio
from collections import deque
import time

class ResponseTimeMonitor:
    def __init__(self, window_size=100):
        self.response_times = deque(maxlen=window_size)
    
    def record_response_time(self, response_time):
        """レスポンス時間記録"""
        self.response_times.append(response_time)
    
    def get_average_response_time(self):
        """平均レスポンス時間取得"""
        if not self.response_times:
            return 0
        return sum(self.response_times) / len(self.response_times)
    
    def is_slow_response(self, threshold=1.0):
        """遅いレスポンスかチェック"""
        avg_time = self.get_average_response_time()
        return avg_time > threshold
```

## 開発ツール

### ホットリロード

```python
import importlib
import sys

class HotReloader:
    def __init__(self, bot):
        self.bot = bot
        self.watched_modules = set()
    
    def watch_module(self, module_name):
        """モジュール監視"""
        self.watched_modules.add(module_name)
    
    async def reload_module(self, module_name):
        """モジュールリロード"""
        try:
            if module_name in sys.modules:
                importlib.reload(sys.modules[module_name])
                return f"モジュール {module_name} をリロードしました"
        except Exception as e:
            return f"リロードエラー: {e}"
```

### テスト環境

```python
import unittest.mock as mock

class TestEnvironment:
    def __init__(self):
        self.mock_bot = mock.MagicMock()
        self.mock_guild = mock.MagicMock()
        self.mock_channel = mock.MagicMock()
        self.mock_user = mock.MagicMock()
    
    def setup_test_environment(self):
        """テスト環境セットアップ"""
        # モックオブジェクトの設定
        self.mock_bot.user.id = 123456789
        self.mock_guild.id = 987654321
        self.mock_channel.id = 555666777
        
        return {
            'bot': self.mock_bot,
            'guild': self.mock_guild,
            'channel': self.mock_channel,
            'user': self.mock_user
        }
```

## 関連ドキュメント

- [ログシステム](../02-core/03-logging-system.md)
- [エラーハンドリング](../02-core/04-error-handling.md)
- [テストフレームワーク](02-testing-framework.md)
- [デプロイメントガイド](03-deployment-guide.md)
