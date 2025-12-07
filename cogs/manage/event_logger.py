"""
イベントログシステム

サーバー内で発生する様々なイベントをフォーラムチャンネルに記録します。
各イベントタイプごとにポスト（スレッド）を作成し、ログを投稿します。
"""

from datetime import datetime
from enum import IntFlag, auto
from typing import Optional

import discord
import pytz
from discord import app_commands
from discord.ext import commands

from utils.database import execute_query
from utils.logging import setup_logging

logger = setup_logging()

# 日本時間のタイムゾーン
JST = pytz.timezone('Asia/Tokyo')


class LogEventType(IntFlag):
    """ログイベントタイプ（ビットフラグ）"""
    NONE = 0
    MEMBER_JOIN = auto()          # メンバー参加
    MEMBER_LEAVE = auto()         # メンバー退出
    MEMBER_BAN = auto()           # BAN
    MEMBER_UNBAN = auto()         # BAN解除
    MEMBER_KICK = auto()          # キック
    MEMBER_TIMEOUT = auto()       # タイムアウト
    MEMBER_ROLE_ADD = auto()      # ロール付与
    MEMBER_ROLE_REMOVE = auto()   # ロール削除
    MEMBER_NICK_CHANGE = auto()   # ニックネーム変更
    MESSAGE_DELETE = auto()       # メッセージ削除
    MESSAGE_BULK_DELETE = auto()  # メッセージ一括削除
    MESSAGE_EDIT = auto()         # メッセージ編集
    VOICE_JOIN = auto()           # VC参加
    VOICE_LEAVE = auto()          # VC退出
    VOICE_MOVE = auto()           # VC移動
    CHANNEL_CREATE = auto()       # チャンネル作成
    CHANNEL_DELETE = auto()       # チャンネル削除
    CHANNEL_UPDATE = auto()       # チャンネル更新
    ROLE_CREATE = auto()          # ロール作成
    ROLE_DELETE = auto()          # ロール削除
    ROLE_UPDATE = auto()          # ロール更新

    # プリセット
    ALL = (
        MEMBER_JOIN | MEMBER_LEAVE | MEMBER_BAN | MEMBER_UNBAN | MEMBER_KICK |
        MEMBER_TIMEOUT | MEMBER_ROLE_ADD | MEMBER_ROLE_REMOVE | MEMBER_NICK_CHANGE |
        MESSAGE_DELETE | MESSAGE_BULK_DELETE | MESSAGE_EDIT |
        VOICE_JOIN | VOICE_LEAVE | VOICE_MOVE |
        CHANNEL_CREATE | CHANNEL_DELETE | CHANNEL_UPDATE |
        ROLE_CREATE | ROLE_DELETE | ROLE_UPDATE
    )
    MODERATION = MEMBER_BAN | MEMBER_UNBAN | MEMBER_KICK | MEMBER_TIMEOUT | MESSAGE_DELETE | MESSAGE_BULK_DELETE
    MEMBERS = MEMBER_JOIN | MEMBER_LEAVE | MEMBER_ROLE_ADD | MEMBER_ROLE_REMOVE | MEMBER_NICK_CHANGE
    MESSAGES = MESSAGE_DELETE | MESSAGE_BULK_DELETE | MESSAGE_EDIT
    VOICE = VOICE_JOIN | VOICE_LEAVE | VOICE_MOVE
    SERVER = CHANNEL_CREATE | CHANNEL_DELETE | CHANNEL_UPDATE | ROLE_CREATE | ROLE_DELETE | ROLE_UPDATE


# イベントタイプのカテゴリ名
EVENT_CATEGORY = {
    LogEventType.MEMBER_JOIN: "member",
    LogEventType.MEMBER_LEAVE: "member",
    LogEventType.MEMBER_BAN: "moderation",
    LogEventType.MEMBER_UNBAN: "moderation",
    LogEventType.MEMBER_KICK: "moderation",
    LogEventType.MEMBER_TIMEOUT: "moderation",
    LogEventType.MEMBER_ROLE_ADD: "member",
    LogEventType.MEMBER_ROLE_REMOVE: "member",
    LogEventType.MEMBER_NICK_CHANGE: "member",
    LogEventType.MESSAGE_DELETE: "message",
    LogEventType.MESSAGE_BULK_DELETE: "message",
    LogEventType.MESSAGE_EDIT: "message",
    LogEventType.VOICE_JOIN: "voice",
    LogEventType.VOICE_LEAVE: "voice",
    LogEventType.VOICE_MOVE: "voice",
    LogEventType.CHANNEL_CREATE: "server",
    LogEventType.CHANNEL_DELETE: "server",
    LogEventType.CHANNEL_UPDATE: "server",
    LogEventType.ROLE_CREATE: "server",
    LogEventType.ROLE_DELETE: "server",
    LogEventType.ROLE_UPDATE: "server",
}

# イベントタイプの名前マッピング
EVENT_NAMES = {
    LogEventType.MEMBER_JOIN: "メンバー参加",
    LogEventType.MEMBER_LEAVE: "メンバー退出",
    LogEventType.MEMBER_BAN: "BAN",
    LogEventType.MEMBER_UNBAN: "BAN解除",
    LogEventType.MEMBER_KICK: "キック",
    LogEventType.MEMBER_TIMEOUT: "タイムアウト",
    LogEventType.MEMBER_ROLE_ADD: "ロール付与",
    LogEventType.MEMBER_ROLE_REMOVE: "ロール削除",
    LogEventType.MEMBER_NICK_CHANGE: "ニックネーム変更",
    LogEventType.MESSAGE_DELETE: "メッセージ削除",
    LogEventType.MESSAGE_BULK_DELETE: "一括削除",
    LogEventType.MESSAGE_EDIT: "メッセージ編集",
    LogEventType.VOICE_JOIN: "VC参加",
    LogEventType.VOICE_LEAVE: "VC退出",
    LogEventType.VOICE_MOVE: "VC移動",
    LogEventType.CHANNEL_CREATE: "チャンネル作成",
    LogEventType.CHANNEL_DELETE: "チャンネル削除",
    LogEventType.CHANNEL_UPDATE: "チャンネル更新",
    LogEventType.ROLE_CREATE: "ロール作成",
    LogEventType.ROLE_DELETE: "ロール削除",
    LogEventType.ROLE_UPDATE: "ロール更新",
}

# イベント絵文字マッピング
EVENT_EMOJI = {
    LogEventType.MEMBER_JOIN: "📥",
    LogEventType.MEMBER_LEAVE: "📤",
    LogEventType.MEMBER_BAN: "🔨",
    LogEventType.MEMBER_UNBAN: "✨",
    LogEventType.MEMBER_KICK: "🚪",
    LogEventType.MEMBER_TIMEOUT: "🔇",
    LogEventType.MEMBER_ROLE_ADD: "📗",
    LogEventType.MEMBER_ROLE_REMOVE: "📕",
    LogEventType.MEMBER_NICK_CHANGE: "✏️",
    LogEventType.MESSAGE_DELETE: "🗑️",
    LogEventType.MESSAGE_BULK_DELETE: "🗑️",
    LogEventType.MESSAGE_EDIT: "📝",
    LogEventType.VOICE_JOIN: "🎙️",
    LogEventType.VOICE_LEAVE: "🔇",
    LogEventType.VOICE_MOVE: "📞",
    LogEventType.CHANNEL_CREATE: "📄",
    LogEventType.CHANNEL_DELETE: "🗑️",
    LogEventType.CHANNEL_UPDATE: "📎",
    LogEventType.ROLE_CREATE: "📖",
    LogEventType.ROLE_DELETE: "🗑️",
    LogEventType.ROLE_UPDATE: "📚",
}

# フォーラムポスト設定
FORUM_POSTS = {
    "member": {"name": "📋 メンバーログ", "emoji": "👥"},
    "moderation": {"name": "🔨 モデレーションログ", "emoji": "🛡️"},
    "message": {"name": "💬 メッセージログ", "emoji": "📝"},
    "voice": {"name": "🎙️ ボイスログ", "emoji": "🔊"},
    "server": {"name": "⚙️ サーバーログ", "emoji": "🏠"},
}


class EventLogger(commands.Cog):
    """イベントログ機能を提供するCog"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._settings: dict[int, dict] = {}  # guild_id -> settings
        self._thread_cache: dict[int, dict[str, int]] = {}  # guild_id -> {category: thread_id}

    async def cog_load(self):
        """Cogロード時にテーブルを作成"""
        await self._setup_table()
        await self._load_settings()

    async def _setup_table(self):
        """イベントログ設定テーブルを作成・マイグレーション"""
        # 既存テーブルがあるか確認
        table_exists = await execute_query(
            '''
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'event_log_settings'
            )
            ''',
            fetch_type='row'
        )

        if table_exists and table_exists['exists']:
            # 既存テーブルのカラムを確認
            columns = await execute_query(
                '''
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'event_log_settings'
                ''',
                fetch_type='all'
            )
            column_names = [c['column_name'] for c in columns]

            # 古いスキーマからの移行（channel_id → forum_channel_id）
            if 'channel_id' in column_names and 'forum_channel_id' not in column_names:
                await execute_query(
                    'ALTER TABLE event_log_settings RENAME COLUMN channel_id TO forum_channel_id',
                    fetch_type='status'
                )
                logger.info("カラム名を channel_id → forum_channel_id に変更しました")

            # thread_ids カラムがなければ追加
            if 'thread_ids' not in column_names:
                await execute_query(
                    "ALTER TABLE event_log_settings ADD COLUMN thread_ids JSONB DEFAULT '{}'",
                    fetch_type='status'
                )
                logger.info("thread_ids カラムを追加しました")

            # ignore_channels カラムがあれば削除（不要）
            if 'ignore_channels' in column_names:
                await execute_query(
                    'ALTER TABLE event_log_settings DROP COLUMN ignore_channels',
                    fetch_type='status'
                )
                logger.info("ignore_channels カラムを削除しました")
        else:
            # 新規作成
            await execute_query(
                '''
                CREATE TABLE IF NOT EXISTS event_log_settings (
                    guild_id BIGINT PRIMARY KEY,
                    forum_channel_id BIGINT NOT NULL,
                    events BIGINT NOT NULL DEFAULT 0,
                    ignore_bots BOOLEAN DEFAULT TRUE,
                    thread_ids JSONB DEFAULT '{}',
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
                ''',
                fetch_type='status'
            )

        logger.info("イベントログ設定テーブルを確認・作成しました")

    async def _load_settings(self):
        """設定をメモリにロード"""
        settings = await execute_query(
            "SELECT guild_id, forum_channel_id, events, ignore_bots, thread_ids FROM event_log_settings",
            fetch_type='all'
        )
        for setting in settings:
            self._settings[setting['guild_id']] = {
                'forum_channel_id': setting['forum_channel_id'],
                'events': LogEventType(setting['events']),
                'ignore_bots': setting['ignore_bots'],
            }
            self._thread_cache[setting['guild_id']] = setting['thread_ids'] or {}
        logger.info(f"イベントログ設定をロード: {len(self._settings)} サーバー")

    def _should_log(self, guild_id: int, event_type: LogEventType) -> bool:
        """イベントをログすべきかチェック"""
        if guild_id not in self._settings:
            return False
        return bool(self._settings[guild_id]['events'] & event_type)

    async def _get_or_create_thread(
        self,
        guild: discord.Guild,
        category: str
    ) -> Optional[discord.Thread]:
        """カテゴリ用のスレッドを取得または作成"""
        if guild.id not in self._settings:
            return None

        forum_channel_id = self._settings[guild.id]['forum_channel_id']
        forum_channel = self.bot.get_channel(forum_channel_id)

        if not forum_channel or not isinstance(forum_channel, discord.ForumChannel):
            return None

        # キャッシュからスレッドIDを取得
        if guild.id in self._thread_cache and category in self._thread_cache[guild.id]:
            thread_id = self._thread_cache[guild.id][category]
            thread = guild.get_thread(thread_id)
            if thread and not thread.archived:
                return thread
            # アーカイブされている場合はアンアーカイブ
            if thread:
                try:
                    await thread.edit(archived=False)
                    return thread
                except discord.HTTPException:
                    pass

        # 新しいスレッドを作成
        try:
            post_config = FORUM_POSTS.get(category, {"name": f"📋 {category}ログ", "emoji": "📋"})

            thread, _ = await forum_channel.create_thread(
                name=post_config["name"],
                content=f"{post_config['emoji']} **{post_config['name']}**\n\nこのスレッドには{category}関連のイベントログが記録されます。"
            )

            # キャッシュとDBを更新
            if guild.id not in self._thread_cache:
                self._thread_cache[guild.id] = {}
            self._thread_cache[guild.id][category] = thread.id

            await execute_query(
                '''
                UPDATE event_log_settings
                SET thread_ids = thread_ids || $1::jsonb
                WHERE guild_id = $2
                ''',
                {category: thread.id},
                guild.id,
                fetch_type='status'
            )

            return thread

        except discord.Forbidden:
            logger.warning(f"フォーラムへのスレッド作成権限がありません: {guild.id}")
        except Exception as e:
            logger.error(f"スレッド作成エラー: {e}")

        return None

    async def _send_log(
        self,
        guild: discord.Guild,
        event_type: LogEventType,
        embed: discord.Embed
    ):
        """ログを対応するスレッドに送信"""
        if not self._should_log(guild.id, event_type):
            return

        category = EVENT_CATEGORY.get(event_type, "server")
        thread = await self._get_or_create_thread(guild, category)

        if not thread:
            return

        try:
            emoji = EVENT_EMOJI.get(event_type, "📋")
            embed.set_footer(text=f"{emoji} {EVENT_NAMES.get(event_type, 'イベント')}")
            embed.timestamp = datetime.now(JST)

            await thread.send(embed=embed)
        except discord.Forbidden:
            logger.warning(f"スレッドへの送信権限がありません: {guild.id}")
        except Exception as e:
            logger.error(f"ログ送信エラー: {e}")

    # === イベントリスナー ===

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """メンバー参加"""
        if not self._should_log(member.guild.id, LogEventType.MEMBER_JOIN):
            return

        embed = discord.Embed(
            title="メンバーが参加しました",
            color=discord.Color.green()
        )
        embed.set_author(name=str(member), icon_url=member.display_avatar.url)
        embed.add_field(name="ユーザー", value=member.mention, inline=True)
        embed.add_field(name="ID", value=str(member.id), inline=True)
        embed.add_field(
            name="アカウント作成日",
            value=f"<t:{int(member.created_at.timestamp())}:R>",
            inline=True
        )

        await self._send_log(member.guild, LogEventType.MEMBER_JOIN, embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """メンバー退出"""
        if not self._should_log(member.guild.id, LogEventType.MEMBER_LEAVE):
            return

        embed = discord.Embed(
            title="メンバーが退出しました",
            color=discord.Color.orange()
        )
        embed.set_author(name=str(member), icon_url=member.display_avatar.url)
        embed.add_field(name="ユーザー", value=member.mention, inline=True)
        embed.add_field(name="ID", value=str(member.id), inline=True)
        if member.joined_at:
            embed.add_field(
                name="参加期間",
                value=f"<t:{int(member.joined_at.timestamp())}:R>から",
                inline=True
            )

        await self._send_log(member.guild, LogEventType.MEMBER_LEAVE, embed)

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        """BAN"""
        if not self._should_log(guild.id, LogEventType.MEMBER_BAN):
            return

        embed = discord.Embed(
            title="ユーザーがBANされました",
            color=discord.Color.red()
        )
        embed.set_author(name=str(user), icon_url=user.display_avatar.url)
        embed.add_field(name="ユーザー", value=user.mention, inline=True)
        embed.add_field(name="ID", value=str(user.id), inline=True)

        try:
            async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.ban):
                if entry.target.id == user.id:
                    embed.add_field(name="実行者", value=entry.user.mention, inline=True)
                    if entry.reason:
                        embed.add_field(name="理由", value=entry.reason, inline=False)
                    break
        except discord.Forbidden:
            pass

        await self._send_log(guild, LogEventType.MEMBER_BAN, embed)

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User):
        """BAN解除"""
        if not self._should_log(guild.id, LogEventType.MEMBER_UNBAN):
            return

        embed = discord.Embed(
            title="ユーザーのBANが解除されました",
            color=discord.Color.green()
        )
        embed.set_author(name=str(user), icon_url=user.display_avatar.url)
        embed.add_field(name="ユーザー", value=user.mention, inline=True)
        embed.add_field(name="ID", value=str(user.id), inline=True)

        await self._send_log(guild, LogEventType.MEMBER_UNBAN, embed)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """メンバー更新"""
        guild = after.guild

        # ニックネーム変更
        if before.nick != after.nick and self._should_log(guild.id, LogEventType.MEMBER_NICK_CHANGE):
            embed = discord.Embed(
                title="ニックネームが変更されました",
                color=discord.Color.blue()
            )
            embed.set_author(name=str(after), icon_url=after.display_avatar.url)
            embed.add_field(name="ユーザー", value=after.mention, inline=True)
            embed.add_field(name="変更前", value=before.nick or "(なし)", inline=True)
            embed.add_field(name="変更後", value=after.nick or "(なし)", inline=True)
            await self._send_log(guild, LogEventType.MEMBER_NICK_CHANGE, embed)

        # ロール追加
        added_roles = set(after.roles) - set(before.roles)
        if added_roles and self._should_log(guild.id, LogEventType.MEMBER_ROLE_ADD):
            embed = discord.Embed(
                title="ロールが付与されました",
                color=discord.Color.green()
            )
            embed.set_author(name=str(after), icon_url=after.display_avatar.url)
            embed.add_field(name="ユーザー", value=after.mention, inline=True)
            embed.add_field(
                name="追加されたロール",
                value=", ".join(r.mention for r in added_roles),
                inline=False
            )
            await self._send_log(guild, LogEventType.MEMBER_ROLE_ADD, embed)

        # ロール削除
        removed_roles = set(before.roles) - set(after.roles)
        if removed_roles and self._should_log(guild.id, LogEventType.MEMBER_ROLE_REMOVE):
            embed = discord.Embed(
                title="ロールが削除されました",
                color=discord.Color.orange()
            )
            embed.set_author(name=str(after), icon_url=after.display_avatar.url)
            embed.add_field(name="ユーザー", value=after.mention, inline=True)
            embed.add_field(
                name="削除されたロール",
                value=", ".join(r.mention for r in removed_roles),
                inline=False
            )
            await self._send_log(guild, LogEventType.MEMBER_ROLE_REMOVE, embed)

        # タイムアウト
        if before.timed_out_until != after.timed_out_until and self._should_log(guild.id, LogEventType.MEMBER_TIMEOUT):
            if after.timed_out_until:
                embed = discord.Embed(
                    title="タイムアウトが適用されました",
                    color=discord.Color.red()
                )
                embed.add_field(
                    name="解除予定",
                    value=f"<t:{int(after.timed_out_until.timestamp())}:F>",
                    inline=True
                )
            else:
                embed = discord.Embed(
                    title="タイムアウトが解除されました",
                    color=discord.Color.green()
                )
            embed.set_author(name=str(after), icon_url=after.display_avatar.url)
            embed.add_field(name="ユーザー", value=after.mention, inline=True)
            await self._send_log(guild, LogEventType.MEMBER_TIMEOUT, embed)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        """メッセージ削除"""
        if not message.guild:
            return
        if not self._should_log(message.guild.id, LogEventType.MESSAGE_DELETE):
            return

        if self._settings.get(message.guild.id, {}).get('ignore_bots', True) and message.author.bot:
            return

        embed = discord.Embed(
            title="メッセージが削除されました",
            color=discord.Color.red()
        )
        embed.set_author(name=str(message.author), icon_url=message.author.display_avatar.url)
        embed.add_field(name="送信者", value=message.author.mention, inline=True)
        embed.add_field(name="チャンネル", value=message.channel.mention, inline=True)

        if message.content:
            content = message.content[:1000]
            if len(message.content) > 1000:
                content += "..."
            embed.add_field(name="内容", value=content, inline=False)

        if message.attachments:
            embed.add_field(
                name="添付ファイル",
                value=", ".join(a.filename for a in message.attachments),
                inline=False
            )

        await self._send_log(message.guild, LogEventType.MESSAGE_DELETE, embed)

    @commands.Cog.listener()
    async def on_bulk_message_delete(self, messages: list[discord.Message]):
        """メッセージ一括削除"""
        if not messages:
            return
        guild = messages[0].guild
        if not guild:
            return
        if not self._should_log(guild.id, LogEventType.MESSAGE_BULK_DELETE):
            return

        embed = discord.Embed(
            title="メッセージが一括削除されました",
            color=discord.Color.red()
        )
        embed.add_field(name="チャンネル", value=messages[0].channel.mention, inline=True)
        embed.add_field(name="削除件数", value=f"{len(messages)} 件", inline=True)

        authors = {}
        for msg in messages:
            authors[str(msg.author)] = authors.get(str(msg.author), 0) + 1
        top_authors = sorted(authors.items(), key=lambda x: x[1], reverse=True)[:5]
        if top_authors:
            embed.add_field(
                name="送信者（上位）",
                value="\n".join(f"{name}: {count}件" for name, count in top_authors),
                inline=False
            )

        await self._send_log(guild, LogEventType.MESSAGE_BULK_DELETE, embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        """メッセージ編集"""
        if not after.guild:
            return
        if before.content == after.content:
            return
        if not self._should_log(after.guild.id, LogEventType.MESSAGE_EDIT):
            return

        if self._settings.get(after.guild.id, {}).get('ignore_bots', True) and after.author.bot:
            return

        embed = discord.Embed(
            title="メッセージが編集されました",
            color=discord.Color.blue(),
            url=after.jump_url
        )
        embed.set_author(name=str(after.author), icon_url=after.author.display_avatar.url)
        embed.add_field(name="送信者", value=after.author.mention, inline=True)
        embed.add_field(name="チャンネル", value=after.channel.mention, inline=True)

        before_content = before.content[:500] if before.content else "(なし)"
        after_content = after.content[:500] if after.content else "(なし)"
        embed.add_field(name="変更前", value=before_content, inline=False)
        embed.add_field(name="変更後", value=after_content, inline=False)

        await self._send_log(after.guild, LogEventType.MESSAGE_EDIT, embed)

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState
    ):
        """ボイス状態更新"""
        guild = member.guild

        # VC参加
        if before.channel is None and after.channel is not None:
            if self._should_log(guild.id, LogEventType.VOICE_JOIN):
                embed = discord.Embed(
                    title="VCに参加しました",
                    color=discord.Color.green()
                )
                embed.set_author(name=str(member), icon_url=member.display_avatar.url)
                embed.add_field(name="ユーザー", value=member.mention, inline=True)
                embed.add_field(name="チャンネル", value=after.channel.mention, inline=True)
                await self._send_log(guild, LogEventType.VOICE_JOIN, embed)

        # VC退出
        elif before.channel is not None and after.channel is None:
            if self._should_log(guild.id, LogEventType.VOICE_LEAVE):
                embed = discord.Embed(
                    title="VCから退出しました",
                    color=discord.Color.orange()
                )
                embed.set_author(name=str(member), icon_url=member.display_avatar.url)
                embed.add_field(name="ユーザー", value=member.mention, inline=True)
                embed.add_field(name="チャンネル", value=before.channel.mention, inline=True)
                await self._send_log(guild, LogEventType.VOICE_LEAVE, embed)

        # VC移動
        elif before.channel != after.channel and before.channel and after.channel:
            if self._should_log(guild.id, LogEventType.VOICE_MOVE):
                embed = discord.Embed(
                    title="VCを移動しました",
                    color=discord.Color.blue()
                )
                embed.set_author(name=str(member), icon_url=member.display_avatar.url)
                embed.add_field(name="ユーザー", value=member.mention, inline=True)
                embed.add_field(name="移動前", value=before.channel.mention, inline=True)
                embed.add_field(name="移動後", value=after.channel.mention, inline=True)
                await self._send_log(guild, LogEventType.VOICE_MOVE, embed)

    # === 設定コマンド ===

    eventlog_group = app_commands.Group(
        name="eventlog",
        description="イベントログ設定",
        default_permissions=discord.Permissions(administrator=True)
    )

    @eventlog_group.command(name="setup", description="イベントログ用フォーラムチャンネルを作成して設定します")
    @app_commands.describe(
        category="フォーラムを作成するカテゴリ（省略時: カテゴリなし）",
        preset="ログするイベントのプリセット"
    )
    @app_commands.choices(preset=[
        app_commands.Choice(name="すべて", value="all"),
        app_commands.Choice(name="モデレーション（BAN/キック/削除）", value="moderation"),
        app_commands.Choice(name="メンバー（参加/退出/ロール）", value="members"),
        app_commands.Choice(name="メッセージ（削除/編集）", value="messages"),
        app_commands.Choice(name="ボイス（参加/退出/移動）", value="voice"),
        app_commands.Choice(name="サーバー（チャンネル/ロール変更）", value="server"),
    ])
    async def eventlog_setup(
        self,
        interaction: discord.Interaction,
        category: Optional[discord.CategoryChannel] = None,
        preset: str = "all"
    ):
        """イベントログを設定（フォーラムチャンネルを自動作成）"""
        await interaction.response.defer()

        events = {
            "all": LogEventType.ALL,
            "moderation": LogEventType.MODERATION,
            "members": LogEventType.MEMBERS,
            "messages": LogEventType.MESSAGES,
            "voice": LogEventType.VOICE,
            "server": LogEventType.SERVER,
        }.get(preset, LogEventType.ALL)

        # フォーラムチャンネルを作成
        try:
            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(
                    view_channel=False
                ),
                interaction.guild.me: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    manage_threads=True,
                    create_public_threads=True
                )
            }

            # 管理者ロールにも権限を付与
            for role in interaction.guild.roles:
                if role.permissions.administrator:
                    overwrites[role] = discord.PermissionOverwrite(
                        view_channel=True,
                        send_messages=True
                    )

            forum_channel = await interaction.guild.create_forum(
                name="📋 イベントログ",
                category=category,
                overwrites=overwrites,
                reason="イベントログ機能のセットアップ"
            )

        except discord.Forbidden:
            await interaction.followup.send(
                "❌ フォーラムチャンネルを作成する権限がありません。",
                ephemeral=True
            )
            return
        except Exception as e:
            await interaction.followup.send(
                f"❌ フォーラムチャンネルの作成に失敗しました: {e}",
                ephemeral=True
            )
            return

        # DBに保存
        await execute_query(
            '''
            INSERT INTO event_log_settings (guild_id, forum_channel_id, events, thread_ids)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (guild_id)
            DO UPDATE SET forum_channel_id = $2, events = $3, thread_ids = $4, updated_at = NOW()
            ''',
            interaction.guild.id,
            forum_channel.id,
            int(events),
            {},
            fetch_type='status'
        )

        # メモリに反映
        self._settings[interaction.guild.id] = {
            'forum_channel_id': forum_channel.id,
            'events': events,
            'ignore_bots': True,
        }
        self._thread_cache[interaction.guild.id] = {}

        # 各カテゴリのスレッドを作成
        created_threads = []
        for cat_key, cat_config in FORUM_POSTS.items():
            thread = await self._get_or_create_thread(interaction.guild, cat_key)
            if thread:
                created_threads.append(f"{cat_config['emoji']} {cat_config['name']}")

        preset_names = {
            "all": "すべて",
            "moderation": "モデレーション",
            "members": "メンバー",
            "messages": "メッセージ",
            "voice": "ボイス",
            "server": "サーバー"
        }

        embed = discord.Embed(
            title="✅ イベントログを設定しました",
            color=discord.Color.green()
        )
        embed.add_field(name="フォーラム", value=forum_channel.mention, inline=True)
        embed.add_field(name="プリセット", value=preset_names.get(preset, preset), inline=True)
        embed.add_field(
            name="作成されたスレッド",
            value="\n".join(created_threads) if created_threads else "なし",
            inline=False
        )

        await interaction.followup.send(embed=embed)

    @eventlog_group.command(name="disable", description="イベントログを無効にします")
    async def eventlog_disable(self, interaction: discord.Interaction):
        """イベントログを無効化"""
        await execute_query(
            "DELETE FROM event_log_settings WHERE guild_id = $1",
            interaction.guild.id,
            fetch_type='status'
        )

        if interaction.guild.id in self._settings:
            del self._settings[interaction.guild.id]
        if interaction.guild.id in self._thread_cache:
            del self._thread_cache[interaction.guild.id]

        await interaction.response.send_message(
            "✅ イベントログを無効にしました。\n"
            "フォーラムチャンネルは手動で削除してください。",
            ephemeral=True
        )

    @eventlog_group.command(name="status", description="イベントログの設定状況を表示します")
    async def eventlog_status(self, interaction: discord.Interaction):
        """設定状況を表示"""
        if interaction.guild.id not in self._settings:
            await interaction.response.send_message(
                "❌ イベントログは設定されていません。\n"
                "`/eventlog setup` で設定してください。",
                ephemeral=True
            )
            return

        config = self._settings[interaction.guild.id]
        forum_channel = self.bot.get_channel(config['forum_channel_id'])

        embed = discord.Embed(
            title="📋 イベントログ設定",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="フォーラムチャンネル",
            value=forum_channel.mention if forum_channel else f"(不明: {config['forum_channel_id']})",
            inline=True
        )
        embed.add_field(
            name="BOT無視",
            value="✅ 有効" if config.get('ignore_bots', True) else "❌ 無効",
            inline=True
        )

        # スレッド一覧
        if interaction.guild.id in self._thread_cache:
            threads = []
            for cat, thread_id in self._thread_cache[interaction.guild.id].items():
                thread = interaction.guild.get_thread(thread_id)
                if thread:
                    threads.append(f"• {FORUM_POSTS.get(cat, {}).get('emoji', '📋')} {thread.mention}")
            if threads:
                embed.add_field(
                    name="ログスレッド",
                    value="\n".join(threads),
                    inline=False
                )

        # 有効なイベント
        enabled_events = [
            f"{EVENT_EMOJI.get(e, '📋')} {EVENT_NAMES[e]}"
            for e in LogEventType
            if e in config['events'] and e in EVENT_NAMES
        ]
        if enabled_events:
            embed.add_field(
                name=f"有効なイベント ({len(enabled_events)}件)",
                value="\n".join(enabled_events),
                inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @eventlog_group.command(name="ignore_bots", description="BOTのメッセージをログするか設定します")
    @app_commands.describe(ignore="BOTのメッセージを無視するか")
    async def eventlog_ignore_bots(self, interaction: discord.Interaction, ignore: bool):
        """BOT無視設定"""
        if interaction.guild.id not in self._settings:
            await interaction.response.send_message(
                "❌ イベントログが設定されていません。",
                ephemeral=True
            )
            return

        await execute_query(
            "UPDATE event_log_settings SET ignore_bots = $1 WHERE guild_id = $2",
            ignore,
            interaction.guild.id,
            fetch_type='status'
        )

        self._settings[interaction.guild.id]['ignore_bots'] = ignore

        await interaction.response.send_message(
            f"✅ BOTのメッセージを{'無視する' if ignore else 'ログする'}ように設定しました。",
            ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(EventLogger(bot))
