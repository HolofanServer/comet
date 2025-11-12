import discord
from discord import app_commands
from discord.ext import commands

from utils.commands_help import is_guild_app, is_owner_app, log_commands
from utils.db_manager import db
from utils.logging import setup_logging

logger = setup_logging()

class AutoReactionCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def setup_database(self):
        async with db.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS auto_reactions (
                    id SERIAL PRIMARY KEY,
                    guild_id BIGINT NOT NULL,
                    trigger_word TEXT NOT NULL,
                    reaction TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

    @app_commands.command(name="リアクション設定", description="自動リアクションの設定を行います")
    @is_guild_app()
    @is_owner_app()
    @log_commands()
    async def set_reaction(
        self,
        interaction: discord.Interaction,
        トリガーワード: str,
        リアクション: str
    ):
        await interaction.response.defer()
        async with db.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO auto_reactions (guild_id, trigger_word, reaction) VALUES ($1, $2, $3)",
                interaction.guild_id, トリガーワード, リアクション
            )

        await interaction.response.send_message(
            f"自動リアクションを設定しました:\nトリガーワード: {トリガーワード}\nリアクション: {リアクション}",
            ephemeral=True
        )

    @app_commands.command(name="リアクション削除", description="設定された自動リアクションを削除します")
    @is_guild_app()
    @is_owner_app()
    @log_commands()
    async def remove_reaction(
        self,
        interaction: discord.Interaction,
        トリガーワード: str
    ):
        await interaction.response.defer()
        async with db.pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM auto_reactions WHERE guild_id = $1 AND trigger_word = $2",
                interaction.guild_id, トリガーワード
            )

            if result != "DELETE 0":
                await interaction.response.send_message(
                    f"トリガーワード「{トリガーワード}」の自動リアクションを削除しました",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"トリガーワード「{トリガーワード}」の設定は見つかりませんでした",
                    ephemeral=True
                )

    @app_commands.command(name="リアクション一覧", description="設定された自動リアクションの一覧を表示します")
    @is_guild_app()
    @is_owner_app()
    @log_commands()
    async def list_reactions(self, interaction: discord.Interaction):
        await interaction.response.defer()
        async with db.pool.acquire() as conn:
            reactions = await conn.fetch(
                "SELECT trigger_word, reaction FROM auto_reactions WHERE guild_id = $1",
                interaction.guild_id
            )

        if not reactions:
            await interaction.response.send_message("自動リアクションの設定はありません", ephemeral=True)
            return

        embed = discord.Embed(title="自動リアクション一覧", color=discord.Color.blue())
        for trigger, reaction in reactions:
            embed.add_field(name=f"トリガー: {trigger}", value=f"リアクション: {reaction}", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        async with db.pool.acquire() as conn:
            reactions = await conn.fetch(
                "SELECT reaction FROM auto_reactions WHERE guild_id = $1 AND $2 LIKE '%' || trigger_word || '%'",
                message.guild.id, message.content
            )

        for reaction, in reactions:
            try:
                await message.add_reaction(reaction)
            except discord.errors.HTTPException:
                continue

async def setup(bot):
    cog = AutoReactionCog(bot)
    await cog.setup_database()
    await bot.add_cog(cog)
