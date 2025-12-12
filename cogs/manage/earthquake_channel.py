"""
地震チャンネルシステム

P2P地震情報APIから地震情報を受信し、震度3以上の地震発生時に
特定カテゴリーのチャンネルを一時的に公開する機能を提供します。
- 自動オープン: 震度3以上の地震検知時にロール取得ボタンを送信し、24時間後に自動クローズ
- 手動オープン: コマンドで手動オープンも可能
- クローズ: 全ユーザーからロールを剥奪し、ボタンを無効化
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Optional

import aiohttp
import discord
import pytz
from discord import app_commands
from discord.ext import commands, tasks

from config.setting import get_settings
from utils.commands_help import is_guild_app, is_moderator_app
from utils.components_v2 import (
    ComponentsV2Message,
    Container,
    Separator,
    TextDisplay,
    send_components_v2_followup,
    send_components_v2_response,
    send_components_v2_to_channel,
)
from utils.database import execute_query
from utils.logging import setup_logging

logger = setup_logging()
settings = get_settings()
# 日本時間
JST = pytz.timezone('Asia/Tokyo')

# 地震チャンネル閲覧ロール名
EARTHQUAKE_ROLE_NAME = "地震ch閲覧"

# P2P地震情報 WebSocket API
P2P_WEBSOCKET_URL_PRODUCTION = "wss://api.p2pquake.net/v2/ws"
P2P_WEBSOCKET_URL_SANDBOX = "wss://api-realtime-sandbox.p2pquake.net/v2/ws"

# 自動オープンする最低震度 (30 = 震度3)
MIN_SCALE_FOR_AUTO_OPEN = 30

# 震度の表示名マッピング
SCALE_NAMES = {
    -1: "不明",
    10: "震度1",
    20: "震度2",
    30: "震度3",
    40: "震度4",
    45: "震度5弱",
    50: "震度5強",
    55: "震度6弱",
    60: "震度6強",
    70: "震度7",
}


class EarthquakeRoleButton(discord.ui.View):
    """地震チャンネル閲覧ロール取得ボタン"""

    def __init__(self, role_id: int, talk_channel_id: int = 0, disabled: bool = False):
        super().__init__(timeout=None)
        self.role_id = role_id
        self.talk_channel_id = talk_channel_id

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

            # 地震の話題チャンネルへのリンクを取得
            cog = interaction.client.get_cog('EarthquakeChannel')
            channel_link = ""
            if cog and interaction.guild.id in cog._active_sessions:
                talk_ch_id = cog._active_sessions[interaction.guild.id].get('talk_channel_id')
                if talk_ch_id:
                    channel_link = f"\nhttps://discord.com/channels/{interaction.guild.id}/{talk_ch_id}"

            await interaction.response.send_message(
                f"✅ 地震チャンネルが閲覧可能になりました！{channel_link}\n"
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
        self._ws_session: Optional[aiohttp.ClientSession] = None
        self._ws_connection: Optional[aiohttp.ClientWebSocketResponse] = None
        self._ws_task: Optional[asyncio.Task] = None
        self._reconnect_delay = 5  # 再接続待機時間（秒）

        # サンドボックスモードの設定を取得
        self._use_sandbox = settings.p2p_earthquake_sandbox
        self._ws_url = P2P_WEBSOCKET_URL_SANDBOX if self._use_sandbox else P2P_WEBSOCKET_URL_PRODUCTION

    async def cog_load(self):
        """Cogロード時の初期化"""
        await self._setup_table()
        await self._load_settings()
        self._register_views()
        self.auto_close_check.start()
        # WebSocket接続を開始
        self._ws_task = asyncio.create_task(self._websocket_listener())

        mode = "サンドボックス" if self._use_sandbox else "本番"
        logger.info(f"地震チャンネルシステム起動: {mode}モード ({self._ws_url})")

    async def cog_unload(self):
        """Cogアンロード時のクリーンアップ"""
        self.auto_close_check.cancel()
        # WebSocket接続を終了
        if self._ws_task:
            self._ws_task.cancel()
        if self._ws_connection:
            await self._ws_connection.close()
        if self._ws_session:
            await self._ws_session.close()

    def _register_views(self):
        """永続的なViewを登録"""
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
                min_scale INTEGER DEFAULT 30,
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
                talk_channel_id BIGINT,
                info_channel_id BIGINT,
                opened_at TIMESTAMP WITH TIME ZONE NOT NULL,
                closes_at TIMESTAMP WITH TIME ZONE NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                closed_at TIMESTAMP WITH TIME ZONE,
                earthquake_info JSONB,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
            ''',
            fetch_type='status'
        )

        # 既存テーブルにカラムを追加（存在しない場合）
        await execute_query(
            '''
            ALTER TABLE earthquake_channel_sessions
            ADD COLUMN IF NOT EXISTS talk_channel_id BIGINT,
            ADD COLUMN IF NOT EXISTS info_channel_id BIGINT,
            ADD COLUMN IF NOT EXISTS earthquake_info JSONB
            ''',
            fetch_type='status'
        )

        await execute_query(
            '''
            ALTER TABLE earthquake_channel_settings
            ADD COLUMN IF NOT EXISTS min_scale INTEGER DEFAULT 30
            ''',
            fetch_type='status'
        )

        logger.info("地震チャンネル設定テーブルを確認・作成しました")

    async def _load_settings(self):
        """設定をメモリにロード"""
        settings_data = await execute_query(
            '''
            SELECT guild_id, category_id, notification_channel_id,
                   notification_role_id, earthquake_role_id, min_scale
            FROM earthquake_channel_settings
            ''',
            fetch_type='all'
        )
        for s in settings_data:
            self._settings[s['guild_id']] = {
                'category_id': s['category_id'],
                'notification_channel_id': s['notification_channel_id'],
                'notification_role_id': s['notification_role_id'],
                'earthquake_role_id': s['earthquake_role_id'],
                'min_scale': s.get('min_scale', MIN_SCALE_FOR_AUTO_OPEN),
            }

        # アクティブなセッションをロード
        sessions = await execute_query(
            '''
            SELECT guild_id, message_id, channel_id, talk_channel_id, info_channel_id, closes_at
            FROM earthquake_channel_sessions
            WHERE is_active = TRUE
            ''',
            fetch_type='all'
        )
        for session in sessions:
            self._active_sessions[session['guild_id']] = {
                'message_id': session['message_id'],
                'channel_id': session['channel_id'],
                'talk_channel_id': session.get('talk_channel_id'),
                'info_channel_id': session.get('info_channel_id'),
                'closes_at': session['closes_at'],
            }

        logger.info(f"地震チャンネル設定をロード: {len(self._settings)} サーバー, {len(self._active_sessions)} アクティブセッション")

    # === WebSocket関連 ===

    async def _websocket_listener(self):
        """P2P地震情報WebSocketを監視"""
        await self.bot.wait_until_ready()
        current_delay = self._reconnect_delay

        while True:
            try:
                await self._connect_websocket()
                # 接続成功したらリセット
                current_delay = self._reconnect_delay
            except asyncio.CancelledError:
                logger.info("WebSocketリスナーがキャンセルされました")
                break
            except Exception as e:
                # 429エラーの場合は長めに待機
                if "429" in str(e):
                    current_delay = min(current_delay * 2, 300)  # 最大5分
                    logger.warning(f"レート制限 (429): {current_delay}秒後に再接続")
                else:
                    logger.error(f"WebSocket接続エラー: {e}")
                await asyncio.sleep(current_delay)

    async def _connect_websocket(self):
        """WebSocketに接続して地震情報を受信"""
        self._ws_session = aiohttp.ClientSession()

        try:
            mode = "サンドボックス" if self._use_sandbox else "本番"
            logger.info(f"P2P地震情報WebSocketに接続中 ({mode}): {self._ws_url}")
            self._ws_connection = await self._ws_session.ws_connect(self._ws_url)
            logger.info("P2P地震情報WebSocketに接続しました")

            async for msg in self._ws_connection:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    await self._handle_earthquake_message(msg.data)
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error(f"WebSocketエラー: {self._ws_connection.exception()}")
                    break
                elif msg.type == aiohttp.WSMsgType.CLOSED:
                    logger.warning("WebSocket接続が閉じられました")
                    break

        finally:
            if self._ws_connection and not self._ws_connection.closed:
                await self._ws_connection.close()
            if self._ws_session and not self._ws_session.closed:
                await self._ws_session.close()

        logger.info(f"WebSocket再接続まで{self._reconnect_delay}秒待機...")

    async def _handle_earthquake_message(self, data: str):
        """地震情報メッセージを処理"""
        try:
            info = json.loads(data)
        except json.JSONDecodeError:
            logger.error(f"JSONパースエラー: {data}")
            return

        # 地震情報（code: 551）のみ処理
        if info.get('code') != 551:
            return

        earthquake = info.get('earthquake', {})
        max_scale = earthquake.get('maxScale', -1)

        # 震度情報がない場合はスキップ
        if max_scale < 0:
            return

        mode = "[SANDBOX] " if self._use_sandbox else ""
        logger.info(f"{mode}地震情報受信: 最大震度={SCALE_NAMES.get(max_scale, '不明')}, 震源={earthquake.get('hypocenter', {}).get('name', '不明')}")

        # 設定されている全サーバーをチェック
        for guild_id, guild_settings in self._settings.items():
            min_scale = guild_settings.get('min_scale', MIN_SCALE_FOR_AUTO_OPEN)

            # 最低震度未満ならスキップ
            if max_scale < min_scale:
                continue

            # 既にオープン中ならスキップ
            if guild_id in self._active_sessions:
                logger.info(f"サーバー {guild_id} は既に地震チャンネルがオープン中です")
                continue

            guild = self.bot.get_guild(guild_id)
            if not guild:
                continue

            # 自動オープン
            logger.info(f"{mode}サーバー {guild.name} で地震チャンネルを自動オープンします")
            await self._open_earthquake_channel(guild, earthquake_info=info)

    # === チャンネル操作 ===

    async def _get_or_create_role(self, guild: discord.Guild) -> Optional[discord.Role]:
        """地震チャンネル閲覧ロールを取得または作成"""
        if guild.id in self._settings and self._settings[guild.id].get('earthquake_role_id'):
            role = guild.get_role(self._settings[guild.id]['earthquake_role_id'])
            if role:
                return role

        role = discord.utils.get(guild.roles, name=EARTHQUAKE_ROLE_NAME)
        if role:
            await self._update_role_id(guild.id, role.id)
            return role

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
                await asyncio.sleep(0.5)
            except discord.Forbidden:
                pass
            except Exception as e:
                logger.error(f"ロール剥奪エラー: {e}")
        return removed_count

    async def _disable_button(self, channel: discord.TextChannel, message_id: int):
        """メッセージのボタンを無効化"""
        try:
            message = await channel.fetch_message(message_id)
            role_id = self._settings.get(channel.guild.id, {}).get('earthquake_role_id', 0)
            disabled_view = EarthquakeRoleButton(role_id, disabled=True)
            await message.edit(view=disabled_view)
        except discord.NotFound:
            logger.warning(f"メッセージが見つかりません: {message_id}")
        except Exception as e:
            logger.error(f"ボタン無効化エラー: {e}")

    def _format_earthquake_info(self, earthquake_info: dict) -> ComponentsV2Message:
        """地震情報をComponents V2にフォーマット"""
        earthquake = earthquake_info.get('earthquake', {})
        hypocenter = earthquake.get('hypocenter', {})
        issue = earthquake_info.get('issue', {})

        max_scale = earthquake.get('maxScale', -1)
        scale_name = SCALE_NAMES.get(max_scale, '不明')

        # サンドボックスモードの場合はタイトルに表示
        title = "# 🚨 地震情報"
        if self._use_sandbox:
            title = "# 🚨 地震情報 [テストデータ]"

        # 情報を構築
        info_lines = []
        if earthquake.get('time'):
            info_lines.append(f"**発生時刻:** {earthquake['time']}")
        if hypocenter.get('name'):
            info_lines.append(f"**震源地:** {hypocenter['name']}")
        info_lines.append(f"**最大震度:** {scale_name}")

        magnitude = hypocenter.get('magnitude', -1)
        if magnitude > 0:
            info_lines.append(f"**マグニチュード:** M{magnitude}")

        depth = hypocenter.get('depth', -1)
        if depth >= 0:
            depth_str = "ごく浅い" if depth == 0 else f"{depth}km"
            info_lines.append(f"**深さ:** {depth_str}")

        # 津波情報
        tsunami = earthquake.get('domesticTsunami', 'Unknown')
        tsunami_text = {
            'None': 'なし',
            'Unknown': '不明',
            'Checking': '調査中',
            'NonEffective': '若干の海面変動（被害なし）',
            'Watch': '津波注意報',
            'Warning': '津波予報',
        }.get(tsunami, tsunami)
        info_lines.append(f"**津波:** {tsunami_text}")

        # コンテナを作成
        container = Container(color=0xED4245)  # 赤色
        container.add(TextDisplay(title))
        container.add(Separator())
        container.add(TextDisplay("\n".join(info_lines)))

        # 発表元
        if issue.get('source'):
            container.add(Separator())
            container.add(TextDisplay(f"-# 発表: {issue['source']} ({issue.get('time', '')})"))

        msg = ComponentsV2Message()
        msg.add(container)
        return msg

    async def _open_earthquake_channel(
        self,
        guild: discord.Guild,
        earthquake_info: Optional[dict] = None
    ) -> tuple[bool, str]:
        """地震チャンネルをオープン"""
        if guild.id not in self._settings:
            return False, "設定が見つかりません。"

        if guild.id in self._active_sessions:
            return False, "すでに地震チャンネルがオープン中です。"

        guild_settings = self._settings[guild.id]

        # ロールを取得または作成
        role = await self._get_or_create_role(guild)
        if not role:
            return False, "地震ch閲覧ロールの作成に失敗しました。"

        # 通知チャンネルを取得
        notification_channel = self.bot.get_channel(guild_settings['notification_channel_id'])
        if not notification_channel:
            return False, "通知チャンネルが見つかりません。"

        # 通知ロールを取得
        notification_role = guild.get_role(guild_settings['notification_role_id'])
        if not notification_role:
            return False, "通知ロールが見つかりません。"

        # カテゴリーを取得
        category = guild.get_channel(guild_settings['category_id'])
        if not category:
            return False, "対象カテゴリーが見つかりません。"

        # 終了時刻を計算
        now = datetime.now(JST)
        closes_at = now + timedelta(hours=24)

        # === チャンネル作成 ===
        try:
            overwrites = category.overwrites.copy()
            overwrites[role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True
            )

            talk_channel = await guild.create_text_channel(
                name="🌍地震の話題",
                category=category,
                overwrites=overwrites,
                reason="地震チャンネルオープン"
            )

            info_channel = await guild.create_text_channel(
                name="📢地震の情報共有",
                category=category,
                overwrites=overwrites,
                reason="地震チャンネルオープン"
            )

            # ルールメッセージを送信してピン留め (Components V2)
            talk_rule_msg = ComponentsV2Message()
            talk_rule_container = Container(color=0xE67E22)  # オレンジ
            talk_rule_container.add(TextDisplay("# 📋 地震チャンネルのルール"))
            talk_rule_container.add(Separator())
            talk_rule_container.add(TextDisplay(
                "地震に関する話題はこのチャンネルでお願いします。\n\n"
                "**⚠️ 注意事項**\n"
                "- 他のチャンネルでは地震の話題は控えてください\n"
                "- みんなを不安にさせるような発言は禁止です\n"
                "- 落ち着いて行動しましょう"
            ))
            talk_rule_container.add(Separator())
            talk_rule_container.add(TextDisplay("-# このチャンネルは24時間後に自動で削除されます。"))
            talk_rule_msg.add(talk_rule_container)
            talk_msg_id = await send_components_v2_to_channel(
                talk_channel,
                talk_rule_msg,
                self.bot.http.token
            )
            # メッセージをピン留め
            if talk_msg_id:
                try:
                    talk_msg = await talk_channel.fetch_message(int(talk_msg_id))
                    await talk_msg.pin()
                except Exception as e:
                    logger.warning(f"トークチャンネルのメッセージピン留めに失敗: {e}")

            info_rule_msg = ComponentsV2Message()
            info_rule_container = Container(color=0x3498DB)  # 青
            info_rule_container.add(TextDisplay("# 📋 情報共有のルール"))
            info_rule_container.add(Separator())
            info_rule_container.add(TextDisplay(
                "地震に関する情報を共有するチャンネルです。\n\n"
                "**⚠️ 注意事項**\n"
                "- フェイクニュースやソースが不確かな情報は投稿しないでください\n"
                "- 運営が不適切と判断した情報は削除する場合があります\n"
                "- 信頼できる情報源からの情報のみ共有してください\n"
                "  （気象庁、NHK、官公庁など）"
            ))
            info_rule_container.add(Separator())
            info_rule_container.add(TextDisplay("-# このチャンネルは24時間後に自動で削除されます。"))
            info_rule_msg.add(info_rule_container)
            info_msg_id = await send_components_v2_to_channel(
                info_channel,
                info_rule_msg,
                self.bot.http.token
            )
            # メッセージをピン留め
            if info_msg_id:
                try:
                    info_msg = await info_channel.fetch_message(int(info_msg_id))
                    await info_msg.pin()
                except Exception as e:
                    logger.warning(f"情報共有チャンネルのメッセージピン留めに失敗: {e}")

        except discord.Forbidden:
            return False, "チャンネルの作成に失敗しました。"
        except Exception as e:
            logger.error(f"チャンネル作成エラー: {e}")
            return False, f"チャンネルの作成中にエラーが発生しました: {e}"

        # 通知メッセージを作成 (Components V2)
        title = "# 🚨 臨時の地震チャンネルが作成されました"
        if self._use_sandbox:
            title = "# 🚨 臨時の地震チャンネルが作成されました [テスト]"

        notify_container = Container(color=0xED4245)  # 赤
        notify_container.add(TextDisplay(title))
        notify_container.add(Separator())

        # サンドボックスモードの場合は注意書きを追加
        if self._use_sandbox:
            notify_container.add(TextDisplay("⚠️ **これはテストデータです。実際の地震ではありません。**"))
            notify_container.add(Separator())

        notify_container.add(TextDisplay(
            "地震に関する情報共有のため、地震チャンネルを一時的に開放しました。\n\n"
            "下のボタンを押すと、地震関連チャンネルを閲覧できるようになります。\n\n"
            "**地震に関する話題は地震チャンネル内のみにしてください。**\n\n"
            "**24時間後に自動的にアクセス権が解除されます。**"
        ))
        notify_container.add(Separator())
        notify_container.add(TextDisplay(f"**⏰ 自動クローズ:** <t:{int(closes_at.timestamp())}:F>"))

        notify_msg = ComponentsV2Message()
        notify_msg.add(notify_container)

        view = EarthquakeRoleButton(role.id, talk_channel.id)

        # Components V2 + View を送信
        message_id = await send_components_v2_to_channel(
            notification_channel,
            notify_msg,
            self.bot.http.token,
            content=notification_role.mention,
            view=view,
            allowed_mentions=discord.AllowedMentions(roles=True)
        )
        
        if not message_id:
            logger.error("通知メッセージの送信に失敗しました")
            return False, "通知メッセージの送信に失敗しました。"
        
        # メッセージオブジェクトを取得
        try:
            message = await notification_channel.fetch_message(int(message_id))
        except Exception as e:
            logger.error(f"通知メッセージの取得に失敗: {e}")
            return False, "通知メッセージの取得に失敗しました。"

        # チャットチャンネルにもメンションなしで通知
        chat_channel = self.bot.get_channel(settings.hfs_chat_channel_id)
        if chat_channel:
            try:
                await send_components_v2_to_channel(
                    chat_channel,
                    notify_msg,
                    self.bot.http.token,
                    view=EarthquakeRoleButton(role.id, talk_channel.id)
                )
            except Exception as e:
                logger.warning(f"チャットチャンネルへの通知に失敗: {e}")

        # DBに保存
        await execute_query(
            '''
            INSERT INTO earthquake_channel_sessions
            (guild_id, message_id, channel_id, talk_channel_id, info_channel_id, opened_at, closes_at, earthquake_info)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ''',
            guild.id,
            message.id,
            notification_channel.id,
            talk_channel.id,
            info_channel.id,
            now,
            closes_at,
            json.dumps(earthquake_info) if earthquake_info else None,
            fetch_type='status'
        )

        # メモリに保存
        self._active_sessions[guild.id] = {
            'message_id': message.id,
            'channel_id': notification_channel.id,
            'talk_channel_id': talk_channel.id,
            'info_channel_id': info_channel.id,
            'closes_at': closes_at,
        }

        mode = "自動(テスト)" if self._use_sandbox else "自動"
        logger.info(f"地震チャンネルを{mode}オープン: {guild.name}")
        return True, "地震チャンネルをオープンしました。"

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
        guild_settings = self._settings.get(guild.id)

        if not guild_settings:
            return False, "設定が見つかりません。"

        role = guild.get_role(guild_settings.get('earthquake_role_id'))
        if not role:
            return False, "地震ch閲覧ロールが見つかりません。"

        removed_count = await self._remove_role_from_all(guild, role)

        channel = self.bot.get_channel(session['channel_id'])
        if channel:
            await self._disable_button(channel, session['message_id'])

        deleted_channels = []
        for ch_key in ['talk_channel_id', 'info_channel_id']:
            ch_id = session.get(ch_key)
            if ch_id:
                ch = guild.get_channel(ch_id)
                if ch:
                    try:
                        await ch.delete(reason="地震チャンネルクローズ")
                        deleted_channels.append(ch.name)
                    except discord.Forbidden:
                        logger.warning(f"チャンネル削除権限がありません: {ch.name}")
                    except Exception as e:
                        logger.error(f"チャンネル削除エラー: {e}")

        await execute_query(
            '''
            UPDATE earthquake_channel_sessions
            SET is_active = FALSE, closed_at = NOW()
            WHERE guild_id = $1 AND is_active = TRUE
            ''',
            guild.id,
            fetch_type='status'
        )

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
        notification_role="通知時にメンションするロール（通知ONロール）",
        min_scale="自動オープンする最低震度（デフォルト: 震度3）"
    )
    @app_commands.choices(min_scale=[
        app_commands.Choice(name="震度1", value=10),
        app_commands.Choice(name="震度2", value=20),
        app_commands.Choice(name="震度3", value=30),
        app_commands.Choice(name="震度4", value=40),
        app_commands.Choice(name="震度5弱", value=45),
        app_commands.Choice(name="震度5強", value=50),
        app_commands.Choice(name="震度6弱", value=55),
        app_commands.Choice(name="震度6強", value=60),
        app_commands.Choice(name="震度7", value=70),
    ])
    @is_moderator_app()
    @is_guild_app()
    async def earthquake_setup(
        self,
        interaction: discord.Interaction,
        category: discord.CategoryChannel,
        notification_channel: discord.TextChannel,
        notification_role: discord.Role,
        min_scale: int = 30
    ):
        """地震チャンネルシステムを設定"""
        await execute_query(
            '''
            INSERT INTO earthquake_channel_settings
            (guild_id, category_id, notification_channel_id, notification_role_id, min_scale)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (guild_id)
            DO UPDATE SET
                category_id = $2,
                notification_channel_id = $3,
                notification_role_id = $4,
                min_scale = $5,
                updated_at = NOW()
            ''',
            interaction.guild.id,
            category.id,
            notification_channel.id,
            notification_role.id,
            min_scale,
            fetch_type='status'
        )

        self._settings[interaction.guild.id] = {
            'category_id': category.id,
            'notification_channel_id': notification_channel.id,
            'notification_role_id': notification_role.id,
            'earthquake_role_id': None,
            'min_scale': min_scale,
        }

        # Components V2で応答
        setup_container = Container(color=0x57F287)  # 緑
        setup_container.add(TextDisplay("# ✅ 地震チャンネルシステムを設定しました"))
        setup_container.add(Separator())
        setup_container.add(TextDisplay(
            f"**対象カテゴリー:** {category.mention}\n"
            f"**通知チャンネル:** {notification_channel.mention}\n"
            f"**通知ロール:** {notification_role.mention}\n"
            f"**自動オープン震度:** {SCALE_NAMES.get(min_scale, '震度3')}"
        ))

        # サンドボックスモードの注意
        if self._use_sandbox:
            setup_container.add(Separator())
            setup_container.add(TextDisplay(
                "⚠️ **テストモード**\n"
                "現在サンドボックスモードで動作しています。テストデータが約30秒ごとに配信されます。"
            ))

        setup_msg = ComponentsV2Message()
        setup_msg.add(setup_container)
        await send_components_v2_response(interaction, setup_msg)

    @earthquake_group.command(name="オープン", description="地震チャンネルを手動で開放します")
    @is_moderator_app()
    @is_guild_app()
    async def earthquake_open(self, interaction: discord.Interaction):
        """地震チャンネルを手動オープン"""
        await interaction.response.defer()

        success, message = await self._open_earthquake_channel(interaction.guild)

        if success:
            session = self._active_sessions.get(interaction.guild.id, {})
            closes_at = session.get('closes_at')

            open_container = Container(color=0x57F287)  # 緑
            open_container.add(TextDisplay("# ✅ 地震チャンネルをオープンしました"))
            open_container.add(Separator())

            info_lines = []
            talk_ch = interaction.guild.get_channel(session.get('talk_channel_id', 0))
            info_ch = interaction.guild.get_channel(session.get('info_channel_id', 0))

            if talk_ch:
                info_lines.append(f"**話題チャンネル:** {talk_ch.mention}")
            if info_ch:
                info_lines.append(f"**情報共有チャンネル:** {info_ch.mention}")
            if closes_at:
                info_lines.append(f"**自動クローズ:** <t:{int(closes_at.timestamp())}:R>")

            open_container.add(TextDisplay("\n".join(info_lines)))
        else:
            open_container = Container(color=0xED4245)  # 赤
            open_container.add(TextDisplay("# ❌ オープンに失敗しました"))
            open_container.add(Separator())
            open_container.add(TextDisplay(message))

        open_msg = ComponentsV2Message()
        open_msg.add(open_container)
        await send_components_v2_followup(interaction, open_msg)

    @earthquake_group.command(name="クローズ", description="地震チャンネルを閉鎖します")
    @is_moderator_app()
    @is_guild_app()
    async def earthquake_close(self, interaction: discord.Interaction):
        """地震チャンネルをクローズ"""
        await interaction.response.defer()

        success, message = await self._close_earthquake_channel(interaction.guild, auto=False)

        if success:
            close_container = Container(color=0x57F287)  # 緑
            close_container.add(TextDisplay("# ✅ 地震チャンネルをクローズしました"))
            close_container.add(Separator())
            close_container.add(TextDisplay(message))
        else:
            close_container = Container(color=0xED4245)  # 赤
            close_container.add(TextDisplay("# ❌ クローズに失敗しました"))
            close_container.add(Separator())
            close_container.add(TextDisplay(message))

        close_msg = ComponentsV2Message()
        close_msg.add(close_container)
        await send_components_v2_followup(interaction, close_msg)

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

        guild_settings = self._settings[interaction.guild.id]

        category = interaction.guild.get_channel(guild_settings['category_id'])
        notification_channel = self.bot.get_channel(guild_settings['notification_channel_id'])
        notification_role = interaction.guild.get_role(guild_settings['notification_role_id'])
        earthquake_role = interaction.guild.get_role(guild_settings.get('earthquake_role_id') or 0)
        min_scale = guild_settings.get('min_scale', MIN_SCALE_FOR_AUTO_OPEN)

        # WebSocket接続状態
        ws_connected = self._ws_connection and not self._ws_connection.closed
        mode = "サンドボックス" if self._use_sandbox else "本番"
        ws_status = f"🟢 接続中 ({mode})" if ws_connected else f"🔴 切断中 ({mode})"

        # Components V2で構築
        status_container = Container(color=0x3498DB)  # 青
        status_container.add(TextDisplay("# 📊 地震チャンネル ステータス"))
        status_container.add(Separator())

        # 設定情報
        status_container.add(TextDisplay(
            f"**対象カテゴリー:** {category.mention if category else '(見つかりません)'}\n"
            f"**通知チャンネル:** {notification_channel.mention if notification_channel else '(見つかりません)'}\n"
            f"**通知ロール:** {notification_role.mention if notification_role else '(見つかりません)'}\n"
            f"**閲覧ロール:** {earthquake_role.mention if earthquake_role else '(未作成)'}\n"
            f"**自動オープン震度:** {SCALE_NAMES.get(min_scale, '震度3')}\n"
            f"**P2P地震情報:** {ws_status}"
        ))

        status_container.add(Separator())

        if interaction.guild.id in self._active_sessions:
            session = self._active_sessions[interaction.guild.id]
            closes_at = session['closes_at']
            if closes_at.tzinfo is None:
                closes_at = JST.localize(closes_at)

            session_lines = ["## 🟢 オープン中"]

            talk_ch = interaction.guild.get_channel(session.get('talk_channel_id') or 0)
            info_ch = interaction.guild.get_channel(session.get('info_channel_id') or 0)
            if talk_ch:
                session_lines.append(f"**話題チャンネル:** {talk_ch.mention}")
            if info_ch:
                session_lines.append(f"**情報共有チャンネル:** {info_ch.mention}")

            session_lines.append(f"**自動クローズ:** <t:{int(closes_at.timestamp())}:F> (<t:{int(closes_at.timestamp())}:R>)")

            if earthquake_role:
                session_lines.append(f"**現在の閲覧者数:** {len(earthquake_role.members)}人")

            status_container.add(TextDisplay("\n".join(session_lines)))
        else:
            status_container.add(TextDisplay("## 🔴 クローズ中"))

        status_msg = ComponentsV2Message()
        status_msg.add(status_container)
        await send_components_v2_response(interaction, status_msg, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(EarthquakeChannel(bot))
