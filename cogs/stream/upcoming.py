"""
Upcoming配信メッセージの管理
各ブランチチャンネルに配信予定を埋め込みメッセージで表示
"""

from collections import defaultdict
from datetime import datetime
from typing import Optional

import discord
import pytz

from utils.logging import setup_logging

from .constants import (
    MAX_DISPLAY_UPCOMING,
    MEMBER_NAME_TO_NAME_JA,
    STREAM_CHANNELS,
    get_branch_for_member,
    get_emoji_for_member,
)

logger = setup_logging("D")

JST = pytz.timezone('Asia/Tokyo')


class UpcomingStreamsManager:
    """各ブランチチャンネルのUpcoming配信埋め込みメッセージを管理"""

    def __init__(self, bot: discord.Client):
        """
        UpcomingStreamsManagerの初期化

        Args:
            bot: Discord Botインスタンス
        """
        self.bot = bot
        self.message_cache: dict[str, int] = {}  # branch -> message_id

    async def update_all_branches(self, upcoming_streams: list[dict]) -> None:
        """
        全ブランチのUpcoming配信メッセージを更新

        Args:
            upcoming_streams: Holodex APIから取得したupcoming配信のリスト
        """
        # ブランチごとに配信を分類
        branch_streams: dict[str, list[dict]] = defaultdict(list)

        for stream in upcoming_streams:
            channel_info = stream.get("channel", {})
            channel_name = channel_info.get("english_name") or channel_info.get("name", "")

            # ブランチを特定
            branch = get_branch_for_member(channel_name)
            if not branch:
                logger.debug(f"ブランチが特定できないメンバー: {channel_name}")
                continue

            branch_streams[branch].append(stream)

        # 各ブランチのメッセージを更新
        for branch in ["jp", "en", "id", "dev_is"]:
            await self._update_branch_upcoming(branch, branch_streams[branch])

    async def _update_branch_upcoming(
        self,
        branch: str,
        upcoming_streams: list[dict]
    ) -> None:
        """
        特定ブランチのUpcoming配信メッセージを更新

        Args:
            branch: ブランチ名（jp/en/id/dev_is）
            upcoming_streams: そのブランチのupcoming配信リスト
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
        if not channel or not isinstance(channel, discord.TextChannel):
            logger.warning(f"{branch}テキストチャンネルが見つかりません: {channel_id}")
            return

        # 配信予定を時刻でソート
        upcoming_streams.sort(
            key=lambda x: x.get("start_scheduled") or x.get("available_at") or "",
            reverse=False
        )

        # 埋め込みメッセージを生成
        embed = self._build_embed(branch, upcoming_streams[:MAX_DISPLAY_UPCOMING])

        # 既存のメッセージを探して編集、なければ新規作成
        try:
            existing_message = await self._find_existing_embed(channel, branch)

            if existing_message:
                await existing_message.edit(embed=embed)
                logger.info(f"{branch}のUpcomingメッセージを更新しました")
            else:
                new_message = await channel.send(embed=embed)
                self.message_cache[branch] = new_message.id
                logger.info(f"{branch}のUpcomingメッセージを新規作成しました")

        except discord.HTTPException as e:
            logger.error(f"{branch}のUpcomingメッセージ更新に失敗: {e}")
        except Exception as e:
            logger.error(f"{branch}のUpcomingメッセージ更新中に予期しないエラー: {e}", exc_info=True)

    async def _find_existing_embed(
        self,
        channel: discord.TextChannel,
        branch: str
    ) -> Optional[discord.Message]:
        """
        既存のUpcoming埋め込みメッセージを探す

        Args:
            channel: 検索対象チャンネル
            branch: ブランチ名

        Returns:
            見つかったメッセージ、なければNone
        """
        # キャッシュからメッセージIDを取得
        if branch in self.message_cache:
            try:
                message = await channel.fetch_message(self.message_cache[branch])
                # Botが送信したメッセージで、埋め込みがあるか確認
                if message.author == self.bot.user and message.embeds:
                    return message
            except discord.NotFound:
                # メッセージが削除されている
                del self.message_cache[branch]
            except discord.HTTPException:
                pass

        # キャッシュにない場合、最近のメッセージから探す
        try:
            async for message in channel.history(limit=50):
                if message.author == self.bot.user and message.embeds:
                    embed = message.embeds[0]
                    # タイトルで判定
                    channel_config = STREAM_CHANNELS.get(branch)
                    if embed.title and channel_config:
                        if channel_config["upcoming_title"] in embed.title:
                            self.message_cache[branch] = message.id
                            return message
        except discord.HTTPException:
            pass

        return None

    def _build_embed(self, branch: str, upcoming_streams: list[dict]) -> discord.Embed:
        """
        Upcoming配信の埋め込みメッセージを生成

        Args:
            branch: ブランチ名
            upcoming_streams: upcoming配信のリスト（最大MAX_DISPLAY_UPCOMING件）

        Returns:
            discord.Embed
        """
        channel_config = STREAM_CHANNELS[branch]

        # Embedの基本設定
        embed = discord.Embed(
            title=channel_config["upcoming_title"],
            color=channel_config["color"],
            timestamp=datetime.now(pytz.UTC)
        )

        if not upcoming_streams:
            embed.description = "現在、予定されている配信はありません"
            embed.set_footer(text="更新")
            return embed

        # 配信予定を追加
        description_lines = []

        for stream in upcoming_streams:
            # チャンネル情報
            channel_info = stream.get("channel", {})
            channel_name_en = channel_info.get("english_name") or channel_info.get("name", "Unknown")
            
            # 日本語名を取得（なければ英語名を使用）
            channel_name = MEMBER_NAME_TO_NAME_JA.get(channel_name_en, channel_name_en)

            # 絵文字を取得
            emoji = get_emoji_for_member(channel_name_en)
            if not emoji:
                emoji = "📺"

            # 配信開始時刻
            start_time_str = stream.get("start_scheduled") or stream.get("available_at")
            if start_time_str:
                try:
                    start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
                    jst_time = start_time.astimezone(JST)
                    jst_str = jst_time.strftime("%m/%d %H:%M JST")
                    discord_timestamp = f"<t:{int(start_time.timestamp())}:R>"
                except (ValueError, AttributeError):
                    jst_str = "時刻不明"
                    discord_timestamp = ""
            else:
                jst_str = "時刻不明"
                discord_timestamp = ""

            # 配信タイトル（60文字まで）
            title = stream.get("title", "タイトルなし")
            if len(title) > 60:
                title = title[:57] + "..."

            # 配信URL
            video_id = stream.get("id", "")
            url = f"https://youtube.com/watch?v={video_id}" if video_id else ""

            # コラボ情報を取得
            collab_info = ""
            mentions = stream.get("mentions", [])
            if mentions:
                # コラボ相手の名前を取得（日本語名優先）
                collab_names = []
                for mention in mentions:
                    mention_en = mention.get("english_name") or mention.get("name", "")
                    mention_ja = MEMBER_NAME_TO_NAME_JA.get(mention_en, mention_en)
                    if mention_ja:
                        collab_names.append(mention_ja)
                
                if collab_names:
                    collab_info = f" (Collab with {', '.join(collab_names)})"

            # フォーマット：タイトルにURLを付ける
            if url:
                line = f"**{jst_str}** ({discord_timestamp})\n{emoji} {channel_name}: [{title}]({url}){collab_info}\n"
            else:
                line = f"**{jst_str}** ({discord_timestamp})\n{emoji} {channel_name}: {title}{collab_info}\n"

            description_lines.append(line)

        embed.description = "\n".join(description_lines)

        # 一番直近の配信のサムネイル画像を設定
        if upcoming_streams:
            first_stream = upcoming_streams[0]
            
            # サムネイル画像を設定
            thumbnail_url = first_stream.get("thumbnail")
            if not thumbnail_url:
                # APIから取得できない場合は、video_idから生成
                video_id = first_stream.get("id")
                if video_id:
                    thumbnail_url = f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
            
            if thumbnail_url:
                embed.set_image(url=thumbnail_url)
            
            # フッター：次の配信時刻
            start_time_str = first_stream.get("start_scheduled") or first_stream.get("available_at")
            if start_time_str:
                try:
                    start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
                    jst_time = start_time.astimezone(JST)
                    next_stream_str = jst_time.strftime("%m/%d %H:%M JST")
                    embed.set_footer(text=f"次の配信: {next_stream_str} | 更新")
                except (ValueError, AttributeError):
                    embed.set_footer(text="更新")
            else:
                embed.set_footer(text="更新")

        return embed
