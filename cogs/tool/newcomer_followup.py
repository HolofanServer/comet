"""
新規参加者フォローアップDMシステム

Week 1 Retention改善のため、サーバー参加後12時間経過+発言なしの
ユーザーに対して、雑談への参加を促すDMを自動送信する。

機能:
- 新規メンバー参加時にDBに記録
- 30分ごとに対象ユーザーをチェック
- 12時間経過 + 発言なし → DM送信
- 発言検知時は has_spoken フラグを更新
- 統計情報の収集（効果測定用）
"""

import asyncio
import traceback
from datetime import datetime, timedelta, timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks

from config.setting import get_settings
from utils.db_manager import db
from utils.logging import setup_logging

# 未使用だが将来使用予定
# from utils.commands_help import is_guild, is_owner, log_commands

logger = setup_logging("NewcomerFollowup")
settings = get_settings()

# 設定から取得
DEFAULT_CHAT_CHANNEL_ID = settings.hfs_chat_channel_id
HFS_GUILD_ID = settings.hfs_main_guild_id


class NewcomerFollowupConfig:
    """フォローアップ設定のデータクラス"""

    def __init__(
        self,
        guild_id: int,
        enabled: bool = True,
        delay_hours: int = 12,
        chat_channel_id: Optional[int] = None,
        check_channels: list[int] = None,
        custom_message: Optional[str] = None
    ):
        self.guild_id = guild_id
        self.enabled = enabled
        self.delay_hours = delay_hours
        self.chat_channel_id = chat_channel_id or DEFAULT_CHAT_CHANNEL_ID
        self.check_channels = check_channels or []
        self.custom_message = custom_message


class NewcomerFollowup(commands.Cog):
    """新規参加者フォローアップDMシステム"""

    # デフォルトのフォローアップメッセージ
    DEFAULT_MESSAGE = """こんにちは！HFSに参加してくれてありがとうございます 🎉

最初は「雑談が活発で流れが早いな…」と感じるかもしれませんが、心配はいりません。
ここにいるみんなは、新しく来た人の一言にもちゃんと反応してくれる人たちです。

まずは雑談チャンネルで、こんな一言だけでも大丈夫です 👇
・「〇〇の配信見てます！」
・「〇〇が好きで参加しました」
・「こんばんは！」だけでもOK

深く考えなくていいので、まずは1メッセージだけ送ってみてください ✨
その一言から、会話が広がっていきます。

▶️ 雑談チャンネルはこちら
https://discord.com/channels/{guild_id}/{channel_id}"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db_manager = None
        self._config_cache: dict[int, NewcomerFollowupConfig] = {}
        logger.info("NewcomerFollowup Cogを初期化中...")

        # 初期化タスク
        self.bot.loop.create_task(self._initialize())

    async def _initialize(self):
        """初期化処理"""
        try:
            await db.initialize()
            self.db_manager = db
            logger.info("NewcomerFollowup: データベース接続完了")

            # 定期タスクを開始
            if not self.check_pending_followups.is_running():
                self.check_pending_followups.start()
                logger.info("NewcomerFollowup: 定期チェックタスク開始")
        except Exception as e:
            logger.error(f"NewcomerFollowup初期化エラー: {e}\n{traceback.format_exc()}")

    def cog_unload(self):
        """Cogアンロード時の処理"""
        if self.check_pending_followups.is_running():
            self.check_pending_followups.cancel()
            logger.info("NewcomerFollowup: 定期チェックタスク停止")

    async def _get_config(self, guild_id: int) -> NewcomerFollowupConfig:
        """ギルドの設定を取得（キャッシュ付き）"""
        if guild_id in self._config_cache:
            return self._config_cache[guild_id]

        if not self.db_manager:
            return NewcomerFollowupConfig(guild_id)

        try:
            async with self.db_manager.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT enabled, delay_hours, chat_channel_id, check_channels, custom_message
                    FROM newcomer_followup_config
                    WHERE guild_id = $1
                    """,
                    guild_id
                )

                if row:
                    config = NewcomerFollowupConfig(
                        guild_id=guild_id,
                        enabled=row['enabled'],
                        delay_hours=row['delay_hours'],
                        chat_channel_id=row['chat_channel_id'],
                        check_channels=list(row['check_channels']) if row['check_channels'] else [],
                        custom_message=row['custom_message']
                    )
                else:
                    config = NewcomerFollowupConfig(guild_id)

                self._config_cache[guild_id] = config
                return config
        except Exception as e:
            logger.error(f"設定取得エラー: {e}")
            return NewcomerFollowupConfig(guild_id)

    async def _save_config(self, config: NewcomerFollowupConfig) -> bool:
        """設定を保存"""
        if not self.db_manager:
            return False

        try:
            async with self.db_manager.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO newcomer_followup_config
                    (guild_id, enabled, delay_hours, chat_channel_id, check_channels, custom_message, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, NOW())
                    ON CONFLICT (guild_id) DO UPDATE SET
                        enabled = $2,
                        delay_hours = $3,
                        chat_channel_id = $4,
                        check_channels = $5,
                        custom_message = $6,
                        updated_at = NOW()
                    """,
                    config.guild_id,
                    config.enabled,
                    config.delay_hours,
                    config.chat_channel_id,
                    config.check_channels,
                    config.custom_message
                )

            self._config_cache[config.guild_id] = config
            return True
        except Exception as e:
            logger.error(f"設定保存エラー: {e}")
            return False

    async def _record_new_member(self, member: discord.Member) -> bool:
        """新規メンバーをDBに記録"""
        if not self.db_manager:
            return False

        try:
            async with self.db_manager.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO newcomer_followup (guild_id, user_id, joined_at)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (guild_id, user_id) DO UPDATE SET
                        joined_at = $3,
                        dm_sent_at = NULL,
                        has_spoken = FALSE,
                        first_message_at = NULL,
                        updated_at = NOW()
                    """,
                    member.guild.id,
                    member.id,
                    member.joined_at or datetime.now(timezone.utc)
                )

                # 統計更新
                await conn.execute(
                    """
                    INSERT INTO newcomer_followup_stats (guild_id, date, new_members)
                    VALUES ($1, $2, 1)
                    ON CONFLICT (guild_id, date) DO UPDATE SET
                        new_members = newcomer_followup_stats.new_members + 1
                    """,
                    member.guild.id,
                    datetime.now(timezone.utc).date()
                )

            logger.info(f"新規メンバー記録: {member.name}({member.id}) in {member.guild.name}")
            return True
        except Exception as e:
            logger.error(f"新規メンバー記録エラー: {e}")
            return False

    async def _mark_as_spoken(self, guild_id: int, user_id: int) -> bool:
        """ユーザーが発言したことを記録"""
        if not self.db_manager:
            return False

        try:
            async with self.db_manager.pool.acquire() as conn:
                result = await conn.execute(
                    """
                    UPDATE newcomer_followup
                    SET has_spoken = TRUE,
                        first_message_at = COALESCE(first_message_at, NOW()),
                        updated_at = NOW()
                    WHERE guild_id = $1 AND user_id = $2
                        AND has_spoken = FALSE
                    """,
                    guild_id,
                    user_id
                )

                if "UPDATE 1" in result:
                    # DM送信前に発言した場合は統計を更新
                    await conn.execute(
                        """
                        UPDATE newcomer_followup_stats
                        SET spoke_before_dm = spoke_before_dm + 1
                        WHERE guild_id = $1 AND date = $2
                        """,
                        guild_id,
                        datetime.now(timezone.utc).date()
                    )
                    logger.info(f"発言検知: user_id={user_id} in guild_id={guild_id}")
                    return True
            return False
        except Exception as e:
            logger.error(f"発言記録エラー: {e}")
            return False

    async def _get_pending_users(self, guild_id: int, delay_hours: int) -> list[dict]:
        """DM送信対象のユーザーを取得"""
        if not self.db_manager:
            return []

        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=delay_hours)

            async with self.db_manager.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT user_id, joined_at
                    FROM newcomer_followup
                    WHERE guild_id = $1
                        AND joined_at <= $2
                        AND dm_sent_at IS NULL
                        AND has_spoken = FALSE
                    """,
                    guild_id,
                    cutoff_time
                )

                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"対象ユーザー取得エラー: {e}")
            return []

    async def _send_followup_dm(
        self,
        member: discord.Member,
        config: NewcomerFollowupConfig
    ) -> bool:
        """フォローアップDMを送信"""
        try:
            # メッセージを生成
            message = config.custom_message or self.DEFAULT_MESSAGE
            message = message.format(
                guild_id=member.guild.id,
                channel_id=config.chat_channel_id
            )

            # DM送信
            await member.send(message)

            # DB更新
            if self.db_manager:
                async with self.db_manager.pool.acquire() as conn:
                    await conn.execute(
                        """
                        UPDATE newcomer_followup
                        SET dm_sent_at = NOW(), updated_at = NOW()
                        WHERE guild_id = $1 AND user_id = $2
                        """,
                        member.guild.id,
                        member.id
                    )

                    # 統計更新
                    await conn.execute(
                        """
                        INSERT INTO newcomer_followup_stats (guild_id, date, dm_sent)
                        VALUES ($1, $2, 1)
                        ON CONFLICT (guild_id, date) DO UPDATE SET
                            dm_sent = newcomer_followup_stats.dm_sent + 1
                        """,
                        member.guild.id,
                        datetime.now(timezone.utc).date()
                    )

            logger.info(f"フォローアップDM送信: {member.name}({member.id}) in {member.guild.name}")
            return True

        except discord.Forbidden:
            logger.warning(f"DM送信不可（DM拒否）: {member.name}({member.id})")
            # DM送信済みとしてマーク（再送信防止）
            if self.db_manager:
                async with self.db_manager.pool.acquire() as conn:
                    await conn.execute(
                        """
                        UPDATE newcomer_followup
                        SET dm_sent_at = NOW(), updated_at = NOW()
                        WHERE guild_id = $1 AND user_id = $2
                        """,
                        member.guild.id,
                        member.id
                    )
            return False
        except Exception as e:
            logger.error(f"DM送信エラー: {e}")
            return False

    @tasks.loop(minutes=30)
    async def check_pending_followups(self):
        """定期的にペンディング中のフォローアップをチェック"""
        logger.debug("NewcomerFollowup: 定期チェック実行中...")

        for guild in self.bot.guilds:
            try:
                config = await self._get_config(guild.id)

                if not config.enabled:
                    continue

                # 対象ユーザーを取得
                pending_users = await self._get_pending_users(guild.id, config.delay_hours)

                if not pending_users:
                    continue

                logger.info(f"Guild {guild.name}: {len(pending_users)}人のフォローアップ対象")

                for user_data in pending_users:
                    user_id = user_data['user_id']
                    member = guild.get_member(user_id)

                    if not member:
                        # メンバーが見つからない（退出済み）
                        logger.debug(f"メンバー不在（退出済み）: user_id={user_id}")
                        if self.db_manager:
                            async with self.db_manager.pool.acquire() as conn:
                                await conn.execute(
                                    """
                                    UPDATE newcomer_followup
                                    SET dm_sent_at = NOW(), updated_at = NOW()
                                    WHERE guild_id = $1 AND user_id = $2
                                    """,
                                    guild.id,
                                    user_id
                                )
                                await conn.execute(
                                    """
                                    UPDATE newcomer_followup_stats
                                    SET left_before_dm = left_before_dm + 1
                                    WHERE guild_id = $1 AND date = $2
                                    """,
                                    guild.id,
                                    datetime.now(timezone.utc).date()
                                )
                        continue

                    # DM送信
                    await self._send_followup_dm(member, config)

                    # レート制限対策
                    await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"Guild {guild.name} の処理中にエラー: {e}\n{traceback.format_exc()}")

    @check_pending_followups.before_loop
    async def before_check_pending_followups(self):
        """タスク開始前にBotの準備を待つ"""
        await self.bot.wait_until_ready()
        logger.info("NewcomerFollowup: Bot準備完了、定期チェック開始")

    # === イベントハンドラ ===

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """メンバー参加時の処理"""
        if member.bot:
            return

        config = await self._get_config(member.guild.id)
        if not config.enabled:
            return

        await self._record_new_member(member)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """メッセージ検知時の処理"""
        # Botのメッセージは無視
        if message.author.bot:
            return

        # DMは無視
        if not message.guild:
            return

        # 発言を記録
        await self._mark_as_spoken(message.guild.id, message.author.id)

    # === 管理コマンド ===

    followup = app_commands.Group(
        name="newcomer_followup",
        description="新規参加者フォローアップDM設定"
    )

    @followup.command(name="status")
    @app_commands.describe()
    async def followup_status(self, interaction: discord.Interaction):
        """フォローアップシステムの状態を確認"""
        await interaction.response.defer(ephemeral=True)

        config = await self._get_config(interaction.guild_id)

        # 統計を取得
        stats = None
        if self.db_manager:
            async with self.db_manager.pool.acquire() as conn:
                stats = await conn.fetchrow(
                    """
                    SELECT
                        COALESCE(SUM(new_members), 0) as total_new,
                        COALESCE(SUM(dm_sent), 0) as total_dm,
                        COALESCE(SUM(spoke_before_dm), 0) as spoke_before,
                        COALESCE(SUM(spoke_after_dm), 0) as spoke_after
                    FROM newcomer_followup_stats
                    WHERE guild_id = $1
                        AND date >= CURRENT_DATE - INTERVAL '30 days'
                    """,
                    interaction.guild_id
                )

        embed = discord.Embed(
            title="📊 新規参加者フォローアップ状態",
            color=discord.Color.blue()
        )

        embed.add_field(
            name="🔧 設定",
            value=f"**有効:** {'✅' if config.enabled else '❌'}\n"
                  f"**待機時間:** {config.delay_hours}時間\n"
                  f"**雑談チャンネル:** <#{config.chat_channel_id}>",
            inline=False
        )

        if stats:
            embed.add_field(
                name="📈 過去30日の統計",
                value=f"**新規参加:** {stats['total_new']}人\n"
                      f"**DM送信:** {stats['total_dm']}通\n"
                      f"**DM前に発言:** {stats['spoke_before']}人\n"
                      f"**DM後に発言:** {stats['spoke_after']}人",
                inline=False
            )

        await interaction.followup.send(embed=embed, ephemeral=True)

    @followup.command(name="enable")
    @app_commands.describe(enabled="有効/無効")
    async def followup_enable(
        self,
        interaction: discord.Interaction,
        enabled: bool
    ):
        """フォローアップシステムの有効/無効を切り替え"""
        await interaction.response.defer(ephemeral=True)

        config = await self._get_config(interaction.guild_id)
        config.enabled = enabled

        if await self._save_config(config):
            status = "有効" if enabled else "無効"
            await interaction.followup.send(
                f"✅ フォローアップDMを**{status}**にしました。",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                "❌ 設定の保存に失敗しました。",
                ephemeral=True
            )

    @followup.command(name="set_delay")
    @app_commands.describe(hours="DM送信までの待機時間（時間）")
    async def followup_set_delay(
        self,
        interaction: discord.Interaction,
        hours: int
    ):
        """DM送信までの待機時間を設定"""
        await interaction.response.defer(ephemeral=True)

        if hours < 1 or hours > 168:  # 1時間〜1週間
            await interaction.followup.send(
                "❌ 待機時間は1〜168時間の範囲で指定してください。",
                ephemeral=True
            )
            return

        config = await self._get_config(interaction.guild_id)
        config.delay_hours = hours

        if await self._save_config(config):
            await interaction.followup.send(
                f"✅ 待機時間を**{hours}時間**に設定しました。",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                "❌ 設定の保存に失敗しました。",
                ephemeral=True
            )

    @followup.command(name="set_channel")
    @app_commands.describe(channel="案内先の雑談チャンネル")
    async def followup_set_channel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel
    ):
        """案内先の雑談チャンネルを設定"""
        await interaction.response.defer(ephemeral=True)

        config = await self._get_config(interaction.guild_id)
        config.chat_channel_id = channel.id

        if await self._save_config(config):
            await interaction.followup.send(
                f"✅ 雑談チャンネルを {channel.mention} に設定しました。",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                "❌ 設定の保存に失敗しました。",
                ephemeral=True
            )

    @followup.command(name="test")
    @app_commands.describe(user="テスト送信先のユーザー（省略時は自分）")
    async def followup_test(
        self,
        interaction: discord.Interaction,
        user: discord.Member = None
    ):
        """フォローアップDMをテスト送信"""
        await interaction.response.defer(ephemeral=True)

        target = user or interaction.user
        config = await self._get_config(interaction.guild_id)

        message = config.custom_message or self.DEFAULT_MESSAGE
        message = message.format(
            guild_id=interaction.guild_id,
            channel_id=config.chat_channel_id
        )

        try:
            await target.send(f"**[テスト送信]**\n\n{message}")
            await interaction.followup.send(
                f"✅ {target.mention} にテストDMを送信しました。",
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.followup.send(
                f"❌ {target.mention} へのDM送信が拒否されました。",
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(
                f"❌ エラーが発生しました: {e}",
                ephemeral=True
            )

    @followup.command(name="preview")
    async def followup_preview(self, interaction: discord.Interaction):
        """現在設定されているメッセージをプレビュー"""
        await interaction.response.defer(ephemeral=True)

        config = await self._get_config(interaction.guild_id)

        message = config.custom_message or self.DEFAULT_MESSAGE
        message = message.format(
            guild_id=interaction.guild_id,
            channel_id=config.chat_channel_id
        )

        embed = discord.Embed(
            title="📝 フォローアップDMプレビュー",
            description=message,
            color=discord.Color.green()
        )

        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    """Cogのセットアップ"""
    logger.info("NewcomerFollowup Cogをセットアップ中...")
    try:
        await bot.add_cog(NewcomerFollowup(bot))
        logger.info("NewcomerFollowup Cogの登録が完了しました")
    except Exception as e:
        logger.error(f"NewcomerFollowup Cogの登録に失敗しました: {e}\n{traceback.format_exc()}")
