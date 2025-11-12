# テストフレームワーク

## C.O.M.E.T.について

**C.O.M.E.T.**の名前は以下の頭文字から構成されています：

- **C**ommunity of
- **O**shilove
- **M**oderation &
- **E**njoyment
- **T**ogether

HFS - ホロライブ非公式ファンサーバーのコミュニティを支える、推し愛とモデレーション、そして楽しさを一緒に提供するボットです。

## 概要

COMETボットのテストフレームワークは、包括的なテスト戦略を提供し、コードの品質と信頼性を確保します。ユニットテスト、統合テスト、エンドツーエンドテスト、パフォーマンステストを含む多層的なテストアプローチを採用しています。

## テストアーキテクチャ

```
┌─────────────────────────────────────────────────────────────┐
│                    テストアーキテクチャ                       │
├─────────────────────────────────────────────────────────────┤
│  テスト管理層 (Test Management)                             │
│  ├── テストランナー                                          │
│  ├── テスト設定管理                                          │
│  ├── レポート生成                                            │
│  └── CI/CD統合                                              │
├─────────────────────────────────────────────────────────────┤
│  テスト実行層 (Test Execution)                              │
│  ├── ユニットテスト                                          │
│  ├── 統合テスト                                              │
│  ├── エンドツーエンドテスト                                  │
│  └── パフォーマンステスト                                    │
├─────────────────────────────────────────────────────────────┤
│  テストユーティリティ層 (Test Utilities)                    │
│  ├── モックオブジェクト                                      │
│  ├── テストデータ生成                                        │
│  ├── アサーションヘルパー                                    │
│  └── テスト環境管理                                          │
├─────────────────────────────────────────────────────────────┤
│  テスト対象層 (System Under Test)                           │
│  ├── Cogsテスト                                             │
│  ├── ユーティリティテスト                                    │
│  ├── APIテスト                                               │
│  └── データベーステスト                                      │
└─────────────────────────────────────────────────────────────┘
```

## テスト設定とセットアップ

### 1. テスト環境設定

```python
# tests/conftest.py
import pytest
import asyncio
import discord
from discord.ext import commands
import tempfile
import os
from unittest.mock import AsyncMock, MagicMock
from typing import Dict, Any

@pytest.fixture(scope="session")
def event_loop():
    """セッション全体で使用するイベントループ"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
async def mock_bot():
    """モックボットインスタンス"""
    intents = discord.Intents.all()
    bot = commands.Bot(command_prefix="!", intents=intents)
    
    # 必要な属性をモック
    bot.user = MagicMock()
    bot.user.id = 123456789
    bot.user.name = "COMET"
    bot.user.discriminator = "0001"
    
    bot.guilds = []
    bot.get_channel = AsyncMock()
    bot.get_guild = MagicMock()
    bot.get_user = MagicMock()
    
    yield bot
    
    if not bot.is_closed():
        await bot.close()

@pytest.fixture
def mock_guild():
    """モックギルドオブジェクト"""
    guild = MagicMock(spec=discord.Guild)
    guild.id = 987654321
    guild.name = "Test Guild"
    guild.member_count = 100
    guild.get_channel = MagicMock()
    guild.get_member = MagicMock()
    guild.get_role = MagicMock()
    return guild

@pytest.fixture
def mock_user():
    """モックユーザーオブジェクト"""
    user = MagicMock(spec=discord.User)
    user.id = 111111111
    user.name = "TestUser"
    user.discriminator = "1234"
    user.bot = False
    user.mention = "<@111111111>"
    return user

@pytest.fixture
def mock_member(mock_user, mock_guild):
    """モックメンバーオブジェクト"""
    member = MagicMock(spec=discord.Member)
    member.id = mock_user.id
    member.name = mock_user.name
    member.discriminator = mock_user.discriminator
    member.bot = mock_user.bot
    member.mention = mock_user.mention
    member.guild = mock_guild
    member.roles = []
    member.guild_permissions = discord.Permissions.all()
    return member

@pytest.fixture
def mock_channel():
    """モックチャンネルオブジェクト"""
    channel = MagicMock(spec=discord.TextChannel)
    channel.id = 222222222
    channel.name = "test-channel"
    channel.mention = "<#222222222>"
    channel.send = AsyncMock()
    return channel

@pytest.fixture
def mock_message(mock_user, mock_channel):
    """モックメッセージオブジェクト"""
    message = MagicMock(spec=discord.Message)
    message.id = 333333333
    message.author = mock_user
    message.channel = mock_channel
    message.content = "Test message"
    message.created_at = discord.utils.utcnow()
    message.jump_url = "https://discord.com/channels/987654321/222222222/333333333"
    return message

@pytest.fixture
def mock_context(mock_bot, mock_message, mock_channel, mock_user, mock_guild):
    """モックコンテキストオブジェクト"""
    ctx = MagicMock(spec=commands.Context)
    ctx.bot = mock_bot
    ctx.message = mock_message
    ctx.channel = mock_channel
    ctx.author = mock_user
    ctx.guild = mock_guild
    ctx.send = AsyncMock()
    ctx.reply = AsyncMock()
    return ctx

@pytest.fixture
def temp_database():
    """一時的なテスト用データベース"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
        db_path = tmp_file.name
    
    yield db_path
    
    # クリーンアップ
    if os.path.exists(db_path):
        os.unlink(db_path)

@pytest.fixture
def test_config():
    """テスト用設定"""
    return {
        "bot": {
            "token": "test_token",
            "prefix": "!",
            "debug": True
        },
        "database": {
            "url": ":memory:"
        },
        "logging": {
            "level": "DEBUG"
        }
    }
```

### 2. テストユーティリティ

```python
# tests/utils/test_helpers.py
import asyncio
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock
import discord
from discord.ext import commands

class TestDataGenerator:
    """テストデータ生成ユーティリティ"""
    
    @staticmethod
    def generate_user_data(user_id: int = None, **kwargs) -> Dict[str, Any]:
        """ユーザーデータの生成"""
        return {
            "id": user_id or 123456789,
            "username": kwargs.get("username", "testuser"),
            "discriminator": kwargs.get("discriminator", "0001"),
            "avatar": kwargs.get("avatar", "avatar_hash"),
            "bot": kwargs.get("bot", False),
            "system": kwargs.get("system", False),
            "mfa_enabled": kwargs.get("mfa_enabled", False),
            "verified": kwargs.get("verified", True),
            "email": kwargs.get("email", "test@example.com"),
            "flags": kwargs.get("flags", 0),
            "premium_type": kwargs.get("premium_type", 0),
            "public_flags": kwargs.get("public_flags", 0)
        }
    
    @staticmethod
    def generate_guild_data(guild_id: int = None, **kwargs) -> Dict[str, Any]:
        """ギルドデータの生成"""
        return {
            "id": guild_id or 987654321,
            "name": kwargs.get("name", "Test Guild"),
            "icon": kwargs.get("icon", "icon_hash"),
            "description": kwargs.get("description", "Test guild description"),
            "splash": kwargs.get("splash", None),
            "discovery_splash": kwargs.get("discovery_splash", None),
            "features": kwargs.get("features", []),
            "emojis": kwargs.get("emojis", []),
            "banner": kwargs.get("banner", None),
            "owner_id": kwargs.get("owner_id", 111111111),
            "application_id": kwargs.get("application_id", None),
            "region": kwargs.get("region", "japan"),
            "afk_channel_id": kwargs.get("afk_channel_id", None),
            "afk_timeout": kwargs.get("afk_timeout", 300),
            "system_channel_id": kwargs.get("system_channel_id", None),
            "widget_enabled": kwargs.get("widget_enabled", False),
            "widget_channel_id": kwargs.get("widget_channel_id", None),
            "verification_level": kwargs.get("verification_level", 0),
            "roles": kwargs.get("roles", []),
            "default_message_notifications": kwargs.get("default_message_notifications", 0),
            "mfa_level": kwargs.get("mfa_level", 0),
            "explicit_content_filter": kwargs.get("explicit_content_filter", 0),
            "max_presences": kwargs.get("max_presences", None),
            "max_members": kwargs.get("max_members", 250000),
            "max_video_channel_users": kwargs.get("max_video_channel_users", 25),
            "vanity_url_code": kwargs.get("vanity_url_code", None),
            "premium_tier": kwargs.get("premium_tier", 0),
            "premium_subscription_count": kwargs.get("premium_subscription_count", 0),
            "system_channel_flags": kwargs.get("system_channel_flags", 0),
            "preferred_locale": kwargs.get("preferred_locale", "ja"),
            "rules_channel_id": kwargs.get("rules_channel_id", None),
            "public_updates_channel_id": kwargs.get("public_updates_channel_id", None)
        }
    
    @staticmethod
    def generate_message_data(message_id: int = None, **kwargs) -> Dict[str, Any]:
        """メッセージデータの生成"""
        return {
            "id": message_id or 333333333,
            "channel_id": kwargs.get("channel_id", 222222222),
            "guild_id": kwargs.get("guild_id", 987654321),
            "author": kwargs.get("author", TestDataGenerator.generate_user_data()),
            "member": kwargs.get("member", None),
            "content": kwargs.get("content", "Test message content"),
            "timestamp": kwargs.get("timestamp", "2023-01-01T00:00:00.000000+00:00"),
            "edited_timestamp": kwargs.get("edited_timestamp", None),
            "tts": kwargs.get("tts", False),
            "mention_everyone": kwargs.get("mention_everyone", False),
            "mentions": kwargs.get("mentions", []),
            "mention_roles": kwargs.get("mention_roles", []),
            "mention_channels": kwargs.get("mention_channels", []),
            "attachments": kwargs.get("attachments", []),
            "embeds": kwargs.get("embeds", []),
            "reactions": kwargs.get("reactions", []),
            "nonce": kwargs.get("nonce", None),
            "pinned": kwargs.get("pinned", False),
            "webhook_id": kwargs.get("webhook_id", None),
            "type": kwargs.get("type", 0),
            "activity": kwargs.get("activity", None),
            "application": kwargs.get("application", None),
            "application_id": kwargs.get("application_id", None),
            "message_reference": kwargs.get("message_reference", None),
            "flags": kwargs.get("flags", 0),
            "referenced_message": kwargs.get("referenced_message", None),
            "interaction": kwargs.get("interaction", None),
            "thread": kwargs.get("thread", None),
            "components": kwargs.get("components", []),
            "sticker_items": kwargs.get("sticker_items", [])
        }

class AsyncTestCase:
    """非同期テスト用ベースクラス"""
    
    async def async_setup(self):
        """非同期セットアップ"""
        pass
    
    async def async_teardown(self):
        """非同期ティアダウン"""
        pass
    
    async def run_async_test(self, test_func, *args, **kwargs):
        """非同期テストの実行"""
        await self.async_setup()
        try:
            await test_func(*args, **kwargs)
        finally:
            await self.async_teardown()

class MockDiscordAPI:
    """Discord API のモック"""
    
    def __init__(self):
        self.responses = {}
        self.call_history = []
    
    def set_response(self, endpoint: str, response: Any):
        """APIレスポンスの設定"""
        self.responses[endpoint] = response
    
    async def request(self, method: str, endpoint: str, **kwargs):
        """APIリクエストのモック"""
        self.call_history.append({
            "method": method,
            "endpoint": endpoint,
            "kwargs": kwargs
        })
        
        if endpoint in self.responses:
            return self.responses[endpoint]
        
        # デフォルトレスポンス
        return {"status": "ok"}
    
    def get_call_history(self) -> List[Dict[str, Any]]:
        """呼び出し履歴の取得"""
        return self.call_history.copy()
    
    def clear_history(self):
        """履歴のクリア"""
        self.call_history.clear()
```

## ユニットテスト

### 1. Cogテスト例

```python
# tests/test_cogs/test_report_cogs.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from cogs.report.report_message import ReportMessageCog
from tests.utils.test_helpers import TestDataGenerator

class TestReportMessageCog:
    
    @pytest.fixture
    async def report_cog(self, mock_bot):
        """レポートCogのフィクスチャ"""
        cog = ReportMessageCog(mock_bot)
        await mock_bot.add_cog(cog)
        return cog
    
    @pytest.mark.asyncio
    async def test_report_message_setup(self, report_cog, mock_bot):
        """レポートメッセージのセットアップテスト"""
        # Cogが正しく追加されているかテスト
        assert report_cog in mock_bot.cogs.values()
    
    @pytest.mark.asyncio
    async def test_report_reason_select_callback(self, report_cog, mock_bot):
        """通報理由選択のコールバックテスト"""
        from cogs.report.report_message import ReportReasonSelect
        
        # モックオブジェクトの作成
        mock_message = MagicMock()
        mock_message.content = "Test message"
        mock_message.author.display_name = "TestUser"
        mock_message.author.id = 123456789
        mock_message.jump_url = "https://discord.com/test"
        
        mock_channel = MagicMock()
        mock_channel.send = AsyncMock()
        
        mock_interaction = MagicMock()
        mock_interaction.response.send_message = AsyncMock()
        mock_interaction.guild.get_role = MagicMock(return_value=MagicMock())
        
        # ReportReasonSelect のテスト
        select = ReportReasonSelect(mock_message, mock_channel)
        select.values = ["スパム"]
        select.view = MagicMock()
        select.view.stop = MagicMock()
        
        await select.callback(mock_interaction)
        
        # アサーション
        mock_interaction.response.send_message.assert_called_once()
        select.view.stop.assert_called_once()
        assert select.view.value == "スパム"
    
    @pytest.mark.asyncio
    async def test_other_reason_modal_submit(self, report_cog):
        """その他理由モーダルの送信テスト"""
        from cogs.report.report_message import OtherReasonModal
        
        # モックオブジェクトの作成
        mock_message = MagicMock()
        mock_message.content = "Test message"
        mock_message.author.display_name = "TestUser"
        mock_message.author.id = 123456789
        mock_message.jump_url = "https://discord.com/test"
        
        mock_channel = MagicMock()
        mock_channel.send = AsyncMock()
        
        mock_interaction = MagicMock()
        mock_interaction.response.send_message = AsyncMock()
        mock_interaction.followup.send = AsyncMock()
        mock_interaction.user.mention = "<@123456789>"
        mock_interaction.user.display_name = "Reporter"
        mock_interaction.user.id = 987654321
        mock_interaction.guild.roles = [MagicMock(name="moderator")]
        
        # OtherReasonModal のテスト
        modal = OtherReasonModal(mock_message, mock_channel)
        modal.reason.value = "カスタム通報理由"
        
        with patch('cogs.report.report_message.datetime') as mock_datetime:
            mock_datetime.now.return_value.astimezone.return_value = MagicMock()
            await modal.on_submit(mock_interaction)
        
        # アサーション
        mock_interaction.response.send_message.assert_called_once()
        mock_channel.send.assert_called_once()
        mock_interaction.followup.send.assert_called_once()
```

### 2. ユーティリティテスト例

```python
# tests/test_utils/test_logging.py
import pytest
import logging
import tempfile
import os
from utils.logging import setup_logging, COMETLogger

class TestLoggingSystem:
    
    @pytest.fixture
    def temp_log_dir(self):
        """一時ログディレクトリ"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    def test_setup_logging_basic(self):
        """基本的なログ設定のテスト"""
        logger = setup_logging("TEST")
        
        assert logger.name == "TEST"
        assert logger.level == logging.INFO
        assert len(logger.handlers) > 0
    
    def test_comet_logger_initialization(self):
        """COMETLoggerの初期化テスト"""
        logger = COMETLogger("TEST_COMET", "DEBUG")
        
        assert logger.name == "TEST_COMET"
        assert logger.level == logging.DEBUG
        assert logger.session_id is not None
        assert len(logger.session_id) == 8
    
    def test_log_file_creation(self, temp_log_dir):
        """ログファイル作成のテスト"""
        with patch('utils.logging.os.makedirs') as mock_makedirs:
            logger = COMETLogger("TEST_FILE")
            mock_makedirs.assert_called_with("logs", exist_ok=True)
    
    @pytest.mark.asyncio
    async def test_structured_logging(self):
        """構造化ログのテスト"""
        from utils.logging import StructuredLogger
        
        base_logger = logging.getLogger("TEST_STRUCTURED")
        structured_logger = StructuredLogger(base_logger)
        
        with patch.object(base_logger, 'log') as mock_log:
            structured_logger.info("Test message", user_id=123, command="test")
            
            mock_log.assert_called_once()
            args, kwargs = mock_log.call_args
            
            # ログレベルの確認
            assert args[0] == logging.INFO
            
            # JSON形式の確認
            import json
            log_data = json.loads(args[1])
            assert log_data["message"] == "Test message"
            assert log_data["user_id"] == 123
            assert log_data["command"] == "test"
```

## 統合テスト

### 1. データベース統合テスト

```python
# tests/test_integration/test_database_integration.py
import pytest
import sqlite3
import tempfile
import os
from utils.db_manager import DatabaseManager

class TestDatabaseIntegration:
    
    @pytest.fixture
    async def db_manager(self):
        """データベースマネージャーのフィクスチャ"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
            db_path = tmp_file.name
        
        manager = DatabaseManager(db_path)
        await manager.initialize()
        
        yield manager
        
        await manager.close()
        if os.path.exists(db_path):
            os.unlink(db_path)
    
    @pytest.mark.asyncio
    async def test_database_initialization(self, db_manager):
        """データベース初期化のテスト"""
        # テーブルの存在確認
        tables = await db_manager.get_table_list()
        expected_tables = ["system_info", "guild_settings", "logs", "error_statistics"]
        
        for table in expected_tables:
            assert table in tables
    
    @pytest.mark.asyncio
    async def test_crud_operations(self, db_manager):
        """CRUD操作のテスト"""
        # Create
        await db_manager.execute_query(
            "INSERT INTO system_info (key, value) VALUES (?, ?)",
            ("test_key", "test_value")
        )
        
        # Read
        result = await db_manager.fetch_one(
            "SELECT value FROM system_info WHERE key = ?",
            ("test_key",)
        )
        assert result["value"] == "test_value"
        
        # Update
        await db_manager.execute_query(
            "UPDATE system_info SET value = ? WHERE key = ?",
            ("updated_value", "test_key")
        )
        
        result = await db_manager.fetch_one(
            "SELECT value FROM system_info WHERE key = ?",
            ("test_key",)
        )
        assert result["value"] == "updated_value"
        
        # Delete
        await db_manager.execute_query(
            "DELETE FROM system_info WHERE key = ?",
            ("test_key",)
        )
        
        result = await db_manager.fetch_one(
            "SELECT value FROM system_info WHERE key = ?",
            ("test_key",)
        )
        assert result is None
    
    @pytest.mark.asyncio
    async def test_transaction_rollback(self, db_manager):
        """トランザクションロールバックのテスト"""
        try:
            async with db_manager.transaction():
                await db_manager.execute_query(
                    "INSERT INTO system_info (key, value) VALUES (?, ?)",
                    ("rollback_test", "value1")
                )
                
                # 意図的にエラーを発生させる
                await db_manager.execute_query(
                    "INSERT INTO system_info (key, value) VALUES (?, ?)",
                    ("rollback_test", "value2")  # 重複キーエラー
                )
        except Exception:
            pass  # エラーは期待される
        
        # ロールバックされているか確認
        result = await db_manager.fetch_one(
            "SELECT value FROM system_info WHERE key = ?",
            ("rollback_test",)
        )
        assert result is None
```

### 2. API統合テスト

```python
# tests/test_integration/test_api_integration.py
import pytest
import aiohttp
from unittest.mock import patch, AsyncMock
from utils.api_integration import HTTPClient, OpenAIClient

class TestAPIIntegration:
    
    @pytest.mark.asyncio
    async def test_http_client_get_request(self):
        """HTTPクライアントのGETリクエストテスト"""
        with patch('aiohttp.ClientSession.get') as mock_get:
            # モックレスポンスの設定
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={"status": "ok"})
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)
            mock_get.return_value = mock_response
            
            # HTTPクライアントのテスト
            async with HTTPClient("https://api.example.com") as client:
                result = await client.get("/test")
                
                assert result["status"] == "ok"
                mock_get.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_openai_client_chat_completion(self):
        """OpenAIクライアントのチャット補完テスト"""
        with patch('aiohttp.ClientSession.post') as mock_post:
            # モックレスポンスの設定
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={
                "choices": [
                    {
                        "message": {
                            "content": "Test response"
                        }
                    }
                ]
            })
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)
            mock_post.return_value = mock_response
            
            # OpenAIクライアントのテスト
            client = OpenAIClient("test_api_key")
            await client.create_session()
            
            messages = [{"role": "user", "content": "Hello"}]
            result = await client.chat_completion(messages)
            
            assert "choices" in result
            assert result["choices"][0]["message"]["content"] == "Test response"
            
            await client.close_session()
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self):
        """レート制限のテスト"""
        from utils.api_integration import RateLimiter
        import time
        
        rate_limiter = RateLimiter()
        rate_limiter.set_limit("/test", 2, 1)  # 1秒間に2リクエスト
        
        # 最初の2リクエストは即座に通る
        start_time = time.time()
        await rate_limiter.wait_if_needed("/test")
        await rate_limiter.wait_if_needed("/test")
        first_duration = time.time() - start_time
        
        assert first_duration < 0.1  # ほぼ即座
        
        # 3番目のリクエストは待機が必要
        start_time = time.time()
        await rate_limiter.wait_if_needed("/test")
        second_duration = time.time() - start_time
        
        assert second_duration >= 0.9  # 約1秒待機
```

## エンドツーエンドテスト

### 1. コマンド実行テスト

```python
# tests/test_e2e/test_command_execution.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from discord.ext import commands

class TestCommandExecution:
    
    @pytest.mark.asyncio
    async def test_ping_command_execution(self, mock_bot, mock_context):
        """pingコマンドの実行テスト"""
        # pingコマンドの追加
        @mock_bot.command()
        async def ping(ctx):
            await ctx.send("Pong!")
        
        # コマンドの実行
        await mock_bot.invoke(mock_context)
        
        # アサーション
        mock_context.send.assert_called_with("Pong!")
    
    @pytest.mark.asyncio
    async def test_error_handling_in_command(self, mock_bot, mock_context):
        """コマンドエラーハンドリングのテスト"""
        # エラーを発生させるコマンド
        @mock_bot.command()
        async def error_command(ctx):
            raise ValueError("Test error")
        
        # エラーハンドラーの設定
        error_handled = False
        
        @mock_bot.event
        async def on_command_error(ctx, error):
            nonlocal error_handled
            error_handled = True
            assert isinstance(error, commands.CommandInvokeError)
            assert isinstance(error.original, ValueError)
        
        # コマンドの実行
        mock_context.command = error_command
        await mock_bot.invoke(mock_context)
        
        # エラーハンドリングの確認
        assert error_handled
    
    @pytest.mark.asyncio
    async def test_permission_check(self, mock_bot, mock_context, mock_member):
        """権限チェックのテスト"""
        # 権限が必要なコマンド
        @mock_bot.command()
        @commands.has_permissions(manage_guild=True)
        async def admin_command(ctx):
            await ctx.send("Admin command executed")
        
        # 権限なしでテスト
        mock_member.guild_permissions.manage_guild = False
        mock_context.author = mock_member
        
        with pytest.raises(commands.MissingPermissions):
            await mock_bot.invoke(mock_context)
        
        # 権限ありでテスト
        mock_member.guild_permissions.manage_guild = True
        await mock_bot.invoke(mock_context)
        
        mock_context.send.assert_called_with("Admin command executed")
```

## パフォーマンステスト

### 1. 負荷テスト

```python
# tests/test_performance/test_load_testing.py
import pytest
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor

class TestPerformance:
    
    @pytest.mark.asyncio
    async def test_concurrent_command_execution(self, mock_bot):
        """並行コマンド実行のパフォーマンステスト"""
        execution_times = []
        
        @mock_bot.command()
        async def test_command(ctx):
            start_time = time.time()
            await asyncio.sleep(0.1)  # 模擬処理時間
            end_time = time.time()
            execution_times.append(end_time - start_time)
            await ctx.send("Command completed")
        
        # 複数のコンテキストを作成
        contexts = []
        for i in range(10):
            ctx = MagicMock()
            ctx.send = AsyncMock()
            ctx.command = test_command
            contexts.append(ctx)
        
        # 並行実行
        start_time = time.time()
        tasks = [mock_bot.invoke(ctx) for ctx in contexts]
        await asyncio.gather(*tasks)
        total_time = time.time() - start_time
        
        # アサーション
        assert len(execution_times) == 10
        assert total_time < 1.0  # 並行実行により1秒未満で完了
        assert all(0.1 <= t <= 0.2 for t in execution_times)  # 各コマンドは約0.1秒
    
    @pytest.mark.asyncio
    async def test_memory_usage_monitoring(self, mock_bot):
        """メモリ使用量監視のテスト"""
        import psutil
        import gc
        
        process = psutil.Process()
        initial_memory = process.memory_info().rss
        
        # メモリを消費する処理
        large_data = []
        for i in range(1000):
            large_data.append("x" * 1000)  # 1KB × 1000 = 1MB
        
        peak_memory = process.memory_info().rss
        
        # メモリ解放
        del large_data
        gc.collect()
        
        final_memory = process.memory_info().rss
        
        # アサーション
        memory_increase = peak_memory - initial_memory
        memory_decrease = peak_memory - final_memory
        
        assert memory_increase > 500000  # 少なくとも500KB増加
        assert memory_decrease > 0  # メモリが解放されている
    
    @pytest.mark.asyncio
    async def test_database_query_performance(self, temp_database):
        """データベースクエリパフォーマンステスト"""
        import sqlite3
        
        # データベース接続
        conn = sqlite3.connect(temp_database)
        cursor = conn.cursor()
        
        # テストテーブル作成
        cursor.execute("""
            CREATE TABLE performance_test (
                id INTEGER PRIMARY KEY,
                data TEXT
            )
        """)
        
        # 大量データ挿入のパフォーマンステスト
        start_time = time.time()
        
        data_to_insert = [(i, f"test_data_{i}") for i in range(1000)]
        cursor.executemany("INSERT INTO performance_test (id, data) VALUES (?, ?)", data_to_insert)
        conn.commit()
        
        insert_time = time.time() - start_time
        
        # 検索パフォーマンステスト
        start_time = time.time()
        
        cursor.execute("SELECT * FROM performance_test WHERE id < 100")
        results = cursor.fetchall()
        
        select_time = time.time() - start_time
        
        conn.close()
        
        # アサーション
        assert insert_time < 1.0  # 1秒以内で1000件挿入
        assert select_time < 0.1  # 0.1秒以内で検索完了
        assert len(results) == 100  # 正しい件数が取得されている
```

## テスト実行とレポート

### 1. テスト設定ファイル

```ini
# pytest.ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    --verbose
    --tb=short
    --strict-markers
    --disable-warnings
    --cov=cogs
    --cov=utils
    --cov-report=html
    --cov-report=term-missing
    --cov-fail-under=80
markers =
    unit: Unit tests
    integration: Integration tests
    e2e: End-to-end tests
    performance: Performance tests
    slow: Slow running tests
asyncio_mode = auto
```

### 2. テスト実行スクリプト

```python
# scripts/run_tests.py
import subprocess
import sys
import os
from pathlib import Path

def run_tests():
    """テストの実行"""
    
    # テストディレクトリの確認
    test_dir = Path("tests")
    if not test_dir.exists():
        print("❌ Tests directory not found")
        return False
    
    # pytest の実行
    cmd = [
        sys.executable, "-m", "pytest",
        "--verbose",
        "--tb=short",
        "--cov=cogs",
        "--cov=utils",
        "--cov-report=html",
        "--cov-report=term-missing",
        "--cov-fail-under=80"
    ]
    
    # 環境変数の設定
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path.cwd())
    
    try:
        result = subprocess.run(cmd, env=env, check=True)
        print("✅ All tests passed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Tests failed with exit code {e.returncode}")
        return False

def run_specific_test_category(category: str):
    """特定カテゴリのテスト実行"""
    cmd = [
        sys.executable, "-m", "pytest",
        "-m", category,
        "--verbose"
    ]
    
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path.cwd())
    
    try:
        subprocess.run(cmd, env=env, check=True)
        print(f"✅ {category} tests passed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {category} tests failed with exit code {e.returncode}")
        return False

if __name__ == "__main__":
    if len(sys.argv) > 1:
        category = sys.argv[1]
        run_specific_test_category(category)
    else:
        run_tests()
```

### 3. CI/CD統合

```yaml
# .github/workflows/tests.yml
name: Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.8, 3.9, "3.10", "3.11"]

    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v3
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install pytest pytest-cov pytest-asyncio
    
    - name: Run unit tests
      run: |
        python -m pytest tests/ -m "unit" --cov=cogs --cov=utils --cov-report=xml
    
    - name: Run integration tests
      run: |
        python -m pytest tests/ -m "integration" --cov=cogs --cov=utils --cov-report=xml --cov-append
    
    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
        flags: unittests
        name: codecov-umbrella
```

---

## 関連ドキュメント

- [開発環境セットアップ](01-development-setup.md)
- [デプロイガイド](03-deployment-guide.md)
- [貢献ガイドライン](04-contributing-guidelines.md)
- [エラーハンドリング](../02-core/04-error-handling.md)
