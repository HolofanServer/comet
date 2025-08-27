"""
Pytest configuration and shared fixtures for COMET bot tests.
"""

import pytest
import asyncio
import os
import tempfile
import sqlite3
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

import sys
from unittest.mock import MagicMock

discord_mock = MagicMock()
discord_mock.Intents = MagicMock()
discord_mock.Intents.default = MagicMock(return_value=MagicMock())
discord_mock.Guild = MagicMock()
discord_mock.TextChannel = MagicMock()
discord_mock.User = MagicMock()
discord_mock.Member = MagicMock()
discord_mock.Message = MagicMock()
discord_mock.Interaction = MagicMock()
discord_mock.Embed = MagicMock()
discord_mock.Color = MagicMock()
discord_mock.Status = MagicMock()
discord_mock.Status.online = "online"
discord_mock.Status.idle = "idle"
discord_mock.Status.dnd = "dnd"
discord_mock.Status.offline = "offline"
discord_mock.MessageType = MagicMock()
discord_mock.MessageType.default = "default"

permissions_mock = MagicMock()
permissions_mock.send_messages = True
permissions_mock.read_messages = True
permissions_mock.embed_links = True
permissions_mock.attach_files = True
permissions_mock.read_message_history = True
permissions_mock.add_reactions = True
permissions_mock.use_external_emojis = True
permissions_mock.manage_messages = True
permissions_mock.kick_members = True
permissions_mock.ban_members = True
permissions_mock.manage_roles = True
permissions_mock.manage_channels = True
permissions_mock.view_audit_log = True
discord_mock.Permissions = MagicMock(return_value=permissions_mock)

commands_mock = MagicMock()
commands_mock.Bot = MagicMock()
commands_mock.Cog = MagicMock()

ext_mock = MagicMock()
ext_mock.commands = commands_mock

sys.modules['discord'] = discord_mock
sys.modules['discord.ext'] = ext_mock
sys.modules['discord.ext.commands'] = commands_mock

import discord
from discord.ext import commands

TEST_BOT_TOKEN = "test_token_123456789"
TEST_GUILD_ID = 123456789012345678
TEST_CHANNEL_ID = 987654321098765432
TEST_USER_ID = 111222333444555666


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_bot():
    """Create a mock Discord bot instance."""
    bot = MagicMock()
    bot.user = MagicMock()
    bot.user.id = 987654321012345678
    bot.user.name = "COMET Test"
    bot.user.discriminator = "0000"
    bot.latency = 0.1
    bot.guilds = []
    bot.get_guild = MagicMock(return_value=None)
    bot.get_channel = MagicMock(return_value=None)
    bot.get_user = MagicMock(return_value=None)
    return bot


@pytest.fixture
def mock_guild():
    """Create a mock Discord guild."""
    guild = MagicMock()
    guild.id = TEST_GUILD_ID
    guild.name = "Test Guild"
    guild.member_count = 100
    guild.owner_id = TEST_USER_ID
    guild.channels = []
    guild.roles = []
    guild.members = []
    guild.get_channel = MagicMock(return_value=None)
    guild.get_member = MagicMock(return_value=None)
    guild.get_role = MagicMock(return_value=None)
    return guild


@pytest.fixture
def mock_channel():
    """Create a mock Discord channel."""
    channel = MagicMock()
    channel.id = TEST_CHANNEL_ID
    channel.name = "test-channel"
    channel.guild = None
    channel.send = AsyncMock()
    channel.purge = AsyncMock()
    return channel


@pytest.fixture
def mock_user():
    """Create a mock Discord user."""
    user = MagicMock()
    user.id = TEST_USER_ID
    user.name = "TestUser"
    user.discriminator = "1234"
    user.display_name = "Test User"
    user.bot = False
    user.created_at = None
    return user


@pytest.fixture
def mock_member():
    """Create a mock Discord member."""
    member = MagicMock()
    member.id = TEST_USER_ID
    member.name = "TestUser"
    member.discriminator = "1234"
    member.display_name = "Test User"
    member.nick = None
    member.bot = False
    member.guild = None
    member.roles = []
    member.joined_at = None
    member.created_at = None
    return member


@pytest.fixture
def mock_message():
    """Create a mock Discord message."""
    message = MagicMock()
    message.id = 123456789012345678
    message.content = "Test message"
    message.author = None
    message.channel = None
    message.guild = None
    message.created_at = None
    message.edited_at = None
    message.delete = AsyncMock()
    message.edit = AsyncMock()
    message.add_reaction = AsyncMock()
    return message


@pytest.fixture
def mock_interaction():
    """Create a mock Discord interaction."""
    interaction = MagicMock()
    interaction.user = None
    interaction.guild = None
    interaction.channel = None
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.defer = AsyncMock()
    interaction.followup = MagicMock()
    interaction.followup.send = AsyncMock()
    return interaction


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS test_data (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            value TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    
    yield db_path
    
    os.unlink(db_path)


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = MagicMock()
    settings.bot_token = TEST_BOT_TOKEN
    settings.admin_main_guild_id = str(TEST_GUILD_ID)
    settings.admin_dev_guild_id = str(TEST_GUILD_ID + 1)
    settings.openai_api_key = "test_openai_key"
    settings.webhook_url = "https://example.com/webhook"
    settings.uptime_kuma_url = "https://example.com/uptime"
    return settings


@pytest.fixture
def mock_logger():
    """Create a mock logger for testing."""
    logger = MagicMock()
    logger.info = MagicMock()
    logger.warning = MagicMock()
    logger.error = MagicMock()
    logger.debug = MagicMock()
    return logger


@pytest.fixture
def mock_aiohttp_session():
    """Create a mock aiohttp session for testing."""
    session = MagicMock()
    
    class MockHTTPMethod:
        def __init__(self):
            self.return_value = MockHTTPResponse()
        
        def __call__(self, *args, **kwargs):
            return self.return_value
    
    session.get = MockHTTPMethod()
    session.post = MockHTTPMethod()
    session.put = MockHTTPMethod()
    session.delete = MockHTTPMethod()
    
    return session


@pytest.fixture(autouse=True)
def mock_discord_api():
    """Automatically mock Discord API calls for all tests."""
    with patch('discord.Client.start'), \
         patch('discord.Client.close'), \
         patch('discord.Client.login'), \
         patch('discord.Client.connect'), \
         patch('discord.Client.wait_until_ready'):
        yield


@pytest.fixture
def sample_cog_data():
    """Sample data for testing cogs."""
    return {
        "commands": [
            {"name": "test_command", "description": "Test command"},
            {"name": "admin_command", "description": "Admin only command"}
        ],
        "events": [
            "on_message",
            "on_member_join",
            "on_guild_join"
        ],
        "settings": {
            "enabled": True,
            "log_channel": TEST_CHANNEL_ID
        }
    }


@pytest.fixture
def mock_file_system():
    """Mock file system operations."""
    with patch('builtins.open'), \
         patch('os.path.exists', return_value=True), \
         patch('os.makedirs'), \
         patch('pathlib.Path.mkdir'), \
         patch('pathlib.Path.exists', return_value=True):
        yield


class AsyncContextManager:
    """Helper class for async context managers in tests."""
    
    def __init__(self, return_value=None):
        self.return_value = return_value
    
    async def __aenter__(self):
        return self.return_value
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


class MockHTTPResponse:
    """Mock HTTP response that supports async context manager protocol."""
    
    def __init__(self):
        self.status = 200
        self.json = AsyncMock(return_value={"test": "data"})
        self.text = AsyncMock(return_value="test response")
        self.read = AsyncMock(return_value=b"test bytes")
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
    
    def __await__(self):
        async def _await():
            return self
        return _await().__await__()


@pytest.fixture
def async_context_manager():
    """Factory for creating async context managers."""
    return AsyncContextManager
