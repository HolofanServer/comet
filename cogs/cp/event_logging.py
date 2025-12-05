"""
Checkpoint イベントログ収集

メッセージ・リアクション・VC・メンションを自動記録
"""
from datetime import datetime, timezone

import discord
from discord.ext import commands

from utils.logging import setup_logging

from .db import checkpoint_db
from .models import MentionLog, MessageLog, ReactionLog, VoiceLog

logger = setup_logging(__name__)


class CheckpointLogging(commands.Cog):
    """Checkpoint ログ収集Cog"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # VC セッション追跡: {user_id: {guild_id: session_info}}
        self._voice_sessions: dict[int, dict[int, dict]] = {}
        # 除外チャンネルキャッシュ: {guild_id: set[channel_id]}
        self._excluded_channels_cache: dict[int, set[int]] = {}

    async def cog_load(self):
        """Cog読み込み時にDB初期化"""
        success = await checkpoint_db.initialize()
        if success:
            logger.info("✅ Checkpoint Logging Cog 読み込み完了")
        else:
            logger.warning("⚠️ Checkpoint DB 未接続（ログ収集は無効）")

    async def cog_unload(self):
        """Cog終了時にDB切断"""
        await checkpoint_db.close()

    def _is_excluded(self, guild_id: int, channel_id: int) -> bool:
        """除外チャンネルかどうか"""
        excluded = self._excluded_channels_cache.get(guild_id, set())
        return channel_id in excluded

    # ==================== メッセージログ ====================

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """メッセージ送信をログ"""
        # Bot・DMは除外
        if message.author.bot or not message.guild:
            return

        # 除外チャンネルチェック
        if self._is_excluded(message.guild.id, message.channel.id):
            return

        content = message.content or ""
        word_count = len(content.split()) if content else 0
        char_count = len(content) if content else 0

        # スレッド・フォーラム判定
        thread_id = None
        forum_id = None
        if isinstance(message.channel, discord.Thread):
            thread_id = message.channel.id
            if message.channel.parent and isinstance(
                message.channel.parent, discord.ForumChannel
            ):
                forum_id = message.channel.parent_id

        log = MessageLog(
            user_id=message.author.id,
            guild_id=message.guild.id,
            channel_id=message.channel.id,
            message_id=message.id,
            content=content[:2000],
            word_count=word_count,
            char_count=char_count,
            has_attachments=len(message.attachments) > 0,
            has_embeds=len(message.embeds) > 0,
            thread_id=thread_id,
            forum_id=forum_id,
            created_at=message.created_at.replace(tzinfo=timezone.utc),
        )

        await checkpoint_db.log_message(log)

        # メンション・リプライをログ
        await self._log_mentions(message)

        # ユーザーメタデータ更新（低頻度で）
        if message.id % 100 == 0:  # 100メッセージに1回
            await checkpoint_db.update_user_metadata(
                user_id=message.author.id,
                guild_id=message.guild.id,
                username=message.author.name,
                display_name=message.author.display_name,
                avatar_url=(
                    message.author.avatar.url if message.author.avatar else None
                ),
            )

    async def _log_mentions(self, message: discord.Message):
        """メンション・リプライをログ"""
        now = datetime.now(timezone.utc)

        # リプライ
        if message.reference and message.reference.message_id:
            try:
                ref_msg = message.reference.cached_message
                if not ref_msg:
                    ref_msg = await message.channel.fetch_message(
                        message.reference.message_id
                    )
                if ref_msg and not ref_msg.author.bot:
                    log = MentionLog(
                        from_user_id=message.author.id,
                        to_user_id=ref_msg.author.id,
                        guild_id=message.guild.id,
                        message_id=message.id,
                        mention_type="reply",
                        channel_id=message.channel.id,
                        created_at=now,
                    )
                    await checkpoint_db.log_mention(log)
            except (discord.NotFound, discord.HTTPException):
                pass

        # メンション
        for user in message.mentions:
            if user.bot or user.id == message.author.id:
                continue
            log = MentionLog(
                from_user_id=message.author.id,
                to_user_id=user.id,
                guild_id=message.guild.id,
                message_id=message.id,
                mention_type="mention",
                channel_id=message.channel.id,
                created_at=now,
            )
            await checkpoint_db.log_mention(log)

    # ==================== リアクションログ ====================

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """リアクション追加をログ"""
        if payload.user_id == self.bot.user.id:
            return

        if not payload.guild_id:
            return

        if self._is_excluded(payload.guild_id, payload.channel_id):
            return

        emoji = payload.emoji
        log = ReactionLog(
            user_id=payload.user_id,
            guild_id=payload.guild_id,
            message_id=payload.message_id,
            emoji_name=emoji.name or "unknown",
            emoji_id=emoji.id if emoji.is_custom_emoji() else None,
            emoji_animated=emoji.animated if emoji.is_custom_emoji() else False,
            is_add=True,
            created_at=datetime.now(timezone.utc),
        )

        await checkpoint_db.log_reaction(log)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        """リアクション削除をログ（統計用ではなく履歴として）"""
        if payload.user_id == self.bot.user.id:
            return

        if not payload.guild_id:
            return

        emoji = payload.emoji
        log = ReactionLog(
            user_id=payload.user_id,
            guild_id=payload.guild_id,
            message_id=payload.message_id,
            emoji_name=emoji.name or "unknown",
            emoji_id=emoji.id if emoji.is_custom_emoji() else None,
            emoji_animated=emoji.animated if emoji.is_custom_emoji() else False,
            is_add=False,
            created_at=datetime.now(timezone.utc),
        )

        await checkpoint_db.log_reaction(log)

    # ==================== VCログ ====================

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        """VC参加・退出をログ"""
        if member.bot:
            return

        guild_id = member.guild.id
        user_id = member.id
        now = datetime.now(timezone.utc)

        # VC参加
        if before.channel is None and after.channel is not None:
            log = VoiceLog(
                user_id=user_id,
                guild_id=guild_id,
                channel_id=after.channel.id,
                joined_at=now,
                was_self_muted=after.self_mute,
                was_self_deafened=after.self_deaf,
            )
            session_id = await checkpoint_db.log_voice_join(log)

            # セッション追跡
            if user_id not in self._voice_sessions:
                self._voice_sessions[user_id] = {}
            self._voice_sessions[user_id][guild_id] = {
                "session_id": session_id,
                "channel_id": after.channel.id,
                "joined_at": now,
            }

        # VC退出
        elif before.channel is not None and after.channel is None:
            await checkpoint_db.log_voice_leave(
                user_id=user_id,
                guild_id=guild_id,
                channel_id=before.channel.id,
                left_at=now,
            )

            # セッション追跡クリア
            if user_id in self._voice_sessions:
                self._voice_sessions[user_id].pop(guild_id, None)

        # チャンネル移動
        elif (
            before.channel is not None
            and after.channel is not None
            and before.channel.id != after.channel.id
        ):
            # 前のチャンネルを退出
            await checkpoint_db.log_voice_leave(
                user_id=user_id,
                guild_id=guild_id,
                channel_id=before.channel.id,
                left_at=now,
            )

            # 新しいチャンネルに参加
            log = VoiceLog(
                user_id=user_id,
                guild_id=guild_id,
                channel_id=after.channel.id,
                joined_at=now,
                was_self_muted=after.self_mute,
                was_self_deafened=after.self_deaf,
            )
            session_id = await checkpoint_db.log_voice_join(log)

            if user_id not in self._voice_sessions:
                self._voice_sessions[user_id] = {}
            self._voice_sessions[user_id][guild_id] = {
                "session_id": session_id,
                "channel_id": after.channel.id,
                "joined_at": now,
            }


async def setup(bot: commands.Bot):
    """Cog setup"""
    await bot.add_cog(CheckpointLogging(bot))
