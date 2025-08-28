# イベントCogs

## C.O.M.E.T.について

**C.O.M.E.T.**の名前は以下の頭文字から構成されています：

- **C**ommunity of
- **O**shilove
- **M**oderation &
- **E**njoyment
- **T**ogether

HFS - ホロライブ非公式ファンサーバーのコミュニティを支える、推し愛とモデレーション、そして楽しさを一緒に提供するボットです。

## 概要

イベントCogsはDiscordイベントとサーバーモニタリング機能を処理します。これらのCogsは様々なDiscordイベントに反応し、サーバーのセキュリティと視覚的一貫性を維持する責任があります。

## 利用可能なイベントCogs

### 1. バナー同期 (`banner_sync.py`)

**目的**: メインサーバーのバナーをボットのプロフィールバナーに自動同期します。

**主要機能**:
- **自動同期**: `@tasks.loop(hours=3)`により3時間ごとに実行
- **変更検出**: バナーハッシュが変更された場合のみ更新し、不要なAPI呼び出しを回避
- **画像処理**: 自動MIMEタイプ検出でPNG、JPEG、GIF形式をサポート
- **Base64エンコーディング**: Discord API用にバナー画像をデータURIに変換
- **手動同期コマンド**: 管理者がトリガーする`/sync_banner`更新

**実装詳細**:
```python
@tasks.loop(hours=3)
async def sync_banner(self):
    # メインギルドからバナーをダウンロード
    # base64データURIに変換
    # Discord API PATCH /users/@me経由でボットプロフィールを更新
```

**コマンド**:
- `sync_banner` (ハイブリッドコマンド): 手動バナー同期（管理者のみ）

### 2. ギルドウォッチャー (`guild_watcher.py`)

**目的**: 未承認サーバーからボットを自動的に削除するセキュリティシステム。

**主要機能**:
- **ホワイトリストシステム**: 指定されたメインと開発ギルドでのみボットを許可
- **自動退出**: 参加時に未承認サーバーから自動的に退出
- **起動チェック**: ボット起動時に現在のすべてのギルドを検証
- **ギルドモニタリング**: すべてのギルド参加/退出イベントをログ記録

**設定**:
```python
self.main_guild_id = int(settings.admin_main_guild_id)
self.dev_guild_id = int(settings.admin_dev_guild_id)
self.allowed_guild_ids = [self.main_guild_id, self.dev_guild_id]
```

**処理されるイベント**:
- `on_guild_join`: 新しいギルドが承認されているかチェック、そうでなければ退出
- `on_ready`: 起動時にすべての現在のギルドを検証

**コマンド**:
- `list_guilds`: ボットが現在参加しているすべてのギルドをリスト（オーナーのみ）

## Event Processing Architecture

```
Discord Event → Event Listener → Processing Logic → Action/Response
     ↓              ↓                ↓                 ↓
Guild Update → Guild Watcher → Analysis & Logging → Notification
```

## Common Event Patterns

### Event Listener Structure
```python
@commands.Cog.listener()
async def on_event_name(self, *args):
    try:
        # Event processing logic
        await self.process_event(*args)
    except Exception as e:
        logger.error(f"Error processing {event_name}: {e}")
```

### Async Event Handling
```python
@commands.Cog.listener()
async def on_member_join(self, member):
    # Non-blocking event processing
    asyncio.create_task(self.welcome_new_member(member))
    asyncio.create_task(self.log_member_join(member))
    asyncio.create_task(self.check_member_verification(member))
```

## Event Data Flow

### 1. Event Reception
- Discord sends event to bot
- Event router identifies appropriate cog
- Event listener method invoked

### 2. Data Processing
- Extract relevant information
- Validate event data
- Apply business logic

### 3. Response Generation
- Determine appropriate response
- Execute actions (messages, role changes, etc.)
- Log event for audit trail

## Performance Considerations

### 1. Event Rate Limiting
- Handle high-frequency events efficiently
- Implement event batching where appropriate
- Use async processing to prevent blocking

### 2. Memory Management
- Clean up event data after processing
- Avoid storing unnecessary event history
- Use efficient data structures

### 3. Error Resilience
- Graceful handling of malformed events
- Retry mechanisms for failed operations
- Fallback behaviors for critical events

## Configuration

### Event Filtering
```python
# Example configuration for event filtering
EVENT_CONFIG = {
    "guild_watcher": {
        "track_member_joins": True,
        "track_role_changes": True,
        "ignore_bot_events": True
    },
    "banner_sync": {
        "auto_sync": True,
        "sync_interval": 3600  # 1 hour
    }
}
```

### Channel Routing
Events can be routed to specific channels based on type:
- Member events → Welcome channel
- Moderation events → Staff channel
- System events → Log channel

## Integration with Other Systems

### Database Logging
```python
async def log_event(self, event_type: str, data: dict):
    log_entry = {
        "timestamp": datetime.utcnow(),
        "event_type": event_type,
        "guild_id": data.get("guild_id"),
        "data": data
    }
    await self.db.insert_log(log_entry)
```

### Webhook Notifications
```python
async def send_webhook_notification(self, event_data):
    webhook_url = self.config.get("webhook_url")
    if webhook_url:
        await self.send_webhook(webhook_url, event_data)
```

## Debugging and Monitoring

### Event Logging
```python
logger.info(f"Processing {event_type} for guild {guild.id}")
logger.debug(f"Event data: {event_data}")
```

### Performance Metrics
- Event processing time
- Event frequency statistics
- Error rates by event type

## Security Considerations

### 1. Event Validation
- Verify event authenticity
- Validate event data structure
- Check permissions before processing

### 2. Rate Limiting Protection
- Implement per-guild rate limits
- Detect and handle spam events
- Protect against event flooding

### 3. Sensitive Data Handling
- Sanitize logged event data
- Protect user privacy
- Secure webhook endpoints

---

## Related Documentation

- [Guild Watcher Details](02-events-cogs/guild-watcher.md)
- [Banner Sync Details](02-events-cogs/banner-sync.md)
- [Cogs Architecture](01-cogs-architecture.md)
- [Error Handling](../02-core/04-error-handling.md)
