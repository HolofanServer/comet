# Cogs Architecture

## Overview

The iPhone3G bot uses Discord.py's cogs system to organize functionality into modular, reloadable extensions. This architecture enables clean separation of concerns and dynamic feature management.

## Cog Categories

### 1. Events Cogs (`cogs/events/`)
**Purpose**: Handle Discord events and server monitoring

| Cog | File | Description |
|-----|------|-------------|
| Banner Sync | `banner_sync.py` | Synchronizes server banners and visual elements |
| Guild Watcher | `guild_watcher.py` | Monitors guild events and member activities |

### 2. Homepage Cogs (`cogs/homepage/`)
**Purpose**: Website integration and server analysis

| Cog | File | Description |
|-----|------|-------------|
| Staff Manager | `staff_manager.py` | Manages staff roles and permissions |
| Server Analyzer | `server_analyzer.py` | Analyzes server statistics and metrics |
| Website Integration | `website_integration.py` | Connects bot with external website |

### 3. Management Cogs (`cogs/manage/`)
**Purpose**: Bot administration and control

| Cog | File | Description |
|-----|------|-------------|
| Manage Cogs | `manage_cogs.py` | Dynamic cog loading/unloading |
| DB Migration Commands | `db_migration_commands.py` | Database schema management |
| Help System | `help.py` | Custom help command implementation |
| Manage Bot | `manage_bot.py` | Bot configuration and control |

### 4. Tool Cogs (`cogs/tool/`)
**Purpose**: Utility commands and features

| Cog | File | Description |
|-----|------|-------------|
| Announcement New | `announcement_new.py` | Advanced announcement system |
| Recorder | `recorder.py` | Voice/activity recording features |
| User Analyzer | `user_analyzer.py` | User behavior analysis |
| Oshi Role Panel | `oshi_role_panel.py` | Role selection interface |
| Custom Announcement | `custom_announcement.py` | Customizable announcements |
| Server Stats | `server_stats.py` | Real-time server statistics |
| CV2 Test | `cv2_test.py` | Computer vision testing tools |
| Welcome Message | `welcom_message.py` | New member welcome system |
| MS Ana | `ms_ana.py` | Message analysis tools |
| Bug Reporter | `bug.py` | Bug reporting system |

## Cog Loading System

### Dynamic Loading Process

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
- **Recursive Discovery**: Automatically finds all Python files in cogs directory
- **Development Filtering**: Skips cogs in 'Dev' directories for production
- **Error Resilience**: Continues loading other cogs if one fails
- **Path Normalization**: Converts file paths to Python import paths

### Hot Reloading

Cogs can be dynamically reloaded without restarting the bot:

```python
# Reload a specific cog
await bot.reload_extension('cogs.tool.announcement_new')

# Unload a cog
await bot.unload_extension('cogs.events.banner_sync')

# Load a new cog
await bot.load_extension('cogs.manage.new_feature')
```

## Cog Structure Template

### Basic Cog Structure
```python
import discord
from discord.ext import commands

class ExampleCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        
    @commands.Cog.listener()
    async def on_ready(self):
        print(f"{self.__class__.__name__} is ready!")
    
    @commands.command()
    async def example_command(self, ctx):
        await ctx.send("Hello from ExampleCog!")
    
    @discord.app_commands.command()
    async def example_slash(self, interaction: discord.Interaction):
        await interaction.response.send_message("Hello from slash command!")

async def setup(bot):
    await bot.add_cog(ExampleCog(bot))
```

### Advanced Cog Features

#### 1. Event Listeners
```python
@commands.Cog.listener()
async def on_member_join(self, member):
    # Handle new member events
    pass

@commands.Cog.listener()
async def on_message(self, message):
    # Process all messages
    pass
```

#### 2. Slash Commands
```python
@discord.app_commands.command(name="example", description="Example slash command")
async def example_slash(self, interaction: discord.Interaction, param: str):
    await interaction.response.send_message(f"You said: {param}")
```

#### 3. Context Menus
```python
@discord.app_commands.context_menu(name="Analyze User")
async def analyze_user(self, interaction: discord.Interaction, member: discord.Member):
    # Right-click context menu on users
    pass
```

## Cog Dependencies

### Shared Utilities
Cogs commonly use shared utilities from the `utils/` directory:

- **Database**: `utils/database.py`, `utils/db_manager.py`
- **Logging**: `utils/logging.py`
- **API Integration**: `utils/api.py`
- **Configuration**: `config/setting.py`

### Inter-Cog Communication
```python
# Access other cogs
other_cog = self.bot.get_cog('OtherCogName')
if other_cog:
    result = await other_cog.some_method()
```

## Error Handling in Cogs

### Local Error Handling
```python
@example_command.error
async def example_command_error(self, ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Missing required argument!")
    else:
        # Let global handler deal with it
        raise error
```

### Global Error Integration
Cogs integrate with the bot's global error handling system automatically.

## Performance Considerations

### 1. Async Best Practices
- Use `await` for all Discord API calls
- Implement proper connection pooling
- Handle rate limits gracefully

### 2. Memory Management
- Clean up resources in cog teardown
- Avoid storing large objects in memory
- Use generators for large data processing

### 3. Database Optimization
- Use connection pooling
- Implement proper indexing
- Cache frequently accessed data

## Development Guidelines

### 1. Naming Conventions
- Cog classes: `PascalCase` (e.g., `UserAnalyzer`)
- File names: `snake_case` (e.g., `user_analyzer.py`)
- Commands: `snake_case` (e.g., `analyze_user`)

### 2. Documentation
- Document all public methods
- Include usage examples
- Explain complex algorithms

### 3. Testing
- Write unit tests for core functionality
- Test error conditions
- Validate Discord API interactions

---

## Related Documentation

- [Events Cogs](02-events-cogs.md)
- [Homepage Cogs](03-homepage-cogs.md)
- [Management Cogs](04-management-cogs.md)
- [Tool Cogs](05-tool-cogs.md)
- [Main Bot Class](../02-core/01-main-bot-class.md)
