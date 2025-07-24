# Database Management

## Overview

The iPhone3G bot uses PostgreSQL as its primary database with asyncpg for connection management, along with JSON files for configuration and caching.

## Database Architecture

### Current Implementation
- **Primary Database**: PostgreSQL with asyncpg connection pooling
- **Configuration Storage**: JSON files for local configuration
- **Connection Management**: Railway environment support with fallback to local development
- **Migration System**: Database migration commands available

### Database Configuration
```python
# Railway Production Environment
PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE

# Local Development Environment  
DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME

# Connection URL (Preferred)
DATABASE_PUBLIC_URL
```

## Database Utilities

### 1. Database Manager (`utils/db_manager.py`)

**Purpose**: Centralized database operations and connection management

**Key Features**:
- Connection pooling
- Transaction management
- Query optimization
- Error handling

### 2. Database Migration (`utils/db_migration.py`)

**Purpose**: Schema versioning and data migration

**Key Features**:
- Version-controlled schema changes
- Rollback capabilities
- Data transformation utilities
- Migration validation

### 3. Core Database (`utils/database.py`)

**Purpose**: Low-level database operations and utilities

**Key Features**:
- CRUD operations
- Data validation
- Connection management
- Query building

## Data Models

### Member Data Structure
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

### Message Analytics Structure
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

## Database Operations

### Reading Data
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

### Writing Data
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

### Batch Operations
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

## Migration System

### Migration Structure
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

### Example Migration
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

## Backup and Recovery

### Automated Backups
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

### Recovery Operations
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

## Performance Optimization

### 1. Caching Strategy
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

### 2. Connection Pooling
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

## Error Handling

### Database Exceptions
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

### Error Recovery
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

## Related Documentation

- [Database Migration Commands](../03-cogs/04-management-cogs.md#db-migration-commands)
- [Configuration Management](../01-architecture/04-configuration-management.md)
- [API Integration](02-api-integration.md)
- [Error Handling](../02-core/04-error-handling.md)
