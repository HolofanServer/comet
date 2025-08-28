"""
Tests for user commands functionality.
"""

import random
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest


class TestBasicCommands:
    """Test basic user commands."""

    @pytest.mark.asyncio
    async def test_ping_command(self, mock_interaction, mock_bot):
        """Test ping command functionality."""

        async def ping_command(interaction):
            """Mock ping command."""
            latency = mock_bot.latency * 1000  # Convert to ms

            embed = {
                "title": "🏓 Pong!",
                "fields": [
                    {"name": "Bot Latency", "value": f"{latency:.2f}ms"},
                    {"name": "API Latency", "value": "50.00ms"}
                ]
            }

            await interaction.response.send_message(embed=embed)

        mock_bot.latency = 0.1  # 100ms
        await ping_command(mock_interaction)

        mock_interaction.response.send_message.assert_called_once()
        call_args = mock_interaction.response.send_message.call_args
        embed = call_args[1]["embed"]

        assert embed["title"] == "🏓 Pong!"
        assert "100.00ms" in embed["fields"][0]["value"]

    @pytest.mark.asyncio
    async def test_help_command(self, mock_interaction):
        """Test help command functionality."""

        def get_command_categories():
            """Mock command categories."""
            return {
                "General": ["ping", "help", "info"],
                "Fun": ["dice", "8ball", "joke"],
                "Utility": ["translate", "weather", "timer"]
            }

        async def help_command(interaction, command_name=None):
            """Mock help command."""
            if command_name:
                command_info = {
                    "ping": "Check bot latency and response time",
                    "dice": "Roll a dice with specified sides",
                    "translate": "Translate text to another language"
                }

                if command_name in command_info:
                    embed = {
                        "title": f"Help: {command_name}",
                        "description": command_info[command_name]
                    }
                else:
                    embed = {
                        "title": "Command Not Found",
                        "description": f"Command '{command_name}' not found"
                    }
            else:
                categories = get_command_categories()
                embed = {
                    "title": "Bot Commands",
                    "fields": [
                        {"name": category, "value": ", ".join(commands)}
                        for category, commands in categories.items()
                    ]
                }

            await interaction.response.send_message(embed=embed)

        await help_command(mock_interaction)
        mock_interaction.response.send_message.assert_called()

        mock_interaction.response.send_message.reset_mock()
        await help_command(mock_interaction, "ping")

        call_args = mock_interaction.response.send_message.call_args
        embed = call_args[1]["embed"]
        assert embed["title"] == "Help: ping"

    @pytest.mark.asyncio
    async def test_info_command(self, mock_interaction, mock_bot):
        """Test bot info command."""

        async def info_command(interaction):
            """Mock info command."""
            bot_info = {
                "name": "COMET",
                "version": "1.0.0",
                "guilds": len(mock_bot.guilds),
                "users": sum(guild.member_count for guild in mock_bot.guilds),
                "uptime": "2 days, 5 hours"
            }

            embed = {
                "title": f"{bot_info['name']} Bot Information",
                "fields": [
                    {"name": "Version", "value": bot_info["version"]},
                    {"name": "Servers", "value": str(bot_info["guilds"])},
                    {"name": "Users", "value": str(bot_info["users"])},
                    {"name": "Uptime", "value": bot_info["uptime"]}
                ]
            }

            await interaction.response.send_message(embed=embed)

        mock_guild1 = MagicMock()
        mock_guild1.member_count = 100
        mock_guild2 = MagicMock()
        mock_guild2.member_count = 200
        mock_bot.guilds = [mock_guild1, mock_guild2]

        await info_command(mock_interaction)

        call_args = mock_interaction.response.send_message.call_args
        embed = call_args[1]["embed"]

        assert "COMET Bot Information" in embed["title"]
        assert any("2" in field["value"] for field in embed["fields"] if field["name"] == "Servers")
        assert any("300" in field["value"] for field in embed["fields"] if field["name"] == "Users")


class TestFunCommands:
    """Test entertainment commands."""

    @pytest.mark.asyncio
    async def test_dice_command(self, mock_interaction):
        """Test dice rolling command."""

        async def dice_command(interaction, sides=6, count=1):
            """Mock dice command."""
            if sides < 2 or sides > 100:
                await interaction.response.send_message("Dice sides must be between 2 and 100")
                return

            if count < 1 or count > 10:
                await interaction.response.send_message("Dice count must be between 1 and 10")
                return

            results = [random.randint(1, sides) for _ in range(count)]
            total = sum(results)

            embed = {
                "title": f"🎲 Dice Roll (d{sides})",
                "description": f"Results: {', '.join(map(str, results))}",
                "fields": [
                    {"name": "Total", "value": str(total)},
                    {"name": "Average", "value": f"{total/count:.1f}"}
                ]
            }

            await interaction.response.send_message(embed=embed)

        with patch('random.randint', return_value=4):
            await dice_command(mock_interaction, 6, 2)

        call_args = mock_interaction.response.send_message.call_args
        embed = call_args[1]["embed"]

        assert "🎲 Dice Roll (d6)" in embed["title"]
        assert "4, 4" in embed["description"]
        assert "8" in next(field["value"] for field in embed["fields"] if field["name"] == "Total")

        mock_interaction.response.send_message.reset_mock()
        await dice_command(mock_interaction, 150, 1)  # Too many sides

        call_args = mock_interaction.response.send_message.call_args
        assert "between 2 and 100" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_8ball_command(self, mock_interaction):
        """Test 8ball command."""

        async def eightball_command(interaction, question):
            """Mock 8ball command."""
            if not question.strip():
                await interaction.response.send_message("Please provide a question!")
                return

            responses = [
                "Yes, definitely!",
                "No, absolutely not.",
                "Maybe, try again later.",
                "The signs point to yes.",
                "Very doubtful.",
                "Without a doubt.",
                "My sources say no.",
                "It is certain."
            ]

            response = random.choice(responses)

            embed = {
                "title": "🎱 Magic 8-Ball",
                "fields": [
                    {"name": "Question", "value": question},
                    {"name": "Answer", "value": response}
                ]
            }

            await interaction.response.send_message(embed=embed)

        with patch('random.choice', return_value="Yes, definitely!"):
            await eightball_command(mock_interaction, "Will it rain today?")

        call_args = mock_interaction.response.send_message.call_args
        embed = call_args[1]["embed"]

        assert embed["title"] == "🎱 Magic 8-Ball"
        assert "Will it rain today?" in embed["fields"][0]["value"]
        assert "Yes, definitely!" in embed["fields"][1]["value"]

    @pytest.mark.asyncio
    async def test_choice_command(self, mock_interaction):
        """Test choice command."""

        async def choice_command(interaction, *options):
            """Mock choice command."""
            if len(options) < 2:
                await interaction.response.send_message("Please provide at least 2 options!")
                return

            if len(options) > 10:
                await interaction.response.send_message("Too many options! Maximum is 10.")
                return

            chosen = random.choice(options)

            embed = {
                "title": "🎯 Random Choice",
                "fields": [
                    {"name": "Options", "value": ", ".join(options)},
                    {"name": "Chosen", "value": chosen}
                ]
            }

            await interaction.response.send_message(embed=embed)

        options = ["pizza", "burger", "sushi"]
        with patch('random.choice', return_value="pizza"):
            await choice_command(mock_interaction, *options)

        call_args = mock_interaction.response.send_message.call_args
        embed = call_args[1]["embed"]

        assert embed["title"] == "🎯 Random Choice"
        assert "pizza, burger, sushi" in embed["fields"][0]["value"]
        assert "pizza" in embed["fields"][1]["value"]


class TestUtilityCommands:
    """Test utility commands."""

    @pytest.mark.asyncio
    async def test_translate_command(self, mock_interaction, mock_aiohttp_session):
        """Test translate command."""

        async def translate_command(interaction, target_lang, text):
            """Mock translate command."""
            mock_aiohttp_session.post.return_value.json.return_value = {
                "translated_text": f"[{target_lang.upper()}] {text}",
                "source_language": "en",
                "confidence": 0.95
            }

            if len(text) > 1000:
                await interaction.response.send_message("Text too long! Maximum 1000 characters.")
                return

            response = await mock_aiohttp_session.post(
                "https://api.translate.example.com/v1/translate",
                json={"text": text, "target": target_lang}
            )
            result = await response.json()

            embed = {
                "title": "🌐 Translation",
                "fields": [
                    {"name": "Original", "value": text},
                    {"name": "Translated", "value": result["translated_text"]},
                    {"name": "Language", "value": f"{result['source_language']} → {target_lang}"}
                ]
            }

            await interaction.response.send_message(embed=embed)

        await translate_command(mock_interaction, "ja", "Hello world")

        call_args = mock_interaction.response.send_message.call_args
        embed = call_args[1]["embed"]

        assert embed["title"] == "🌐 Translation"
        assert "Hello world" in embed["fields"][0]["value"]
        assert "[JA] Hello world" in embed["fields"][1]["value"]

    @pytest.mark.asyncio
    async def test_timer_command(self, mock_interaction):
        """Test timer command."""

        async def timer_command(interaction, duration, message="Timer finished!"):
            """Mock timer command."""

            def parse_duration(duration_str):
                """Parse duration string."""
                duration_map = {
                    's': 1, 'm': 60, 'h': 3600, 'd': 86400
                }

                if duration_str[-1] in duration_map:
                    try:
                        value = int(duration_str[:-1])
                        unit = duration_str[-1]
                        return value * duration_map[unit]
                    except ValueError:
                        return None
                return None

            seconds = parse_duration(duration)
            if not seconds or seconds > 86400:  # Max 1 day
                await interaction.response.send_message("Invalid duration! Use format like '5m', '1h', '30s'")
                return

            embed = {
                "title": "⏰ Timer Set",
                "description": f"Timer set for {duration}",
                "fields": [
                    {"name": "Message", "value": message},
                    {"name": "Duration", "value": f"{seconds} seconds"}
                ]
            }

            await interaction.response.send_message(embed=embed)

        await timer_command(mock_interaction, "5m", "Break time!")

        call_args = mock_interaction.response.send_message.call_args
        embed = call_args[1]["embed"]

        assert embed["title"] == "⏰ Timer Set"
        assert "5m" in embed["description"]
        assert "Break time!" in embed["fields"][0]["value"]
        assert "300 seconds" in embed["fields"][1]["value"]

    @pytest.mark.asyncio
    async def test_poll_command(self, mock_interaction):
        """Test poll command."""

        async def poll_command(interaction, question, *options):
            """Mock poll command."""
            if len(options) < 2:
                await interaction.response.send_message("Please provide at least 2 options!")
                return

            if len(options) > 10:
                await interaction.response.send_message("Too many options! Maximum is 10.")
                return

            embed = {
                "title": "📊 Poll",
                "description": question,
                "fields": []
            }

            emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

            for i, option in enumerate(options):
                embed["fields"].append({
                    "name": f"{emojis[i]} Option {i+1}",
                    "value": option
                })

            await interaction.response.send_message(embed=embed)

        options = ["Option A", "Option B", "Option C"]
        await poll_command(mock_interaction, "What should we do?", *options)

        call_args = mock_interaction.response.send_message.call_args
        embed = call_args[1]["embed"]

        assert embed["title"] == "📊 Poll"
        assert "What should we do?" in embed["description"]
        assert len(embed["fields"]) == 3
        assert "Option A" in embed["fields"][0]["value"]


class TestUserInfoCommands:
    """Test user information commands."""

    @pytest.mark.asyncio
    async def test_avatar_command(self, mock_interaction, mock_user):
        """Test avatar command."""

        async def avatar_command(interaction, user=None):
            """Mock avatar command."""
            target_user = user or interaction.user

            avatar_url = f"https://cdn.discordapp.com/avatars/{target_user.id}/avatar.png"

            embed = {
                "title": f"{target_user.display_name}'s Avatar",
                "image": {"url": avatar_url},
                "fields": [
                    {"name": "User", "value": f"{target_user.name}#{target_user.discriminator}"},
                    {"name": "User ID", "value": str(target_user.id)}
                ]
            }

            await interaction.response.send_message(embed=embed)

        mock_interaction.user = mock_user
        mock_user.display_name = "TestUser"
        mock_user.name = "TestUser"
        mock_user.discriminator = "1234"

        await avatar_command(mock_interaction)

        call_args = mock_interaction.response.send_message.call_args
        embed = call_args[1]["embed"]

        assert "TestUser's Avatar" in embed["title"]
        assert f"avatars/{mock_user.id}/avatar.png" in embed["image"]["url"]
        assert "TestUser#1234" in embed["fields"][0]["value"]

    @pytest.mark.asyncio
    async def test_userinfo_command(self, mock_interaction, mock_member, mock_guild):
        """Test userinfo command."""

        async def userinfo_command(interaction, user=None):
            """Mock userinfo command."""
            target_user = user or interaction.user

            created_at = datetime(2020, 1, 1)
            joined_at = datetime(2021, 6, 15)

            embed = {
                "title": f"User Information: {target_user.display_name}",
                "fields": [
                    {"name": "Username", "value": f"{target_user.name}#{target_user.discriminator}"},
                    {"name": "User ID", "value": str(target_user.id)},
                    {"name": "Account Created", "value": created_at.strftime("%Y-%m-%d")},
                    {"name": "Joined Server", "value": joined_at.strftime("%Y-%m-%d")},
                    {"name": "Roles", "value": "3 roles"},
                    {"name": "Status", "value": "Online"}
                ]
            }

            await interaction.response.send_message(embed=embed)

        mock_interaction.user = mock_member
        mock_member.display_name = "TestMember"
        mock_member.name = "TestMember"
        mock_member.discriminator = "5678"

        await userinfo_command(mock_interaction)

        call_args = mock_interaction.response.send_message.call_args
        embed = call_args[1]["embed"]

        assert "User Information: TestMember" in embed["title"]
        assert "TestMember#5678" in embed["fields"][0]["value"]
        assert str(mock_member.id) in embed["fields"][1]["value"]
