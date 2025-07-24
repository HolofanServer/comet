# データベース管理

## 概要

COMETボットは、PostgreSQLを主要データベースとして使用し、asyncpgで接続管理を行い、設定とキャッシュにはJSONファイルを使用します。

## データベースアーキテクチャ

### 現在の実装
- **主要データベース**: asyncpg接続プールを使用したPostgreSQL
- **設定ストレージ**: ローカル設定用のJSONファイル
- **接続管理**: ローカル開発へのフォールバック付きRailway環境サポート
- **マイグレーションシステム**: データベースマイグレーションコマンドが利用可能

### データベース設定
```python
# Railway Production Environment
PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE

# Local Development Environment  
DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME

# Connection URL (Preferred)
DATABASE_PUBLIC_URL
```

## データベースユーティリティ

### 1. データベースマネージャー (`utils/db_manager.py`)

**目的**: 一元化されたデータベース操作と接続管理

**主要機能**:
- 接続プール
- トランザクション管理
- クエリ最適化
- エラーハンドリング

### 2. データベースマイグレーション (`utils/db_migration.py`)

**目的**: スキーマバージョニングとデータマイグレーション

**主要機能**:
- バージョン管理されたスキーマ変更
- ロールバック機能
- データ変換ユーティリティ
- マイグレーション検証

### 3. コアデータベース (`utils/database.py`)

**目的**: 低レベルデータベース操作とユーティリティ

**主要機能**:
- CRUD操作
- データ検証
- 接続管理
- クエリ構築

## データモデル

### メンバーデータ構造
```json
{
  "user_id": "123456789",
  "guild_id": "987654321",
  "join_date": "2024-01-01T00:00:00Z",
  "roles": ["role1", "role2"],
  "preferences": {
    "notifications": true,
    "language": "ja"
  },
  "statistics": {
    "message_count": 150,
    "last_active": "2024-01-15T12:00:00Z"
  }
}
```

### メッセージ分析構造
```json
{
  "message_id": "123456789",
  "channel_id": "987654321",
  "author_id": "456789123",
  "timestamp": "2024-01-01T12:00:00Z",
  "content_length": 50,
  "attachments": 0,
  "reactions": 3,
  "analysis": {
    "sentiment": "positive",
    "topics": ["gaming", "discussion"]
  }
}
```

## データベース操作

### データ読み取り
```python
async def get_member_data(user_id: int, guild_id: int) -> dict:
    """Retrieve member data from database"""
    try:
        with open('config/members.json', 'r') as f:
            members = json.load(f)
        
        key = f"{guild_id}_{user_id}"
        return members.get(key, {})
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"Error reading member data: {e}")
        return {}
```

### データ書き込み
```python
async def save_member_data(user_id: int, guild_id: int, data: dict) -> bool:
    """Save member data to database"""
    try:
        # Read existing data
        try:
            with open('config/members.json', 'r') as f:
                members = json.load(f)
        except FileNotFoundError:
            members = {}
        
        # Update data
        key = f"{guild_id}_{user_id}"
        members[key] = data
        
        # Write back to file
        with open('config/members.json', 'w') as f:
            json.dump(members, f, indent=2, ensure_ascii=False)
        
        return True
    except Exception as e:
        logger.error(f"Error saving member data: {e}")
        return False
```

### バッチ操作
```python
async def batch_update_members(updates: list) -> int:
    """Perform batch updates on member data"""
    success_count = 0
    
    try:
        with open('config/members.json', 'r') as f:
            members = json.load(f)
    except FileNotFoundError:
        members = {}
    
    for update in updates:
        try:
            user_id = update['user_id']
            guild_id = update['guild_id']
            data = update['data']
            
            key = f"{guild_id}_{user_id}"
            members[key] = data
            success_count += 1
        except KeyError as e:
            logger.error(f"Invalid update format: {e}")
    
    # Save all changes
    with open('config/members.json', 'w') as f:
        json.dump(members, f, indent=2, ensure_ascii=False)
    
    return success_count
```

## マイグレーションシステム

### マイグレーション構造
```python
class Migration:
    def __init__(self, version: str, description: str):
        self.version = version
        self.description = description
    
    async def up(self):
        """Apply migration"""
        raise NotImplementedError
    
    async def down(self):
        """Rollback migration"""
        raise NotImplementedError
```

### マイグレーション例
```python
class AddUserPreferences(Migration):
    def __init__(self):
        super().__init__("1.1.0", "Add user preferences to member data")
    
    async def up(self):
        with open('config/members.json', 'r') as f:
            members = json.load(f)
        
        for key, member in members.items():
            if 'preferences' not in member:
                member['preferences'] = {
                    'notifications': True,
                    'language': 'ja'
                }
        
        with open('config/members.json', 'w') as f:
            json.dump(members, f, indent=2, ensure_ascii=False)
    
    async def down(self):
        with open('config/members.json', 'r') as f:
            members = json.load(f)
        
        for key, member in members.items():
            if 'preferences' in member:
                del member['preferences']
        
        with open('config/members.json', 'w') as f:
            json.dump(members, f, indent=2, ensure_ascii=False)
```

## バックアップと復旧

### 自動バックアップ
```python
async def create_backup():
    """Create timestamped backup of all data files"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = f"backups/{timestamp}"
    
    os.makedirs(backup_dir, exist_ok=True)
    
    # Backup configuration files
    for file in ['members.json', 'spam_blocker.json', 'version.json']:
        src = f"config/{file}"
        dst = f"{backup_dir}/{file}"
        if os.path.exists(src):
            shutil.copy2(src, dst)
    
    # Backup data files
    for file in glob.glob("*.json"):
        if file.startswith(('message', 'roles')):
            shutil.copy2(file, f"{backup_dir}/{file}")
    
    logger.info(f"Backup created: {backup_dir}")
```

### 復旧操作
```python
async def restore_backup(backup_timestamp: str):
    """Restore from backup"""
    backup_dir = f"backups/{backup_timestamp}"
    
    if not os.path.exists(backup_dir):
        raise FileNotFoundError(f"Backup not found: {backup_timestamp}")
    
    # Restore files
    for file in os.listdir(backup_dir):
        src = f"{backup_dir}/{file}"
        
        if file in ['members.json', 'spam_blocker.json', 'version.json']:
            dst = f"config/{file}"
        else:
            dst = file
        
        shutil.copy2(src, dst)
    
    logger.info(f"Backup restored: {backup_timestamp}")
```

## パフォーマンス最適化

### 1. キャッシュ戦略
```python
from functools import lru_cache
import asyncio

class DatabaseCache:
    def __init__(self, ttl: int = 300):  # 5 minutes TTL
        self.cache = {}
        self.ttl = ttl
    
    async def get(self, key: str):
        if key in self.cache:
            data, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                return data
            else:
                del self.cache[key]
        return None
    
    async def set(self, key: str, value):
        self.cache[key] = (value, time.time())
```

### 2. 接続プール
```python
class ConnectionPool:
    def __init__(self, max_connections: int = 10):
        self.max_connections = max_connections
        self.connections = asyncio.Queue(maxsize=max_connections)
        self.active_connections = 0
    
    async def get_connection(self):
        if self.connections.empty() and self.active_connections < self.max_connections:
            # Create new connection
            connection = await self.create_connection()
            self.active_connections += 1
            return connection
        else:
            # Wait for available connection
            return await self.connections.get()
    
    async def return_connection(self, connection):
        await self.connections.put(connection)
```

## エラーハンドリング

### データベース例外
```python
class DatabaseError(Exception):
    """Base database exception"""
    pass

class ConnectionError(DatabaseError):
    """Database connection error"""
    pass

class ValidationError(DatabaseError):
    """Data validation error"""
    pass

class MigrationError(DatabaseError):
    """Migration operation error"""
    pass
```

### エラー復旧
```python
async def safe_database_operation(operation, *args, **kwargs):
    """Execute database operation with error recovery"""
    max_retries = 3
    retry_delay = 1
    
    for attempt in range(max_retries):
        try:
            return await operation(*args, **kwargs)
        except ConnectionError as e:
            if attempt < max_retries - 1:
                logger.warning(f"Database connection failed, retrying in {retry_delay}s: {e}")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2
            else:
                logger.error(f"Database operation failed after {max_retries} attempts: {e}")
                raise
        except ValidationError as e:
            logger.error(f"Data validation failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected database error: {e}")
            raise
```

---

## 関連ドキュメント

- [データベースマイグレーションコマンド](../03-cogs/04-management-cogs.md#db-migration-commands)
- [設定管理](../01-architecture/04-configuration-management.md)
- [API統合](02-api-integration.md)
- [エラーハンドリング](../02-core/04-error-handling.md)
