# トラブルシューティング

C.O.M.E.T. Discord botの一般的な問題と解決方法について説明します。

## 概要

本ドキュメントでは、C.O.M.E.T.ボットの運用中に発生する可能性のある問題と、その診断・解決方法を説明します。

## 一般的な問題

### ボットが応答しない

#### 症状
- コマンドに反応しない
- オフライン状態が続く

#### 診断手順
```bash
# プロセス確認
ps aux | grep comet

# ログ確認
tail -f /var/log/comet/error.log

# ネットワーク接続確認
ping discord.com
```

#### 解決方法
```bash
# サービス再起動
systemctl restart comet-bot

# 設定確認
cat /etc/comet/config.env
```

### メモリ使用量が高い

#### 症状
- システムが重い
- メモリ不足エラー

#### 診断手順
```bash
# メモリ使用量確認
free -h
top -p $(pgrep -f comet)

# プロセス詳細確認
ps -o pid,ppid,cmd,%mem,%cpu -p $(pgrep -f comet)
```

#### 解決方法
```python
# メモリ使用量監視
import psutil
import gc

def monitor_memory():
    process = psutil.Process()
    memory_info = process.memory_info()
    
    if memory_info.rss > 500 * 1024 * 1024:  # 500MB
        gc.collect()  # ガベージコレクション実行
        logger.warning(f"High memory usage: {memory_info.rss / 1024 / 1024:.1f}MB")
```

### データベース接続エラー

#### 症状
- SQLiteエラー
- データ保存失敗

#### 診断手順
```bash
# データベースファイル確認
ls -la /data/comet.db

# 権限確認
stat /data/comet.db

# データベース整合性チェック
sqlite3 /data/comet.db "PRAGMA integrity_check;"
```

#### 解決方法
```bash
# 権限修正
chown comet:comet /data/comet.db
chmod 644 /data/comet.db

# バックアップから復旧
cp /backup/comet_backup_latest.db /data/comet.db
```

### Discord API制限

#### 症状
- レート制限エラー
- API応答遅延

#### 診断手順
```python
# レート制限監視
import time
from collections import deque

class RateLimitMonitor:
    def __init__(self):
        self.requests = deque()
    
    def log_request(self):
        now = time.time()
        self.requests.append(now)
        
        # 1分以内のリクエスト数確認
        while self.requests and now - self.requests[0] > 60:
            self.requests.popleft()
        
        if len(self.requests) > 50:  # 制限値
            logger.warning(f"High API usage: {len(self.requests)} requests/min")
```

#### 解決方法
```python
# リクエスト間隔調整
import asyncio

async def rate_limited_request(func, *args, **kwargs):
    """レート制限対応リクエスト"""
    try:
        return await func(*args, **kwargs)
    except discord.RateLimited as e:
        logger.warning(f"Rate limited, waiting {e.retry_after}s")
        await asyncio.sleep(e.retry_after)
        return await func(*args, **kwargs)
```

## ログ分析

### エラーパターン

```bash
# よくあるエラーパターン検索
grep -E "(ERROR|CRITICAL)" /var/log/comet/error.log | tail -20

# Discord API エラー
grep "discord.errors" /var/log/comet/error.log

# データベースエラー
grep -i "sqlite" /var/log/comet/error.log
```

### パフォーマンス分析

```python
import time
import functools

def performance_monitor(func):
    """パフォーマンス監視デコレータ"""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            return result
        finally:
            execution_time = time.time() - start_time
            if execution_time > 1.0:  # 1秒以上
                logger.warning(
                    f"Slow execution: {func.__name__} took {execution_time:.2f}s"
                )
    return wrapper
```

## 緊急時対応

### 1. 即座の対応
```bash
# サービス停止
systemctl stop comet-bot

# プロセス強制終了（必要時）
pkill -f comet
```

### 2. 状況確認
```bash
# システムリソース確認
df -h
free -h
top

# ネットワーク確認
netstat -tuln
```

### 3. 復旧作業
```bash
# バックアップから復旧
/opt/comet/scripts/restore.sh

# サービス再起動
systemctl start comet-bot

# 動作確認
systemctl status comet-bot
```

## 予防保守

### 定期チェック項目
- ディスク使用量
- メモリ使用量
- ログファイルサイズ
- データベース整合性

### 自動化スクリプト
```bash
#!/bin/bash
# health-check.sh

# ディスク使用量チェック
DISK_USAGE=$(df / | awk 'NR==2 {print $5}' | sed 's/%//')
if [ $DISK_USAGE -gt 80 ]; then
    echo "WARNING: Disk usage is ${DISK_USAGE}%"
fi

# メモリ使用量チェック
MEM_USAGE=$(free | awk 'NR==2{printf "%.0f", $3*100/$2}')
if [ $MEM_USAGE -gt 80 ]; then
    echo "WARNING: Memory usage is ${MEM_USAGE}%"
fi
```
