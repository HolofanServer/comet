import base64
import traceback
from datetime import datetime

import aiohttp
from discord.ext import commands, tasks

from config.setting import get_settings
from utils.logging import setup_logging

settings = get_settings()
logger = setup_logging(__name__)

class BannerSync(commands.Cog):
    """サーバーのバナーをBOTのバナーに同期する機能"""

    def __init__(self, bot):
        self.bot = bot
        self.main_guild_id = int(settings.admin_main_guild_id)
        self.last_banner_hash = None
        logger.info(f"バナー同期機能を初期化: メインサーバーID={self.main_guild_id}")
        self.sync_banner.start()

    def cog_unload(self):
        """Cogがアンロードされる際に呼ばれる"""
        self.sync_banner.cancel()
        logger.info("バナー同期タスクをキャンセル")

    @tasks.loop(hours=3)  # 3時間ごとに実行（レート制限を考慮）
    async def sync_banner(self):
        """メインサーバーのバナーをBOTのバナーに同期"""
        try:
            # メインサーバーを取得
            guild = self.bot.get_guild(self.main_guild_id)
            if not guild:
                logger.warning(f"メインサーバー（ID: {self.main_guild_id}）が見つかりません")
                return

            # バナーがない場合は処理しない
            if not guild.banner:
                logger.info(f"サーバー「{guild.name}」にバナーが設定されていません")
                return

            # 前回と同じバナーなら更新しない
            banner_hash = guild.banner.key
            if banner_hash == self.last_banner_hash:
                logger.info("バナーに変更がないため、更新をスキップします")
                return

            self.last_banner_hash = banner_hash
            logger.info(f"新しいバナーを検出: {banner_hash}, URL: {guild.banner.url}")

            # バナー画像をダウンロード
            async with aiohttp.ClientSession() as session:
                async with session.get(str(guild.banner.url)) as resp:
                    if resp.status != 200:
                        logger.error(f"バナー画像のダウンロードに失敗: ステータスコード {resp.status}")
                        return

                    banner_data = await resp.read()
                    logger.info(f"バナー画像をダウンロード: {len(banner_data)} バイト")

            # BOTアプリケーションのバナーを更新
            app_id = self.bot.application.id
            token = self.bot.http.token

            # 日時を追加したログ
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.info(f"BOTバナー更新を開始 [{now}]: アプリケーションID={app_id}")

            # APIリクエストを構築してバナーを更新
            # アプリケーションバナーではなくボットのプロフィールバナーを更新するために
            # /users/@meエンドポイントを使用
            url = "https://discord.com/api/v10/users/@me"
            logger.info(f"バナー更新用エンドポイント: {url}")

            # バナー画像をBase64エンコードしてJSONで送信
            banner_b64 = base64.b64encode(banner_data).decode('utf-8')
            # 画像の先頭バイトを確認して適切なMIMEタイプを判断
            mime_type = "image/png"
            if banner_data[:3] == b'GIF':
                mime_type = "image/gif"
            elif banner_data[:2] == b'\xff\xd8':
                mime_type = "image/jpeg"

            logger.info(f"検出された画像タイプ: {mime_type}")
            data_uri = f"data:{mime_type};base64,{banner_b64}"

            payload = {
                "banner": data_uri
            }

            # ヘッダーを準備
            headers = {
                "Authorization": f"Bot {token}",
                "Content-Type": "application/json"
            }

            async with aiohttp.ClientSession() as session:
                async with session.patch(url, headers=headers, json=payload) as resp:
                    response_text = await resp.text()
                    if resp.status in (200, 201):
                        logger.info(f"BOTバナーの更新に成功しました: {resp.status}")
                    else:
                        logger.error(f"BOTバナーの更新に失敗: ステータス {resp.status}")
                        logger.error(f"応答: {response_text}")

        except Exception as e:
            logger.error(f"バナー同期中にエラーが発生: {e}")
            logger.error(traceback.format_exc())

    @sync_banner.before_loop
    async def before_sync(self):
        """タスク開始前に実行"""
        await self.bot.wait_until_ready()
        logger.info("バナー同期タスクを開始します")

    @commands.hybrid_command(name="sync_banner", description="BOTのバナーをサーバーのバナーと手動で同期します")
    @commands.has_permissions(administrator=True)
    async def manual_sync(self, ctx):
        """BOTのバナーをサーバーのバナーと手動で同期するコマンド"""
        await ctx.defer()

        # 同期処理実行
        await self.sync_banner()

        await ctx.send("サーバーバナーとBOTバナーの同期を実行しました", ephemeral=True)

async def setup(bot):
    await bot.add_cog(BannerSync(bot))
