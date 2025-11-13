import os
from typing import Optional

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from config.setting import get_settings
from utils.logging import setup_logging

logger = setup_logging("D")
settings = get_settings()


class MembersCard(commands.Cog):
    """HFS Members Card連携機能を提供するCog"""

    def __init__(self, bot):
        self.bot = bot
        # API設定
        self.api_base_url = os.getenv("HFS_API_BASE_URL", "https://example.com/api/bot")
        self.api_key = os.getenv("HFS_API_KEY", "")

        if not self.api_key:
            logger.warning("HFS_API_KEYが設定されていません。Members Card機能は動作しません。")

        # APIヘッダー
        self.headers = {
            "x-api-key": self.api_key
        }

    @staticmethod
    def format_member_number(num: int) -> str:
        """メンバー番号をフォーマット"""
        return f"#{str(num).zfill(4)}"

    @staticmethod
    def role_label(role_type: str) -> str:
        """ロールタイプを日本語に変換"""
        labels = {
            "administrator": "Admin",
            "moderator": "Mod",
            "staff": "Staff",
            "community_mod": "CMod"
        }
        return labels.get(role_type, role_type)

    async def fetch_user_data(
        self,
        discord_id: Optional[str] = None,
        member_number: Optional[int] = None,
        username: Optional[str] = None
    ) -> Optional[dict]:
        """APIからユーザーデータを取得"""
        if not self.api_key:
            return None

        # パラメータ決定
        params = {}
        if member_number is not None:
            params["memberNumber"] = str(member_number)
        elif username:
            params["username"] = username
        elif discord_id:
            params["discordId"] = discord_id
        else:
            return None

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.api_base_url}/user",
                    headers=self.headers,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    elif response.status == 404:
                        logger.debug(f"ユーザーが見つかりません: {params}")
                        return None
                    elif response.status == 429:
                        logger.warning("レート制限超過")
                        return {"error": "rate_limit"}
                    else:
                        logger.error(f"API Error: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"API Request Error: {e}")
            return None

    async def fetch_stats(self) -> Optional[dict]:
        """全体統計情報を取得"""
        if not self.api_key:
            return None

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.api_base_url}/stats",
                    headers=self.headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        logger.error(f"Stats API Error: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"Stats API Request Error: {e}")
            return None

    @app_commands.command(name="card", description="ユーザーのプロフィールを表示")
    @app_commands.describe(
        ユーザー="プロフィールを表示するユーザー（省略で自分）",
        メンバー番号="メンバー番号で検索",
        ユーザー名="ユーザー名で検索"
    )
    async def show_profile(
        self,
        interaction: discord.Interaction,
        ユーザー: Optional[discord.Member] = None,
        メンバー番号: Optional[int] = None,
        ユーザー名: Optional[str] = None
    ):
        """ユーザーのプロフィールを表示"""
        await interaction.response.defer()

        # APIキーチェック
        if not self.api_key:
            await interaction.followup.send(
                "❌ Members Card機能が設定されていません。管理者に連絡してください。"
            )
            return

        # パラメータ決定
        discord_id = None
        if メンバー番号 is None and not ユーザー名:
            if ユーザー:
                discord_id = str(ユーザー.id)
            else:
                discord_id = str(interaction.user.id)

        # データ取得
        data = await self.fetch_user_data(
            discord_id=discord_id,
            member_number=メンバー番号,
            username=ユーザー名
        )

        if data is None:
            await interaction.followup.send("❌ ユーザーが見つかりませんでした")
            return

        if isinstance(data, dict) and data.get("error") == "rate_limit":
            await interaction.followup.send(
                "⏰ リクエストが多すぎます。しばらく待ってから再度お試しください"
            )
            return

        # Embedを作成
        try:
            user_data = data.get("user", {})
            profile_data = data.get("profile", {})
            links = data.get("links", [])
            oshi = data.get("oshi", [])
            roles = data.get("roles", [])
            badges = data.get("badges", [])
            stats = data.get("stats", {})
            urls = data.get("urls", {})

            embed = discord.Embed(
                title=f"{profile_data.get('displayName', 'Unknown')} {self.format_member_number(user_data.get('memberNumber', 0))}",
                description=profile_data.get('bio') or "自己紹介なし",
                color=discord.Color.blue(),
                url=urls.get('profile')
            )

            # アバター設定
            if profile_data.get('avatarUrl'):
                embed.set_thumbnail(url=profile_data['avatarUrl'])

            # バッジ表示
            if roles:
                role_text = " · ".join([self.role_label(r) for r in roles])
                embed.add_field(name="🛡️ ロール", value=role_text, inline=False)

            if badges:
                badge_text = " · ".join([f"{b.get('icon', '🏅')} {b.get('name', '')}" for b in badges])
                embed.add_field(name="🏅 バッジ", value=badge_text, inline=False)

            # 推し表示
            if oshi:
                oshi_text = " ".join([f"{o.get('emoji', '💙')} {o.get('name', '')}" for o in oshi])
                embed.add_field(name="💙 推し", value=oshi_text, inline=False)

            # リンク表示（上位5件）
            if links:
                links_text = "\n".join([
                    f"[{link.get('title', 'Link')}]({link.get('url', '#')}) - {link.get('clickCount', 0)}クリック"
                    for link in links[:5]
                ])
                embed.add_field(name="🔗 リンク", value=links_text, inline=False)

            # 統計情報
            embed.add_field(
                name="📊 統計",
                value=f"リンク: {stats.get('totalLinks', 0)} | 閲覧: {stats.get('totalViews', 0)} | クリック: {stats.get('totalLinkClicks', 0)}",
                inline=False
            )

            # リダイレクトURL
            if urls.get('redirect'):
                embed.add_field(name="🔗 短縮URL", value=urls['redirect'], inline=False)

            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"プロフィール表示エラー: {e}")
            await interaction.followup.send("❌ プロフィールの表示中にエラーが発生しました")

    @app_commands.command(name="cstats", description="サーバー全体の統計情報を表示")
    async def show_stats(self, interaction: discord.Interaction):
        """サーバー全体の統計情報を表示"""
        await interaction.response.defer()

        # APIキーチェック
        if not self.api_key:
            await interaction.followup.send(
                "❌ Members Card機能が設定されていません。管理者に連絡してください。"
            )
            return

        # データ取得
        data = await self.fetch_stats()

        if data is None:
            await interaction.followup.send("❌ 統計情報の取得に失敗しました")
            return

        try:
            stats = data.get("stats", {})
            recent_users = data.get("recentUsers", [])

            embed = discord.Embed(
                title="📊 HFS Members Card 統計",
                color=discord.Color.green()
            )

            embed.add_field(
                name="総ユーザー数",
                value=f"{stats.get('totalUsers', 0)}人",
                inline=True
            )
            embed.add_field(
                name="プロフィール作成済み",
                value=f"{stats.get('totalProfiles', 0)}人",
                inline=True
            )
            embed.add_field(
                name="総リンク数",
                value=f"{stats.get('totalLinks', 0)}個",
                inline=True
            )
            embed.add_field(
                name="総閲覧数",
                value=f"{stats.get('totalViews', 0)}回",
                inline=False
            )

            # 最近のユーザー
            if recent_users:
                recent_text = "\n".join([
                    f"• {u.get('displayName', 'Unknown')} (#{u.get('memberNumber', 0)})"
                    for u in recent_users[:5]
                ])
                embed.add_field(name="最近登録したユーザー", value=recent_text, inline=False)

            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"統計表示エラー: {e}")
            await interaction.followup.send("❌ 統計情報の表示中にエラーが発生しました")

    @app_commands.command(name="links", description="ユーザーのリンク一覧を表示")
    @app_commands.describe(
        ユーザー="リンクを表示するユーザー（省略で自分）",
        メンバー番号="メンバー番号で検索"
    )
    async def show_links(
        self,
        interaction: discord.Interaction,
        ユーザー: Optional[discord.Member] = None,
        メンバー番号: Optional[int] = None
    ):
        """ユーザーのリンク一覧を表示"""
        await interaction.response.defer()

        # APIキーチェック
        if not self.api_key:
            await interaction.followup.send(
                "❌ Members Card機能が設定されていません。管理者に連絡してください。"
            )
            return

        # パラメータ決定
        discord_id = None
        if メンバー番号 is None:
            if ユーザー:
                discord_id = str(ユーザー.id)
            else:
                discord_id = str(interaction.user.id)

        # データ取得
        data = await self.fetch_user_data(
            discord_id=discord_id,
            member_number=メンバー番号
        )

        if data is None:
            await interaction.followup.send("❌ ユーザーが見つかりませんでした")
            return

        try:
            profile_data = data.get("profile", {})
            links = data.get("links", [])
            urls = data.get("urls", {})

            embed = discord.Embed(
                title=f"🔗 {profile_data.get('displayName', 'Unknown')} のリンク一覧",
                color=discord.Color.blue(),
                url=urls.get('profile')
            )

            if not links:
                embed.description = "リンクが登録されていません"
            else:
                for i, link in enumerate(links, 1):
                    embed.add_field(
                        name=f"{i}. {link.get('title', 'Link')}",
                        value=f"[リンクを開く]({link.get('url', '#')})\nクリック数: {link.get('clickCount', 0)}回",
                        inline=False
                    )

            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"リンク表示エラー: {e}")
            await interaction.followup.send("❌ リンクの表示中にエラーが発生しました")

    @app_commands.command(name="oshi", description="推しメンバーの情報を表示")
    @app_commands.describe(
        ユーザー="推しを表示するユーザー（省略で自分）"
    )
    async def show_oshi(
        self,
        interaction: discord.Interaction,
        ユーザー: Optional[discord.Member] = None
    ):
        """推しメンバーの情報を表示"""
        await interaction.response.defer()

        # APIキーチェック
        if not self.api_key:
            await interaction.followup.send(
                "❌ Members Card機能が設定されていません。管理者に連絡してください。"
            )
            return

        # パラメータ決定
        discord_id = str(ユーザー.id) if ユーザー else str(interaction.user.id)

        # データ取得
        data = await self.fetch_user_data(discord_id=discord_id)

        if data is None:
            await interaction.followup.send("❌ ユーザーが見つかりませんでした")
            return

        try:
            profile_data = data.get("profile", {})
            oshi = data.get("oshi", [])

            embed = discord.Embed(
                title=f"💙 {profile_data.get('displayName', 'Unknown')} の推し",
                color=discord.Color.from_str(oshi[0].get('color', '#5865F2')) if oshi else discord.Color.blue()
            )

            if not oshi:
                embed.description = "推しが登録されていません"
            else:
                for o in oshi:
                    embed.add_field(
                        name=f"{o.get('emoji', '💙')} {o.get('name', 'Unknown')}",
                        value="━━━━━━━━━━",
                        inline=False
                    )

            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"推し表示エラー: {e}")
            await interaction.followup.send("❌ 推しの表示中にエラーが発生しました")

    @app_commands.command(name="cranking", description="各種ランキングを表示")
    @app_commands.describe(
        種類="表示するランキングの種類"
    )
    @app_commands.choices(種類=[
        app_commands.Choice(name="閲覧数", value="views"),
        app_commands.Choice(name="リンククリック数", value="clicks"),
        app_commands.Choice(name="新規登録順", value="recent")
    ])
    async def show_ranking(
        self,
        interaction: discord.Interaction,
        種類: app_commands.Choice[str]
    ):
        """各種ランキングを表示"""
        await interaction.response.defer()

        await interaction.followup.send(
            f"❌ {種類.name}ランキング機能は現在開発中です。\n"
            "実装予定の機能:\n"
            "• 閲覧数ランキング\n"
            "• リンククリック数ランキング\n"
            "• 新規登録順\n\n"
            "しばらくお待ちください。"
        )


async def setup(bot):
    await bot.add_cog(MembersCard(bot))
