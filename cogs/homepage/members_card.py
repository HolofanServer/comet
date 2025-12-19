from typing import Optional

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks

from config.setting import get_settings
from utils.logging import setup_logging

logger = setup_logging("D")
settings = get_settings()


class MembersCard(commands.Cog):
    """HFS Members Card連携機能を提供するCog"""

    def __init__(self, bot):
        self.bot = bot
        # API設定
        self.api_base_url = settings.hfs_api_base_url
        self.api_key = settings.hfs_api_key
        self.hfs_guild_id = settings.hfs_guild_id

        if not self.api_key:
            logger.warning("HFS_API_KEYが設定されていません。Members Card機能は動作しません。")

        if not self.hfs_guild_id:
            logger.warning("HFS_GUILD_IDが設定されていません。メンバー同期機能は動作しません。")

        # APIヘッダー
        self.headers = {
            "x-api-key": self.api_key
        }

        # ウェブサイトAPI設定（Members Card URL管理用）
        self.website_api_url = "https://hfs.jp"
        self.website_api_token = settings.staff_api_key  # STAFF_API_KEYを使用

        if not self.website_api_token:
            logger.warning("STAFF_API_KEYが設定されていません。Members Card URL管理機能は動作しません。")
        else:
            logger.info(f"Members Card URL管理用API設定: URL={self.website_api_url}, Token先頭4文字={self.website_api_token[:4]}...")

        # メンバー同期タスクを開始
        if self.api_key and self.hfs_guild_id:
            self.sync_members_task.start()
            logger.info("メンバー同期タスクを開始しました")

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

    @app_commands.command(name="card", description="HFS Members Card URLを表示")
    @app_commands.describe(ユーザー="URLを表示するユーザー（省略で自分）")
    async def show_profile(
        self,
        interaction: discord.Interaction,
        ユーザー: Optional[discord.Member] = None
    ):
        """HFS Members Card URLを表示"""
        await interaction.response.defer(ephemeral=True)

        if not self.api_key:
            await interaction.followup.send(
                "❌ Members Card機能が設定されていません",
                ephemeral=True
            )
            return

        target_user = ユーザー if ユーザー else interaction.user
        discord_id = str(target_user.id)

        try:
            # HFS Members Card APIからプロフィール情報を取得
            data = await self.fetch_user_data(discord_id=discord_id)

            if data is None:
                await interaction.followup.send(
                    "❌ ユーザーが見つかりませんでした",
                    ephemeral=True
                )
                return

            if isinstance(data, dict) and data.get("error") == "rate_limit":
                await interaction.followup.send(
                    "❌ リクエストが多すぎます",
                    ephemeral=True
                )
                return

            # プロフィールデータからMembers Card URLを取得
            profile_data = data.get("profile", {})
            member_card_url = profile_data.get("memberCardUrl")

            if member_card_url:
                await interaction.followup.send(
                    member_card_url,
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "❌ 未設定",
                    ephemeral=True
                )

        except Exception as e:
            logger.error(f"cardコマンドエラー: {e}")
            await interaction.followup.send(
                f"❌ {e}",
                ephemeral=True
            )

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

    def cog_unload(self):
        """Cogがアンロードされるときにタスクを停止"""
        if self.sync_members_task.is_running():
            self.sync_members_task.cancel()
            logger.info("メンバー同期タスクを停止しました")

    async def sync_members_to_api(self):
        """メンバーリストをAPIに送信"""
        if not self.api_key or not self.hfs_guild_id:
            return

        try:
            guild = self.bot.get_guild(self.hfs_guild_id)
            if not guild:
                logger.error(f"Guild ID {self.hfs_guild_id} が見つかりません")
                return

            # Botを除くメンバーIDのリストを作成
            member_ids = [str(m.id) for m in guild.members if not m.bot]

            # APIに送信
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_base_url}/sync-members",
                    headers=self.headers,
                    json={
                        "guildId": str(self.hfs_guild_id),
                        "memberIds": member_ids
                    },
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        logger.info(f"✅ メンバーリスト同期完了: {len(member_ids)}人")
                    else:
                        logger.error(f"メンバー同期APIエラー: {response.status}")

        except Exception as e:
            logger.error(f"メンバー同期エラー: {e}")

    @tasks.loop(seconds=10)
    async def sync_members_task(self):
        """10秒ごとにメンバーリストを同期"""
        await self.sync_members_to_api()

    @sync_members_task.before_loop
    async def before_sync_members_task(self):
        """タスク開始前にBotの準備を待つ"""
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """メンバーが参加したときに即座に同期"""
        if member.guild.id == self.hfs_guild_id:
            logger.info(f"➕ メンバー参加: {member.name} ({member.id})")
            await self.sync_members_to_api()

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """メンバーが退出したときに即座に同期"""
        if member.guild.id == self.hfs_guild_id:
            logger.info(f"➖ メンバー退出: {member.name} ({member.id})")
            await self.sync_members_to_api()

    # ========== Members Card URL管理機能 ==========

    async def set_member_card_url(self, user_id: str, card_url: str) -> dict:
        """メンバーカードURLを設定"""
        if not self.website_api_token:
            return {"error": "API認証が設定されていません"}

        headers = {
            "Authorization": f"Bearer {self.website_api_token}",
            "Content-Type": "application/json"
        }

        data = {
            "userId": user_id,
            "memberCardUrl": card_url
        }

        url = f"{self.website_api_url}/api/members/update-card-url"
        logger.debug(f"Members Card URL設定リクエスト: URL={url}, UserID={user_id}")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    headers=headers,
                    json=data,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    result = await response.json()
                    if response.status == 200:
                        return result
                    else:
                        logger.error(f"Members Card URL設定エラー: {response.status}, レスポンス: {result}")
                        return {"error": result.get("error", "不明なエラー"), "status": response.status}
        except Exception as e:
            logger.error(f"Members Card URL設定エラー: {e}")
            return {"error": f"リクエストエラー: {str(e)}"}

    async def get_member_card_url(self, user_id: str) -> Optional[dict]:
        """メンバーカードURLを取得"""
        if not self.website_api_token:
            return None

        headers = {
            "Authorization": f"Bearer {self.website_api_token}"
        }

        url = f"{self.website_api_url}/api/members/update-card-url?userId={user_id}"
        logger.debug(f"Members Card URL取得リクエスト: URL={url}, Token先頭4文字={self.website_api_token[:4]}...")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        response_text = await response.text()
                        logger.error(f"Members Card URL取得エラー: {response.status}, レスポンス: {response_text[:200]}")
                        return None
        except Exception as e:
            logger.error(f"Members Card URL取得エラー: {e}")
            return None

    async def delete_member_card_url(self, user_id: str) -> dict:
        """メンバーカードURLを削除"""
        if not self.website_api_token:
            return {"error": "API認証が設定されていません"}

        headers = {
            "Authorization": f"Bearer {self.website_api_token}",
            "Content-Type": "application/json"
        }

        data = {
            "userId": user_id
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.delete(
                    f"{self.website_api_url}/api/members/update-card-url",
                    headers=headers,
                    json=data,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    result = await response.json()
                    if response.status == 200:
                        return result
                    else:
                        return {"error": result.get("error", "不明なエラー"), "status": response.status}
        except Exception as e:
            logger.error(f"Members Card URL削除エラー: {e}")
            return {"error": f"リクエストエラー: {str(e)}"}

    @app_commands.command(name="set_card_url", description="HFS Members Card URLを設定します")
    @app_commands.describe(url="HFS Members Card URL (https://card.hfs.jp/members/番号 または https://c.hfs.jp/スラッグ)")
    async def set_card_url_slash(self, interaction: discord.Interaction, url: str):
        """HFS Members Card URLを設定するスラッシュコマンド"""
        await interaction.response.defer(ephemeral=True)

        if not self.website_api_token:
            await interaction.followup.send(
                "❌ Members Card URL管理機能が設定されていません。管理者に連絡してください。",
                ephemeral=True
            )
            return

        try:
            result = await self.set_member_card_url(str(interaction.user.id), url)
            if "error" in result:
                await interaction.followup.send(
                    f"❌ {result['error']}",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    f"✅ {url}",
                    ephemeral=True
                )
        except Exception as e:
            logger.error(f"set_card_url_slashエラー: {e}")
            await interaction.followup.send(
                f"❌ {e}",
                ephemeral=True
            )

    @app_commands.command(name="get_card_url", description="HFS Members Card URLを取得します")
    @app_commands.describe(ユーザー="URLを取得するユーザー（省略で自分）")
    async def get_card_url_slash(self, interaction: discord.Interaction, ユーザー: Optional[discord.Member] = None):
        """HFS Members Card URLを取得するスラッシュコマンド"""
        await interaction.response.defer(ephemeral=True)

        if not self.website_api_token:
            await interaction.followup.send(
                "❌ Members Card URL管理機能が設定されていません。管理者に連絡してください。",
                ephemeral=True
            )
            return

        target_user = ユーザー if ユーザー else interaction.user

        try:
            result = await self.get_member_card_url(str(target_user.id))
            if result is None:
                await interaction.followup.send(
                    "❌ データの取得に失敗しました",
                    ephemeral=True
                )
                return

            if result.get("success"):
                member = result.get("member", {})
                card_url = member.get("memberCardUrl")
                if card_url:
                    await interaction.followup.send(
                        card_url,
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        "❌ 未設定",
                        ephemeral=True
                    )
            else:
                await interaction.followup.send(
                    "❌ メンバーが見つかりません",
                    ephemeral=True
                )
        except Exception as e:
            logger.error(f"get_card_url_slashエラー: {e}")
            await interaction.followup.send(
                f"❌ {e}",
                ephemeral=True
            )

    @app_commands.command(name="delete_card_url", description="HFS Members Card URLを削除します")
    async def delete_card_url_slash(self, interaction: discord.Interaction):
        """HFS Members Card URLを削除するスラッシュコマンド"""
        await interaction.response.defer(ephemeral=True)

        if not self.website_api_token:
            await interaction.followup.send(
                "❌ Members Card URL管理機能が設定されていません。管理者に連絡してください。",
                ephemeral=True
            )
            return

        try:
            result = await self.delete_member_card_url(str(interaction.user.id))
            if "error" in result:
                await interaction.followup.send(
                    f"❌ {result['error']}",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "✅ 削除しました",
                    ephemeral=True
                )
        except Exception as e:
            logger.error(f"delete_card_url_slashエラー: {e}")
            await interaction.followup.send(
                f"❌ {e}",
                ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(MembersCard(bot))
