# Command Categories

## Overview

The iPhone3G bot provides a comprehensive set of commands organized into logical categories. Commands are available as both traditional prefix commands and modern slash commands.

## Command Categories

### 🛠️ Administrative Commands
**Purpose**: Bot management and server administration

| Command | Type | Description | Permission Required |
|---------|------|-------------|-------------------|
| `reload` | Prefix | Reload specific cog | Administrator |
| `load` | Prefix | Load new cog | Administrator |
| `unload` | Prefix | Unload cog | Administrator |
| `sync` | Prefix | Sync slash commands | Administrator |
| `shutdown` | Prefix | Gracefully shutdown bot | Bot Owner |

### 📊 Analysis Commands
**Purpose**: Server and user analytics

| Command | Type | Description | Permission Required |
|---------|------|-------------|-------------------|
| `/analyze_user` | Slash | Analyze user activity patterns | Moderator |
| `/server_stats` | Slash | Display server statistics | Member |
| `/message_analysis` | Slash | Analyze message patterns | Moderator |
| `/activity_report` | Slash | Generate activity report | Moderator |

### 📢 Announcement Commands
**Purpose**: Server announcements and notifications

| Command | Type | Description | Permission Required |
|---------|------|-------------|-------------------|
| `/announce` | Slash | Create server announcement | Moderator |
| `/custom_announce` | Slash | Create custom announcement | Moderator |
| `/announcement_new` | Slash | Advanced announcement system | Administrator |
| `/schedule_announce` | Slash | Schedule future announcement | Moderator |

### 🎭 Role Management Commands
**Purpose**: Role assignment and management

| Command | Type | Description | Permission Required |
|---------|------|-------------|-------------------|
| `/oshi_panel` | Slash | Display role selection panel | Member |
| `/assign_role` | Slash | Assign role to user | Moderator |
| `/remove_role` | Slash | Remove role from user | Moderator |
| `/role_info` | Slash | Display role information | Member |

### 🔍 Utility Commands
**Purpose**: General utility and information

| Command | Type | Description | Permission Required |
|---------|------|-------------|-------------------|
| `/help` | Slash | Display help information | Member |
| `/ping` | Slash | Check bot latency | Member |
| `/uptime` | Slash | Display bot uptime | Member |
| `/version` | Slash | Show bot version | Member |

### 🎮 Entertainment Commands
**Purpose**: Fun and interactive features

| Command | Type | Description | Permission Required |
|---------|------|-------------|-------------------|
| `/cv2_test` | Slash | Computer vision testing | Member |
| `/recorder` | Slash | Voice recording features | Member |
| `/game_stats` | Slash | Gaming statistics | Member |

### 🐛 Debug Commands
**Purpose**: Debugging and development

| Command | Type | Description | Permission Required |
|---------|------|-------------|-------------------|
| `/bug_report` | Slash | Report bug to developers | Member |
| `/debug_info` | Slash | Display debug information | Administrator |
| `/test_feature` | Slash | Test new features | Developer |

## Command Structure

### Slash Command Structure
```python
@discord.app_commands.command(name="command_name", description="Command description")
@discord.app_commands.describe(
    parameter1="Description of parameter 1",
    parameter2="Description of parameter 2"
)
async def command_name(
    self, 
    interaction: discord.Interaction, 
    parameter1: str, 
    parameter2: int = None
):
    await interaction.response.send_message("Response")
```

### Prefix Command Structure
```python
@commands.command(name="command_name", help="Command help text")
@commands.has_permissions(administrator=True)
async def command_name(self, ctx, parameter1: str, parameter2: int = None):
    await ctx.send("Response")
```

## Permission System

### Permission Levels
1. **Bot Owner**: Full access to all commands
2. **Administrator**: Server administration commands
3. **Moderator**: Moderation and analysis commands
4. **Member**: Basic utility and entertainment commands
5. **Guest**: Limited read-only commands

### Permission Decorators
```python
# Discord.py permission checks
@commands.has_permissions(administrator=True)
@commands.has_role("Moderator")
@commands.has_any_role("Admin", "Moderator")

# Custom permission checks
@commands.check(is_bot_owner)
@commands.check(is_staff_member)
```

## Command Error Handling

### Common Error Types
- **Missing Permissions**: User lacks required permissions
- **Missing Arguments**: Required parameters not provided
- **Invalid Arguments**: Parameters don't match expected types
- **Command Not Found**: Command doesn't exist
- **Command Disabled**: Command temporarily disabled

### Error Response Examples
```python
# Permission error
"❌ You don't have permission to use this command."

# Missing argument error
"❌ Missing required argument: `user`. Usage: `/analyze_user <user>`"

# Invalid argument error
"❌ Invalid user specified. Please mention a valid server member."

# Command disabled error
"⚠️ This command is temporarily disabled for maintenance."
```

## Command Usage Statistics

### Most Used Commands
1. `/help` - Help and information
2. `/server_stats` - Server statistics
3. `/oshi_panel` - Role selection
4. `/ping` - Bot status check
5. `/announce` - Announcements

### Command Response Times
- **Simple Commands**: < 100ms
- **Database Queries**: < 500ms
- **Analysis Commands**: < 2s
- **Complex Operations**: < 5s

## Command Aliases

### Common Aliases
```python
# Multiple names for same command
@commands.command(aliases=['stats', 'info', 'status'])
async def server_stats(self, ctx):
    pass

# Short forms
@commands.command(aliases=['r'])
async def reload(self, ctx, cog):
    pass
```

## Command Cooldowns

### Cooldown Configuration
```python
# Per-user cooldown
@commands.cooldown(1, 30, commands.BucketType.user)

# Per-guild cooldown
@commands.cooldown(5, 60, commands.BucketType.guild)

# Global cooldown
@commands.cooldown(1, 10, commands.BucketType.default)
```

### Cooldown Bypass
- Bot owners bypass all cooldowns
- Administrators have reduced cooldowns
- Premium users may have cooldown reductions

## Command Documentation

### Help System
The bot includes a comprehensive help system:

```python
# General help
/help

# Category-specific help
/help category:administration

# Command-specific help
/help command:analyze_user
```

### Command Examples
Each command includes usage examples:

```
/analyze_user user:@username
/announce title:"Server Update" message:"New features available!"
/oshi_panel category:"Gaming Roles"
```

## Internationalization

### Supported Languages
- **Japanese (ja)**: Primary language
- **English (en)**: Secondary language

### Language Selection
```python
# User can set preferred language
/settings language:ja
/settings language:en
```

## Command Metrics

### Performance Monitoring
- Command execution time
- Success/failure rates
- Usage frequency
- Error patterns

### Analytics Dashboard
- Most popular commands
- Peak usage times
- User engagement metrics
- Error rate trends

---

## Related Documentation

- [Admin Commands](02-admin-commands.md)
- [User Commands](03-user-commands.md)
- [Tool Commands](04-tool-commands.md)
- [Error Handling](../02-core/04-error-handling.md)
