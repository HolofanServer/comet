# Tool Cogs

## Overview

Tool cogs provide utility functions, analysis capabilities, and interactive features for server members and administrators.

## Available Tool Cogs

### 1. User Analyzer (`user_analyzer.py`)

**Purpose**: AI-powered analysis of user behavior and communication patterns using OpenAI GPT-4.

**Key Features**:
- **Message Collection**: Scans server channels for user messages
- **AI Analysis**: Uses GPT-4 to analyze communication patterns
- **Comprehensive Reports**: Generates detailed personality and behavior insights
- **File Output**: Saves analysis results as Markdown files
- **Progress Tracking**: Real-time progress updates during analysis

**Implementation Details**:
```python
@app_commands.command(name="user_analyze")
@is_guild_app()
@is_owner_app()
async def analyze_user(self, interaction, user: discord.Member, 
                      channel_limit: Optional[int] = None,
                      message_limit: Optional[int] = None):
```

**Analysis Process**:
1. **Message Collection**: Scans specified channels for user messages
2. **Data Formatting**: Structures messages with timestamps, reactions, attachments
3. **AI Processing**: Sends data to OpenAI GPT-4 for analysis
4. **Report Generation**: Creates comprehensive personality analysis
5. **File Storage**: Saves results to `cache/user_analysis/`

**Analysis Categories**:
- Communication style and patterns
- Topic preferences and interests
- Emotional tendencies
- Social interaction patterns
- Language usage characteristics
- Personality trait assessment

### 2. Bug Reporter (`bug.py`)

**Purpose**: Streamlined bug reporting system for users to report issues directly to developers.

**Key Features**:
- **DM-Only Interface**: Private bug reporting via direct messages
- **Image Attachments**: Support for screenshot attachments
- **Automatic Forwarding**: Routes reports to designated bug report channel
- **User-Friendly**: Simple command interface

**Commands**:
```python
@commands.hybrid_command(name="bug_report")
@commands.dm_only()
async def bug_report(self, ctx, 内容: str, 画像: discord.Attachment = None):
```

### 3. Message Analyzer (`ms_ana.py`)

**Purpose**: Analyzes message patterns and content for moderation and insights.

**Key Features**:
- **Message Pattern Analysis**: Identifies trends in server communication
- **Content Analysis**: Examines message content for various metrics
- **File Processing**: Can analyze uploaded text files
- **Statistical Reports**: Generates usage statistics and patterns

**Commands**:
- `analyze`: Analyze recent server messages
- `analyze_file`: Analyze uploaded text files

### 4. Welcome Message (`welcom_message.py`)

**Purpose**: Manages welcome messages and new member onboarding.

**Key Features**:
- **Custom Welcome Messages**: Configurable welcome content
- **Channel Management**: Set specific welcome channels
- **Role Assignment**: Automatic role assignment for new members
- **Personalization**: Customizable welcome experience

**Commands**:
```python
@commands.hybrid_command(name="set_welcome_channel")
@is_guild()
@is_owner()
async def set_welcome_channel(self, ctx, channel: discord.TextChannel):
```

### 5. Additional Tool Cogs

Based on the codebase structure, additional tool cogs include:

- **Announcement New** (`announcement_new.py`): Advanced announcement system
- **Recorder** (`recorder.py`): Voice/activity recording features  
- **Oshi Role Panel** (`oshi_role_panel.py`): Role selection interface
- **Custom Announcement** (`custom_announcement.py`): Customizable announcements
- **Server Stats** (`server_stats.py`): Real-time server statistics
- **CV2 Test** (`cv2_test.py`): Computer vision testing tools

## Common Patterns

### Permission Decorators
```python
@is_guild_app()      # Guild-only slash commands
@is_owner_app()      # Owner-only slash commands
@is_guild()          # Guild-only prefix commands
@is_owner()          # Owner-only prefix commands
@log_commands()      # Command usage logging
```

### Error Handling
```python
try:
    # Tool operation
    result = await perform_analysis()
    await interaction.response.send_message(f"✅ {result}")
except Exception as e:
    logger.error(f"Tool operation failed: {e}")
    await interaction.response.send_message(f"❌ Operation failed: {e}")
```

### Async Task Management
```python
# For long-running operations
task = asyncio.create_task(long_running_analysis())
self.analysis_tasks[user.id] = task
```

## Configuration

### API Keys
Tool cogs often require external API access:
```python
OPENAI_API_KEY = settings.etc_api_openai_api_key
async_client_ai = AsyncOpenAI(api_key=OPENAI_API_KEY)
```

### File Storage
Results are typically stored in organized directories:
```
cache/
├── user_analysis/
│   └── analysis_123456_20240101_120000.md
├── message_data/
└── reports/
```

### Rate Limiting
Commands implement appropriate rate limiting:
```python
@commands.cooldown(1, 30, commands.BucketType.user)
```

## Usage Examples

### User Analysis
```
/user_analyze user:@username channel_limit:10 message_limit:500
```

### Bug Reporting
```
/bug_report 内容:"Bot crashes when using command" 画像:[screenshot.png]
```

### Welcome Setup
```
/set_welcome_channel channel:#welcome
```

---

## Related Documentation

- [AI Integration](../04-utilities/03-ai-integration.md)
- [File Management](../04-utilities/04-file-management.md)
- [Command Categories](../06-commands/01-command-categories.md)
- [Error Handling](../02-core/04-error-handling.md)
