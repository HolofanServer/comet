from datetime import datetime

import discord
from discord.ext import commands

from utils.db_manager import db
from utils.logging import setup_logging

logger = setup_logging()


class ChannelMuteSystem(commands.Cog):
    """チャンネル権限によるミュート（発言禁止）システム"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # guild_id -> {user_id: set[excluded_channel_ids]}
        self.muted_users: dict[int, dict[int, set[int]]] = {}
        # guild_id -> log_channel_id
        self.log_channel_ids: dict[int, int] = {}

    async def cog_load(self):
        """Cog読み込み時の初期化"""
        await self._create_tables()
        await self._load_data_from_db()
        logger.info("ChannelMuteSystem Cogが読み込まれました")

    async def _create_tables(self):
        """必要なテーブルを作成"""
        try:
            async with db.pool.acquire() as conn:
                # ミュート対象ユーザーテーブル
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS channel_muted_users (
                        id SERIAL PRIMARY KEY,
                        guild_id BIGINT NOT NULL,
                        user_id BIGINT NOT NULL,
                        added_by BIGINT NOT NULL,
                        added_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        reason TEXT,
                        UNIQUE(guild_id, user_id)
                    )
                """)

                # ユーザーごとの除外チャンネルテーブル
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS channel_mute_exclusions (
                        id SERIAL PRIMARY KEY,
                        guild_id BIGINT NOT NULL,
                        user_id BIGINT NOT NULL,
                        channel_id BIGINT NOT NULL,
                        added_by BIGINT NOT NULL,
                        added_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(guild_id, user_id, channel_id)
                    )
                """)

                # ミュートシステム設定テーブル
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS channel_mute_config (
                        id SERIAL PRIMARY KEY,
                        guild_id BIGINT NOT NULL UNIQUE,
                        log_channel_id BIGINT,
                        is_enabled BOOLEAN DEFAULT TRUE,
                        updated_by BIGINT NOT NULL,
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # ミュートログテーブル
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS channel_mute_logs (
                        id SERIAL PRIMARY KEY,
                        guild_id BIGINT NOT NULL,
                        user_id BIGINT NOT NULL,
                        action TEXT NOT NULL,
                        performed_by BIGINT NOT NULL,
                        details TEXT,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    )
                """)

            logger.info("ChannelMuteSystemのテーブル作成完了")
        except Exception as e:
            logger.error(f"テーブル作成エラー: {e}")

    async def _load_data_from_db(self):
        """データベースからデータを読み込み"""
        try:
            async with db.pool.acquire() as conn:
                # ミュート対象ユーザーを読み込み
                muted_data = await conn.fetch("SELECT guild_id, user_id FROM channel_muted_users")
                for row in muted_data:
                    guild_id = row['guild_id']
                    user_id = row['user_id']
                    if guild_id not in self.muted_users:
                        self.muted_users[guild_id] = {}
                    if user_id not in self.muted_users[guild_id]:
                        self.muted_users[guild_id][user_id] = set()

                # 除外チャンネルを読み込み
                exclusion_data = await conn.fetch("SELECT guild_id, user_id, channel_id FROM channel_mute_exclusions")
                for row in exclusion_data:
                    guild_id = row['guild_id']
                    user_id = row['user_id']
                    channel_id = row['channel_id']
                    if guild_id in self.muted_users and user_id in self.muted_users[guild_id]:
                        self.muted_users[guild_id][user_id].add(channel_id)

                # ログチャンネル設定を読み込み
                config_data = await conn.fetch("SELECT guild_id, log_channel_id FROM channel_mute_config WHERE is_enabled = TRUE")
                for row in config_data:
                    if row['log_channel_id']:
                        self.log_channel_ids[row['guild_id']] = row['log_channel_id']

            total_users = sum(len(users) for users in self.muted_users.values())
            logger.info(f"ChannelMuteSystemデータ読み込み完了: ミュートユーザー {total_users}人")
        except Exception as e:
            logger.error(f"データ読み込みエラー: {e}")

    async def _apply_mute_to_all_channels(
        self,
        guild: discord.Guild,
        user_id: int,
        excluded_channels: set[int],
        reason: str = "Channel Mute System"
    ) -> tuple[int, int]:
        """全チャンネルにミュート権限を適用

        Returns:
            tuple[int, int]: (成功数, 失敗数)
        """
        success_count = 0
        fail_count = 0
        member = guild.get_member(user_id)

        if not member:
            # メンバーがサーバーにいない場合はObjectで代用
            target = discord.Object(id=user_id)
        else:
            target = member

        for channel in guild.channels:
            # 除外チャンネルはスキップ
            if channel.id in excluded_channels:
                logger.debug(f"除外チャンネルをスキップ: {channel.name}")
                continue

            # テキスト系チャンネルのみ対象
            if not isinstance(channel, (discord.TextChannel, discord.VoiceChannel, discord.ForumChannel, discord.StageChannel)):
                continue

            try:
                # 権限オーバーライドを設定
                overwrite = channel.overwrites_for(target)
                overwrite.send_messages = False
                overwrite.send_messages_in_threads = False
                overwrite.create_public_threads = False
                overwrite.create_private_threads = False
                overwrite.add_reactions = False  # リアクションも禁止（オプション）

                await channel.set_permissions(target, overwrite=overwrite, reason=reason)
                success_count += 1
                logger.debug(f"ミュート権限を適用: {channel.name}")

            except discord.Forbidden:
                fail_count += 1
                logger.warning(f"権限不足でミュート適用失敗: {channel.name}")
            except Exception as e:
                fail_count += 1
                logger.error(f"ミュート適用エラー ({channel.name}): {e}")

        return success_count, fail_count

    async def _remove_mute_from_all_channels(
        self,
        guild: discord.Guild,
        user_id: int,
        reason: str = "Channel Mute System - Unmute"
    ) -> tuple[int, int]:
        """全チャンネルからミュート権限を解除

        Returns:
            tuple[int, int]: (成功数, 失敗数)
        """
        success_count = 0
        fail_count = 0
        member = guild.get_member(user_id)

        if not member:
            target = discord.Object(id=user_id)
        else:
            target = member

        for channel in guild.channels:
            if not isinstance(channel, (discord.TextChannel, discord.VoiceChannel, discord.ForumChannel, discord.StageChannel)):
                continue

            try:
                # 現在の権限オーバーライドを取得
                overwrite = channel.overwrites_for(target)

                # ミュート関連の権限をリセット（Noneに戻す）
                overwrite.send_messages = None
                overwrite.send_messages_in_threads = None
                overwrite.create_public_threads = None
                overwrite.create_private_threads = None
                overwrite.add_reactions = None

                # すべてNoneなら権限オーバーライド自体を削除
                if overwrite.is_empty():
                    await channel.set_permissions(target, overwrite=None, reason=reason)
                else:
                    await channel.set_permissions(target, overwrite=overwrite, reason=reason)

                success_count += 1

            except discord.Forbidden:
                fail_count += 1
                logger.warning(f"権限不足でミュート解除失敗: {channel.name}")
            except Exception as e:
                fail_count += 1
                logger.error(f"ミュート解除エラー ({channel.name}): {e}")

        return success_count, fail_count

    async def _send_log(self, guild_id: int, embed: discord.Embed):
        """ログチャンネルにメッセージを送信"""
        log_channel_id = self.log_channel_ids.get(guild_id)
        if not log_channel_id:
            return

        channel = self.bot.get_channel(log_channel_id)
        if channel:
            try:
                await channel.send(embed=embed)
            except Exception as e:
                logger.error(f"ログ送信エラー: {e}")

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        """新規チャンネル作成時に自動でミュート権限を適用"""
        if not isinstance(channel, (discord.TextChannel, discord.VoiceChannel, discord.ForumChannel, discord.StageChannel)):
            return

        guild_id = channel.guild.id
        guild_muted = self.muted_users.get(guild_id, {})

        if not guild_muted:
            return

        for user_id, excluded_channels in guild_muted.items():
            # 除外チャンネルではない場合のみ適用
            if channel.id not in excluded_channels:
                try:
                    member = channel.guild.get_member(user_id)
                    target = member if member else discord.Object(id=user_id)

                    overwrite = discord.PermissionOverwrite(
                        send_messages=False,
                        send_messages_in_threads=False,
                        create_public_threads=False,
                        create_private_threads=False,
                        add_reactions=False
                    )
                    await channel.set_permissions(target, overwrite=overwrite, reason="Channel Mute System - Auto apply on new channel")
                    logger.info(f"新規チャンネル {channel.name} にミュート権限を自動適用: User ID {user_id}")

                except Exception as e:
                    logger.error(f"新規チャンネルへのミュート自動適用エラー: {e}")

    # ==================== コマンドグループ ====================

    @commands.hybrid_group(name="cmute", aliases=["channelmute"])
    @commands.has_permissions(manage_channels=True)
    async def cmute_group(self, ctx: commands.Context):
        """チャンネルミュートシステム管理コマンドグループ"""
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(
                title="🔇 チャンネルミュートシステム",
                description="チャンネル権限を使って特定ユーザーの発言を禁止します。",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="`cmute add <ユーザー> [理由] [除外チャンネル...]`",
                value="ユーザーをミュート（除外チャンネルも同時指定可）",
                inline=False
            )
            embed.add_field(
                name="`cmute remove <ユーザー>`",
                value="ユーザーのミュートを解除",
                inline=False
            )
            embed.add_field(
                name="`cmute exclude <ユーザー> <チャンネル>`",
                value="ミュートユーザーに除外チャンネルを追加",
                inline=False
            )
            embed.add_field(
                name="`cmute unexclude <ユーザー> <チャンネル>`",
                value="除外チャンネルを削除",
                inline=False
            )
            embed.add_field(
                name="`cmute list`",
                value="ミュート中のユーザー一覧を表示",
                inline=False
            )
            embed.add_field(
                name="`cmute status <ユーザー>`",
                value="ユーザーの詳細を表示",
                inline=False
            )
            embed.add_field(
                name="`cmute logchannel <チャンネル>`",
                value="ログ送信先チャンネルを設定",
                inline=False
            )
            embed.add_field(
                name="`cmute refresh <ユーザー>`",
                value="ユーザーの権限を再適用（同期ズレ修正）",
                inline=False
            )
            await ctx.send(embed=embed)

    @cmute_group.command(name="add")
    @commands.has_permissions(manage_channels=True)
    async def add_muted_user(
        self,
        ctx: commands.Context,
        user: discord.User,
        reason: str = "指定なし",
        excluded_channels: commands.Greedy[discord.TextChannel] = None
    ):
        """ユーザーをチャンネルミュートに追加

        Parameters
        ----------
        user : discord.User
            ミュート対象のユーザー
        reason : str
            ミュートの理由
        excluded_channels : list[discord.TextChannel]
            除外するチャンネル（複数指定可）
        """
        await ctx.defer()

        guild_id = ctx.guild.id
        excluded_ids = set()

        if excluded_channels:
            excluded_ids = {ch.id for ch in excluded_channels}

        # 既にミュート中かチェック
        if guild_id in self.muted_users and user.id in self.muted_users[guild_id]:
            await ctx.send(f"❌ {user.mention} は既にミュート中です。除外チャンネルを追加する場合は `cmute exclude` を使用してください。")
            return

        try:
            # データベースに追加
            async with db.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO channel_muted_users (guild_id, user_id, added_by, reason)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (guild_id, user_id) DO NOTHING
                """, guild_id, user.id, ctx.author.id, reason)

                # 除外チャンネルを追加
                for channel_id in excluded_ids:
                    await conn.execute("""
                        INSERT INTO channel_mute_exclusions (guild_id, user_id, channel_id, added_by)
                        VALUES ($1, $2, $3, $4)
                        ON CONFLICT (guild_id, user_id, channel_id) DO NOTHING
                    """, guild_id, user.id, channel_id, ctx.author.id)

                # ログを記録
                await conn.execute("""
                    INSERT INTO channel_mute_logs (guild_id, user_id, action, performed_by, details)
                    VALUES ($1, $2, $3, $4, $5)
                """, guild_id, user.id, "MUTE", ctx.author.id, f"理由: {reason}, 除外: {len(excluded_ids)}チャンネル")

            # キャッシュを更新
            if guild_id not in self.muted_users:
                self.muted_users[guild_id] = {}
            self.muted_users[guild_id][user.id] = excluded_ids

            # 権限を適用
            success, fail = await self._apply_mute_to_all_channels(
                ctx.guild,
                user.id,
                excluded_ids,
                f"Channel Mute by {ctx.author} - {reason}"
            )

            # 結果を表示
            embed = discord.Embed(
                title="🔇 チャンネルミュート適用完了",
                color=discord.Color.orange(),
                timestamp=datetime.now()
            )
            embed.add_field(name="対象ユーザー", value=f"{user.mention} ({user})", inline=False)
            embed.add_field(name="理由", value=reason, inline=False)
            embed.add_field(name="適用結果", value=f"✅ 成功: {success}チャンネル\n❌ 失敗: {fail}チャンネル", inline=False)

            if excluded_channels:
                excluded_text = "\n".join([f"• {ch.mention}" for ch in excluded_channels])
                embed.add_field(name="除外チャンネル", value=excluded_text, inline=False)

            embed.set_footer(text=f"実行者: {ctx.author}")

            await ctx.send(embed=embed)

            # ログチャンネルにも送信
            await self._send_log(guild_id, embed)

            logger.info(f"チャンネルミュート追加: {user} (ID: {user.id}) in guild {guild_id}")

        except Exception as e:
            await ctx.send(f"❌ エラーが発生しました: {e}")
            logger.error(f"チャンネルミュート追加エラー: {e}")

    @cmute_group.command(name="remove")
    @commands.has_permissions(manage_channels=True)
    async def remove_muted_user(self, ctx: commands.Context, user: discord.User):
        """ユーザーのチャンネルミュートを解除"""
        await ctx.defer()

        guild_id = ctx.guild.id

        # ミュート中かチェック
        if guild_id not in self.muted_users or user.id not in self.muted_users[guild_id]:
            await ctx.send(f"❌ {user.mention} はミュートされていません。")
            return

        try:
            # データベースから削除
            async with db.pool.acquire() as conn:
                await conn.execute("""
                    DELETE FROM channel_muted_users
                    WHERE guild_id = $1 AND user_id = $2
                """, guild_id, user.id)

                await conn.execute("""
                    DELETE FROM channel_mute_exclusions
                    WHERE guild_id = $1 AND user_id = $2
                """, guild_id, user.id)

                # ログを記録
                await conn.execute("""
                    INSERT INTO channel_mute_logs (guild_id, user_id, action, performed_by, details)
                    VALUES ($1, $2, $3, $4, $5)
                """, guild_id, user.id, "UNMUTE", ctx.author.id, "ミュート解除")

            # キャッシュを更新
            del self.muted_users[guild_id][user.id]

            # 権限を解除
            success, fail = await self._remove_mute_from_all_channels(
                ctx.guild,
                user.id,
                f"Channel Unmute by {ctx.author}"
            )

            # 結果を表示
            embed = discord.Embed(
                title="🔊 チャンネルミュート解除完了",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            embed.add_field(name="対象ユーザー", value=f"{user.mention} ({user})", inline=False)
            embed.add_field(name="解除結果", value=f"✅ 成功: {success}チャンネル\n❌ 失敗: {fail}チャンネル", inline=False)
            embed.set_footer(text=f"実行者: {ctx.author}")

            await ctx.send(embed=embed)
            await self._send_log(guild_id, embed)

            logger.info(f"チャンネルミュート解除: {user} (ID: {user.id}) in guild {guild_id}")

        except Exception as e:
            await ctx.send(f"❌ エラーが発生しました: {e}")
            logger.error(f"チャンネルミュート解除エラー: {e}")

    @cmute_group.command(name="exclude")
    @commands.has_permissions(manage_channels=True)
    async def add_exclusion(self, ctx: commands.Context, user: discord.User, channel: discord.TextChannel):
        """ミュートユーザーに除外チャンネルを追加"""
        guild_id = ctx.guild.id

        # ミュート中かチェック
        if guild_id not in self.muted_users or user.id not in self.muted_users[guild_id]:
            await ctx.send(f"❌ {user.mention} はミュートされていません。")
            return

        excluded = self.muted_users[guild_id][user.id]
        if channel.id in excluded:
            await ctx.send(f"❌ {channel.mention} は既に除外チャンネルです。")
            return

        try:
            # データベースに追加
            async with db.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO channel_mute_exclusions (guild_id, user_id, channel_id, added_by)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (guild_id, user_id, channel_id) DO NOTHING
                """, guild_id, user.id, channel.id, ctx.author.id)

            # キャッシュを更新
            self.muted_users[guild_id][user.id].add(channel.id)

            # このチャンネルの権限を解除
            member = ctx.guild.get_member(user.id)
            target = member if member else discord.Object(id=user.id)

            overwrite = channel.overwrites_for(target)
            overwrite.send_messages = None
            overwrite.send_messages_in_threads = None
            overwrite.create_public_threads = None
            overwrite.create_private_threads = None
            overwrite.add_reactions = None

            if overwrite.is_empty():
                await channel.set_permissions(target, overwrite=None, reason=f"Exclusion added by {ctx.author}")
            else:
                await channel.set_permissions(target, overwrite=overwrite, reason=f"Exclusion added by {ctx.author}")

            await ctx.send(f"✅ {user.mention} の除外チャンネルに {channel.mention} を追加しました。このチャンネルでは発言できます。")
            logger.info(f"除外チャンネル追加: {channel.name} for user {user.id} in guild {guild_id}")

        except Exception as e:
            await ctx.send(f"❌ エラーが発生しました: {e}")
            logger.error(f"除外チャンネル追加エラー: {e}")

    @cmute_group.command(name="unexclude")
    @commands.has_permissions(manage_channels=True)
    async def remove_exclusion(self, ctx: commands.Context, user: discord.User, channel: discord.TextChannel):
        """除外チャンネルを削除（ミュートを適用）"""
        guild_id = ctx.guild.id

        # ミュート中かチェック
        if guild_id not in self.muted_users or user.id not in self.muted_users[guild_id]:
            await ctx.send(f"❌ {user.mention} はミュートされていません。")
            return

        excluded = self.muted_users[guild_id][user.id]
        if channel.id not in excluded:
            await ctx.send(f"❌ {channel.mention} は除外チャンネルではありません。")
            return

        try:
            # データベースから削除
            async with db.pool.acquire() as conn:
                await conn.execute("""
                    DELETE FROM channel_mute_exclusions
                    WHERE guild_id = $1 AND user_id = $2 AND channel_id = $3
                """, guild_id, user.id, channel.id)

            # キャッシュを更新
            self.muted_users[guild_id][user.id].discard(channel.id)

            # このチャンネルにミュート権限を適用
            member = ctx.guild.get_member(user.id)
            target = member if member else discord.Object(id=user.id)

            overwrite = channel.overwrites_for(target)
            overwrite.send_messages = False
            overwrite.send_messages_in_threads = False
            overwrite.create_public_threads = False
            overwrite.create_private_threads = False
            overwrite.add_reactions = False

            await channel.set_permissions(target, overwrite=overwrite, reason=f"Exclusion removed by {ctx.author}")

            await ctx.send(f"✅ {user.mention} の除外チャンネルから {channel.mention} を削除しました。このチャンネルでは発言できなくなりました。")
            logger.info(f"除外チャンネル削除: {channel.name} for user {user.id} in guild {guild_id}")

        except Exception as e:
            await ctx.send(f"❌ エラーが発生しました: {e}")
            logger.error(f"除外チャンネル削除エラー: {e}")

    @cmute_group.command(name="list")
    @commands.has_permissions(manage_channels=True)
    async def list_muted_users(self, ctx: commands.Context):
        """ミュート中のユーザー一覧を表示"""
        guild_id = ctx.guild.id
        guild_muted = self.muted_users.get(guild_id, {})

        if not guild_muted:
            await ctx.send("📝 現在ミュート中のユーザーはいません。")
            return

        embed = discord.Embed(
            title="🔇 チャンネルミュート中のユーザー一覧",
            color=discord.Color.blue()
        )

        for user_id, excluded_channels in guild_muted.items():
            try:
                user = await self.bot.fetch_user(user_id)
                user_text = f"{user.mention} ({user})"
            except discord.NotFound:
                user_text = f"不明なユーザー (ID: `{user_id}`)"

            excluded_count = len(excluded_channels)
            value = f"除外チャンネル: {excluded_count}個"
            embed.add_field(name=user_text, value=value, inline=False)

        await ctx.send(embed=embed)

    @cmute_group.command(name="status")
    @commands.has_permissions(manage_channels=True)
    async def show_user_status(self, ctx: commands.Context, user: discord.User):
        """ユーザーの詳細を表示"""
        guild_id = ctx.guild.id

        # ミュート情報を取得
        async with db.pool.acquire() as conn:
            user_data = await conn.fetchrow("""
                SELECT added_by, added_at, reason
                FROM channel_muted_users
                WHERE guild_id = $1 AND user_id = $2
            """, guild_id, user.id)

        if not user_data:
            await ctx.send(f"❌ {user.mention} はミュートされていません。")
            return

        # 除外チャンネルを取得
        excluded_ids = self.muted_users.get(guild_id, {}).get(user.id, set())

        embed = discord.Embed(
            title=f"🔇 ミュートステータス: {user.display_name}",
            color=discord.Color.orange(),
            timestamp=user_data['added_at']
        )

        # 基本情報
        try:
            added_by = await self.bot.fetch_user(user_data['added_by'])
            added_by_name = f"{added_by.mention}"
        except Exception:
            added_by_name = f"ID: {user_data['added_by']}"

        embed.add_field(name="ユーザー", value=f"{user.mention} ({user})", inline=False)
        embed.add_field(name="追加者", value=added_by_name, inline=True)
        embed.add_field(name="追加日時", value=user_data['added_at'].strftime('%Y-%m-%d %H:%M'), inline=True)
        embed.add_field(name="理由", value=user_data['reason'] or "指定なし", inline=False)

        # 除外チャンネル
        if excluded_ids:
            excluded_list = []
            for ch_id in excluded_ids:
                channel = self.bot.get_channel(ch_id)
                if channel:
                    excluded_list.append(f"• {channel.mention}")
                else:
                    excluded_list.append(f"• 不明 (ID: `{ch_id}`)")
            embed.add_field(name=f"除外チャンネル ({len(excluded_ids)}個)", value="\n".join(excluded_list[:10]), inline=False)
            if len(excluded_list) > 10:
                embed.add_field(name="", value=f"...他 {len(excluded_list) - 10}個", inline=False)
        else:
            embed.add_field(name="除外チャンネル", value="なし", inline=False)

        embed.set_footer(text=f"ユーザーID: {user.id}")

        await ctx.send(embed=embed)

    @cmute_group.command(name="logchannel")
    @commands.has_permissions(manage_channels=True)
    async def set_log_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        """ログ送信先チャンネルを設定"""
        try:
            guild_id = ctx.guild.id

            async with db.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO channel_mute_config (guild_id, log_channel_id, updated_by)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (guild_id)
                    DO UPDATE SET log_channel_id = $2, updated_by = $3, updated_at = CURRENT_TIMESTAMP
                """, guild_id, channel.id, ctx.author.id)

            self.log_channel_ids[guild_id] = channel.id

            await ctx.send(f"✅ ログチャンネルを {channel.mention} に設定しました。")
            logger.info(f"ログチャンネル設定: {channel.name} (ID: {channel.id}) in guild {guild_id}")

        except Exception as e:
            await ctx.send(f"❌ エラーが発生しました: {e}")
            logger.error(f"ログチャンネル設定エラー: {e}")

    @cmute_group.command(name="refresh")
    @commands.has_permissions(manage_channels=True)
    async def refresh_permissions(self, ctx: commands.Context, user: discord.User):
        """ユーザーの権限を再適用（同期ズレ修正）"""
        await ctx.defer()

        guild_id = ctx.guild.id

        if guild_id not in self.muted_users or user.id not in self.muted_users[guild_id]:
            await ctx.send(f"❌ {user.mention} はミュートされていません。")
            return

        excluded_channels = self.muted_users[guild_id][user.id]

        success, fail = await self._apply_mute_to_all_channels(
            ctx.guild,
            user.id,
            excluded_channels,
            f"Permission refresh by {ctx.author}"
        )

        await ctx.send(f"✅ {user.mention} の権限を再適用しました。\n成功: {success}チャンネル, 失敗: {fail}チャンネル")


async def setup(bot: commands.Bot):
    """Cog setup関数"""
    await bot.add_cog(ChannelMuteSystem(bot))
