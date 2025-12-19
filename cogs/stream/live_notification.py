"""
配信開始通知の管理
Webhook経由でタレントのアイコンと名前を使って配信開始通知を送信
配信終了時に通知を削除
"""

import aiohttp
import discord

from utils.database import execute_query
from utils.logging import setup_logging

from .constants import MEMBER_NAME_TO_NAME_JA, STREAM_CHANNELS, get_branch_for_member

logger = setup_logging("D")


class LiveNotificationManager:
    """配信開始通知を管理するクラス"""

    def __init__(self):
        """LiveNotificationManagerの初期化"""
        # 配信中のメンバーとそのメッセージIDを記録
        # {video_id: {"branch": str, "message_id": int, "webhook_id": int}}
        self.active_notifications: dict[str, dict] = {}
        self._initialized = False

    async def initialize(self) -> None:
        """
        DB初期化とキャッシュ読み込み
        """
        if self._initialized:
            return

        try:
            # テーブル作成
            await execute_query(
                """
                CREATE TABLE IF NOT EXISTS live_notifications (
                    video_id TEXT PRIMARY KEY,
                    branch TEXT NOT NULL,
                    message_id BIGINT NOT NULL,
                    webhook_id BIGINT NOT NULL,
                    webhook_token TEXT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
                """,
                fetch_type='status'
            )

            # DBからキャッシュを読み込み
            rows = await execute_query(
                "SELECT video_id, branch, message_id, webhook_id, webhook_token FROM live_notifications"
            )
            for row in rows:
                self.active_notifications[row['video_id']] = {
                    "branch": row['branch'],
                    "message_id": row['message_id'],
                    "webhook_id": row['webhook_id'],
                    "webhook_token": row['webhook_token']
                }

            self._initialized = True
            logger.info(f"配信通知キャッシュを読み込みました: {len(self.active_notifications)}件")

        except Exception as e:
            logger.error(f"配信通知DB初期化エラー: {e}", exc_info=True)

    async def _save_notification(self, video_id: str, data: dict) -> None:
        """通知をDBに保存"""
        try:
            await execute_query(
                """
                INSERT INTO live_notifications (video_id, branch, message_id, webhook_id, webhook_token)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (video_id) DO UPDATE SET
                    branch = EXCLUDED.branch,
                    message_id = EXCLUDED.message_id,
                    webhook_id = EXCLUDED.webhook_id,
                    webhook_token = EXCLUDED.webhook_token
                """,
                video_id, data['branch'], data['message_id'], data['webhook_id'], data['webhook_token'],
                fetch_type='status'
            )
        except Exception as e:
            logger.error(f"通知保存エラー: {e}")

    async def _delete_notification(self, video_id: str) -> None:
        """通知をDBから削除"""
        try:
            await execute_query(
                "DELETE FROM live_notifications WHERE video_id = $1",
                video_id,
                fetch_type='status'
            )
        except Exception as e:
            logger.error(f"通知削除エラー: {e}")

    async def notify_stream_start(self, stream: dict) -> None:
        """
        配信開始通知を送信

        Args:
            stream: Holodex APIから取得した配信情報
        """
        # チャンネル情報
        channel_info = stream.get("channel", {})
        channel_name_en = channel_info.get("english_name") or channel_info.get("name", "")

        # 日本語名を取得
        channel_name_ja = MEMBER_NAME_TO_NAME_JA.get(channel_name_en, channel_name_en)

        # ブランチを特定
        branch = get_branch_for_member(channel_name_en)
        if not branch:
            logger.debug(f"ブランチが特定できないメンバー: {channel_name_en}")
            return

        # Webhook URLを取得
        channel_config = STREAM_CHANNELS.get(branch)
        if not channel_config:
            return

        webhook_url = channel_config.get("webhook_url")
        if not webhook_url:
            logger.debug(f"{branch}のWebhook URLが設定されていません")
            return

        # 配信情報
        video_id = stream.get("id", "")
        title = stream.get("title", "タイトルなし")
        url = f"https://youtube.com/watch?v={video_id}" if video_id else ""

        # タレントのアイコン
        avatar_url = channel_info.get("photo") or channel_info.get("banner") or ""

        # サムネイル画像を取得
        thumbnail_url = stream.get("thumbnail")
        if not thumbnail_url and video_id:
            # APIから取得できない場合は、video_idから生成
            thumbnail_url = f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"

        # 同時視聴者数
        viewers = stream.get("live_viewers")

        # トピック（カテゴリ）
        topic_id = stream.get("topic_id", "")
        # topic_idをわかりやすい名前に変換
        topic_names = {
            "singing": "🎤 歌枠",
            "music_cover": "🎵 歌ってみた",
            "asmr": "🎧 ASMR",
            "apex": "🎮 APEX",
            "minecraft": "⛏️ Minecraft",
            "zatsudan": "💬 雑談",
            "game": "🎮 ゲーム",
            "mahjong": "🀄 麻雀",
            "horror": "👻 ホラー",
            "collab": "👥 コラボ",
            "drawing": "🎨 お絵描き",
            "podcast": "🎙️ Podcast"
        }
        topic_display = topic_names.get(topic_id, topic_id if topic_id else None)

        # 既に通知済みの場合はスキップ
        if video_id in self.active_notifications:
            logger.debug(f"既に通知済み: {channel_name_ja} - {title}")
            return

        try:
            async with aiohttp.ClientSession() as session:
                webhook = discord.Webhook.from_url(
                    webhook_url,
                    session=session
                )

                # Webhookで通知を送信（タレントの名前とアイコンを使用）
                # YouTubeのOGPのような見た目
                description_parts = ["🔴 配信開始！"]

                # トピックを追加
                if topic_display:
                    description_parts.append(f"**トピック**\n{topic_display}")

                # 視聴者数を追加
                if viewers is not None:
                    description_parts.append(f"**視聴者数**\n{viewers:,}")

                embed = discord.Embed(
                    title=title,
                    url=url,
                    description="\n\n".join(description_parts),
                    color=channel_config["color"]
                )

                # サムネイル画像を設定
                if thumbnail_url:
                    embed.set_image(url=thumbnail_url)

                message = await webhook.send(
                    content=url,
                    username=channel_name_ja,
                    avatar_url=avatar_url,
                    embed=embed,
                    wait=True
                )

                # メッセージIDを記録
                if message:
                    notification_data = {
                        "branch": branch,
                        "message_id": message.id,
                        "webhook_id": webhook.id,
                        "webhook_token": webhook.token
                    }
                    self.active_notifications[video_id] = notification_data
                    await self._save_notification(video_id, notification_data)
                    logger.info(f"配信開始通知を送信: {channel_name_ja} - {title}")

        except discord.HTTPException as e:
            logger.error(f"Webhook送信に失敗: {e}")
        except Exception as e:
            logger.error(f"配信開始通知中にエラー: {e}", exc_info=True)

    async def notify_stream_end(self, video_id: str) -> None:
        """
        配信終了時に通知を削除

        Args:
            video_id: 配信のvideo_id
        """
        if video_id not in self.active_notifications:
            return

        notification = self.active_notifications[video_id]
        branch = notification["branch"]
        message_id = notification["message_id"]
        webhook_id = notification["webhook_id"]
        webhook_token = notification.get("webhook_token")

        # Webhook URLを取得
        channel_config = STREAM_CHANNELS.get(branch)
        if not channel_config:
            return

        webhook_url = channel_config.get("webhook_url")
        if not webhook_url or not webhook_token:
            logger.debug(f"{branch}のWebhook URLが設定されていません")
            return

        try:
            async with aiohttp.ClientSession() as session:
                # Webhookを再構築（IDとtokenから）
                webhook = discord.Webhook.partial(
                    id=webhook_id,
                    token=webhook_token,
                    session=session
                )

                # メッセージを削除
                await webhook.delete_message(message_id)
                logger.info(f"配信終了通知を削除: video_id={video_id}")

        except discord.NotFound:
            logger.debug(f"メッセージが既に削除されています: {message_id}")
        except discord.HTTPException as e:
            logger.error(f"メッセージ削除に失敗: {e}")
        except Exception as e:
            logger.error(f"配信終了通知削除中にエラー: {e}", exc_info=True)
        finally:
            # 記録から削除
            if video_id in self.active_notifications:
                del self.active_notifications[video_id]
            await self._delete_notification(video_id)

    async def update_notifications(
        self,
        current_live_streams: list[dict],
        previous_live_streams: list[dict]
    ) -> None:
        """
        配信開始・終了を検知して通知を更新

        Args:
            current_live_streams: 現在のライブ配信リスト
            previous_live_streams: 前回のライブ配信リスト
        """
        # 現在のvideo_idセット
        current_video_ids = {stream.get("id") for stream in current_live_streams if stream.get("id")}
        # 前回のvideo_idセット
        previous_video_ids = {stream.get("id") for stream in previous_live_streams if stream.get("id")}

        # 新しく開始した配信
        new_streams = [
            stream for stream in current_live_streams
            if stream.get("id") in (current_video_ids - previous_video_ids)
        ]

        # 終了した配信（active_notificationsにあるが現在ライブ中でないもの）
        # previous_live_streamsだけでなくactive_notificationsも確認することで、
        # Bot再起動後も正しく終了検出できる
        ended_video_ids = set(self.active_notifications.keys()) - current_video_ids

        # 配信開始通知を送信
        for stream in new_streams:
            await self.notify_stream_start(stream)

        # 配信終了通知を削除
        for video_id in ended_video_ids:
            await self.notify_stream_end(video_id)
