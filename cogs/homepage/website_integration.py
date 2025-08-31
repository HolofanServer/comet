import base64
import os
from datetime import datetime

import aiohttp
import discord
from discord.ext import commands, tasks

from config.setting import get_settings
from utils.logging import setup_logging

logger = setup_logging("D")
settings = get_settings()

class WebsiteIntegration(commands.Cog):
    """ウェブサイト連携機能を提供するCog"""

    def __init__(self, bot):
        self.bot = bot
        # 設定ファイルの値が期待と異なるため、直接URLを指定
        self.api_base_url = "https://hfs.jp/api"
        self.api_token = settings.homepage_api_token
        self.target_guild_id = settings.homepage_target_guild_id
        self.cache_dir = os.path.join(os.getcwd(), "cache", "website")
        self.ensure_cache_dir()
        self.server_stats_update.start()
        # logger.info("ウェブサイト連携タスクを開始しました")
        # logger.info(f"APIエンドポイント設定: {self.api_base_url} (設定ファイルの値 {settings.homepage_api_url} は使用しません)")

    def ensure_cache_dir(self):
        """キャッシュディレクトリが存在することを確認"""
        os.makedirs(self.cache_dir, exist_ok=True)

    def cog_unload(self):
        """Cogがアンロードされるときにタスクを停止"""
        self.server_stats_update.cancel()

    @tasks.loop(minutes=10)
    async def server_stats_update(self):
        """サーバー統計情報を定期的に更新"""
        try:
            guild = self.bot.get_guild(self.target_guild_id)
            if not guild:
                # logger.error(f"ギルドID {self.target_guild_id} が見つかりません")
                return

            # サーバー統計情報の収集
            stats = {
                "member_count": guild.member_count,
                "online_count": len([m for m in guild.members if m.status != discord.Status.offline]),
                "updated_at": datetime.utcnow().isoformat(),
                "server_name": guild.name
            }

            # バナー画像の取得と保存
            await self.update_server_banner(guild)

            # APIにデータを送信
            await self.send_to_api("/server-stats", stats)

            # logger.info(f"サーバー統計情報を更新しました: {stats}")
        except Exception:
            # logger.error(f"サーバー統計情報の更新中にエラーが発生しました: {e}")
            pass

    @server_stats_update.before_loop
    async def before_server_stats_update(self):
        """BOTが準備完了するまで待機"""
        await self.bot.wait_until_ready()
        # logger.info("ウェブサイト連携タスクの準備完了")

    async def update_server_banner(self, guild):
        """サーバーのバナー画像を取得して保存"""
        try:
            if guild.banner:
                # Discord.pyの最新バージョンでの正しいバナーURL取得方法
                # guild.banner_urlはプロパティなので、直接アクセス可能
                try:
                    # アセットURLを文字列として取得
                    if hasattr(guild, 'banner_url'):
                        banner_url = str(guild.banner_url)
                    else:
                        # 旧バージョン互換性のための代替手段
                        banner_url = str(guild.banner.url)

                    # logger.info(f"バナーURL取得: {banner_url}")

                    async with aiohttp.ClientSession() as session:
                        async with session.get(banner_url) as resp:
                            if resp.status == 200:
                                banner_data = await resp.read()
                                # バナー画像をファイルに保存
                                banner_path = os.path.join(self.cache_dir, "server_banner.png")
                                with open(banner_path, "wb") as f:
                                    f.write(banner_data)

                                # バナー画像をBase64エンコードしてAPIに送信
                                base64_data = base64.b64encode(banner_data).decode('utf-8')
                                await self.send_to_api("/server-banner", {
                                    "banner_base64": base64_data,
                                    "updated_at": datetime.utcnow().isoformat()
                                })

                                # logger.info(f"サーバーバナーを更新しました: {banner_path}")
                                return True
                            else:
                                # logger.error(f"バナー画像の取得に失敗しました: ステータスコード {resp.status}")
                                pass
                except Exception:
                    # logger.error(f"バナーURL取得または処理中にエラーが発生しました: {e}")
                    pass
            else:
                # logger.info("サーバーにバナーが設定されていません")
                pass
            return False
        except Exception:
            # logger.error(f"バナー画像の更新中にエラーが発生しました: {e}")
            pass
            return False

    @commands.hybrid_group(name="website")
    async def website(self, ctx):
        """ウェブサイト関連のコマンドグループ"""
        if ctx.invoked_subcommand is None:
            await ctx.send("サブコマンドを指定してください。`update`など")

    @website.command(name="update", description="ウェブサイトの情報を手動で更新します")
    @commands.has_permissions(administrator=True)
    async def update_website(self, ctx):
        """ウェブサイトの情報を手動で更新するコマンド"""
        await ctx.defer()

        try:
            guild = ctx.guild
            if guild.id != self.target_guild_id:
                await ctx.send("このコマンドは対象のサーバーでのみ使用できます。")
                return

            # サーバー統計情報の更新
            await self.server_stats_update()

            # ロール情報の更新
            role_counts = {}
            for role in guild.roles:
                if not role.is_default():
                    role_counts[role.id] = {
                        "name": role.name,
                        "color": role.color.value,
                        "count": len(role.members)
                    }

            await self.send_to_api("/role-stats", {"roles": role_counts})

            await ctx.send("ウェブサイト情報を更新しました。")
        except Exception as e:
            # logger.error(f"サイト更新コマンド実行中にエラーが発生しました: {e}")
            await ctx.send(f"エラーが発生しました: {e}")

    async def send_to_api(self, endpoint, data):
        """APIにデータを送信"""
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_token}"
            }

            # エンドポイントの先頭のスラッシュを削除して二重スラッシュを防ぐ
            clean_endpoint = endpoint.lstrip('/')

            # base_urlの末尾がスラッシュで終わっているか確認
            if not self.api_base_url.endswith('/'):
                url = f"{self.api_base_url}/{clean_endpoint}"
            else:
                url = f"{self.api_base_url}{clean_endpoint}"

            # logger.info(f"APIエンドポイントにデータを送信: {url}")

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    headers=headers,
                    json=data
                ) as resp:
                    if resp.status not in (200, 201, 204):
                        await resp.text()
                        # logger.error(f"API呼び出しに失敗しました: {resp.status} - {response_text}")
                        return False
                    return True
        except Exception:
            # logger.error(f"API呼び出し中にエラーが発生しました: {e}")
            return False

async def setup(bot):
    """Cogをボットに追加"""
    await bot.add_cog(WebsiteIntegration(bot))
    # logger.info("WebsiteIntegration Cogを読み込みました")
