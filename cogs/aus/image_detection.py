"""
AUS Image Detection System
画像検出・逆検索システム（SauceNAO + Google Cloud Vision + AWS Rekognition）
"""

import asyncio
from typing import Optional

import aiohttp
import discord
from discord.ext import commands
from google.cloud import vision

from config.setting import get_settings
from utils.logging import setup_logging

from .database import DatabaseManager
from .views.notification_views import NoSourceNotificationView, WebSearchResultView

logger = setup_logging()
settings = get_settings()


class ImageDetection(commands.Cog):
    """画像検出・逆検索システム"""

    def __init__(self, bot: commands.Bot, db: DatabaseManager):
        self.bot = bot
        self.db = db

        # 設定から取得
        self.mod_channel_id = settings.aus_mod_channel_id
        self.saucenao_api_key = settings.saucenao_api_key
        # Google Vision APIが有効かチェック（JSON文字列またはファイルパス）
        self.google_vision_enabled = bool(
            settings.google_cloud_credentials_json or settings.google_application_credentials
        )

        # 除外設定
        self.excluded_channel_ids = self._parse_ids(settings.aus_excluded_channel_ids)
        self.excluded_category_ids = self._parse_ids(settings.aus_excluded_category_ids)

        # Google Cloud Vision クライアント
        if self.google_vision_enabled:
            try:
                # 環境変数から認証情報を取得（Railway対応）
                self.google_vision_client = self._initialize_vision_client()
                logger.info("✅ Google Cloud Vision API initialized")
            except Exception as e:
                logger.warning(f"⚠️ Google Cloud Vision API initialization failed: {e}")
                self.google_vision_enabled = False

        # レート制限管理
        self.saucenao_requests = []  # タイムスタンプのリスト
        self.saucenao_rate_limit = 20  # 20リクエスト/30秒

    def _initialize_vision_client(self):
        """Google Cloud Vision APIクライアントを初期化"""
        import json
        import os

        from google.oauth2 import service_account

        # 環境変数からJSON認証情報を読み込む（Railway対応）
        credentials_json = settings.google_cloud_credentials_json

        if credentials_json:
            # JSONストリングから認証情報を読み込み
            try:
                credentials_info = json.loads(credentials_json)
                credentials = service_account.Credentials.from_service_account_info(credentials_info)
                return vision.ImageAnnotatorClient(credentials=credentials)
            except json.JSONDecodeError as e:
                logger.error(f"❌ Invalid GOOGLE_CLOUD_CREDENTIALS_JSON format: {e}")
                raise

        # フォールバック: ファイルパスから読み込み（ローカル開発用）
        credentials_path = settings.google_application_credentials
        if credentials_path and os.path.exists(credentials_path):
            credentials = service_account.Credentials.from_service_account_file(credentials_path)
            return vision.ImageAnnotatorClient(credentials=credentials)

        # デフォルト認証（GOOGLE_APPLICATION_CREDENTIALS環境変数）
        return vision.ImageAnnotatorClient()

    def _parse_ids(self, ids_str: str) -> set[int]:
        """カンマ区切りのID文字列をセットに変換"""
        if not ids_str:
            return set()
        try:
            return {int(id_str.strip()) for id_str in ids_str.split(',') if id_str.strip()}
        except ValueError:
            return set()

    def _is_excluded(self, channel: discord.TextChannel | discord.Thread) -> bool:
        """チャンネルが除外対象かどうか判定"""
        # チャンネルID除外
        if channel.id in self.excluded_channel_ids:
            return True

        # カテゴリ除外
        if hasattr(channel, 'category') and channel.category:
            if channel.category.id in self.excluded_category_ids:
                return True

        return False

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """メッセージ送信時の画像検出"""
        # Bot自身のメッセージは無視
        if message.author.bot:
            return

        # DMは無視
        if not message.guild:
            return

        # モデレーションチャンネルは除外
        if message.channel.id == self.mod_channel_id:
            return

        # 除外設定チェック
        if self._is_excluded(message.channel):
            return

        # 添付ファイルがない場合は終了
        if not message.attachments:
            return

        # 画像添付ファイルのみ処理
        image_attachments = [
            att for att in message.attachments
            if att.content_type and att.content_type.startswith('image/')
        ]

        if not image_attachments:
            return

        # 認証済み絵師の場合はスキップ
        is_verified = await self.db.is_verified_artist(message.author.id)
        if is_verified:
            logger.info(f"✅ Skipping verified artist: {message.author} ({message.author.id})")
            return

        # 各画像を検出
        for attachment in image_attachments:
            await self._process_image(message, attachment)

    async def _process_image(
        self,
        message: discord.Message,
        attachment: discord.Attachment
    ):
        """画像を処理して検出"""
        logger.info(f"🔍 Processing image: {attachment.filename} from {message.author}")

        try:
            # 画像データをダウンロード
            image_bytes = await attachment.read()

            # ステップ1: SauceNAO検索
            saucenao_result = await self._search_saucenao(image_bytes)

            if saucenao_result:
                # Twitter URLが検出された場合
                twitter_url = saucenao_result.get('url')
                similarity = saucenao_result.get('similarity', 0)

                logger.info(f"✅ SauceNAO detected: {twitter_url} (similarity: {similarity}%)")

                # メッセージ内容にURLが含まれているかチェック
                if not self._has_source_url(message, twitter_url):
                    # 無断転載の可能性 - 運営に通知
                    await self._send_no_source_notification(
                        message,
                        attachment,
                        twitter_url,
                        f"SauceNAO (類似度: {similarity}%)"
                    )
                    return

            # ステップ2: Google Cloud Vision検索（SauceNAOで検出されなかった場合）
            if self.google_vision_enabled:
                google_results = await self._search_google_vision(image_bytes)

                if google_results:
                    logger.info(f"✅ Google Vision detected {len(google_results)} results")
                    # Web検索結果通知
                    await self._send_web_search_notification(
                        message,
                        attachment,
                        google_results
                    )
                    return

            logger.info(f"ℹ️ No source detected for: {attachment.filename}")

        except Exception as e:
            logger.error(f"❌ Error processing image {attachment.filename}: {e}")

    async def _search_saucenao(self, image_bytes: bytes) -> Optional[dict]:
        """SauceNAO APIで画像を検索"""
        if not self.saucenao_api_key:
            logger.warning("⚠️ SauceNAO API key not configured")
            return None

        # レート制限チェック
        await self._check_saucenao_rate_limit()

        try:
            async with aiohttp.ClientSession() as session:
                # SauceNAO API URL
                url = 'https://saucenao.com/search.php'

                # ファイルデータを準備
                data = aiohttp.FormData()
                data.add_field('file', image_bytes, filename='image.jpg')
                data.add_field('api_key', self.saucenao_api_key)
                data.add_field('output_type', '2')  # JSON
                data.add_field('numres', '10')  # 最大10件
                data.add_field('db', '999')  # 全データベースを検索

                async with session.post(url, data=data, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status != 200:
                        logger.warning(f"⚠️ SauceNAO API error: {resp.status}")
                        return None

                    result = await resp.json()

                    # APIステータスチェック
                    header = result.get('header', {})
                    status = header.get('status', 0)
                    if status != 0:
                        logger.warning(f"⚠️ SauceNAO API status error: {status}")
                        return None

                    # レート制限情報をログ出力
                    short_remaining = header.get('short_remaining', 'N/A')
                    long_remaining = header.get('long_remaining', 'N/A')
                    logger.debug(f"SauceNAO rate limit - Short: {short_remaining}, Long: {long_remaining}")

                    # 結果を解析
                    if 'results' not in result or not result['results']:
                        logger.info("ℹ️ SauceNAO: No results found")
                        return None

                    # 最小類似度を取得（これより低い結果は信頼性が低い）
                    minimum_similarity = float(header.get('minimum_similarity', 50.0))

                    # 最も類似度の高い結果を取得
                    for item in result['results']:
                        item_header = item.get('header', {})
                        similarity = float(item_header.get('similarity', 0))

                        # 最小類似度チェック
                        if similarity < minimum_similarity:
                            logger.debug(f"⚠️ Result similarity {similarity}% < minimum {minimum_similarity}%")
                            continue

                        # Twitter URLを優先的に抽出
                        data_section = item.get('data', {})
                        urls = data_section.get('ext_urls', [])
                        for url in urls:
                            if 'twitter.com' in url or 'x.com' in url:
                                logger.info(f"✅ Found Twitter URL: {url} (similarity: {similarity}%)")
                                return {
                                    'url': url,
                                    'similarity': similarity,
                                    'title': data_section.get('title', ''),
                                    'author': data_section.get('member_name', ''),
                                    'index_id': item_header.get('index_id', 0)
                                }

                    logger.info("ℹ️ SauceNAO: No Twitter URLs found in results")
                    return None

        except asyncio.TimeoutError:
            logger.warning("⚠️ SauceNAO API timeout")
            return None
        except Exception as e:
            logger.error(f"❌ SauceNAO API error: {e}")
            return None

    async def _check_saucenao_rate_limit(self):
        """SauceNAOレート制限チェック（20リクエスト/30秒）"""
        import time

        now = time.time()

        # 30秒以上前のリクエストを削除
        self.saucenao_requests = [
            req for req in self.saucenao_requests
            if now - req < 30
        ]

        # レート制限超過の場合は待機
        if len(self.saucenao_requests) >= self.saucenao_rate_limit:
            wait_time = 30 - (now - self.saucenao_requests[0])
            if wait_time > 0:
                logger.info(f"⏳ SauceNAO rate limit - waiting {wait_time:.1f}s")
                await asyncio.sleep(wait_time)
                self.saucenao_requests = []

        # リクエスト記録
        self.saucenao_requests.append(now)

    async def _search_google_vision(self, image_bytes: bytes) -> list[str]:
        """Google Cloud Vision APIで画像を検索"""
        if not self.google_vision_enabled:
            return []

        try:
            # Google Cloud Vision API（同期API）を非同期で実行
            # run_in_executorを使ってブロッキングを回避
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                self._call_vision_api,
                image_bytes
            )

            if not response:
                return []

            if response.error.message:
                logger.warning(f"⚠️ Google Vision API error: {response.error.message}")
                return []

            # Twitter URLを含むページを優先抽出
            twitter_urls = []

            if response.web_detection.pages_with_matching_images:
                for page in response.web_detection.pages_with_matching_images[:10]:
                    if 'twitter.com' in page.url or 'x.com' in page.url:
                        twitter_urls.append(page.url)
                        logger.debug(f"Found Twitter URL via Google Vision: {page.url}")

            if twitter_urls:
                logger.info(f"✅ Google Vision found {len(twitter_urls)} Twitter URLs")

            return twitter_urls

        except Exception as e:
            logger.error(f"❌ Google Vision API error: {e}")
            return []

    def _call_vision_api(self, image_bytes: bytes):
        """Vision APIを同期的に呼び出す（executor内で実行）"""
        try:
            image = vision.Image(content=image_bytes)
            return self.google_vision_client.web_detection(image=image)
        except Exception as e:
            logger.error(f"❌ Vision API call failed: {e}")
            return None

    def _has_source_url(self, message: discord.Message, source_url: str) -> bool:
        """メッセージ内容にソースURLが含まれているかチェック"""
        # メッセージ本文
        content = message.content.lower()

        # 基本的なURL抽出（twitter.com/x.comのステータスURL）
        if 'twitter.com' in content or 'x.com' in content:
            # 同じステータスIDが含まれているかチェック
            import re
            status_match = re.search(r'/status/(\d+)', source_url)
            if status_match:
                status_id = status_match.group(1)
                if status_id in content:
                    return True

        return False

    async def _send_no_source_notification(
        self,
        message: discord.Message,
        attachment: discord.Attachment,
        source_url: str,
        detection_method: str
    ):
        """Twitter出典未記載の通知を送信"""
        mod_channel = self.bot.get_channel(self.mod_channel_id)
        if not mod_channel:
            logger.warning(f"⚠️ Mod channel not found: {self.mod_channel_id}")
            return

        # Embed作成
        embed = discord.Embed(
            title="🔍 Twitter出典未記載",
            description=(
                f"無断転載の可能性がある画像が検出されました。\n"
                f"**検出元:** {detection_method}"
            ),
            color=discord.Color.red(),
            timestamp=message.created_at
        )

        embed.add_field(
            name="投稿者",
            value=message.author.mention,
            inline=True
        )
        embed.add_field(
            name="チャンネル",
            value=message.channel.mention,
            inline=True
        )
        embed.add_field(
            name="検出ソース",
            value=f"[Twitter]({source_url})",
            inline=False
        )
        embed.add_field(
            name="メッセージリンク",
            value=f"[ジャンプ]({message.jump_url})",
            inline=False
        )

        # 画像を添付
        if attachment.url:
            embed.set_image(url=attachment.url)

        embed.set_footer(
            text=f"User ID: {message.author.id} | Message ID: {message.id}"
        )

        # Component V2 View
        view = NoSourceNotificationView(
            message.id,
            message.jump_url,
            source_url
        )

        await mod_channel.send(embed=embed, view=view)
        logger.info(f"📢 Notification sent to mod channel: {message.jump_url}")

    async def _send_web_search_notification(
        self,
        message: discord.Message,
        attachment: discord.Attachment,
        detected_urls: list[str]
    ):
        """Web検索結果通知を送信"""
        mod_channel = self.bot.get_channel(self.mod_channel_id)
        if not mod_channel:
            return

        # Embed作成
        embed = discord.Embed(
            title="🌐 Web検索結果あり",
            description=(
                "Google Visionで類似画像を検出しました。手動確認をお願いします。"
            ),
            color=discord.Color.orange(),
            timestamp=message.created_at
        )

        embed.add_field(
            name="投稿者",
            value=message.author.mention,
            inline=True
        )
        embed.add_field(
            name="チャンネル",
            value=message.channel.mention,
            inline=True
        )

        # 検出URL
        url_text = "\n".join(f"• {url}" for url in detected_urls[:3])
        embed.add_field(
            name="検出URL",
            value=url_text or "なし",
            inline=False
        )
        embed.add_field(
            name="メッセージリンク",
            value=f"[ジャンプ]({message.jump_url})",
            inline=False
        )

        # 画像を添付
        if attachment.url:
            embed.set_image(url=attachment.url)

        embed.set_footer(
            text=f"User ID: {message.author.id} | Message ID: {message.id}"
        )

        # Component V2 View
        view = WebSearchResultView(message.id, detected_urls)

        await mod_channel.send(embed=embed, view=view)
        logger.info(f"📢 Web search notification sent: {message.jump_url}")


async def setup(bot: commands.Bot):
    """Cog setup"""
    db = bot.db
    await bot.add_cog(ImageDetection(bot, db))
