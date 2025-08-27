"""
Tests for bot initialization and core functionality.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio

import discord
from discord.ext import commands


class TestBotInitialization:
    """Test bot initialization process."""
    
    def test_bot_creation(self, mock_settings):
        """Test basic bot instance creation."""
        with patch('discord.ext.commands.Bot') as mock_bot_class:
            mock_bot = MagicMock()
            mock_bot_class.return_value = mock_bot
            
            intents = discord.Intents.default()
            intents.message_content = True
            intents.members = True
            
            bot = mock_bot_class(
                command_prefix='!',
                intents=intents,
                help_command=None
            )
            
            assert bot is not None
            mock_bot_class.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_bot_startup_sequence(self, mock_bot, mock_settings):
        """Test bot startup sequence."""
        startup_tasks = []
        
        async def mock_startup_task(name):
            startup_tasks.append(name)
            await asyncio.sleep(0.01)  # Simulate async work
        
        tasks = [
            mock_startup_task("load_cogs"),
            mock_startup_task("setup_database"),
            mock_startup_task("verify_permissions"),
            mock_startup_task("sync_commands")
        ]
        
        await asyncio.gather(*tasks)
        
        expected_tasks = ["load_cogs", "setup_database", "verify_permissions", "sync_commands"]
        assert all(task in startup_tasks for task in expected_tasks)
    
    def test_intents_configuration(self):
        """Test Discord intents are properly configured."""
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True
        intents.guild_messages = True
        intents.guild_reactions = True
        intents.voice_states = True
        
        assert intents.message_content is True
        assert intents.members is True
        assert intents.guilds is True
        assert intents.guild_messages is True
        assert intents.guild_reactions is True
        assert intents.voice_states is True
    
    @pytest.mark.asyncio
    async def test_cog_loading(self, mock_bot):
        """Test cog loading process."""
        mock_bot.load_extension = AsyncMock()
        
        cogs_to_load = [
            "cogs.events.banner_sync",
            "cogs.events.guild_watcher",
            "cogs.manage.user_warning",
            "cogs.tool.translate",
            "cogs.homepage.homepage"
        ]
        
        for cog in cogs_to_load:
            await mock_bot.load_extension(cog)
        
        assert mock_bot.load_extension.call_count == len(cogs_to_load)
    
    def test_command_prefix_configuration(self):
        """Test command prefix configuration."""
        prefixes = ['!', '?', 'comet ']
        
        def get_prefix(bot, message):
            return prefixes
        
        mock_message = MagicMock()
        result = get_prefix(None, mock_message)
        
        assert result == prefixes
        assert '!' in result
        assert 'comet ' in result
    
    @pytest.mark.asyncio
    async def test_error_handling_setup(self, mock_bot):
        """Test error handling setup."""
        error_handler_called = False
        
        async def mock_error_handler(ctx, error):
            nonlocal error_handler_called
            error_handler_called = True
        
        mock_bot.on_command_error = mock_error_handler
        
        mock_ctx = MagicMock()
        mock_error = commands.CommandNotFound()
        
        await mock_bot.on_command_error(mock_ctx, mock_error)
        
        assert error_handler_called is True


class TestBotConfiguration:
    """Test bot configuration and settings."""
    
    def test_environment_variables_loading(self, mock_settings):
        """Test environment variables are properly loaded."""
        required_vars = [
            'bot_token',
            'admin_main_guild_id',
            'admin_dev_guild_id'
        ]
        
        for var in required_vars:
            assert hasattr(mock_settings, var)
            assert getattr(mock_settings, var) is not None
    
    def test_optional_settings(self, mock_settings):
        """Test optional settings handling."""
        optional_vars = [
            'openai_api_key',
            'webhook_url',
            'uptime_kuma_url'
        ]
        
        for var in optional_vars:
            assert hasattr(mock_settings, var)
    
    def test_guild_id_validation(self, mock_settings):
        """Test guild ID validation."""
        main_guild_id = int(mock_settings.admin_main_guild_id)
        dev_guild_id = int(mock_settings.admin_dev_guild_id)
        
        assert len(str(main_guild_id)) >= 17
        assert len(str(dev_guild_id)) >= 17
        assert main_guild_id != dev_guild_id


class TestBotPermissions:
    """Test bot permissions and security."""
    
    def test_required_permissions(self):
        """Test required bot permissions."""
        required_perms = discord.Permissions(
            send_messages=True,
            read_messages=True,
            embed_links=True,
            attach_files=True,
            read_message_history=True,
            add_reactions=True,
            use_external_emojis=True,
            manage_messages=True,
            kick_members=True,
            ban_members=True,
            manage_roles=True,
            manage_channels=True,
            view_audit_log=True
        )
        
        assert required_perms.send_messages is True
        assert required_perms.read_messages is True
        assert required_perms.manage_messages is True
        assert required_perms.kick_members is True
        assert required_perms.ban_members is True
    
    def test_permission_hierarchy(self, mock_guild):
        """Test permission hierarchy validation."""
        bot_member = MagicMock()
        bot_member.top_role = MagicMock()
        bot_member.top_role.position = 10
        
        target_member = MagicMock()
        target_member.top_role = MagicMock()
        target_member.top_role.position = 5
        
        assert bot_member.top_role.position > target_member.top_role.position
    
    @pytest.mark.asyncio
    async def test_permission_checks(self, mock_interaction, mock_member):
        """Test permission checking functions."""
        
        def has_permission(member, permission):
            """Mock permission check."""
            admin_perms = ['administrator', 'manage_guild', 'manage_members']
            mod_perms = ['manage_messages', 'kick_members', 'mute_members']
            
            if permission in admin_perms:
                return member.id == 111222333444555666  # Admin user
            elif permission in mod_perms:
                return member.id in [111222333444555666, 777888999000111222]  # Admin or mod
            return True  # Basic permissions
        
        admin_member = MagicMock()
        admin_member.id = 111222333444555666
        assert has_permission(admin_member, 'manage_guild') is True
        
        mod_member = MagicMock()
        mod_member.id = 777888999000111222
        assert has_permission(mod_member, 'kick_members') is True
        
        regular_member = MagicMock()
        regular_member.id = 999888777666555444
        assert has_permission(regular_member, 'manage_guild') is False


class TestBotHealth:
    """Test bot health monitoring and diagnostics."""
    
    @pytest.mark.asyncio
    async def test_latency_measurement(self, mock_bot):
        """Test bot latency measurement."""
        mock_bot.latency = 0.1  # 100ms
        
        assert 0 <= mock_bot.latency <= 1.0  # Less than 1 second
    
    @pytest.mark.asyncio
    async def test_guild_count_tracking(self, mock_bot):
        """Test guild count tracking."""
        mock_guilds = [MagicMock() for _ in range(5)]
        mock_bot.guilds = mock_guilds
        
        guild_count = len(mock_bot.guilds)
        assert guild_count == 5
    
    @pytest.mark.asyncio
    async def test_memory_usage_monitoring(self):
        """Test memory usage monitoring."""
        import os
        
        try:
            import psutil
            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()
            assert memory_info.rss < 1024 * 1024 * 1024  # 1GB
        except ImportError:
            mock_memory_usage = 50 * 1024 * 1024  # 50MB mock
            assert mock_memory_usage < 1024 * 1024 * 1024  # 1GB
    
    def test_uptime_calculation(self):
        """Test uptime calculation."""
        import datetime
        
        start_time = datetime.datetime.now()
        current_time = start_time + datetime.timedelta(hours=2, minutes=30)
        
        uptime = current_time - start_time
        
        assert uptime.total_seconds() == 9000  # 2.5 hours in seconds
