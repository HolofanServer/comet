import asyncio
import random
from datetime import datetime, timedelta
from typing import Union

import discord
from discord import app_commands
from discord.ext import commands

from utils.commands_help import is_guild_app, is_owner_app, log_commands
from utils.db_manager import db
from utils.logging import setup_logging

logger = setup_logging()

class GiveawayCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_giveaways = {}

    async def setup_database(self):
        async with db.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS giveaways (
                    id SERIAL PRIMARY KEY,
                    guild_id BIGINT NOT NULL,
                    channel_id BIGINT NOT NULL,
                    message_id BIGINT NOT NULL,
                    creator_id BIGINT NOT NULL,
                    prize TEXT NOT NULL,
                    end_time TIMESTAMP NOT NULL,
                    ended BOOLEAN DEFAULT FALSE,
                    winner_id BIGINT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

    async def load_active_giveaways(self):
        await self.bot.wait_until_ready()
        async with db.pool.acquire() as conn:
            active = await conn.fetch(
                "SELECT channel_id, message_id, end_time FROM giveaways WHERE ended = FALSE"
            )

        for channel_id, message_id, end_time in active:
            # end_timeはすでにdatetimeオブジェクトとして返される
            if end_time > datetime.now():
                self.active_giveaways[message_id] = asyncio.create_task(
                    self.end_giveaway_task(channel_id, message_id, end_time)
                )

    def convert_duration(self, duration: str) -> int:
        try:
            value = int(duration[:-1])
            unit = duration[-1].lower()
            units = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400, 'w': 604800}

            if unit not in units:
                return -1

            return value * units[unit]
        except ValueError:
            return -2

    @app_commands.command(name="giveaway", description="ギブアウェイを開始します")
    @is_guild_app()
    @is_owner_app()
    @log_commands()
    async def giveaway(
        self,
        interaction: discord.Interaction,
        channel: Union[discord.TextChannel, discord.Thread],
        期間: str,
        賞品: str
    ):
        duration = self.convert_duration(期間)
        if duration == -1:
            await interaction.response.send_message(
                "期間の指定が不正です。以下の単位を使用してください:\n"
                "s: 秒\nm: 分\nh: 時間\nd: 日\nw: 週",
                ephemeral=True
            )
            return
        elif duration == -2:
            await interaction.response.send_message(
                "期間は整数で指定してください",
                ephemeral=True
            )
            return

        end_time = datetime.now() + timedelta(seconds=duration)

        embed = discord.Embed(
            title=f"🎉 {賞品}のギブアウェイ",
            description="🎉を押して参加しよう！",
            color=0x00ff00
        )
        embed.add_field(
            name="終了時間",
            value=f"<t:{int(end_time.timestamp())}:R>",
            inline=True
        )
        embed.add_field(name="作成者", value=interaction.user.mention, inline=True)
        embed.add_field(name="賞品", value=賞品, inline=False)

        await interaction.response.send_message(
            f"ギブアウェイを開始しました！\nチャンネル: {channel.mention}",
            ephemeral=True
        )

        message = await channel.send(embed=embed)
        await message.add_reaction("🎉")

        async with db.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO giveaways
                (guild_id, channel_id, message_id, creator_id, prize, end_time)
                VALUES ($1, $2, $3, $4, $5, $6)
            """,
                interaction.guild_id,
                channel.id,
                message.id,
                interaction.user.id,
                賞品,
                end_time
            )

        self.active_giveaways[message.id] = asyncio.create_task(
            self.end_giveaway_task(channel.id, message.id, end_time)
        )

    async def end_giveaway_task(self, channel_id: int, message_id: int, end_time: datetime):
        await discord.utils.sleep_until(end_time)

        channel = self.bot.get_channel(channel_id)
        if not channel:
            return

        try:
            message = await channel.fetch_message(message_id)
            reaction = discord.utils.get(message.reactions, emoji="🎉")

            if not reaction:
                return

            users = [user async for user in reaction.users() if not user.bot]

            if not users:
                winner = None
                winner_text = "参加者がいませんでした"
            else:
                winner = random.choice(users)
                winner_text = winner.mention

            embed = message.embeds[0]
            embed.color = discord.Color.gold()
            embed.description = f"**終了しました！**\n当選者: {winner_text}"
            await message.edit(embed=embed)

            if winner:
                await channel.send(f"🎉 おめでとうございます！ {winner.mention} が当選しました！")

            async with db.pool.acquire() as conn:
                await conn.execute("""
                    UPDATE giveaways
                    SET ended = TRUE, winner_id = $1
                    WHERE message_id = $2
                """, winner.id if winner else None, message_id)

        except discord.NotFound:
            pass
        finally:
            self.active_giveaways.pop(message_id, None)

    @app_commands.command(name="reroll", description="ギブアウェイの当選者を再抽選します")
    @is_guild_app()
    @is_owner_app()
    @log_commands()
    async def reroll(
        self,
        interaction: discord.Interaction,
        message_id: str
    ):
        try:
            message_id = int(message_id)
        except ValueError:
            await interaction.response.send_message(
                "メッセージIDは数値で指定してください",
                ephemeral=True
            )
            return

        async with db.pool.acquire() as conn:
            result = await conn.fetchrow(
                "SELECT channel_id FROM giveaways WHERE message_id = $1 AND ended = TRUE",
                message_id
            )

            if not result:
                await interaction.response.send_message(
                    "指定されたギブアウェイが見つからないか、まだ終了していません",
                    ephemeral=True
                )
                return

            channel_id = result[0]
            channel = interaction.guild.get_channel(channel_id)

            if not channel:
                await interaction.response.send_message(
                    "ギブアウェイのチャンネルが見つかりません",
                    ephemeral=True
                )
                return

            try:
                message = await channel.fetch_message(message_id)
                reaction = discord.utils.get(message.reactions, emoji="🎉")

                if not reaction:
                    await interaction.response.send_message(
                        "リアクションが見つかりません",
                        ephemeral=True
                    )
                    return

                users = [user async for user in reaction.users() if not user.bot]

                if not users:
                    await interaction.response.send_message(
                        "参加者が見つかりません",
                        ephemeral=True
                    )
                    return

                winner = random.choice(users)
                await channel.send(f"🎉 再抽選の結果、{winner.mention} が当選しました！")

                await conn.execute(
                    "UPDATE giveaways SET winner_id = $1 WHERE message_id = $2",
                    winner.id, message_id
                )

                await interaction.response.send_message(
                    "再抽選が完了しました",
                    ephemeral=True
                )

            except discord.NotFound:
                await interaction.response.send_message(
                    "メッセージが見つかりません",
                    ephemeral=True
                )

async def setup(bot):
    cog = GiveawayCog(bot)
    await bot.add_cog(cog)
    # データベース初期化とアクティブなギブアウェイのロードを非同期タスクとして実行
    bot.loop.create_task(cog.setup_database())
    bot.loop.create_task(cog.load_active_giveaways())
