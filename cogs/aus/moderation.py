"""
AUS Moderation System
運営管理機能
"""

import discord
from discord import app_commands
from discord.ext import commands

from .database import DatabaseManager


class Moderation(commands.Cog):
    """運営管理機能"""

    def __init__(self, bot: commands.Bot, db: DatabaseManager):
        self.bot = bot
        self.db = db

    @app_commands.command(
        name="aus_stats",
        description="AUSシステムの統計情報を表示します"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def aus_stats(self, interaction: discord.Interaction):
        """システム統計表示コマンド"""
        # 認証済み絵師数
        verified_artists = await self.db.get_all_verified_artists()
        verified_count = len(verified_artists)

        # チケット統計
        ticket_stats = await self.db.get_ticket_stats()

        # Embed作成
        embed = discord.Embed(
            title="📊 AUSシステム統計",
            description="Art Unauthorized-repost Shield システムの統計情報",
            color=discord.Color.blue(),
            timestamp=interaction.created_at
        )

        embed.add_field(
            name="🎨 認証済み絵師",
            value=f"**{verified_count}** 人",
            inline=True
        )

        embed.add_field(
            name="🎫 チケット統計",
            value=(
                f"未解決: **{ticket_stats['pending']}**\n"
                f"承認済: **{ticket_stats['approved']}**\n"
                f"却下済: **{ticket_stats['rejected']}**\n"
                f"合計: **{ticket_stats['total']}**"
            ),
            inline=True
        )

        # 最近認証された絵師
        if verified_artists:
            recent_artists = verified_artists[:5]
            artist_list = "\n".join(
                f"• <@{artist['user_id']}> - {artist['twitter_handle']}"
                for artist in recent_artists
            )
            embed.add_field(
                name="🆕 最近認証された絵師（5件）",
                value=artist_list,
                inline=False
            )

        embed.set_footer(text=f"実行者: {interaction.user.name}")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="aus_list_artists",
        description="認証済み絵師一覧を表示します"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def aus_list_artists(self, interaction: discord.Interaction):
        """認証済み絵師一覧コマンド"""
        verified_artists = await self.db.get_all_verified_artists()

        if not verified_artists:
            return await interaction.response.send_message(
                "❌ 認証済み絵師はいません",
                ephemeral=True
            )

        # Embed作成
        embed = discord.Embed(
            title="🎨 認証済み絵師一覧",
            description=f"合計: **{len(verified_artists)}** 人",
            color=discord.Color.green()
        )

        # ページネーション（最大25件まで表示）
        for artist in verified_artists[:25]:
            embed.add_field(
                name=f"<@{artist['user_id']}>",
                value=(
                    f"**Twitter:** [{artist['twitter_handle']}]({artist['twitter_url']})\n"
                    f"認証日: <t:{int(artist['verified_at'].timestamp())}:R>"
                ),
                inline=True
            )

        if len(verified_artists) > 25:
            embed.set_footer(text=f"※ 最初の25件のみ表示（全{len(verified_artists)}件）")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="aus_remove_artist",
        description="絵師認証を解除します"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(user="認証を解除するユーザー")
    async def aus_remove_artist(
        self,
        interaction: discord.Interaction,
        user: discord.User
    ):
        """絵師認証解除コマンド"""
        # 認証されているかチェック
        artist_info = await self.db.get_verified_artist(user.id)
        if not artist_info:
            return await interaction.response.send_message(
                f"❌ {user.mention} は絵師認証されていません",
                ephemeral=True
            )

        # 認証解除
        success = await self.db.remove_verified_artist(user.id)

        if success:
            embed = discord.Embed(
                title="✅ 絵師認証を解除しました",
                description=f"**ユーザー:** {user.mention}",
                color=discord.Color.orange()
            )
            embed.add_field(
                name="解除されたTwitterアカウント",
                value=artist_info['twitter_handle']
            )
            embed.set_footer(text=f"実行者: {interaction.user.name}")

            await interaction.response.send_message(embed=embed, ephemeral=False)
        else:
            await interaction.response.send_message(
                "❌ 認証解除に失敗しました",
                ephemeral=True
            )

    @app_commands.command(
        name="aus_pending_tickets",
        description="未解決の認証申請チケット一覧を表示します"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def aus_pending_tickets(self, interaction: discord.Interaction):
        """未解決チケット一覧コマンド"""
        pending_tickets = await self.db.get_all_pending_tickets()

        if not pending_tickets:
            return await interaction.response.send_message(
                "✅ 未解決のチケットはありません",
                ephemeral=True
            )

        # Embed作成
        embed = discord.Embed(
            title="🎫 未解決の認証申請チケット",
            description=f"合計: **{len(pending_tickets)}** 件",
            color=discord.Color.yellow()
        )

        for ticket in pending_tickets[:10]:
            created_ts = int(ticket['created_at'].timestamp())
            embed.add_field(
                name=f"チケット #{ticket['ticket_id']}",
                value=(
                    f"**申請者:** <@{ticket['user_id']}>\n"
                    f"**Twitter:** {ticket['twitter_handle']}\n"
                    f"**作成日:** <t:{created_ts}:R>\n"
                    f"**チャンネル:** <#{ticket['channel_id']}>"
                ),
                inline=True
            )

        if len(pending_tickets) > 10:
            embed.set_footer(text=f"※ 最初の10件のみ表示（全{len(pending_tickets)}件）")

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    """Cog setup"""
    db = bot.db
    await bot.add_cog(Moderation(bot, db))
