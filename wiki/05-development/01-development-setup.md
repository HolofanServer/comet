# Development Setup

## Prerequisites

### System Requirements
- **Operating System**: Linux (Ubuntu/Debian recommended), macOS, or Windows with WSL
- **Python**: 3.8 or higher (3.10+ recommended)
- **Git**: Latest version
- **Text Editor**: VS Code, PyCharm, or similar with Python support

### Required Accounts
- **Discord Developer Account**: For bot token and application management
- **GitHub Account**: For repository access and contributions

## Installation Guide

### 1. Clone Repository
```bash
git clone https://github.com/FreeWiFi7749/hfs-homepage-mg-bot.git
cd hfs-homepage-mg-bot
```

### 2. Python Environment Setup

#### Using venv (Recommended)
```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# On Linux/macOS:
source venv/bin/activate
# On Windows:
venv\Scripts\activate
```

#### Using conda (Alternative)
```bash
# Create conda environment
conda create -n iphone3g python=3.10
conda activate iphone3g
```

### 3. Install Dependencies
```bash
# Install required packages
pip install -r requirements.txt

# For development dependencies (if available)
pip install -r requirements-dev.txt
```

### 4. Environment Configuration

#### Create Environment File
```bash
cp .env.example .env
```

#### Configure Environment Variables
Edit `.env` file with your settings:

```env
# Discord Bot Configuration
BOT_TOKEN=your_discord_bot_token_here
ADMIN_MAIN_GUILD_ID=your_main_guild_id
ADMIN_DEV_GUILD_ID=your_dev_guild_id
ADMIN_STARTUP_CHANNEL_ID=your_startup_channel_id
ADMIN_BUG_REPORT_CHANNEL_ID=your_bug_report_channel_id
ADMIN_ERROR_LOG_CHANNEL_ID=your_error_log_channel_id

# Authentication
AUTH_TOKEN=your_auth_token
AUTH_URL=your_auth_endpoint

# Optional: Sentry (Error Tracking)
SENTRY_DSN=your_sentry_dsn_here

# Optional: Prometheus (Monitoring)
PROMETHEUS_ENABLED=false
PROMETHEUS_PORT=8001
```

### 5. Discord Bot Setup

#### Create Discord Application
1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application"
3. Name your application (e.g., "iPhone3G Dev")
4. Go to "Bot" section
5. Click "Add Bot"
6. Copy the bot token to your `.env` file

#### Bot Permissions
Required permissions for full functionality:
- **General Permissions**:
  - Manage Roles
  - Manage Channels
  - Kick Members
  - Ban Members
  - Create Instant Invite
  - Manage Nicknames
  - Manage Emojis and Stickers
  - View Audit Log

- **Text Permissions**:
  - Send Messages
  - Send Messages in Threads
  - Create Public Threads
  - Create Private Threads
  - Embed Links
  - Attach Files
  - Read Message History
  - Mention Everyone
  - Use External Emojis
  - Add Reactions
  - Use Slash Commands

- **Voice Permissions**:
  - Connect
  - Speak
  - Use Voice Activity

#### Invite Bot to Server
1. Go to "OAuth2" → "URL Generator"
2. Select "bot" and "applications.commands" scopes
3. Select required permissions
4. Use generated URL to invite bot to your test server

## Development Workflow

### 1. Branch Management
```bash
# Create feature branch
git checkout -b feature/your-feature-name

# Make changes and commit
git add .
git commit -m "feat: add new feature"

# Push to remote
git push origin feature/your-feature-name
```

### 2. Running the Bot

#### Development Mode
```bash
# Run with debug logging
python main.py
```

#### Production Mode
```bash
# Set production environment
export ENVIRONMENT=production
python main.py
```

### 3. Testing

#### Manual Testing
1. Start the bot in development mode
2. Use test Discord server for validation
3. Test commands and features
4. Monitor logs for errors

#### Automated Testing (if available)
```bash
# Run unit tests
python -m pytest tests/

# Run with coverage
python -m pytest tests/ --cov=.
```

## Development Tools

### 1. Code Formatting
```bash
# Install black (code formatter)
pip install black

# Format code
black .

# Check formatting
black --check .
```

### 2. Linting
```bash
# Install flake8 (linter)
pip install flake8

# Run linting
flake8 .
```

### 3. Type Checking
```bash
# Install mypy (type checker)
pip install mypy

# Run type checking
mypy .
```

### 4. Pre-commit Hooks (Recommended)
```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install

# Run hooks manually
pre-commit run --all-files
```

## IDE Configuration

### VS Code Setup

#### Recommended Extensions
- Python
- Python Docstring Generator
- GitLens
- Discord.py Snippets
- JSON Tools

#### Settings (`.vscode/settings.json`)
```json
{
    "python.defaultInterpreterPath": "./venv/bin/python",
    "python.linting.enabled": true,
    "python.linting.flake8Enabled": true,
    "python.formatting.provider": "black",
    "python.formatting.blackArgs": ["--line-length", "88"],
    "files.exclude": {
        "**/__pycache__": true,
        "**/*.pyc": true
    }
}
```

### PyCharm Setup

#### Configuration
1. Open project in PyCharm
2. Configure Python interpreter to use virtual environment
3. Enable code inspections for Python
4. Configure code style to match project standards

## Debugging

### 1. Debug Configuration

#### VS Code Debug Configuration (`.vscode/launch.json`)
```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Python: Bot",
            "type": "python",
            "request": "launch",
            "program": "main.py",
            "console": "integratedTerminal",
            "env": {
                "PYTHONPATH": "${workspaceFolder}"
            }
        }
    ]
}
```

### 2. Logging Configuration
```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Discord.py debug logging
logging.getLogger('discord').setLevel(logging.DEBUG)
logging.getLogger('discord.http').setLevel(logging.INFO)
```

### 3. Jishaku (Development Extension)
The bot includes Jishaku for runtime debugging:

```python
# Load/reload cogs
>load cogs.tool.example
>reload cogs.tool.example

# Execute Python code
>py await ctx.send("Hello from Jishaku!")

# Shell commands
>sh git status

# SQL queries (if database available)
>sql SELECT * FROM users LIMIT 5
```

## Common Issues and Solutions

### 1. Import Errors
```bash
# Ensure PYTHONPATH is set correctly
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Or use relative imports in code
from .utils import helper_function
```

### 2. Permission Errors
- Verify bot has required permissions in Discord server
- Check role hierarchy (bot role must be above managed roles)
- Ensure bot is in the correct channels

### 3. Token Issues
- Regenerate bot token if compromised
- Ensure token is correctly set in environment variables
- Check for extra spaces or characters in token

### 4. Database Issues
```bash
# Reset database (development only)
rm -f config/*.json
python main.py  # Will recreate with defaults
```

## Performance Monitoring

### 1. Memory Usage
```python
import psutil
import os

def get_memory_usage():
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1024 / 1024  # MB
```

### 2. Response Times
```python
import time
from functools import wraps

def measure_time(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start = time.time()
        result = await func(*args, **kwargs)
        end = time.time()
        print(f"{func.__name__} took {end - start:.2f} seconds")
        return result
    return wrapper
```

## Contributing Guidelines

### 1. Code Standards
- Follow PEP 8 style guidelines
- Use type hints where possible
- Write descriptive commit messages
- Add docstrings to functions and classes

### 2. Pull Request Process
1. Create feature branch from `main`
2. Make changes with appropriate tests
3. Update documentation if needed
4. Submit pull request with clear description
5. Address review feedback

### 3. Issue Reporting
- Use GitHub issue templates
- Provide clear reproduction steps
- Include relevant logs and error messages
- Tag issues appropriately

---

## Related Documentation

- [Bot Architecture Overview](../01-architecture/01-bot-architecture-overview.md)
- [Configuration Management](../01-architecture/04-configuration-management.md)
- [Testing Framework](02-testing-framework.md)
- [Contributing Guidelines](04-contributing-guidelines.md)
