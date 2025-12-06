"""
Discordチャンネル名の管理
配信中のメンバーに応じてチャンネル名を自動更新
"""

from collections import defaultdict

import discord

from utils.logging import setup_logging

from .constants import (
    MAX_CHANNEL_NAME_EMOJIS,
    STREAM_CHANNELS,
    get_branch_for_member,
    get_emoji_for_member,
)

logger = setup_logging("D")


class StreamChannelManager:
    """Discordチャンネル名の管理を担当"""

    def __init__(self, bot: discord.Client):
        """
        StreamChannelManagerの初期化

        Args:
            bot: Discord Botインスタンス
        """
        self.bot = bot
        self.previous_state: dict[str, list[str]] = {
            "jp": [],
            "en": [],
            "id": [],
            "dev_is": []
        }

    async def update_channels(
        self,
        live_streams: list[dict],
        upcoming_streams: list[dict]
    ) -> None:
        """
        配信中・配信予定メンバーに応じてチャンネル名を更新

        Args:
            live_streams: Holodex APIから取得したライブ配信のリスト
            upcoming_streams: Holodex APIから取得した配信予定のリスト
        """
        # ブランチごとにライブ配信中メンバーを分類
        branch_live_members: dict[str, list[dict]] = defaultdict(list)
        # ブランチごとに配信予定メンバーを分類
        branch_upcoming_members: dict[str, list[dict]] = defaultdict(list)

        # ライブ配信中メンバーを分類
        for stream in live_streams:
            channel_info = stream.get("channel", {})
            channel_name = channel_info.get("english_name") or channel_info.get("name", "")

            # ブランチを特定
            branch = get_branch_for_member(channel_name)
            if not branch:
                logger.debug(f"ブランチが特定できないメンバー: {channel_name}")
                continue

            # 配信開始時刻を取得（ソート用）
            start_actual = stream.get("start_actual")
            stream_data = {
                "channel_name": channel_name,
                "start_actual": start_actual,
                "emoji": get_emoji_for_member(channel_name),
                "is_live": True
            }

            branch_live_members[branch].append(stream_data)

        # 配信予定メンバーを分類
        for stream in upcoming_streams:
            channel_info = stream.get("channel", {})
            channel_name = channel_info.get("english_name") or channel_info.get("name", "")

            # ブランチを特定
            branch = get_branch_for_member(channel_name)
            if not branch:
                continue

            # 配信開始予定時刻を取得（ソート用）
            start_scheduled = stream.get("start_scheduled") or stream.get("available_at")
            stream_data = {
                "channel_name": channel_name,
                "start_scheduled": start_scheduled,
                "emoji": get_emoji_for_member(channel_name),
                "is_live": False
            }

            branch_upcoming_members[branch].append(stream_data)

        # 各ブランチのチャンネル名を更新
        for branch in ["jp", "en", "id", "dev_is"]:
            await self._update_branch_channel(
                branch,
                branch_live_members[branch],
                branch_upcoming_members[branch]
            )

    async def _update_branch_channel(
        self,
        branch: str,
        live_members: list[dict],
        upcoming_members: list[dict]
    ) -> None:
        """
        特定ブランチのチャンネル名を更新

        Args:
            branch: ブランチ名（jp/en/id/dev_is）
            live_members: 配信中メンバーのリスト
            upcoming_members: 配信予定メンバーのリスト
        """
        channel_config = STREAM_CHANNELS.get(branch)
        if not channel_config:
            logger.warning(f"未知のブランチ: {branch}")
            return

        channel_id = channel_config["channel_id"]
        if not channel_id:
            logger.debug(f"{branch}チャンネルIDが設定されていません")
            return

        channel = self.bot.get_channel(channel_id)
        if not channel:
            logger.warning(f"{branch}チャンネルが見つかりません: {channel_id}")
            return

        # 優先度: ライブ配信中 > 配信予定
        if live_members:
            # 配信開始時刻でソート（早い順）
            live_members.sort(
                key=lambda x: x.get("start_actual") or "",
                reverse=False
            )
            display_members = live_members
            status_prefix = "🔴"
        elif upcoming_members:
            # 配信開始予定時刻でソート（早い順）
            upcoming_members.sort(
                key=lambda x: x.get("start_scheduled") or "",
                reverse=False
            )
            display_members = upcoming_members
            status_prefix = "📅"
        else:
            display_members = []
            status_prefix = ""

        # チャンネル名を生成
        new_name = self._build_channel_name(branch, display_members, status_prefix)

        # 前回と変わっていなければスキップ
        member_names = [m["channel_name"] for m in display_members]
        state_key = f"{status_prefix}:{','.join(member_names)}"
        previous_key = f"{self.previous_state.get(f'{branch}_prefix', '')}:{','.join(self.previous_state.get(branch, []))}"

        if state_key == previous_key:
            logger.debug(f"{branch}チャンネルの状態に変化なし")
            return

        # チャンネル名を更新
        try:
            await channel.edit(name=new_name)
            self.previous_state[branch] = member_names
            self.previous_state[f"{branch}_prefix"] = status_prefix
            logger.info(f"{branch}チャンネル名を更新: {new_name}")
        except discord.HTTPException as e:
            logger.error(f"{branch}チャンネル名の更新に失敗: {e}")
        except Exception as e:
            logger.error(f"{branch}チャンネル名更新中に予期しないエラー: {e}", exc_info=True)

    def _build_channel_name(
        self,
        branch: str,
        active_members: list[dict],
        status_prefix: str = ""
    ) -> str:
        """
        チャンネル名を生成

        Args:
            branch: ブランチ名
            active_members: 配信中/配信予定メンバーのリスト
            status_prefix: ステータス絵文字（🔴：ライブ中、📅：配信予定）

        Returns:
            新しいチャンネル名
        """
        channel_config = STREAM_CHANNELS[branch]

        # メンバーがいない場合
        if not active_members:
            return channel_config["idle_name"]

        # メンバーの絵文字を収集
        emojis = []
        for member in active_members[:MAX_CHANNEL_NAME_EMOJIS]:
            emoji = member.get("emoji")
            if emoji:
                emojis.append(emoji)

        # 表示しきれないメンバーがいる場合
        overflow_count = len(active_members) - MAX_CHANNEL_NAME_EMOJIS
        if overflow_count > 0:
            emoji_str = "".join(emojis) + f"+{overflow_count}"
        else:
            emoji_str = "".join(emojis)

        # チャンネル名を生成
        return f"{status_prefix}-{emoji_str}"
