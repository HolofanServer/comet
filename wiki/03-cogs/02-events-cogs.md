# Events Cogs

## Overview

Events cogs handle Discord events and server monitoring functionality. These cogs are responsible for reacting to various Discord events and maintaining server security and visual consistency.

## Available Events Cogs

### 1. Banner Sync (`banner_sync.py`)

**Purpose**: Automatically synchronizes the main server's banner to the bot's profile banner.

**Key Features**:
- **Automatic Synchronization**: Runs every 3 hours via `@tasks.loop(hours=3)`
- **Change Detection**: Only updates when banner hash changes to avoid unnecessary API calls
- **Image Processing**: Supports PNG, JPEG, and GIF formats with automatic MIME type detection
- **Base64 Encoding**: Converts banner images to data URIs for Discord API
- **Manual Sync Command**: `/sync_banner` for administrator-triggered updates

**Implementation Details**:
```python
@tasks.loop(hours=3)
async def sync_banner(self):
    # Downloads banner from main guild
    # Converts to base64 data URI
    # Updates bot profile via Discord API PATCH /users/@me
```

**Commands**:
- `sync_banner` (Hybrid Command): Manual banner synchronization (Administrator only)

### 2. Guild Watcher (`guild_watcher.py`)

**Purpose**: Security system that automatically removes the bot from unauthorized servers.

**Key Features**:
- **Whitelist System**: Only allows bot in specified main and dev guilds
- **Auto-Leave**: Automatically leaves unauthorized servers on join
- **Startup Check**: Validates all current guilds on bot startup
- **Guild Monitoring**: Logs all guild join/leave events

**Configuration**:
```python
self.main_guild_id = int(settings.admin_main_guild_id)
self.dev_guild_id = int(settings.admin_dev_guild_id)
self.allowed_guild_ids = [self.main_guild_id, self.dev_guild_id]
```

**Events Handled**:
- `on_guild_join`: Checks if new guild is authorized, leaves if not
- `on_ready`: Validates all current guilds on startup

**Commands**:
- `list_guilds`: Lists all guilds the bot is currently in (Owner only)

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
