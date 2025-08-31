"""
音声チャンネルXPシステム - Discord音声状態追跡

Discord.pyのVoiceStateUpdateイベントを利用して
音声チャンネルの参加・離脱・状態変化を追跡し、
リアルタイムでXP計算を実行する。
"""

from datetime import datetime
from typing import Optional

import discord
from discord.ext import commands, tasks

from models.rank.voice_activity import VoiceActivityType
from utils.database import execute_query
from utils.logging import setup_logging
from utils.rank.voice_manager import voice_manager

logger = setup_logging("VOICE_TRACKER")

class VoiceTrackerCog(commands.Cog):
    """音声チャンネル状態追跡システム"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

        # 発言検出用のキャッシュ
        self.speaking_cache: dict[int, bool] = {}  # user_id -> is_speaking

        # 定期的なAFK検出タスク
        self.afk_detection_task.start()

        logger.info("音声チャンネル追跡システムを開始しました")

    def cog_unload(self):
        """Cog終了時のクリーンアップ"""
        self.afk_detection_task.cancel()
        logger.info("音声チャンネル追跡システムを停止しました")

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState
    ):
        """音声状態変更イベント処理"""
        try:
            # ボットは除外
            if member.bot:
                return

            guild_id = member.guild.id
            user_id = member.id

            # 音声チャンネル参加処理
            if before.channel is None and after.channel is not None:
                await self._handle_voice_join(guild_id, user_id, after.channel.id, after)

            # 音声チャンネル離脱処理
            elif before.channel is not None and after.channel is None:
                await self._handle_voice_leave(guild_id, user_id)

            # 音声チャンネル移動処理
            elif before.channel != after.channel and before.channel is not None and after.channel is not None:
                await self._handle_voice_move(guild_id, user_id, before.channel.id, after.channel.id, after)

            # 音声状態変更処理（同じチャンネル内）
            elif before.channel == after.channel and after.channel is not None:
                await self._handle_voice_state_change(guild_id, user_id, after)

        except Exception as e:
            logger.error(f"音声状態更新エラー (Guild: {member.guild.id}, User: {member.id}): {e}")

    async def _handle_voice_join(
        self,
        guild_id: int,
        user_id: int,
        channel_id: int,
        voice_state: discord.VoiceState
    ):
        """音声チャンネル参加処理"""
        try:
            # 初期活動状態を判定
            initial_activity = self._determine_activity_type(voice_state)

            # セッション開始
            session_id = await voice_manager.start_voice_session(
                guild_id, user_id, channel_id, initial_activity
            )

            if session_id:
                logger.info(f"Guild {guild_id}, User {user_id}: 音声チャンネル参加 (Channel: {channel_id})")

                # 発言状態をキャッシュに記録
                self.speaking_cache[user_id] = False

        except Exception as e:
            logger.error(f"音声参加処理エラー: {e}")

    async def _handle_voice_leave(self, guild_id: int, user_id: int):
        """音声チャンネル離脱処理"""
        try:
            # セッション終了
            completed_session = await voice_manager.end_voice_session(guild_id, user_id)

            if completed_session:
                logger.info(f"Guild {guild_id}, User {user_id}: 音声チャンネル離脱")

                # 獲得XPをメインレベリングシステムに統合
                await self._integrate_voice_xp_to_main_system(completed_session)

            # キャッシュから削除
            self.speaking_cache.pop(user_id, None)

        except Exception as e:
            logger.error(f"音声離脱処理エラー: {e}")

    async def _handle_voice_move(
        self,
        guild_id: int,
        user_id: int,
        old_channel_id: int,
        new_channel_id: int,
        voice_state: discord.VoiceState
    ):
        """音声チャンネル移動処理"""
        try:
            # 古いセッションを終了
            completed_session = await voice_manager.end_voice_session(guild_id, user_id)

            if completed_session and completed_session.total_xp_earned > 0:
                # 獲得XPをメインシステムに統合
                await self._integrate_voice_xp_to_main_system(completed_session)

            # 新しいセッションを開始
            initial_activity = self._determine_activity_type(voice_state)
            session_id = await voice_manager.start_voice_session(
                guild_id, user_id, new_channel_id, initial_activity
            )

            if session_id:
                logger.info(f"Guild {guild_id}, User {user_id}: チャンネル移動 {old_channel_id} -> {new_channel_id}")

        except Exception as e:
            logger.error(f"音声移動処理エラー: {e}")

    async def _handle_voice_state_change(
        self,
        guild_id: int,
        user_id: int,
        voice_state: discord.VoiceState
    ):
        """音声状態変更処理（同じチャンネル内）"""
        try:
            # 新しい活動状態を判定
            new_activity = self._determine_activity_type(voice_state)

            # 活動状態を更新
            await voice_manager.update_voice_activity(
                guild_id, user_id, new_activity, speaking=False
            )

            logger.debug(f"Guild {guild_id}, User {user_id}: 音声状態変更 -> {new_activity.value}")

        except Exception as e:
            logger.error(f"音声状態変更処理エラー: {e}")

    def _determine_activity_type(self, voice_state: discord.VoiceState) -> VoiceActivityType:
        """VoiceStateからVoiceActivityTypeを判定"""
        # スピーカーオフ（deafened）
        if voice_state.deaf or voice_state.self_deaf:
            return VoiceActivityType.DEAFENED

        # ミュート状態
        if voice_state.mute or voice_state.self_mute:
            return VoiceActivityType.MUTED

        # AFK判定は別途タスクで実行するため、ここではLISTENINGとする
        return VoiceActivityType.LISTENING

    async def _integrate_voice_xp_to_main_system(self, voice_session):
        """音声XPをメインレベリングシステムに統合"""
        try:
            if voice_session.total_xp_earned <= 0:
                return

            # メインレベリングシステムに音声XPを追加

            # Botからレベリングシステムのcogを取得
            leveling_cog = self.bot.get_cog("レベリング")
            if not leveling_cog:
                logger.warning("レベリングシステムcogが見つかりません")
                return

            # ギルドとメンバーを取得
            guild = self.bot.get_guild(voice_session.guild_id)
            if not guild:
                logger.warning(f"Guild {voice_session.guild_id} が見つかりません")
                return

            member = guild.get_member(voice_session.user_id)
            if not member:
                logger.warning(f"User {voice_session.user_id} が見つかりません")
                return

            # 音声XPをメインレベリングシステムに追加
            level_up, new_level = await leveling_cog.db.add_xp(
                voice_session.guild_id,
                voice_session.user_id,
                member.display_name,
                voice_session.total_xp_earned
            )

            # レベルアップした場合の処理
            if level_up:
                # 音声XPによるレベルアップ通知を送信
                try:
                    channel = guild.get_channel(voice_session.channel_id)
                    if channel:
                        embed = discord.Embed(
                            title="🎤 音声XPレベルアップ！",
                            description=f"{member.mention} が音声活動によりレベル **{new_level}** に到達！",
                            color=discord.Color.gold()
                        )

                        embed.add_field(
                            name="📊 音声セッション詳細",
                            value=f"**滞在時間:** {voice_session.duration_seconds // 60}分{voice_session.duration_seconds % 60}秒\n"
                                  f"**獲得XP:** {voice_session.total_xp_earned}\n"
                                  f"**新レベル:** {new_level}",
                            inline=False
                        )

                        embed.set_thumbnail(url=member.display_avatar.url)
                        await channel.send(embed=embed)

                except Exception as notification_error:
                    logger.warning(f"音声XPレベルアップ通知送信エラー: {notification_error}")

                logger.info(f"Guild {voice_session.guild_id}, User {voice_session.user_id}: "
                           f"音声XPレベルアップ {new_level} (音声XP: {voice_session.total_xp_earned})")
            else:
                logger.info(f"Guild {voice_session.guild_id}, User {voice_session.user_id}: "
                           f"音声XP統合 {voice_session.total_xp_earned}")

        except Exception as e:
            logger.error(f"音声XP統合エラー: {e}")

    @tasks.loop(minutes=5)  # 5分ごとにAFK検出
    async def afk_detection_task(self):
        """定期的なAFK検出タスク"""
        try:
            current_time = datetime.now()
            afk_threshold_minutes = 10  # デフォルトAFK判定時間

            for guild in self.bot.guilds:
                try:
                    # ギルドの音声設定を取得
                    config = await voice_manager.get_guild_voice_config(guild.id)
                    afk_threshold_minutes = config.afk_detection_minutes

                    # 音声チャンネルのメンバーをチェック
                    for channel in guild.voice_channels:
                        for member in channel.members:
                            if member.bot:
                                continue

                            # 最後の活動時間をチェック（簡易実装）
                            active_session = None

                            for session in voice_manager.active_sessions.values():
                                if session.guild_id == guild.id and session.user_id == member.id:
                                    active_session = session
                                    break

                            if not active_session:
                                continue

                            # AFK判定
                            time_since_activity = (current_time - active_session.last_activity_time).total_seconds()
                            if time_since_activity > (afk_threshold_minutes * 60):
                                # AFK状態に設定
                                await voice_manager.update_voice_activity(
                                    guild.id, member.id, VoiceActivityType.AFK
                                )

                except Exception as guild_error:
                    logger.debug(f"Guild {guild.id} AFK検出エラー: {guild_error}")

        except Exception as e:
            logger.error(f"AFK検出タスクエラー: {e}")

    @afk_detection_task.before_loop
    async def before_afk_detection_task(self):
        """AFK検出タスク開始前の待機"""
        await self.bot.wait_until_ready()

    # 音声統計表示コマンド
    @commands.hybrid_command(name="voice-stats", description="音声活動統計を表示")
    async def voice_stats(self, ctx: commands.Context, user: Optional[discord.Member] = None):
        """音声活動統計を表示"""
        target_user = user or ctx.author

        try:
            # データベースから音声統計を取得
            query = """
            SELECT total_voice_time_seconds, total_voice_xp, total_sessions,
                   longest_session_seconds, highest_daily_xp, average_xp_per_minute,
                   track_stats, daily_stats
            FROM voice_stats
            WHERE guild_id = $1 AND user_id = $2
            """

            result = await execute_query(query, ctx.guild.id, target_user.id, fetch_type='row')

            if not result:
                embed = discord.Embed(
                    title="📊 音声活動統計",
                    description=f"{target_user.mention} の音声活動データが見つかりません。",
                    color=discord.Color.orange()
                )
                await ctx.send(embed=embed)
                return

            # 統計データを整理
            total_time_seconds = result["total_voice_time_seconds"] or 0
            total_voice_xp = result["total_voice_xp"] or 0
            total_sessions = result["total_sessions"] or 0
            longest_session = result["longest_session_seconds"] or 0
            highest_daily_xp = result["highest_daily_xp"] or 0
            avg_xp_per_minute = result["average_xp_per_minute"] or 0.0

            # 時間の表示形式変換
            hours = total_time_seconds // 3600
            minutes = (total_time_seconds % 3600) // 60

            longest_hours = longest_session // 3600
            longest_minutes = (longest_session % 3600) // 60

            embed = discord.Embed(
                title="📊 音声活動統計",
                description=f"{target_user.mention} の音声チャンネル活動データ",
                color=discord.Color.blue()
            )

            embed.set_thumbnail(url=target_user.display_avatar.url)

            # 基本統計
            embed.add_field(
                name="⏱️ 基本統計",
                value=f"**総滞在時間:** {hours}時間{minutes}分\n"
                      f"**総音声XP:** {total_voice_xp:,}\n"
                      f"**セッション数:** {total_sessions:,}\n"
                      f"**平均XP/分:** {avg_xp_per_minute:.1f}",
                inline=True
            )

            # ベスト記録
            embed.add_field(
                name="🏆 ベスト記録",
                value=f"**最長セッション:** {longest_hours}時間{longest_minutes}分\n"
                      f"**最高日XP:** {highest_daily_xp:,}\n"
                      f"**平均セッション時間:** {(total_time_seconds // total_sessions) // 60 if total_sessions > 0 else 0}分",
                inline=True
            )

            # 現在のアクティブセッション
            user_key = f"{ctx.guild.id}:{target_user.id}"
            active_session = voice_manager.active_sessions.get(user_key)

            if active_session:
                current_session_time = int((datetime.now() - active_session.start_time).total_seconds())
                current_hours = current_session_time // 3600
                current_minutes = (current_session_time % 3600) // 60

                embed.add_field(
                    name="🔴 現在のセッション",
                    value=f"**チャンネル:** <#{active_session.channel_id}>\n"
                          f"**経過時間:** {current_hours}時間{current_minutes}分\n"
                          f"**状態:** {active_session.current_activity.value}\n"
                          f"**累積XP:** {active_session.pending_xp}",
                    inline=False
                )

            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"音声統計表示エラー: {e}")
            await ctx.send(
                f"❌ **エラー**\n音声統計の表示に失敗しました: {str(e)}",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(VoiceTrackerCog(bot))
