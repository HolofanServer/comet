"""
サーバータグ（Guild Tag）取得機能

Discord APIを使用してユーザーのサーバータグ情報を取得し、表示します。
"""
from typing import Optional

import discord
import httpx
from discord.ext import commands

from config.setting import get_settings
from utils.commands_help import is_guild, log_commands
from utils.database import execute_query
from utils.logging import setup_logging

settings = get_settings()
logger = setup_logging("D")


class ServerTagCog(commands.Cog):
    """サーバータグ情報を取得・表示するCogクラス"""

    def __init__(self, bot):
        self.bot = bot
        self.api_base_url = "https://discord.com/api/v10"

    async def fetch_user_server_tag(self, user_id: int) -> Optional[dict]:
        """
        Discord APIから指定ユーザーのサーバータグ情報を取得する関数

        Args:
            user_id: 取得対象のユーザーID

        Returns:
            サーバータグ情報を含む辞書、存在しない場合はNone
        """
        url = f"{self.api_base_url}/users/{user_id}"
        headers = {
            "Authorization": f"Bot {settings.bot_token}"
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()

            # clanフィールドを返す（存在しない場合はNone）
            return data.get("clan")

        except httpx.HTTPStatusError as e:
            logger.error(f"Discord API HTTPエラー: {e.response.status_code} - {e}")
            return None
        except httpx.RequestError as e:
            logger.error(f"Discord API リクエストエラー: {e}")
            return None
        except Exception as e:
            logger.error(f"サーバータグ取得中に予期しないエラー: {e}")
            return None

    async def save_server_tag_history(self, user_id: int, guild_id: int,
                                     tag: str, identity_guild_id: int,
                                     badge: Optional[str]) -> None:
        """
        サーバータグ情報をDBに保存

        Args:
            user_id: ユーザーID
            guild_id: ギルドID
            tag: サーバータグ
            identity_guild_id: タグが紐づけられているサーバーID
            badge: バッジハッシュID
        """
        try:
            await execute_query(
                """
                INSERT INTO server_tag_history (user_id, guild_id, tag, identity_guild_id, badge, checked_at)
                VALUES ($1, $2, $3, $4, $5, CURRENT_TIMESTAMP)
                ON CONFLICT (user_id, guild_id)
                DO UPDATE SET
                    tag = $3,
                    identity_guild_id = $4,
                    badge = $5,
                    checked_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                """,
                user_id, guild_id, tag, identity_guild_id, badge, fetch_type='status'
            )
            logger.info(f"サーバータグ履歴を保存しました: User {user_id}, Tag: {tag}")
        except Exception as e:
            logger.error(f"サーバータグ履歴保存エラー: {e}")

    @commands.hybrid_command(name="taginfo", aliases=["タグ情報", "サーバータグ"])
    @is_guild()
    @log_commands()
    async def taginfo(self, ctx, member: discord.User = None) -> None:
        """
        指定ユーザーのサーバータグを表示するコマンド

        Args:
            member: 対象のユーザー（省略時は自分自身）
        """
        await ctx.defer()

        # ユーザー指定がなければ自分自身を対象にする
        target_user = member or ctx.author

        logger.info(f"サーバータグ情報取得: User {target_user.id} (requested by {ctx.author.id})")

        # Discord APIからサーバータグ情報を取得
        clan = await self.fetch_user_server_tag(target_user.id)

        # サーバータグが存在しない、または無効化されている場合
        if not clan or not clan.get("identity_enabled"):
            embed = discord.Embed(
                title="🏷️ サーバータグ情報",
                description=f"{target_user.mention} さんはサーバータグを装着していません。",
                color=0x99AAB5
            )
            embed.set_thumbnail(url=target_user.display_avatar.url)
            embed.set_footer(text="サーバータグはプロフィールから設定できます")
            await ctx.send(embed=embed)
            return

        # サーバータグ情報を取得
        tag = clan.get("tag")
        identity_guild_id = clan.get("identity_guild_id")
        badge = clan.get("badge")

        # サーバー情報を取得（可能であれば）
        guild_name = "不明なサーバー"
        try:
            tag_guild = self.bot.get_guild(int(identity_guild_id))
            if tag_guild:
                guild_name = tag_guild.name
        except Exception as e:
            logger.debug(f"サーバー名取得失敗: {e}")

        # Embedを作成
        embed = discord.Embed(
            title="🏷️ サーバータグ情報",
            description=f"{target_user.mention} さんのサーバータグ",
            color=0x5865F2
        )

        embed.set_thumbnail(url=target_user.display_avatar.url)

        # タグ情報を追加
        embed.add_field(name="📌 タグ", value=f"`{tag}`", inline=True)
        embed.add_field(name="🏰 サーバー名", value=guild_name, inline=True)
        embed.add_field(name="🆔 サーバーID", value=f"`{identity_guild_id}`", inline=True)

        # バッジ情報がある場合
        if badge:
            embed.add_field(name="🎨 バッジID", value=f"`{badge}`", inline=False)
            # バッジ画像URLを生成
            badge_url = f"https://cdn.discordapp.com/clan-badges/{identity_guild_id}/{badge}.png"
            embed.set_image(url=badge_url)

        embed.set_footer(text="サーバータグは最大4文字まで設定できます")

        await ctx.send(embed=embed)

        # データベースに履歴を保存
        await self.save_server_tag_history(
            target_user.id,
            ctx.guild.id,
            tag,
            identity_guild_id,
            badge
        )

    @commands.hybrid_command(name="tagstats", aliases=["タグ統計"])
    @is_guild()
    @log_commands()
    async def tagstats(self, ctx) -> None:
        """このサーバーでのサーバータグ使用統計を表示"""
        await ctx.defer()

        try:
            # このサーバーでのタグ統計を取得
            stats = await execute_query(
                """
                SELECT
                    COUNT(DISTINCT user_id) as total_users,
                    COUNT(DISTINCT tag) as unique_tags,
                    tag,
                    COUNT(*) as tag_count
                FROM server_tag_history
                WHERE guild_id = $1
                GROUP BY tag
                ORDER BY tag_count DESC
                LIMIT 10
                """,
                ctx.guild.id, fetch_type='all'
            )

            if not stats or stats[0]['total_users'] == 0:
                embed = discord.Embed(
                    title="📊 サーバータグ統計",
                    description="まだこのサーバーでサーバータグの記録がありません。",
                    color=0x99AAB5
                )
                await ctx.send(embed=embed)
                return

            total_users = stats[0]['total_users']
            unique_tags = stats[0]['unique_tags']

            embed = discord.Embed(
                title="📊 サーバータグ統計",
                description="このサーバーでのサーバータグ使用状況",
                color=0x5865F2
            )

            embed.add_field(name="👥 記録されたユーザー数", value=f"`{total_users}` 人", inline=True)
            embed.add_field(name="🏷️ ユニークタグ数", value=f"`{unique_tags}` 種類", inline=True)

            # 人気のタグTop 10
            tag_list = []
            for i, stat in enumerate(stats[:10], start=1):
                tag_list.append(f"{i}. `{stat['tag']}` - {stat['tag_count']}人")

            if tag_list:
                embed.add_field(
                    name="🔝 人気のサーバータグ Top 10",
                    value="\n".join(tag_list),
                    inline=False
                )

            embed.set_footer(text=f"サーバー: {ctx.guild.name}")
            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"タグ統計取得エラー: {e}")
            await ctx.send("統計情報の取得中にエラーが発生しました。")

    @commands.hybrid_group(name="tag", aliases=["タグ"])
    @is_guild()
    async def tag_group(self, ctx) -> None:
        """サーバータグ関連のコマンドグループです"""
        if ctx.invoked_subcommand is None:
            await ctx.send(
                "サーバータグ関連のコマンドです。\n"
                "使用可能なコマンド:\n"
                "• `/tag info [@ユーザー]` - サーバータグ情報を表示\n"
                "• `/tag stats` - サーバータグ統計を表示"
            )

    @tag_group.command(name="info")
    @is_guild()
    @log_commands()
    async def tag_info(self, ctx, member: discord.User = None) -> None:
        """サーバータグ情報を表示（/taginfoのエイリアス）"""
        await self.taginfo(ctx, member)

    @tag_group.command(name="stats")
    @is_guild()
    @log_commands()
    async def tag_stats(self, ctx) -> None:
        """サーバータグ統計を表示（/tagstatsのエイリアス）"""
        await self.tagstats(ctx)


async def setup(bot):
    await bot.add_cog(ServerTagCog(bot))
