# バックアップと復旧

C.O.M.E.T. Discord botのデータバックアップと復旧手順について説明します。

## 概要

本ドキュメントでは、C.O.M.E.T.ボットのデータを安全にバックアップし、障害時に迅速に復旧するための手順を説明します。

## バックアップ対象

### 設定ファイル
- 環境変数設定
- ボット設定ファイル
- データベース設定

### データベース
- ユーザーデータ
- 警告履歴
- インタビューデータ
- 設定情報

### ログファイル
- エラーログ
- アクセスログ
- 監査ログ

## バックアップ戦略

### 自動バックアップ
- 日次：データベース全体
- 週次：設定ファイル
- 月次：ログアーカイブ

### 手動バックアップ
- 重要な設定変更前
- メジャーアップデート前
- 緊急時

## 実装例

```python
import asyncio
import sqlite3
import shutil
from datetime import datetime
from pathlib import Path

class BackupManager:
    def __init__(self, backup_dir: str):
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(exist_ok=True)
    
    async def create_database_backup(self, db_path: str):
        """データベースバックアップ作成"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"comet_backup_{timestamp}.db"
        backup_path = self.backup_dir / backup_name
        
        shutil.copy2(db_path, backup_path)
        return backup_path
    
    async def restore_database(self, backup_path: str, target_path: str):
        """データベース復旧"""
        shutil.copy2(backup_path, target_path)
        return True
```

## 復旧手順

### 1. 障害確認
```bash
# ボット状態確認
systemctl status comet-bot

# ログ確認
tail -f /var/log/comet/error.log
```

### 2. データベース復旧
```bash
# バックアップから復旧
cp /backup/comet_backup_latest.db /data/comet.db

# 権限設定
chown comet:comet /data/comet.db
```

### 3. サービス再起動
```bash
# サービス再起動
systemctl restart comet-bot

# 状態確認
systemctl status comet-bot
```

## 自動化スクリプト

```bash
#!/bin/bash
# backup.sh - 自動バックアップスクリプト

BACKUP_DIR="/backup/comet"
DB_PATH="/data/comet.db"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# バックアップディレクトリ作成
mkdir -p "$BACKUP_DIR"

# データベースバックアップ
cp "$DB_PATH" "$BACKUP_DIR/comet_backup_$TIMESTAMP.db"

# 古いバックアップ削除（30日以上）
find "$BACKUP_DIR" -name "comet_backup_*.db" -mtime +30 -delete

echo "Backup completed: comet_backup_$TIMESTAMP.db"
```

## 定期実行設定

```cron
# crontab -e
# 毎日午前3時にバックアップ実行
0 3 * * * /opt/comet/scripts/backup.sh

# 毎週日曜日に設定ファイルバックアップ
0 4 * * 0 /opt/comet/scripts/backup-config.sh
```
