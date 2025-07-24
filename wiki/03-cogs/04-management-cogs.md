# Management Cogs

## Overview

Management cogs provide administrative functionality for bot control, cog management, database operations, and help systems.

## Available Management Cogs

### 1. Manage Cogs (`manage_cogs.py`)

**Purpose**: Dynamic loading, unloading, and reloading of bot extensions.

**Key Features**:
- **Hot Reloading**: Reload cogs without restarting the bot
- **Extension Management**: Load/unload individual cogs
- **Error Handling**: Graceful handling of extension failures
- **Interactive Interface**: Slash commands for easy management

**Commands Available**:
- `/reload_cog`: Reload a specific cog
- `/load_cog`: Load a new cog
- `/unload_cog`: Unload an existing cog
- `/list_cogs`: List all loaded cogs

### 2. Database Migration Commands (`db_migration_commands.py`)

**Purpose**: Database schema management and migration operations.

**Key Features**:
- **Schema Versioning**: Track database schema changes
- **Migration Scripts**: Apply database updates safely
- **Rollback Support**: Undo problematic migrations
- **Data Integrity**: Ensure data consistency during migrations

**Commands Available**:
- `/migrate`: Apply pending database migrations
- `/rollback`: Rollback last migration
- `/migration_status`: Check current migration status

### 3. Help System (`help.py`)

**Purpose**: Custom help command implementation with enhanced formatting.

**Key Features**:
- **Categorized Commands**: Organize commands by functionality
- **Interactive Help**: Detailed command descriptions and usage
- **Permission Awareness**: Show only accessible commands
- **Rich Formatting**: Enhanced visual presentation

**Commands Available**:
- `/help`: Display general help information
- `/help <command>`: Get detailed help for specific command
- `/help <category>`: Show commands in a category

### 4. Manage Bot (`manage_bot.py`)

**Purpose**: Core bot management and administrative operations.

**Key Features**:
- **Bot Control**: Restart, shutdown, and status operations
- **System Information**: Display bot statistics and health
- **Configuration Management**: Runtime configuration updates
- **Maintenance Mode**: Temporary bot maintenance states

**Commands Available**:
- `/bot_status`: Display bot health and statistics
- `/restart_bot`: Restart the bot (Owner only)
- `/shutdown_bot`: Gracefully shutdown bot (Owner only)
- `/maintenance`: Toggle maintenance mode

## Command Structure

### Permission Levels
Management commands use strict permission checking:

```python
# Owner-only commands
@is_owner()

# Administrator permissions
@commands.has_permissions(administrator=True)

# Guild-specific commands
@is_guild()
```

### Error Handling
All management commands include comprehensive error handling:

```python
try:
    # Command logic
    await operation()
    await interaction.response.send_message("✅ Operation successful")
except Exception as e:
    logger.error(f"Management command failed: {e}")
    await interaction.response.send_message(f"❌ Operation failed: {e}")
```

### Logging Integration
Management operations are logged for audit purposes:

```python
@log_commands()
async def management_command(self, interaction):
    # Command execution is automatically logged
    pass
```

## Security Considerations

### Access Control
- **Owner Verification**: Critical operations require bot owner status
- **Permission Checks**: Commands verify Discord permissions
- **Guild Restrictions**: Some commands limited to specific guilds

### Audit Trail
- **Command Logging**: All management commands are logged
- **Error Tracking**: Failures are recorded with context
- **Change History**: Database migrations maintain history

### Safe Operations
- **Graceful Degradation**: Failed operations don't crash the bot
- **Rollback Capability**: Database changes can be undone
- **Confirmation Prompts**: Destructive operations require confirmation

## Usage Examples

### Cog Management
```
/reload_cog cog:user_analyzer
/load_cog cog:new_feature
/unload_cog cog:deprecated_feature
```

### Database Operations
```
/migrate
/migration_status
/rollback
```

### Bot Control
```
/bot_status
/maintenance mode:on
/restart_bot
```

---

## Related Documentation

- [Main Bot Class](../02-core/01-main-bot-class.md)
- [Database Management](../04-utilities/01-database-management.md)
- [Error Handling](../02-core/04-error-handling.md)
- [Security Guidelines](../05-development/03-security-guidelines.md)
