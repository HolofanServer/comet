"""
地震チャンネルシステム

地震発生時に特定カテゴリーのチャンネルを一時的に公開する機能を提供します。
- オープン: ロール取得ボタンを送信し、24時間後に自動クローズ
- クローズ: 全ユーザーからロールを剥奪し、ボタンを無効化
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional

import discord
import pytz
from discord import app_commands
from discord.ext import commands, tasks

from utils.commands_help import is_guild_app, is_moderator_app
from utils.database import execute_query
from utils.logging import setup_logging

logger = setup_logging()

# 日本時間
JST = pytz.timezone('Asia/Tokyo')

# 地震チャンネル閲覧ロール名
EARTHQUAKE_ROLE_NAME = "地震ch閲覧"


class EarthquakeRoleButton(discord.ui.View):
    """地震チャンネル閲覧ロール取得ボタン"""

    def __init__(self, role_id: int, disabled: bool = False):
        super().__init__(timeout=None)
        self.role_id = role_id

        # ボタンの状態を設定
        self.get_role_button.disabled = disabled
        if disabled:
            self.get_role_button.style = discord.ButtonStyle.secondary
            self.get_role_button.label = "受付終了"

    @discord.ui.button(
        label="🔔 地震チャンネルを見る",
        style=discord.ButtonStyle.primary,
        custom_id="earthquake_role_button"
    )
    async def get_role_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """ロール取得ボタン"""
        role = interaction.guild.get_role(self.role_id)
        if not role:
            await interaction.response.send_message(
                "❌ ロールが見つかりません。管理者にお問い合わせください。",
                ephemeral=True
            )
            return

        if role in interaction.user.roles:
            await interaction.response.send_message(
                "✅ すでに地震チャンネルを閲覧できます。",
                ephemeral=True
            )
            return

        try:
            await interaction.user.add_roles(role, reason="地震チャンネル閲覧リクエスト")
            await interaction.response.send_message(
                "✅ 地震チャンネルが閲覧可能になりました！\n"
                "24時間後に自動的にアクセス権が解除されます。",
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ ロールを付与できませんでした。BOTの権限を確認してください。",
                ephemeral=True
            )


class EarthquakeChannel(commands.Cog):
    """地震チャンネル管理機能"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._settings: dict[int, dict] = {}  # guild_id -> settings
        self._active_sessions: dict[int, dict] = {}  # guild_id -> session info

    async def cog_load(self):
        """Cogロード時の初期化"""
        await self._setup_table()
        await self._load_settings()
        self._register_views()
        self.auto_close_check.start()

    async def cog_unload(self):
        """Cogアンロード時のクリーンアップ"""
        self.auto_close_check.cancel()

    def _register_views(self):
        """永続的なViewを登録"""
        # ダミーのViewを登録（実際のrole_idは後でメッセージから取得）
        self.bot.add_view(EarthquakeRoleButton(0))

    async def _setup_table(self):
        """テーブルを作成"""
        await execute_query(
            '''
            CREATE TABLE IF NOT EXISTS earthquake_channel_settings (
                guild_id BIGINT PRIMARY KEY,
                category_id BIGINT NOT NULL,
                notification_channel_id BIGINT NOT NULL,
                notification_role_id BIGINT NOT NULL,
                earthquake_role_id BIGINT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
            ''',
            fetch_type='status'
        )

        await execute_query(
            '''
            CREATE TABLE IF NOT EXISTS earthquake_channel_sessions (
                id SERIAL PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                message_id BIGINT NOT NULL,
                channel_id BIGINT NOT NULL,
                opened_at TIMESTAMP WITH TIME ZONE NOT NULL,
                closes_at TIMESTAMP WITH TIME ZONE NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                closed_at TIMESTAMP WITH TIME ZONE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
            ''',
            fetch_type='status'
        )
        logger.info("地震チャンネル設定テーブルを確認・作成しました")

    async def _load_settings(self):
        """設定をメモリにロード"""
        settings = await execute_query(
            '''
            SELECT guild_id, category_id, notification_channel_id,
                   notification_role_id, earthquake_role_id
            FROM earthquake_channel_settings
            ''',
            fetch_type='all'
        )
        for s in settings:
            self._settings[s['guild_id']] = {
                'category_id': s['category_id'],
                'notification_channel_id': s['notification_channel_id'],
                'notification_role_id': s['notification_role_id'],
                'earthquake_role_id': s['earthquake_role_id'],
            }

        # アクティブなセッションをロード
        sessions = await execute_query(
            '''
            SELECT guild_id, message_id, channel_id, closes_at
            FROM earthquake_channel_sessions
            WHERE is_active = TRUE
            ''',
            fetch_type='all'
        )
        for session in sessions:
            self._active_sessions[session['guild_id']] = {
                'message_id': session['message_id'],
                'channel_id': session['channel_id'],
                'closes_at': session['closes_at'],
            }

        logger.info(f"地震チャンネル設定をロード: {len(self._settings)} サーバー, {len(self._active_sessions)} アクティブセッション")

    async def _get_or_create_role(self, guild: discord.Guild) -> Optional[discord.Role]:
        """地震チャンネル閲覧ロールを取得または作成"""
        # 設定からロールIDを取得
        if guild.id in self._settings and self._settings[guild.id].get('earthquake_role_id'):
            role = guild.get_role(self._settings[guild.id]['earthquake_role_id'])
            if role:
                return role

        # 既存のロールを検索
        role = discord.utils.get(guild.roles, name=EARTHQUAKE_ROLE_NAME)
        if role:
            # 設定を更新
            await self._update_role_id(guild.id, role.id)
            return role

        # 新規作成
        try:
            role = await guild.create_role(
                name=EARTHQUAKE_ROLE_NAME,
                reason="地震チャンネルシステム用ロール作成",
                mentionable=False,
            )
            await self._update_role_id(guild.id, role.id)
            logger.info(f"地震ch閲覧ロールを作成: {guild.name}")
            return role
        except discord.Forbidden:
            logger.error(f"ロール作成権限がありません: {guild.name}")
            return None

    async def _update_role_id(self, guild_id: int, role_id: int):
        """ロールIDを更新"""
        await execute_query(
            '''
            UPDATE earthquake_channel_settings
            SET earthquake_role_id = $1, updated_at = NOW()
            WHERE guild_id = $2
            ''',
            role_id,
            guild_id,
            fetch_type='status'
        )
        if guild_id in self._settings:
            self._settings[guild_id]['earthquake_role_id'] = role_id

    async def _remove_role_from_all(self, guild: discord.Guild, role: discord.Role):
        """全メンバーからロールを剥奪"""
        removed_count = 0
        for member in role.members:
            try:
                await member.remove_roles(role, reason="地震チャンネルクローズ")
                removed_count += 1
                await asyncio.sleep(0.5)  # レート制限対策
            except discord.Forbidden:
                pass
            except Exception as e:
                logger.error(f"ロール剥奪エラー: {e}")
        return removed_count

    async def _disable_button(self, channel: discord.TextChannel, message_id: int):
        """メッセージのボタンを無効化"""
        try:
            message = await channel.fetch_message(message_id)
            # 無効化されたボタンを持つViewで更新
            role_id = self._settings.get(channel.guild.id, {}).get('earthquake_role_id', 0)
            disabled_view = EarthquakeRoleButton(role_id, disabled=True)
            await message.edit(view=disabled_view)
        except discord.NotFound:
            logger.warning(f"メッセージが見つかりません: {message_id}")
        except Exception as e:
            logger.error(f"ボタン無効化エラー: {e}")

    @tasks.loop(minutes=1)
    async def auto_close_check(self):
        """自動クローズチェック"""
        now = datetime.now(JST)
        to_close = []

        for guild_id, session in list(self._active_sessions.items()):
            closes_at = session['closes_at']
            if closes_at.tzinfo is None:
                closes_at = JST.localize(closes_at)

            if now >= closes_at:
                to_close.append(guild_id)

        for guild_id in to_close:
            guild = self.bot.get_guild(guild_id)
            if guild:
                await self._close_earthquake_channel(guild, auto=True)

    @auto_close_check.before_loop
    async def before_auto_close_check(self):
        await self.bot.wait_until_ready()

    async def _close_earthquake_channel(
        self, guild: discord.Guild, auto: bool = False
    ) -> tuple[bool, str]:
        """地震チャンネルをクローズ"""
        if guild.id not in self._active_sessions:
            return False, "現在オープン中の地震チャンネルセッションはありません。"

        session = self._active_sessions[guild.id]
        settings = self._settings.get(guild.id)

        if not settings:
            return False, "設定が見つかりません。"

        # ロールを取得
        role = guild.get_role(settings.get('earthquake_role_id'))
        if not role:
            return False, "地震ch閲覧ロールが見つかりません。"

        # 全メンバーからロールを剥奪
        removed_count = await self._remove_role_from_all(guild, role)

        # ボタンを無効化
        channel = self.bot.get_channel(session['channel_id'])
        if channel:
            await self._disable_button(channel, session['message_id'])

        # DBを更新
        await execute_query(
            '''
            UPDATE earthquake_channel_sessions
            SET is_active = FALSE, closed_at = NOW()
            WHERE guild_id = $1 AND is_active = TRUE
            ''',
            guild.id,
            fetch_type='status'
        )

        # メモリから削除
        del self._active_sessions[guild.id]

        close_type = "自動" if auto else "手動"
        logger.info(f"地震チャンネルを{close_type}クローズ: {guild.name}, {removed_count}人からロール剥奪")

        return True, f"地震チャンネルを{close_type}クローズしました。\n{removed_count}人から閲覧権限を解除しました。"

    # === コマンド ===

    earthquake_group = app_commands.Group(
        name="地震チャンネル",
        description="地震チャンネル管理",
        default_permissions=discord.Permissions(manage_channels=True)
    )

    @earthquake_group.command(name="設定", description="地震チャンネルシステムを設定します")
    @app_commands.describe(
        category="地震情報を表示するカテゴリー",
        notification_channel="オープン通知を送信するチャンネル",
        notification_role="通知時にメンションするロール（通知ONロール）"
    )
    @is_moderator_app()
    @is_guild_app()
    async def earthquake_setup(
        self,
        interaction: discord.Interaction,
        category: discord.CategoryChannel,
        notification_channel: discord.TextChannel,
        notification_role: discord.Role
    ):
        """地震チャンネルシステムを設定"""
        await execute_query(
            '''
            INSERT INTO earthquake_channel_settings
            (guild_id, category_id, notification_channel_id, notification_role_id)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (guild_id)
            DO UPDATE SET
                category_id = $2,
                notification_channel_id = $3,
                notification_role_id = $4,
                updated_at = NOW()
            ''',
            interaction.guild.id,
            category.id,
            notification_channel.id,
            notification_role.id,
            fetch_type='status'
        )

        self._settings[interaction.guild.id] = {
            'category_id': category.id,
            'notification_channel_id': notification_channel.id,
            'notification_role_id': notification_role.id,
            'earthquake_role_id': None,
        }

        embed = discord.Embed(
            title="✅ 地震チャンネルシステムを設定しました",
            color=discord.Color.green()
        )
        embed.add_field(name="対象カテゴリー", value=category.mention, inline=True)
        embed.add_field(name="通知チャンネル", value=notification_channel.mention, inline=True)
        embed.add_field(name="通知ロール", value=notification_role.mention, inline=True)

        await interaction.response.send_message(embed=embed)

    @earthquake_group.command(name="オープン", description="地震チャンネルを開放します")
    @is_moderator_app()
    @is_guild_app()
    async def earthquake_open(self, interaction: discord.Interaction):
        """地震チャンネルをオープン"""
        await interaction.response.defer()

        # 設定確認
        if interaction.guild.id not in self._settings:
            await interaction.followup.send(
                "❌ 地震チャンネルシステムが設定されていません。\n"
                "`/地震チャンネル 設定` で先に設定してください。",
                ephemeral=True
            )
            return

        # 既にオープン中か確認
        if interaction.guild.id in self._active_sessions:
            await interaction.followup.send(
                "❌ すでに地震チャンネルがオープン中です。\n"
                "先にクローズしてから再度オープンしてください。",
                ephemeral=True
            )
            return

        settings = self._settings[interaction.guild.id]

        # ロールを取得または作成
        role = await self._get_or_create_role(interaction.guild)
        if not role:
            await interaction.followup.send(
                "❌ 地震ch閲覧ロールの作成に失敗しました。\n"
                "BOTにロール作成権限があることを確認してください。",
                ephemeral=True
            )
            return

        # 通知チャンネルを取得
        notification_channel = self.bot.get_channel(settings['notification_channel_id'])
        if not notification_channel:
            await interaction.followup.send(
                "❌ 通知チャンネルが見つかりません。設定を確認してください。",
                ephemeral=True
            )
            return

        # 通知ロールを取得
        notification_role = interaction.guild.get_role(settings['notification_role_id'])
        if not notification_role:
            await interaction.followup.send(
                "❌ 通知ロールが見つかりません。設定を確認してください。",
                ephemeral=True
            )
            return

        # カテゴリーを取得
        category = interaction.guild.get_channel(settings['category_id'])
        if not category:
            await interaction.followup.send(
                "❌ 対象カテゴリーが見つかりません。設定を確認してください。",
                ephemeral=True
            )
            return

        # 終了時刻を計算
        now = datetime.now(JST)
        closes_at = now + timedelta(hours=24)

        # 通知メッセージを送信
        embed = discord.Embed(
            title="🚨 地震チャンネルが開放されました",
            description=(
                "地震に関する情報共有のため、地震チャンネルを一時的に開放します。\n\n"
                "下のボタンを押すと、地震関連チャンネルを閲覧できるようになります。\n"
                "**24時間後に自動的にアクセス権が解除されます。**"
            ),
            color=discord.Color.red(),
            timestamp=now
        )
        embed.add_field(
            name="⏰ 自動クローズ",
            value=f"<t:{int(closes_at.timestamp())}:F>",
            inline=False
        )
        embed.set_footer(text=f"開放者: {interaction.user}")

        view = EarthquakeRoleButton(role.id)
        message = await notification_channel.send(
            content=notification_role.mention,
            embed=embed,
            view=view,
            allowed_mentions=discord.AllowedMentions(roles=True)
        )

        # DBに保存
        await execute_query(
            '''
            INSERT INTO earthquake_channel_sessions
            (guild_id, message_id, channel_id, opened_at, closes_at)
            VALUES ($1, $2, $3, $4, $5)
            ''',
            interaction.guild.id,
            message.id,
            notification_channel.id,
            now,
            closes_at,
            fetch_type='status'
        )

        # メモリに保存
        self._active_sessions[interaction.guild.id] = {
            'message_id': message.id,
            'channel_id': notification_channel.id,
            'closes_at': closes_at,
        }

        # 確認メッセージ
        embed = discord.Embed(
            title="✅ 地震チャンネルをオープンしました",
            color=discord.Color.green()
        )
        embed.add_field(name="通知先", value=notification_channel.mention, inline=True)
        embed.add_field(
            name="自動クローズ",
            value=f"<t:{int(closes_at.timestamp())}:R>",
            inline=True
        )

        await interaction.followup.send(embed=embed)
        logger.info(f"地震チャンネルをオープン: {interaction.guild.name}")

    @earthquake_group.command(name="クローズ", description="地震チャンネルを閉鎖します")
    @is_moderator_app()
    @is_guild_app()
    async def earthquake_close(self, interaction: discord.Interaction):
        """地震チャンネルをクローズ"""
        await interaction.response.defer()

        success, message = await self._close_earthquake_channel(interaction.guild, auto=False)

        if success:
            embed = discord.Embed(
                title="✅ 地震チャンネルをクローズしました",
                description=message,
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                title="❌ クローズに失敗しました",
                description=message,
                color=discord.Color.red()
            )

        await interaction.followup.send(embed=embed)

    @earthquake_group.command(name="ステータス", description="地震チャンネルの状態を確認します")
    @is_moderator_app()
    @is_guild_app()
    async def earthquake_status(self, interaction: discord.Interaction):
        """地震チャンネルの状態を確認"""
        if interaction.guild.id not in self._settings:
            await interaction.response.send_message(
                "❌ 地震チャンネルシステムが設定されていません。",
                ephemeral=True
            )
            return

        settings = self._settings[interaction.guild.id]

        embed = discord.Embed(
            title="📊 地震チャンネル ステータス",
            color=discord.Color.blue()
        )

        # 設定情報
        category = interaction.guild.get_channel(settings['category_id'])
        notification_channel = self.bot.get_channel(settings['notification_channel_id'])
        notification_role = interaction.guild.get_role(settings['notification_role_id'])
        earthquake_role = interaction.guild.get_role(settings.get('earthquake_role_id') or 0)

        embed.add_field(
            name="対象カテゴリー",
            value=category.mention if category else "(見つかりません)",
            inline=True
        )
        embed.add_field(
            name="通知チャンネル",
            value=notification_channel.mention if notification_channel else "(見つかりません)",
            inline=True
        )
        embed.add_field(
            name="通知ロール",
            value=notification_role.mention if notification_role else "(見つかりません)",
            inline=True
        )
        embed.add_field(
            name="閲覧ロール",
            value=earthquake_role.mention if earthquake_role else "(未作成)",
            inline=True
        )

        # セッション情報
        if interaction.guild.id in self._active_sessions:
            session = self._active_sessions[interaction.guild.id]
            closes_at = session['closes_at']
            if closes_at.tzinfo is None:
                closes_at = JST.localize(closes_at)

            embed.add_field(
                name="🟢 ステータス",
                value="**オープン中**",
                inline=False
            )
            embed.add_field(
                name="自動クローズ",
                value=f"<t:{int(closes_at.timestamp())}:F> (<t:{int(closes_at.timestamp())}:R>)",
                inline=False
            )

            if earthquake_role:
                embed.add_field(
                    name="現在の閲覧者数",
                    value=f"{len(earthquake_role.members)}人",
                    inline=True
                )
        else:
            embed.add_field(
                name="🔴 ステータス",
                value="**クローズ中**",
                inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(EarthquakeChannel(bot))
