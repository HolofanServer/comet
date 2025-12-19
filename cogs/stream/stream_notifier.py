"""
Holodex配信通知システムのメインCog
5分間隔で配信情報をチェックし、チャンネル名とUpcomingメッセージを更新
"""

from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks

from utils.logging import setup_logging

from .channel_manager import StreamChannelManager
from .constants import CHECK_INTERVAL_SECONDS, HOLODEX_API_KEY
from .holodex import HolodexClient
from .live_notification import LiveNotificationManager
from .upcoming import UpcomingStreamsManager

logger = setup_logging("D")


class StreamNotifier(commands.Cog):
    """配信通知システムのメインCog"""

    def __init__(self, bot: commands.Bot):
        """
        StreamNotifierの初期化

        Args:
            bot: Discord Botインスタンス
        """
        self.bot = bot
        self.holodex_client: Optional[HolodexClient] = None
        self.channel_manager = StreamChannelManager(bot)
        self.upcoming_manager = UpcomingStreamsManager(bot)
        self.notification_manager = LiveNotificationManager()
        self.error_count = 0
        self.max_errors = 5
        self.previous_live_streams: list[dict] = []  # 前回のライブ配信リスト

    async def cog_load(self):
        """Cogのロード時に呼ばれる"""
        # Holodex APIキーの確認
        if not HOLODEX_API_KEY:
            logger.error("HOLODEX_API_KEYが設定されていません")
            return

        # Holodexクライアントの初期化
        self.holodex_client = HolodexClient(HOLODEX_API_KEY)

        # 配信通知マネージャーのDB初期化
        await self.notification_manager.initialize()

        # 定期チェックタスクを開始
        self.check_streams.start()
        logger.info("配信通知システムを起動しました")

    async def cog_unload(self):
        """Cogのアンロード時に呼ばれる"""
        # 定期チェックタスクを停止
        self.check_streams.cancel()

        # Holodexクライアントをクローズ
        if self.holodex_client:
            await self.holodex_client.close()

        logger.info("配信通知システムを停止しました")

    @tasks.loop(seconds=CHECK_INTERVAL_SECONDS)
    async def check_streams(self):
        """
        定期的に配信情報をチェックして更新
        5分ごとに実行
        """
        try:
            if not self.holodex_client:
                logger.error("Holodexクライアントが初期化されていません")
                return

            # 配信情報を取得
            data = await self.holodex_client.get_live_and_upcoming()
            live_streams = data.get("live", [])
            upcoming_streams = data.get("upcoming", [])

            # 配信開始・終了通知を更新
            await self.notification_manager.update_notifications(
                live_streams,
                self.previous_live_streams
            )

            # チャンネル名を更新（ライブ配信と配信予定の両方を渡す）
            await self.channel_manager.update_channels(live_streams, upcoming_streams)

            # Upcomingメッセージを更新
            await self.upcoming_manager.update_all_branches(upcoming_streams)

            # 前回のライブ配信リストを更新
            self.previous_live_streams = live_streams

            # エラーカウントをリセット
            self.error_count = 0

            logger.info(
                f"配信情報チェック完了: ライブ {len(live_streams)}件、"
                f"予定 {len(upcoming_streams)}件"
            )

        except Exception as e:
            self.error_count += 1
            logger.error(f"配信情報チェック中にエラーが発生: {e}", exc_info=True)

            # 連続エラーが多すぎる場合は警告
            if self.error_count >= self.max_errors:
                logger.critical(
                    f"連続して{self.max_errors}回エラーが発生しました。"
                    "APIキーやネットワーク接続を確認してください。"
                )

    @check_streams.before_loop
    async def before_check_streams(self):
        """タスクループ開始前にBotの準備を待つ"""
        await self.bot.wait_until_ready()
        logger.info("配信情報の定期チェックを開始します")

    @app_commands.command(
        name="streamcheck",
        description="配信情報を手動で即座に更新します（管理者のみ）"
    )
    @app_commands.default_permissions(administrator=True)
    async def streamcheck(self, interaction: discord.Interaction):
        """
        配信情報を手動チェックするコマンド

        Args:
            interaction: Discord Interaction
        """
        await interaction.response.defer(ephemeral=True)

        try:
            if not self.holodex_client:
                await interaction.followup.send("❌ Holodexクライアントが初期化されていません")
                return

            # 配信情報を取得
            data = await self.holodex_client.get_live_and_upcoming()
            live_streams = data.get("live", [])
            upcoming_streams = data.get("upcoming", [])

            # 配信開始・終了通知を更新
            await self.notification_manager.update_notifications(
                live_streams,
                self.previous_live_streams
            )

            # チャンネル名を更新（ライブ配信と配信予定の両方を渡す）
            await self.channel_manager.update_channels(live_streams, upcoming_streams)

            # Upcomingメッセージを更新
            await self.upcoming_manager.update_all_branches(upcoming_streams)

            # 前回のライブ配信リストを更新
            self.previous_live_streams = live_streams

            # 結果を報告
            embed = discord.Embed(
                title="✅ 更新完了！",
                description=(
                    f"ライブ配信: **{len(live_streams)}件**\n"
                    f"予定配信: **{len(upcoming_streams)}件**"
                ),
                color=0x00FF00
            )

            await interaction.followup.send(embed=embed)
            logger.info(f"{interaction.user}が手動で配信情報を更新しました")

        except Exception as e:
            logger.error(f"手動チェック中にエラー: {e}", exc_info=True)
            await interaction.followup.send(f"❌ エラーが発生しました: {str(e)}")

    @app_commands.command(
        name="streamstatus",
        description="現在の配信状況を表示します"
    )
    async def streamstatus(self, interaction: discord.Interaction):
        """
        現在の配信状況を表示するコマンド

        Args:
            interaction: Discord Interaction
        """
        await interaction.response.defer(ephemeral=True)

        try:
            if not self.holodex_client:
                await interaction.followup.send("❌ Holodexクライアントが初期化されていません")
                return

            # 配信情報を取得
            data = await self.holodex_client.get_live_and_upcoming()
            live_streams = data.get("live", [])

            # ブランチごとに分類
            from collections import defaultdict

            from .constants import get_branch_for_member

            branch_streams = defaultdict(list)
            for stream in live_streams:
                channel_info = stream.get("channel", {})
                channel_name = channel_info.get("english_name") or channel_info.get("name", "")
                branch = get_branch_for_member(channel_name)
                if branch:
                    branch_streams[branch].append(channel_name)

            # Embedを作成
            embed = discord.Embed(
                title="📊 配信状況",
                color=0x3498DB
            )

            branch_names = {
                "jp": "JP",
                "en": "EN",
                "id": "ID",
                "dev_is": "DEV_IS"
            }

            for branch in ["jp", "en", "id", "dev_is"]:
                members = branch_streams.get(branch, [])
                if members:
                    value = "\n".join(members)
                else:
                    value = "配信なし"

                embed.add_field(
                    name=f"{branch_names[branch]} ({len(members)})",
                    value=value,
                    inline=False
                )

            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"配信状況表示中にエラー: {e}", exc_info=True)
            await interaction.followup.send(f"❌ エラーが発生しました: {str(e)}")


async def setup(bot: commands.Bot):
    """Cogをセットアップ"""
    await bot.add_cog(StreamNotifier(bot))
