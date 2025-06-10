import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
from datetime import datetime
from utils.db_manager import db
from utils.logging import setup_logging
from utils.commands_help import log_commands, is_owner_app, is_guild_app

logger = setup_logging()

class PinMessageCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def setup_database(self):
        async with db.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS pinned_messages (
                    id SERIAL PRIMARY KEY,
                    guild_id BIGINT NOT NULL,
                    channel_id BIGINT NOT NULL,
                    message_id BIGINT NOT NULL,
                    pinner_id BIGINT NOT NULL,
                    content TEXT NOT NULL,
                    pinned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(guild_id, channel_id, message_id)
                )
            """)

    @app_commands.command(name="pin", description="メッセージをピン留めします")
    @is_guild_app()
    @is_owner_app()
    @log_commands()
    async def pin_message(
        self,
        interaction: discord.Interaction,
        メッセージ: str,
        チャンネル: Optional[discord.TextChannel] = None
    ):
        target_channel = チャンネル or interaction.channel
        
        # メッセージを送信
        message = await target_channel.send(メッセージ)
        
        try:
            # メッセージをピン留め
            await message.pin()
            
            # データベースに記録
            async with db.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO pinned_messages 
                    (guild_id, channel_id, message_id, pinner_id, content)
                    VALUES ($1, $2, $3, $4, $5)
                """,
                    interaction.guild_id,
                    target_channel.id,
                    message.id,
                    interaction.user.id,
                    メッセージ
                )

            await interaction.response.send_message(
                f"メッセージをピン留めしました\nチャンネル: {target_channel.mention}",
                ephemeral=True
            )

        except discord.HTTPException as e:
            await message.delete()
            await interaction.response.send_message(
                f"ピン留めに失敗しました: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="unpin", description="ピン留めされたメッセージを解除します")
    @is_guild_app()
    @is_owner_app()
    @log_commands()
    async def unpin_message(
        self,
        interaction: discord.Interaction,
        メッセージid: str
    ):
        try:
            message_id = int(メッセージid)
        except ValueError:
            await interaction.response.send_message(
                "メッセージIDは数値で指定してください",
                ephemeral=True
            )
            return

        async with db.pool.acquire() as conn:
            result = await conn.fetchrow(
                "SELECT channel_id FROM pinned_messages WHERE message_id = $1 AND guild_id = $2",
                message_id, interaction.guild_id
            )

            if not result:
                await interaction.response.send_message(
                    "指定されたメッセージは見つかりません",
                    ephemeral=True
                )
                return

            channel_id = result[0]
            channel = interaction.guild.get_channel(channel_id)

            if not channel:
                await interaction.response.send_message(
                    "チャンネルが見つかりません",
                    ephemeral=True
                )
                return

            try:
                message = await channel.fetch_message(message_id)
                await message.unpin()
                
                await conn.execute(
                    "DELETE FROM pinned_messages WHERE message_id = $1 AND guild_id = $2",
                    message_id, interaction.guild_id
                )

                await interaction.response.send_message(
                    "ピン留めを解除しました",
                    ephemeral=True
                )

            except discord.NotFound:
                await interaction.response.send_message(
                    "メッセージが見つかりません",
                    ephemeral=True
                )

    @app_commands.command(name="pins", description="ピン留めされたメッセージの一覧を表示します")
    @is_guild_app()
    @is_owner_app()
    @log_commands()
    async def list_pins(
        self,
        interaction: discord.Interaction,
        チャンネル: Optional[discord.TextChannel] = None
    ):
        target_channel = チャンネル or interaction.channel

        async with db.pool.acquire() as conn:
            pins = await conn.fetch("""
                SELECT message_id, content, pinner_id, pinned_at 
                FROM pinned_messages 
                WHERE guild_id = $1 AND channel_id = $2
                ORDER BY pinned_at DESC
            """, interaction.guild_id, target_channel.id)

        if not pins:
            await interaction.response.send_message(
                f"{target_channel.mention} にピン留めされたメッセージはありません",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"{target_channel.name} のピン留めメッセージ",
            color=discord.Color.blue()
        )

        for message_id, content, pinner_id, pinned_at in pins:
            pinner = interaction.guild.get_member(pinner_id)
            pinner_name = pinner.display_name if pinner else "Unknown"
            pinned_time = datetime.fromisoformat(pinned_at).strftime("%Y/%m/%d %H:%M")
            
            embed.add_field(
                name=f"ID: {message_id}",
                value=f"```{content}```\nピン留め者: {pinner_name}\n日時: {pinned_time}",
                inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    cog = PinMessageCog(bot)
    await bot.add_cog(cog)
    # データベース初期化を非同期タスクとして実行
    bot.loop.create_task(cog.setup_database())
