# Logging System

## Overview

The iPhone3G bot implements a comprehensive logging system with colored console output, file logging, and structured log data management.

## Logging Architecture

### Core Components

#### 1. Custom Formatter (`CustomFormatter`)
Provides colored console output for different log levels:

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

**Color Scheme**:
- **DEBUG**: Blue
- **INFO**: White  
- **WARNING**: Yellow
- **ERROR**: Red
- **CRITICAL**: Bold Red

#### 2. Setup Function (`setup_logging`)
Configurable logging setup with multiple modes:

```python
def setup_logging(mode: Optional[str] = None):
    # Supports: "debug", "info", "warning", "error", "critical", "api"
```

**Available Modes**:
- `"debug"` or `"D"`: Debug level logging
- `"info"` or `"I"`: Info level logging  
- `"warning"` or `"W"`: Warning level logging
- `"error"` or `"E"`: Error level logging
- `"critical"` or `"C"`: Critical level logging
- `"api"` or `"API"`: Special API logging with file output

### Log Data Management

#### Structured Log Storage (`save_log`)
Saves structured log data as JSON files with automatic archiving:

```python
def save_log(log_data):
    # Creates timestamped directories: data/logging/YYYY-MM-DD/HH-MM-SS/
    # Generates UUID-based filenames
    # Automatically archives old logs (keeps 10 most recent days)
```

**Directory Structure**:
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

**Log Data Format**:
```json
{
  "event": "BotReady",
  "description": "Bot has successfully connected to Discord",
  "timestamp": "2024-01-01 12:00:00",
  "session_id": "session_123",
  "additional_data": {}
}
```

### Logging Modes

#### 1. Standard Console Logging
Default logging to console with colored output:
```python
logger = setup_logging("info")
logger.info("Bot started successfully")
```

#### 2. API Logging Mode
Special logging mode for API operations with both console and file output:
```python
api_logger = setup_logging("api")
# Logs to both console and data/logging/api/api.log
```

#### 3. Debug Mode
Enhanced logging for development:
```python
debug_logger = setup_logging("debug")
# Shows detailed debug information
```

## Usage Patterns

### In Cogs
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

### Structured Event Logging
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

### Error Tracking
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

## Log Management

### Automatic Archiving
The system automatically manages log storage:
- Keeps 10 most recent days of logs
- Archives older logs to `archive/` directory
- Prevents disk space issues from log accumulation

### File Organization
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

### Log Rotation
- Daily log directories
- Session-based subdirectories
- UUID-based individual log files
- Automatic cleanup of old logs

## Integration with Bot Systems

### Main Bot Logging
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

### Error Handler Integration
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

## Performance Considerations

### Efficient Logging
- Lazy string formatting: `logger.info("User %s joined", user.name)`
- Conditional debug logging: `if logger.isEnabledFor(DEBUG):`
- Async-safe logging operations

### Storage Management
- Automatic log rotation prevents disk space issues
- JSON format allows for easy parsing and analysis
- UUID filenames prevent naming conflicts

---

## Related Documentation

- [Error Handling](../02-core/04-error-handling.md)
- [Configuration Management](../01-architecture/04-configuration-management.md)
- [Development Setup](../05-development/01-development-setup.md)
- [Monitoring and Debugging](../05-development/02-monitoring-debugging.md)
