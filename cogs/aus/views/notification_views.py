"""
AUS Notification Views
無断転載検出通知用のComponent V2 Views
"""

import re

import discord

from utils.logging import setup_logging

logger = setup_logging()


class NoSourceNotificationView(discord.ui.View):
    """Twitter出典未記載検出通知用View（Component V2）"""

    def __init__(self, message_id: int, message_url: str, source_url: str):
        super().__init__(timeout=None)  # Persistent View
        self.message_id = message_id
        self.message_url = message_url
        self.source_url = source_url

    @discord.ui.button(
        label="🚨 即座に削除",
        style=discord.ButtonStyle.danger,
        custom_id="aus:delete"
    )
    async def delete_message(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        """メッセージを削除"""
        # 権限チェック
        if not interaction.user.guild_permissions.manage_messages:
            return await interaction.response.send_message(
                "❌ この操作には`manage_messages`権限が必要です",
                ephemeral=True
            )

        try:
            # メッセージURLからメッセージを取得
            message = await self._fetch_message_from_url(interaction)
            if not message:
                return await interaction.response.send_message(
                    "❌ メッセージが見つかりませんでした",
                    ephemeral=True
                )

            # メッセージを削除
            await message.delete()

            # ボタンを無効化
            for item in self.children:
                item.disabled = True
            await interaction.message.edit(view=self)

            await interaction.response.send_message(
                f"✅ メッセージを削除しました\n削除者: {interaction.user.mention}",
                ephemeral=False
            )

        except discord.errors.NotFound:
            await interaction.response.send_message(
                "❌ メッセージが既に削除されています",
                ephemeral=True
            )
        except discord.errors.Forbidden:
            await interaction.response.send_message(
                "❌ メッセージの削除権限がありません",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ エラーが発生しました: {str(e)}",
                ephemeral=True
            )

    @discord.ui.button(
        label="✓ 確認済み",
        style=discord.ButtonStyle.success,
        custom_id="aus:checked"
    )
    async def mark_checked(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        """確認済みとしてマーク"""
        await interaction.response.send_message(
            f"✅ 確認しました（確認者: {interaction.user.mention}）",
            ephemeral=False
        )

        # ボタンラベルを変更して無効化
        button.disabled = True
        button.label = f"✓ 確認済（by {interaction.user.name}）"
        await interaction.message.edit(view=self)

    @discord.ui.button(
        label="📝 補足/異議",
        style=discord.ButtonStyle.secondary,
        custom_id="aus:feedback"
    )
    async def add_feedback(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        """フィードバックModalを表示"""
        modal = FeedbackModal()
        await interaction.response.send_modal(modal)

    async def _fetch_message_from_url(
        self,
        interaction: discord.Interaction
    ) -> discord.Message | None:
        """メッセージURLからメッセージを取得"""
        # Discord message URL: https://discord.com/channels/{guild_id}/{channel_id}/{message_id}
        pattern = r'https://discord\.com/channels/(\d+)/(\d+)/(\d+)'
        match = re.match(pattern, self.message_url)

        if not match:
            return None

        guild_id, channel_id, message_id = map(int, match.groups())

        try:
            guild = interaction.client.get_guild(guild_id)
            if not guild:
                return None

            # get_channel_or_threadでスレッドにも対応
            channel = guild.get_channel_or_thread(channel_id)
            if not channel or not isinstance(channel, (discord.TextChannel, discord.Thread, discord.ForumChannel)):
                return None

            message = await channel.fetch_message(message_id)
            return message
        except (discord.NotFound, discord.Forbidden, discord.HTTPException) as e:
            logger.debug(f"メッセージ取得失敗: {e}")
            return None


class FeedbackModal(discord.ui.Modal, title="運営フィードバック"):
    """補足・異議申立て用Modal"""

    feedback = discord.ui.TextInput(
        label="コメント・補足・異議申立て",
        style=discord.TextStyle.paragraph,
        placeholder="誤検出の理由、追加情報など...",
        required=True,
        max_length=2000
    )

    async def on_submit(self, interaction: discord.Interaction):
        """フィードバック送信時の処理"""
        # 元のメッセージに返信として記録
        await interaction.response.send_message(
            f"📝 **フィードバック記録**（投稿者: {interaction.user.mention}）\n"
            f"```\n{self.feedback.value}\n```",
            ephemeral=False
        )


class WebSearchResultView(discord.ui.View):
    """Web検索結果通知用View（手動確認推奨）"""

    def __init__(self, message_id: int, detected_urls: list[str]):
        super().__init__(timeout=None)  # Persistent
        self.message_id = message_id
        self.detected_urls = detected_urls

    @discord.ui.button(
        label="✓ 手動確認完了",
        style=discord.ButtonStyle.success,
        custom_id="aus:web_checked"
    )
    async def confirm_check(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        """手動確認完了"""
        await interaction.response.send_message(
            f"✅ 手動確認完了（確認者: {interaction.user.mention}）",
            ephemeral=False
        )

        button.disabled = True
        button.label = f"✓ 確認済（by {interaction.user.name}）"
        await interaction.message.edit(view=self)

    @discord.ui.button(
        label="📋 URL一覧をコピー",
        style=discord.ButtonStyle.primary,
        custom_id="aus:copy_urls"
    )
    async def copy_urls(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        """検出されたURL一覧を表示"""
        if not self.detected_urls:
            return await interaction.response.send_message(
                "❌ 検出されたURLがありません",
                ephemeral=True
            )

        url_list = "\n".join(self.detected_urls)
        await interaction.response.send_message(
            f"**検出されたURL一覧:**\n```\n{url_list}\n```",
            ephemeral=True
        )
