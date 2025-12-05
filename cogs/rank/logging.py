"""
HFS Rank イベントログ

メッセージ・VC・おみくじイベントからXPを付与
"""
from datetime import datetime, timezone

import discord
from discord.ext import commands, tasks

from utils.logging import setup_logging

from .models import rank_db
from .service import rank_service

logger = setup_logging(__name__)


class RankLogging(commands.Cog):
    """Rankログ収集Cog"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # VC追跡: {user_id: {guild_id: joined_at}}
        self._vc_sessions: dict[int, dict[int, datetime]] = {}

    async def cog_load(self):
        """Cog読み込み時に初期化"""
        await rank_db.initialize()
        self.vc_xp_task.start()
        logger.info("✅ Rank Logging Cog 読み込み完了")

    async def cog_unload(self):
        """Cog終了時"""
        self.vc_xp_task.cancel()

    # ==================== メッセージXP ====================

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """メッセージ送信でXP付与"""
        # Bot・DMは除外
        if message.author.bot or not message.guild:
            return

        # 設定取得・除外チェック
        config = await rank_db.get_config(message.guild.id)
        if not config.is_enabled:
            return

        if rank_service.is_channel_excluded(message.channel.id, config):
            return

        # 除外ロールチェック
        if config.excluded_roles:
            member_role_ids = {r.id for r in message.author.roles}
            if member_role_ids & set(config.excluded_roles):
                return

        # XP付与
        await rank_service.add_message_xp(message.author.id, message.guild.id)

    # ==================== VC XP ====================

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        """VC参加・退出を追跡"""
        if member.bot:
            return

        guild_id = member.guild.id
        user_id = member.id
        now = datetime.now(timezone.utc)

        # VC参加
        if before.channel is None and after.channel is not None:
            if user_id not in self._vc_sessions:
                self._vc_sessions[user_id] = {}
            self._vc_sessions[user_id][guild_id] = now

        # VC退出
        elif before.channel is not None and after.channel is None:
            if user_id in self._vc_sessions and guild_id in self._vc_sessions[user_id]:
                joined_at = self._vc_sessions[user_id].pop(guild_id)
                duration = (now - joined_at).total_seconds() / 60
                if duration >= 5:  # 5分以上でXP付与
                    await rank_service.add_vc_xp(user_id, guild_id, int(duration))

        # チャンネル移動
        elif (
            before.channel is not None
            and after.channel is not None
            and before.channel.id != after.channel.id
        ):
            # セッション継続（チャンネル変更では中断しない）
            pass

    @tasks.loop(minutes=10)
    async def vc_xp_task(self):
        """10分ごとにVC中のユーザーにXP付与"""
        now = datetime.now(timezone.utc)

        for user_id, guilds in list(self._vc_sessions.items()):
            for guild_id, joined_at in list(guilds.items()):
                duration = (now - joined_at).total_seconds() / 60
                if duration >= 10:
                    # 10分経過したらXP付与してリセット
                    await rank_service.add_vc_xp(user_id, guild_id, 10)
                    self._vc_sessions[user_id][guild_id] = now

    @vc_xp_task.before_loop
    async def before_vc_xp_task(self):
        """タスク開始前にBotの準備を待つ"""
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    """Cog setup"""
    await bot.add_cog(RankLogging(bot))
