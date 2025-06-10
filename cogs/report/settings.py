import discord
from discord.ext import commands
from discord import app_commands
from utils.db_manager import db
from utils.logging import setup_logging
from utils.commands_help import log_commands, is_owner_app, is_guild_app
logger = setup_logging()

class ReportSettingsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def setup_database(self):
        async with db.pool.acquire() as conn:
            # 通報チャンネルのテーブル
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS report_channels (
                    id SERIAL PRIMARY KEY,
                    guild_id BIGINT NOT NULL UNIQUE,
                    channel_id BIGINT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # モデレーターロールのテーブル
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS moderator_roles (
                    id SERIAL PRIMARY KEY,
                    guild_id BIGINT NOT NULL UNIQUE,
                    role_id BIGINT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

    @app_commands.command(name="set_report_channel", description="通報チャンネルを設定します")
    @is_guild_app()
    @is_owner_app()
    @log_commands()
    async def set_report_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await interaction.response.defer()
        async with db.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO report_channels (guild_id, channel_id)
                VALUES ($1, $2)
                ON CONFLICT (guild_id)
                DO UPDATE SET channel_id = $2
            """, interaction.guild_id, channel.id)

        await interaction.response.send_message(
            f"通報チャンネルを {channel.mention} に設定しました。",
            ephemeral=True
        )

    @app_commands.command(name="set_mod_role", description="モデレーターロールを設定します")
    @is_guild_app()
    @is_owner_app()
    @log_commands()
    async def set_mod_role(self, interaction: discord.Interaction, role: discord.Role):
        await interaction.response.defer()
        async with db.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO moderator_roles (guild_id, role_id)
                VALUES ($1, $2)
                ON CONFLICT (guild_id)
                DO UPDATE SET role_id = $2
            """, interaction.guild_id, role.id)

        await interaction.response.send_message(
            f"モデレーターロールを {role.mention} に設定しました。",
            ephemeral=True
        )

    @staticmethod
    async def load_config(guild_id):
        """通報チャンネルの設定を読み込む"""
        async with db.pool.acquire() as conn:
            record = await conn.fetchrow(
                "SELECT channel_id FROM report_channels WHERE guild_id = $1",
                guild_id
            )
            return record['channel_id'] if record else None

    @staticmethod
    async def load_mod_role(guild_id):
        """モデレーターロールの設定を読み込む"""
        async with db.pool.acquire() as conn:
            record = await conn.fetchrow(
                "SELECT role_id FROM moderator_roles WHERE guild_id = $1",
                guild_id
            )
            return record['role_id'] if record else None

async def setup(bot):
    cog = ReportSettingsCog(bot)
    await cog.setup_database()
    await bot.add_cog(cog)
