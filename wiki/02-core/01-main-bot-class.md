# Main Bot Class (MyBot)

## Overview

The `MyBot` class is the central component of the iPhone3G Discord bot, extending discord.py's `AutoShardedBot` to provide enhanced functionality for the Gizmodo Woods community.

## Class Definition

**Location**: [`main.py:65-199`](../main.py#L65-L199)

```python
class MyBot(commands.AutoShardedBot):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.initialized: bool = False
        self.cog_classes: dict = {}
        self.ERROR_LOG_CHANNEL_ID: int = error_log_channel_id
        self.gagame_sessions: dict = {}
```

## Key Features

### 1. Auto-Sharding Support
- Automatically handles multiple Discord shards
- Scales efficiently across large server counts
- Manages shard-specific operations

### 2. Dynamic Cog Loading
- Loads cogs from the `cogs/` directory automatically
- Skips development cogs in production
- Handles loading failures gracefully

### 3. Comprehensive Error Handling
- Global command error handling
- Application command error handling
- Structured error logging and reporting

### 4. Session Management
- Tracks bot initialization state
- Manages session IDs for logging
- Handles reconnection scenarios

## Core Methods

### `setup_hook()`
**Purpose**: Initializes the bot during startup

```python
async def setup_hook(self) -> None:
    try:
        await self.auth()
        logger.info("認証に成功しました。Cogのロードを開始します。")
        await git_pull()
        await pip_install()
        await check_dev()
        await self.load_cogs('cogs')
        await self.load_extension('jishaku')
    except Exception as e:
        logger.error(f"認証に失敗しました。Cogのロードをスキップします。: {e}")
        return
    self.loop.create_task(self.after_ready())
```

**Key Operations**:
1. **Authentication**: Verifies bot credentials
2. **Git Operations**: Pulls latest code changes
3. **Dependencies**: Installs required packages
4. **Environment Check**: Validates development/production environment
5. **Cog Loading**: Dynamically loads all extension modules
6. **Jishaku**: Loads debugging extension

### `load_cogs(folder_name: str)`
**Purpose**: Dynamically loads all Python modules from the cogs directory

```python
async def load_cogs(self, folder_name: str) -> None:
    cur: pathlib.Path = pathlib.Path('.')
    for p in cur.glob(f"{folder_name}/**/*.py"):
        if 'Dev' in p.parts:
            continue
        if p.stem == "__init__":
            continue
        try:
            cog_path: str = p.relative_to(cur).with_suffix('').as_posix().replace('/', '.')
            await self.load_extension(cog_path)
            logger.info(f"Loaded extension: {cog_path}")
        except commands.ExtensionFailed as e:
            traceback.print_exc()
            logger.error(f"Failed to load extension: {cog_path} | {e}")
```

**Features**:
- Recursive directory scanning
- Development cog filtering
- Error handling for failed loads
- Path normalization for imports

### `on_ready()`
**Purpose**: Handles bot ready event and initialization

```python
async def on_ready(self) -> None:
    logger.info(yokobou())
    logger.info("on_ready is called")
    log_data: dict = {
        "event": "BotReady",
        "description": f"{self.user} has successfully connected to Discord.",
        "timestamp": datetime.now(pytz.timezone('Asia/Tokyo')).strftime('%Y-%m-%d %H:%M:%S'),
        "session_id": session_id
    }
    save_log(log_data)
    if not self.initialized:
        try:
            await startup_send_webhook(self, guild_id=dev_guild_id)
            await startup_send_botinfo(self)
        except Exception as e:
            logger.error(f"Error during startup: {e}")
        self.initialized = True
```

**Operations**:
- Logs successful connection
- Records session information
- Sends startup notifications
- Updates initialization state

## Error Handling

### Command Error Handler
```python
@commands.Cog.listener()
async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
    if hasattr(ctx, 'handled') and ctx.handled:
        return

    error_context = {
        "command": {
            "name": ctx.command.name if ctx.command else "unknown",
            "content": ctx.message.content
        },
        "user": {
            "id": ctx.author.id,
            "name": str(ctx.author)
        }
    }
    
    if ctx.guild:
        error_context["guild"] = {
            "id": ctx.guild.id,
            "name": ctx.guild.name
        }

    handled: bool = await handle_command_error(ctx, error, self.ERROR_LOG_CHANNEL_ID)
    if handled:
        ctx.handled = True
```

### Application Command Error Handler
```python
@commands.Cog.listener()
async def on_application_command_error(self, interaction: discord.Interaction, error: commands.CommandError) -> None:
    # Similar structure for slash command errors
    await handle_application_command_error(interaction, error)
```

## Configuration

### Bot Initialization
```python
intent: discord.Intents = discord.Intents.all()
bot: MyBot = MyBot(command_prefix=command_prefix, intents=intent, help_command=None)
```

**Settings**:
- **Intents**: All Discord intents enabled
- **Prefix**: Configurable command prefixes
- **Help Command**: Disabled (custom implementation)

### Environment Variables
- `TOKEN`: Discord bot token
- `ADMIN_MAIN_GUILD_ID`: Primary server ID
- `ADMIN_DEV_GUILD_ID`: Development server ID
- `ADMIN_STARTUP_CHANNEL_ID`: Startup notification channel
- `ADMIN_ERROR_LOG_CHANNEL_ID`: Error logging channel

## Instance Variables

| Variable | Type | Purpose |
|----------|------|---------|
| `initialized` | `bool` | Tracks initialization state |
| `cog_classes` | `dict` | Stores loaded cog references |
| `ERROR_LOG_CHANNEL_ID` | `int` | Channel for error reporting |
| `gagame_sessions` | `dict` | Game session management |

## Lifecycle

1. **Initialization**: Bot instance created with configuration
2. **Setup Hook**: Authentication, cog loading, and preparation
3. **Ready Event**: Connection established, notifications sent
4. **Runtime**: Event processing and command handling
5. **Shutdown**: Graceful cleanup and disconnection

---

## Related Documentation

- [Authentication System](02-authentication-system.md)
- [Error Handling](04-error-handling.md)
- [Cogs Architecture](../03-cogs/01-cogs-architecture.md)
- [Application Startup Flow](../01-architecture/02-application-startup-flow.md)
