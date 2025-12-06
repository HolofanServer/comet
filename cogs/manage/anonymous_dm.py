"""
HFS Staff DM System - 高機能サポートツール

機能:
- スタッフとしてユーザーとDMやり取り
- メッセージ編集・削除の同期
- 内部メモ機能（相手に見えない）
- スニペット（定型文）
- 対応者の表示
- セッション優先度・タグ
- メッセージ統計
- タイピング通知
"""

from datetime import datetime

import discord
import httpx
from discord import app_commands
from discord.ext import commands

from utils.cv2 import (
    ActionRow,
    Button,
    ButtonStyle,
    ComponentsV2Message,
    Container,
    Separator,
    TextDisplay,
    send_components_v2_followup,
)
from utils.database import get_db_pool
from utils.logging import setup_logging

logger = setup_logging(__name__)


class PrioritySelect(discord.ui.Select):
    """優先度選択メニュー"""

    def __init__(self):
        options = [
            discord.SelectOption(label="🔴 緊急", value="urgent", description="すぐに対応が必要"),
            discord.SelectOption(label="🟠 高", value="high", description="早めに対応"),
            discord.SelectOption(label="🟡 中", value="medium", description="通常対応"),
            discord.SelectOption(label="🟢 低", value="low", description="時間があるとき"),
        ]
        super().__init__(placeholder="優先度を選択...", options=options, custom_id="anon_dm_priority")

    async def callback(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("AnonymousDMv2")
        if cog:
            await cog.set_priority(interaction, self.values[0])


class SessionControlView(discord.ui.View):
    """セッション管理ビュー"""

    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(PrioritySelect())

    @discord.ui.button(label="📝 メモ追加", style=discord.ButtonStyle.secondary, custom_id="anon_dm_memo")
    async def add_memo(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = MemoModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="📊 統計", style=discord.ButtonStyle.secondary, custom_id="anon_dm_stats")
    async def show_stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = interaction.client.get_cog("AnonymousDMv2")
        if cog:
            await cog.show_session_stats(interaction)

    @discord.ui.button(label="🔒 終了", style=discord.ButtonStyle.danger, custom_id="anon_dm_close")
    async def close_session(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = interaction.client.get_cog("AnonymousDMv2")
        if cog:
            await cog.close_session_button(interaction)


class MemoModal(discord.ui.Modal, title="内部メモを追加"):
    """メモ入力モーダル"""

    memo_content = discord.ui.TextInput(
        label="メモ内容",
        style=discord.TextStyle.paragraph,
        placeholder="相手には見えないメモを入力...",
        required=True,
        max_length=1000,
    )

    async def on_submit(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("AnonymousDMv2")
        if cog:
            await cog.add_memo(interaction, self.memo_content.value)


class SnippetModal(discord.ui.Modal, title="スニペットを追加"):
    """スニペット追加モーダル"""

    snippet_name = discord.ui.TextInput(
        label="スニペット名",
        placeholder="greeting",
        required=True,
        max_length=50,
    )

    snippet_content = discord.ui.TextInput(
        label="内容",
        style=discord.TextStyle.paragraph,
        placeholder="お問い合わせありがとうございます。",
        required=True,
        max_length=2000,
    )

    async def on_submit(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("AnonymousDMv2")
        if cog:
            await cog.save_snippet(interaction, self.snippet_name.value, self.snippet_content.value)


class SnippetEditModal(discord.ui.Modal, title="スニペットを編集して送信"):
    """スニペット編集モーダル"""

    snippet_content = discord.ui.TextInput(
        label="内容（編集可能）",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=2000,
    )

    def __init__(self, original_content: str, snippet_name: str):
        super().__init__()
        self.snippet_content.default = original_content
        self.snippet_name = snippet_name

    async def on_submit(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("AnonymousDMv2")
        if cog:
            await cog.send_snippet_content(interaction, self.snippet_content.value, self.snippet_name)


class SnippetPreviewView(discord.ui.View):
    """スニペットプレビュー用のView"""

    def __init__(self, snippet_name: str, snippet_content: str):
        super().__init__(timeout=300)  # 5分でタイムアウト
        self.snippet_name = snippet_name
        self.snippet_content = snippet_content

    @discord.ui.button(label="📨 送信", style=discord.ButtonStyle.success)
    async def send_snippet(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = interaction.client.get_cog("AnonymousDMv2")
        if cog:
            await cog.send_snippet_content(interaction, self.snippet_content, self.snippet_name)
            # プレビューメッセージを削除
            await interaction.message.delete()

    @discord.ui.button(label="✏️ 編集", style=discord.ButtonStyle.secondary)
    async def edit_snippet(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = SnippetEditModal(self.snippet_content, self.snippet_name)
        await interaction.response.send_modal(modal)
        # プレビューメッセージを削除
        await interaction.message.delete()

    @discord.ui.button(label="❌ キャンセル", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()


class AnonymousDMv2(commands.Cog):
    """スタッフDMシステム"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._http_client = httpx.AsyncClient()
        # キャッシュ
        self.active_sessions: dict[int, dict] = {}  # channel_id -> session_info
        self.user_to_channel: dict[int, int] = {}  # user_id -> channel_id
        self.category_ids: dict[int, int] = {}  # guild_id -> category_id
        self.message_map: dict[int, int] = {}  # server_msg_id -> dm_msg_id
        self.dm_to_server: dict[int, int] = {}  # dm_msg_id -> server_msg_id
        self.snippets: dict[int, dict[str, str]] = {}  # guild_id -> {name: content}

    async def cog_unload(self):
        """Cogアンロード時のクリーンアップ"""
        await self._http_client.aclose()

    async def _send_cv2(self, channel_id: int, cv2_msg: ComponentsV2Message) -> dict:
        """CV2メッセージをチャンネルに送信"""
        payload = cv2_msg.to_dict()
        endpoint = f"https://discord.com/api/v10/channels/{channel_id}/messages"
        headers = {"Authorization": f"Bot {self.bot.http.token}"}
        resp = await self._http_client.post(endpoint, headers=headers, json=payload)
        return resp.json()

    async def cog_load(self):
        """Cog読み込み時の初期化"""
        # 永続ビューを登録
        self.bot.add_view(SessionControlView())
        logger.info("AnonymousDMv2 Cogが読み込まれました")

    @commands.Cog.listener()
    async def on_ready(self):
        """Bot準備完了時にDB初期化"""
        await self._create_tables()
        await self._load_data_from_db()
        await self._register_default_snippets()
        logger.info("AnonymousDMv2 DB初期化完了")

    async def _register_default_snippets(self):
        """デフォルトスニペットを登録"""
        default_snippets = {
            # ===== 警告・注意 =====
            "warn-language": "HFS運営チームからのお知らせです。\n\nあなたの発言について、不適切な言葉遣いが確認されました。\n他のメンバーが不快に感じる表現は控えていただくようお願いします。\n\n繰り返される場合、タイムアウト等の対応を行います。",
            "warn-spam": "HFS運営チームからのお知らせです。\n\n連続投稿（スパム行為）が確認されました。\n短時間での大量投稿は他のメンバーの迷惑となります。\n\n今後はお控えください。",
            "warn-promo": "HFS運営チームからのお知らせです。\n\n許可されていない宣伝・勧誘行為が確認されました。\n当サーバーでは無断での宣伝は禁止されています。\n\n繰り返される場合、処分の対象となります。",
            "warn-nsfw": "HFS運営チームからのお知らせです。\n\n不適切なコンテンツ（NSFW）の投稿が確認されました。\n当サーバーではこのようなコンテンツは一切禁止されています。\n\nこれは重大な違反です。再発した場合はBANとなります。",
            "warn-harass": "HFS運営チームからのお知らせです。\n\n他のメンバーへの嫌がらせ・攻撃的な行為が確認されました。\n当サーバーでは全てのメンバーが快適に過ごせる環境を大切にしています。\n\nこのような行為が続く場合、サーバーからの追放を行います。",
            "warn-political": "HFS運営チームからのお知らせです。\n\n政治・宗教・センシティブな話題に関する発言が確認されました。\n当サーバーでは荒れる原因となる話題は控えていただくようお願いしています。\n\nご協力をお願いします。",
            "warn-drama": "HFS運営チームからのお知らせです。\n\n他サーバーや外部のトラブルを持ち込む行為が確認されました。\n当サーバーでは外部のドラマ・炎上案件の持ち込みは禁止しています。\n\nご注意ください。",

            # ===== タイムアウト通知 =====
            "timeout-1h": "HFS運営チームからのお知らせです。\n\nサーバールール違反により、1時間のタイムアウトを適用しました。\n\nタイムアウト中はメッセージ送信やボイスチャットへの参加ができません。\n解除後は通常通りご参加いただけます。\n\n今後はルールを守ってご利用ください。",
            "timeout-1d": "HFS運営チームからのお知らせです。\n\nサーバールール違反により、24時間のタイムアウトを適用しました。\n\n今回の違反は軽微なものではありませんでした。\n再発した場合、より重い処分を検討します。\n\n解除後は、ルールを守ってご参加ください。",
            "timeout-1w": "HFS運営チームからのお知らせです。\n\nサーバールール違反により、1週間のタイムアウトを適用しました。\n\nこれは最終警告です。\n解除後に再び違反が確認された場合、サーバーからの永久追放（BAN）となります。\n\n十分にご注意ください。",

            # ===== BAN通知 =====
            "ban-notice": "HFS運営チームからのお知らせです。\n\n重大なルール違反により、サーバーからの永久追放（BAN）を行いました。\n\n異議申し立てがある場合は、このDMにて理由をお聞かせください。\n内容を確認の上、対応を検討します。",
            "ban-appeal-accept": "異議申し立てを確認しました。\n\n検討の結果、BANを解除することにしました。\n以下の招待リンクからサーバーに再参加できます。\n\n今後は十分にルールを守ってご参加ください。\n再度の違反は即BANとなります。",
            "ban-appeal-deny": "異議申し立てを確認しました。\n\n検討の結果、今回のBANは妥当であると判断しました。\nBANの解除は行いません。\n\nご理解ください。",

            # ===== 確認・調査 =====
            "investigate": "HFS運営チームからのお知らせです。\n\nあなたに関する報告を受け、現在調査を行っています。\n\n状況を確認するため、以下についてお聞かせください：\n・該当の件についての認識\n・経緯の説明\n\nご協力をお願いします。",
            "report-received": "HFS運営チームからのお知らせです。\n\nあなたの行為について、他のメンバーから報告がありました。\n現在、内容を確認中です。\n\n何か弁明がありましたら、このDMでお知らせください。",

            # ===== 一般連絡 =====
            "rule-reminder": "HFS運営チームからのお知らせです。\n\n改めてサーバールールの確認をお願いします。\nhttps://discord.com/channels/1121697597808181248/1121697598768623680\n\nルールを守って、楽しいサーバーライフをお過ごしください。",
            "thanks-report": "HFS運営チームからのお知らせです。\n\nご報告いただいた件について、確認・対応を行いました。\nサーバーの健全な運営にご協力いただきありがとうございます。\n\n今後も何かありましたらお気軽にご報告ください。",
            "welcome-back": "HFS運営チームからのお知らせです。\n\nタイムアウト/BANが解除されました。\nおかえりなさい！\n\n今後はルールを守って、楽しくご参加ください。\n何かご不明な点があればお気軽にどうぞ。",
            "contact": "HFS運営チームです。\n\n少しお話ししたいことがあります。\nお時間のある時にご返信いただけますか？",
            "no-reply": "HFS運営チームです。\n\n先日お送りしたメッセージについて、まだご返信がありません。\nお手数ですが、ご確認の上ご返信をお願いします。\n\n返信がない場合、対応を進めさせていただく場合があります。",
        }

        # 既存のスニペットがなければ登録
        for guild_id in self.category_ids.keys():
            if guild_id not in self.snippets:
                self.snippets[guild_id] = {}

            for name, content in default_snippets.items():
                if name not in self.snippets[guild_id]:
                    try:
                        async with (await get_db_pool()).acquire() as conn:
                            await conn.execute("""
                                INSERT INTO anon_dm_snippets (guild_id, name, content, created_by)
                                VALUES ($1, $2, $3, $4)
                                ON CONFLICT (guild_id, name) DO NOTHING
                            """, guild_id, name, content, self.bot.user.id)
                        self.snippets[guild_id][name] = content
                    except Exception:
                        pass

        logger.info(f"デフォルトスニペット登録完了: {len(default_snippets)}種類")

    async def _register_default_snippets_for_guild(self, guild_id: int):
        """特定サーバーにデフォルトスニペットを登録"""
        default_snippets = {
            "warn-language": "HFS運営チームからのお知らせです。\n\nあなたの発言について、不適切な言葉遣いが確認されました。\n他のメンバーが不快に感じる表現は控えていただくようお願いします。\n\n繰り返される場合、タイムアウト等の対応を行います。",
            "warn-spam": "HFS運営チームからのお知らせです。\n\n連続投稿（スパム行為）が確認されました。\n短時間での大量投稿は他のメンバーの迷惑となります。\n\n今後はお控えください。",
            "warn-promo": "HFS運営チームからのお知らせです。\n\n許可されていない宣伝・勧誘行為が確認されました。\n当サーバーでは無断での宣伝は禁止されています。\n\n繰り返される場合、処分の対象となります。",
            "warn-nsfw": "HFS運営チームからのお知らせです。\n\n不適切なコンテンツ（NSFW）の投稿が確認されました。\n当サーバーではこのようなコンテンツは一切禁止されています。\n\nこれは重大な違反です。再発した場合はBANとなります。",
            "warn-harass": "HFS運営チームからのお知らせです。\n\n他のメンバーへの嫌がらせ・攻撃的な行為が確認されました。\n当サーバーでは全てのメンバーが快適に過ごせる環境を大切にしています。\n\nこのような行為が続く場合、サーバーからの追放を行います。",
            "warn-political": "HFS運営チームからのお知らせです。\n\n政治・宗教・センシティブな話題に関する発言が確認されました。\n当サーバーでは荒れる原因となる話題は控えていただくようお願いしています。\n\nご協力をお願いします。",
            "warn-drama": "HFS運営チームからのお知らせです。\n\n他サーバーや外部のトラブルを持ち込む行為が確認されました。\n当サーバーでは外部のドラマ・炎上案件の持ち込みは禁止しています。\n\nご注意ください。",
            "timeout-1h": "HFS運営チームからのお知らせです。\n\nサーバールール違反により、1時間のタイムアウトを適用しました。\n\nタイムアウト中はメッセージ送信やボイスチャットへの参加ができません。\n解除後は通常通りご参加いただけます。\n\n今後はルールを守ってご利用ください。",
            "timeout-1d": "HFS運営チームからのお知らせです。\n\nサーバールール違反により、24時間のタイムアウトを適用しました。\n\n今回の違反は軽微なものではありませんでした。\n再発した場合、より重い処分を検討します。\n\n解除後は、ルールを守ってご参加ください。",
            "timeout-1w": "HFS運営チームからのお知らせです。\n\nサーバールール違反により、1週間のタイムアウトを適用しました。\n\nこれは最終警告です。\n解除後に再び違反が確認された場合、サーバーからの永久追放（BAN）となります。\n\n十分にご注意ください。",
            "ban-notice": "HFS運営チームからのお知らせです。\n\n重大なルール違反により、サーバーからの永久追放（BAN）を行いました。\n\n異議申し立てがある場合は、このDMにて理由をお聞かせください。\n内容を確認の上、対応を検討します。",
            "ban-appeal-accept": "異議申し立てを確認しました。\n\n検討の結果、BANを解除することにしました。\n以下の招待リンクからサーバーに再参加できます。\n\n今後は十分にルールを守ってご参加ください。\n再度の違反は即BANとなります。",
            "ban-appeal-deny": "異議申し立てを確認しました。\n\n検討の結果、今回のBANは妥当であると判断しました。\nBANの解除は行いません。\n\nご理解ください。",
            "investigate": "HFS運営チームからのお知らせです。\n\nあなたに関する報告を受け、現在調査を行っています。\n\n状況を確認するため、以下についてお聞かせください：\n・該当の件についての認識\n・経緯の説明\n\nご協力をお願いします。",
            "report-received": "HFS運営チームからのお知らせです。\n\nあなたの行為について、他のメンバーから報告がありました。\n現在、内容を確認中です。\n\n何か弁明がありましたら、このDMでお知らせください。",
            "rule-reminder": "HFS運営チームからのお知らせです。\n\n改めてサーバールールの確認をお願いします。\nhttps://discord.com/channels/1121697597808181248/1121697598768623680\n\nルールを守って、楽しいサーバーライフをお過ごしください。",
            "thanks-report": "HFS運営チームからのお知らせです。\n\nご報告いただいた件について、確認・対応を行いました。\nサーバーの健全な運営にご協力いただきありがとうございます。\n\n今後も何かありましたらお気軽にご報告ください。",
            "welcome-back": "HFS運営チームからのお知らせです。\n\nタイムアウト/BANが解除されました。\nおかえりなさい！\n\n今後はルールを守って、楽しくご参加ください。\n何かご不明な点があればお気軽にどうぞ。",
            "contact": "HFS運営チームです。\n\n少しお話ししたいことがあります。\nお時間のある時にご返信いただけますか？",
            "no-reply": "HFS運営チームです。\n\n先日お送りしたメッセージについて、まだご返信がありません。\nお手数ですが、ご確認の上ご返信をお願いします。\n\n返信がない場合、対応を進めさせていただく場合があります。",
        }

        if guild_id not in self.snippets:
            self.snippets[guild_id] = {}

        for name, content in default_snippets.items():
            if name not in self.snippets[guild_id]:
                try:
                    async with (await get_db_pool()).acquire() as conn:
                        await conn.execute("""
                            INSERT INTO anon_dm_snippets (guild_id, name, content, created_by)
                            VALUES ($1, $2, $3, $4)
                            ON CONFLICT (guild_id, name) DO NOTHING
                        """, guild_id, name, content, self.bot.user.id)
                    self.snippets[guild_id][name] = content
                except Exception:
                    pass

        logger.info(f"Guild {guild_id}: デフォルトスニペット {len(self.snippets[guild_id])}件登録")

    async def _create_tables(self):
        """テーブル作成"""
        try:
            async with (await get_db_pool()).acquire() as conn:
                # セッションテーブル
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS anon_dm_sessions_v2 (
                        id SERIAL PRIMARY KEY,
                        guild_id BIGINT NOT NULL,
                        channel_id BIGINT NOT NULL UNIQUE,
                        target_user_id BIGINT NOT NULL,
                        created_by BIGINT NOT NULL,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        closed_at TIMESTAMP WITH TIME ZONE,
                        priority VARCHAR(20) DEFAULT 'medium',
                        tags TEXT[],
                        last_responder_id BIGINT,
                        last_activity_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        is_active BOOLEAN DEFAULT TRUE
                    )
                """)

                # 設定テーブル
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS anon_dm_config_v2 (
                        id SERIAL PRIMARY KEY,
                        guild_id BIGINT NOT NULL UNIQUE,
                        category_id BIGINT NOT NULL,
                        log_channel_id BIGINT,
                        updated_by BIGINT NOT NULL,
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # メッセージマッピングテーブル（編集・削除同期用）
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS anon_dm_message_map (
                        id SERIAL PRIMARY KEY,
                        session_id INT,
                        server_message_id BIGINT NOT NULL,
                        dm_message_id BIGINT NOT NULL,
                        direction VARCHAR(10) NOT NULL,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # メモテーブル
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS anon_dm_memos (
                        id SERIAL PRIMARY KEY,
                        session_id INT NOT NULL,
                        content TEXT NOT NULL,
                        author_id BIGINT NOT NULL,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # スニペットテーブル
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS anon_dm_snippets (
                        id SERIAL PRIMARY KEY,
                        guild_id BIGINT NOT NULL,
                        name VARCHAR(50) NOT NULL,
                        content TEXT NOT NULL,
                        created_by BIGINT NOT NULL,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(guild_id, name)
                    )
                """)

                # メッセージログテーブル
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS anon_dm_messages_v2 (
                        id SERIAL PRIMARY KEY,
                        session_id INT,
                        direction VARCHAR(10) NOT NULL,
                        content TEXT,
                        author_id BIGINT NOT NULL,
                        has_attachment BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    )
                """)

            logger.info("匿名DM v2 テーブル作成完了")
        except Exception as e:
            logger.error(f"テーブル作成エラー: {e}")

    async def _load_data_from_db(self):
        """データ読み込み"""
        try:
            async with (await get_db_pool()).acquire() as conn:
                # アクティブセッション
                sessions = await conn.fetch("""
                    SELECT id, channel_id, target_user_id, priority, last_responder_id
                    FROM anon_dm_sessions_v2 WHERE is_active = TRUE
                """)
                for row in sessions:
                    self.active_sessions[row['channel_id']] = {
                        'id': row['id'],
                        'user_id': row['target_user_id'],
                        'priority': row['priority'],
                        'last_responder': row['last_responder_id'],
                    }
                    self.user_to_channel[row['target_user_id']] = row['channel_id']

                # カテゴリ設定
                configs = await conn.fetch("SELECT guild_id, category_id FROM anon_dm_config_v2")
                for row in configs:
                    self.category_ids[row['guild_id']] = row['category_id']

                # スニペット
                snippets = await conn.fetch("SELECT guild_id, name, content FROM anon_dm_snippets")
                for row in snippets:
                    if row['guild_id'] not in self.snippets:
                        self.snippets[row['guild_id']] = {}
                    self.snippets[row['guild_id']][row['name']] = row['content']

                # メッセージマッピング（最新1000件）
                mappings = await conn.fetch("""
                    SELECT server_message_id, dm_message_id, direction
                    FROM anon_dm_message_map ORDER BY id DESC LIMIT 1000
                """)
                for row in mappings:
                    self.message_map[row['server_message_id']] = row['dm_message_id']
                    self.dm_to_server[row['dm_message_id']] = row['server_message_id']

            logger.info(f"匿名DM v2 データ読み込み完了: {len(self.active_sessions)}セッション")
        except Exception as e:
            logger.error(f"データ読み込みエラー: {e}")

    # ========== コマンドグループ ==========

    staff_dm = app_commands.Group(name="staff-dm", description="スタッフDMシステム")

    @staff_dm.command(name="setup", description="スタッフDMのカテゴリを設定")
    @app_commands.describe(category="チャンネルを作成するカテゴリ")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_category(
        self,
        interaction: discord.Interaction,
        category: discord.CategoryChannel,
    ):
        """カテゴリ設定"""
        try:
            async with (await get_db_pool()).acquire() as conn:
                await conn.execute("""
                    INSERT INTO anon_dm_config_v2 (guild_id, category_id, updated_by)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (guild_id)
                    DO UPDATE SET category_id = $2, updated_by = $3, updated_at = CURRENT_TIMESTAMP
                """, interaction.guild_id, category.id, interaction.user.id)

            self.category_ids[interaction.guild_id] = category.id

            # デフォルトスニペットを登録
            await self._register_default_snippets_for_guild(interaction.guild_id)

            await interaction.response.send_message(
                f"✅ スタッフDMカテゴリを {category.mention} に設定しました\n"
                f"📝 デフォルトスニペット {len(self.snippets.get(interaction.guild_id, {}))}件を登録しました",
                ephemeral=True,
            )
        except Exception as e:
            logger.error(f"カテゴリ設定エラー: {e}")
            await interaction.response.send_message(f"❌ エラー: {e}", ephemeral=True)

    @staff_dm.command(name="start", description="ユーザーとのスタッフDMを開始")
    @app_commands.describe(user="DMを送るユーザー", reason="対応理由")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def start_dm(
        self,
        interaction: discord.Interaction,
        user: discord.User,
        reason: str = None,
    ):
        """セッション開始"""
        guild_id = interaction.guild_id

        category_id = self.category_ids.get(guild_id)
        if not category_id:
            await interaction.response.send_message(
                "❌ 先に `/staff-dm setup` でカテゴリを設定してください",
                ephemeral=True,
            )
            return

        if user.id in self.user_to_channel:
            existing = self.bot.get_channel(self.user_to_channel[user.id])
            if existing:
                await interaction.response.send_message(
                    f"⚠️ 既存セッション: {existing.mention}",
                    ephemeral=True,
                )
                return

        await interaction.response.defer(ephemeral=True)

        try:
            category = interaction.guild.get_channel(category_id)
            if not category:
                await interaction.followup.send("❌ カテゴリが見つかりません")
                return

            # チャンネル作成
            channel = await interaction.guild.create_text_channel(
                name=f"🟡dm-{user.name[:15]}",
                category=category,
                topic=f"👤 {user} ({user.id}) | 📋 {reason or '理由なし'} | 🎫 開始者: {interaction.user}",
            )

            # DB保存
            async with (await get_db_pool()).acquire() as conn:
                row = await conn.fetchrow("""
                    INSERT INTO anon_dm_sessions_v2
                    (guild_id, channel_id, target_user_id, created_by)
                    VALUES ($1, $2, $3, $4) RETURNING id
                """, guild_id, channel.id, user.id, interaction.user.id)
                session_id = row['id']

            # キャッシュ更新
            self.active_sessions[channel.id] = {
                'id': session_id,
                'user_id': user.id,
                'priority': 'medium',
                'last_responder': None,
            }
            self.user_to_channel[user.id] = channel.id

            # セッション情報パネル（CV2）
            cv2_msg = ComponentsV2Message()

            # メイン情報
            info_container = Container(color=0x5865F2)
            info_container.add(TextDisplay("# 📨 Staff DM Session"))
            info_container.add(Separator())
            info_container.add(TextDisplay(f"**👤 対象:** {user.mention} (`{user.id}`)"))
            info_container.add(TextDisplay(f"**🎫 開始者:** {interaction.user.mention}"))
            info_container.add(TextDisplay(f"**📋 理由:** {reason or '指定なし'}"))
            info_container.add(Separator())
            info_container.add(TextDisplay(
                "**💡 使い方**\n"
                "• このチャンネルでメッセージ → DMに送信\n"
                "• `!!メモ内容` → 内部メモ（相手に見えない）\n"
                "• `!!snippet 名前` → 定型文を送信\n"
                "• メッセージを編集/削除 → DM側も同期"
            ))
            # ボタンをCV2に追加
            info_container.add(Separator())
            info_container.add(ActionRow([
                Button("📝 メモ追加", "anon_dm_memo", ButtonStyle.SECONDARY),
                Button("📊 統計", "anon_dm_stats", ButtonStyle.SECONDARY),
                Button("🔒 終了", "anon_dm_close", ButtonStyle.DANGER),
            ]))
            cv2_msg.add(info_container)

            # スニペット一覧（CV2内）
            guild_snippets = self.snippets.get(interaction.guild_id, {})
            if guild_snippets:
                snippet_container = Container(color=0x57F287)
                snippet_container.add(TextDisplay("# 📝 スニペット一覧"))
                snippet_container.add(Separator())

                categories = {
                    "⚠️ 警告": [n for n in guild_snippets if n.startswith("warn-")],
                    "⏰ タイムアウト": [n for n in guild_snippets if n.startswith("timeout-")],
                    "🔨 BAN": [n for n in guild_snippets if n.startswith("ban-")],
                    "🔍 調査": [n for n in guild_snippets if n in ["investigate", "report-received"]],
                    "📢 一般": [n for n in guild_snippets if n in ["rule-reminder", "thanks-report", "welcome-back", "contact", "no-reply"]],
                }

                for cat_name, names in categories.items():
                    if names:
                        snippet_list = " / ".join([f"`{n}`" for n in names])
                        snippet_container.add(TextDisplay(f"**{cat_name}:** {snippet_list}"))

                snippet_container.add(Separator())
                snippet_container.add(TextDisplay("-# `!!snippet 名前` で送信"))
                cv2_msg.add(snippet_container)

            await self._send_cv2(channel.id, cv2_msg)
            # Viewは別途送信（永続ビュー用）
            await channel.send(view=SessionControlView())

            # 相手に初回メッセージを送信
            try:
                welcome_embed = discord.Embed(
                    title="📨 HFS Staff DM System",
                    description=(
                        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                        "こんにちは！\n"
                        "HFS運営チームからのダイレクトメッセージです。\n\n"
                        "このDMでは運営スタッフとやり取りができます。\n"
                        "ご質問やご連絡がありましたら、このDMに返信してください。\n\n"
                        "━━━━━━━━━━━━━━━━━━━━━━"
                    ),
                    color=discord.Color.blue(),
                )
                welcome_embed.set_footer(text="HFS Staff Team")
                await user.send(embed=welcome_embed)
                await channel.send("📤 初回メッセージを送信しました", delete_after=10)
            except discord.Forbidden:
                await channel.send("⚠️ 初回メッセージを送信できませんでした（DM無効化の可能性）")

            await interaction.followup.send(f"✅ セッション開始: {channel.mention}")
            logger.info(f"スタッフDMセッション開始: {user} (Session: {session_id})")

        except Exception as e:
            logger.error(f"セッション開始エラー: {e}")
            await interaction.followup.send(f"❌ エラー: {e}")

    @staff_dm.command(name="snippet", description="スニペット（定型文）を管理")
    @app_commands.describe(action="操作", name="スニペット名")
    @app_commands.choices(action=[
        app_commands.Choice(name="一覧", value="list"),
        app_commands.Choice(name="追加", value="add"),
        app_commands.Choice(name="削除", value="delete"),
    ])
    async def manage_snippet(
        self,
        interaction: discord.Interaction,
        action: str,
        name: str = None,
    ):
        """スニペット管理"""
        guild_id = interaction.guild_id
        guild_snippets = self.snippets.get(guild_id, {})

        if action == "list":
            if not guild_snippets:
                await interaction.response.send_message("📝 スニペットはありません", ephemeral=True)
                return

            # カテゴリ分けして表示
            categories = {
                "⚠️ 警告": [],
                "⏰ タイムアウト": [],
                "🔨 BAN": [],
                "🔍 調査": [],
                "📢 一般": [],
                "📝 その他": [],
            }

            for sname, content in guild_snippets.items():
                if sname.startswith("warn-"):
                    categories["⚠️ 警告"].append((sname, content))
                elif sname.startswith("timeout-"):
                    categories["⏰ タイムアウト"].append((sname, content))
                elif sname.startswith("ban-"):
                    categories["🔨 BAN"].append((sname, content))
                elif sname in ["investigate", "report-received"]:
                    categories["🔍 調査"].append((sname, content))
                elif sname in ["rule-reminder", "thanks-report", "welcome-back", "contact", "no-reply"]:
                    categories["📢 一般"].append((sname, content))
                else:
                    categories["📝 その他"].append((sname, content))

            # CV2で表示
            await interaction.response.defer(ephemeral=True)

            cv2_msg = ComponentsV2Message()
            container = Container(color=0x5865F2)

            container.add(TextDisplay("# 📝 スニペット一覧"))
            container.add(TextDisplay("使い方: `!!snippet 名前` でDMに送信"))
            container.add(Separator())

            for cat_name, items in categories.items():
                if items:
                    snippet_list = "\n".join([f"• `{n}` - {c[:50]}..." for n, c in items])
                    container.add(TextDisplay(f"**{cat_name}**\n{snippet_list}"))
                    container.add(Separator(divider=False))

            cv2_msg.add(container)
            await send_components_v2_followup(interaction, cv2_msg)

        elif action == "add":
            await interaction.response.send_modal(SnippetModal())

        elif action == "delete":
            if not name or name not in guild_snippets:
                await interaction.response.send_message("❌ スニペットが見つかりません", ephemeral=True)
                return

            async with (await get_db_pool()).acquire() as conn:
                await conn.execute(
                    "DELETE FROM anon_dm_snippets WHERE guild_id = $1 AND name = $2",
                    guild_id, name,
                )
            del self.snippets[guild_id][name]
            await interaction.response.send_message(f"✅ スニペット `{name}` を削除しました", ephemeral=True)

    @staff_dm.command(name="list", description="アクティブなセッション一覧")
    async def list_sessions(self, interaction: discord.Interaction):
        """セッション一覧"""
        guild_id = interaction.guild_id

        try:
            async with (await get_db_pool()).acquire() as conn:
                sessions = await conn.fetch("""
                    SELECT channel_id, target_user_id, priority, created_at, last_activity_at
                    FROM anon_dm_sessions_v2
                    WHERE guild_id = $1 AND is_active = TRUE
                    ORDER BY
                        CASE priority
                            WHEN 'urgent' THEN 1
                            WHEN 'high' THEN 2
                            WHEN 'medium' THEN 3
                            WHEN 'low' THEN 4
                        END,
                        last_activity_at DESC
                """, guild_id)

            if not sessions:
                await interaction.response.send_message("📝 アクティブなセッションはありません", ephemeral=True)
                return

            priority_emoji = {'urgent': '🔴', 'high': '🟠', 'medium': '🟡', 'low': '🟢'}

            embed = discord.Embed(title="📋 Staff DM Sessions", color=discord.Color.blue())

            for s in sessions[:15]:
                channel = self.bot.get_channel(s['channel_id'])
                try:
                    user = await self.bot.fetch_user(s['target_user_id'])
                    user_text = str(user)
                except Exception:
                    user_text = f"ID: {s['target_user_id']}"

                embed.add_field(
                    name=f"{priority_emoji.get(s['priority'], '⚪')} {user_text}",
                    value=f"{channel.mention if channel else 'チャンネル不明'}\n最終: {s['last_activity_at'].strftime('%m/%d %H:%M')}",
                    inline=True,
                )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"セッション一覧エラー: {e}")
            await interaction.response.send_message(f"❌ エラー: {e}", ephemeral=True)

    # ========== イベントリスナー ==========

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """メッセージ処理"""
        if message.author.bot:
            return

        # サーバーチャンネル → DM
        if message.guild and message.channel.id in self.active_sessions:
            # 内部メモコマンド
            if message.content.startswith("!!"):
                content = message.content[2:].strip()
                if content.startswith("snippet "):
                    await self._send_snippet(message, content[8:].strip())
                else:
                    await self._add_memo_from_message(message, content)
                return

            await self._forward_to_dm(message)
            return

        # DM → サーバーチャンネル
        if isinstance(message.channel, discord.DMChannel):
            if message.author.id in self.user_to_channel:
                await self._forward_to_channel(message)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        """メッセージ編集の同期"""
        if before.author.bot or before.content == after.content:
            return

        # サーバー → DM編集同期
        if before.guild and before.channel.id in self.active_sessions:
            dm_msg_id = self.message_map.get(before.id)
            if dm_msg_id:
                await self._sync_edit_to_dm(after, dm_msg_id)

        # DM → サーバー編集通知（相手が編集した場合）
        if isinstance(before.channel, discord.DMChannel) and not before.author.bot:
            if before.author.id in self.user_to_channel:
                await self._notify_dm_edit(before, after)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        """メッセージ削除の同期"""
        if message.author.bot:
            return

        # サーバー → DM削除同期
        if message.guild and message.channel.id in self.active_sessions:
            dm_msg_id = self.message_map.get(message.id)
            if dm_msg_id:
                await self._sync_delete_to_dm(message, dm_msg_id)

        # DM → サーバー削除通知（相手が削除した場合）
        if isinstance(message.channel, discord.DMChannel) and not message.author.bot:
            if message.author.id in self.user_to_channel:
                await self._notify_dm_delete(message)

    @commands.Cog.listener()
    async def on_typing(self, channel: discord.abc.Messageable, user: discord.User, when: datetime):
        """タイピング通知"""
        # DMでのタイピング → サーバーチャンネルに通知
        if isinstance(channel, discord.DMChannel) and not user.bot:
            if user.id in self.user_to_channel:
                server_channel = self.bot.get_channel(self.user_to_channel[user.id])
                if server_channel:
                    await server_channel.typing()

    # ========== ヘルパーメソッド ==========

    async def _forward_to_dm(self, message: discord.Message):
        """サーバー → DM転送（普通のテキストメッセージで送信）"""
        session = self.active_sessions[message.channel.id]
        user_id = session['user_id']

        try:
            user = await self.bot.fetch_user(user_id)

            # 普通のテキストメッセージとして送信
            content = message.content or ""

            # 添付ファイル
            files = []
            for att in message.attachments:
                try:
                    files.append(await att.to_file())
                except Exception:
                    content += f"\n📎 添付: {att.url}"

            # DM送信
            dm_msg = await user.send(content=content or "（メッセージなし）", files=files or None)

            # マッピング保存
            self.message_map[message.id] = dm_msg.id
            async with (await get_db_pool()).acquire() as conn:
                await conn.execute("""
                    INSERT INTO anon_dm_message_map (session_id, server_message_id, dm_message_id, direction)
                    VALUES ($1, $2, $3, 'outgoing')
                """, session['id'], message.id, dm_msg.id)

            # 対応者更新
            await self._update_last_responder(message.channel.id, message.author.id)

            await message.add_reaction("✅")

        except discord.Forbidden:
            await message.reply("❌ DMを送信できません（DM無効化の可能性）")
        except Exception as e:
            logger.error(f"DM転送エラー: {e}")
            await message.add_reaction("❌")

    async def _forward_to_channel(self, message: discord.Message):
        """DM → サーバー転送（CV2で表示）"""
        channel_id = self.user_to_channel[message.author.id]
        channel = self.bot.get_channel(channel_id)

        if not channel:
            return

        try:
            # CV2で表示
            cv2_msg = ComponentsV2Message()
            container = Container(color=0x57F287)  # 緑色

            container.add(TextDisplay(f"## 💬 {message.author.display_name} からの返信"))
            container.add(Separator())
            container.add(TextDisplay(message.content or "*内容なし*"))

            # 返信引用
            if message.reference and message.reference.resolved:
                ref = message.reference.resolved
                if ref.author.id == self.bot.user.id:
                    ref_text = ref.content[:150] if ref.content else ""
                    if ref_text:
                        container.add(Separator())
                        container.add(TextDisplay(f"↩️ **返信先:** {ref_text}..."))

            cv2_msg.add(container)
            await self._send_cv2(channel_id, cv2_msg)

            # 添付ファイルは別メッセージで送信
            files = []
            for att in message.attachments:
                try:
                    files.append(await att.to_file())
                except Exception:
                    pass
            if files:
                server_msg = await channel.send(files=files)
            else:
                server_msg = await channel.fetch_message(channel.last_message_id)

            # マッピング保存
            self.dm_to_server[message.id] = server_msg.id
            session = self.active_sessions.get(channel_id)
            if session:
                async with (await get_db_pool()).acquire() as conn:
                    await conn.execute("""
                        INSERT INTO anon_dm_message_map (session_id, server_message_id, dm_message_id, direction)
                        VALUES ($1, $2, $3, 'incoming')
                    """, session['id'], server_msg.id, message.id)

            await message.add_reaction("📨")

            # 最終アクティビティ更新
            await self._update_activity(channel_id)

        except Exception as e:
            logger.error(f"チャンネル転送エラー: {e}")

    async def _sync_edit_to_dm(self, message: discord.Message, dm_msg_id: int):
        """編集同期（サーバー→DM）"""
        try:
            session = self.active_sessions[message.channel.id]
            user = await self.bot.fetch_user(session['user_id'])
            dm_channel = user.dm_channel or await user.create_dm()
            dm_msg = await dm_channel.fetch_message(dm_msg_id)

            # 普通のテキストメッセージとして編集
            await dm_msg.edit(content=message.content + "\n*(編集済み)*")
            await message.add_reaction("✏️")
        except Exception as e:
            logger.error(f"編集同期エラー: {e}")

    async def _sync_delete_to_dm(self, message: discord.Message, dm_msg_id: int):
        """削除同期（サーバー→DM）"""
        try:
            session = self.active_sessions[message.channel.id]
            user = await self.bot.fetch_user(session['user_id'])
            dm_channel = user.dm_channel or await user.create_dm()
            dm_msg = await dm_channel.fetch_message(dm_msg_id)
            await dm_msg.delete()
        except Exception as e:
            logger.error(f"削除同期エラー: {e}")

    async def _notify_dm_edit(self, before: discord.Message, after: discord.Message):
        """DM編集をサーバーに通知（CV2で表示）"""
        channel_id = self.user_to_channel.get(before.author.id)
        if not channel_id:
            return

        try:
            cv2_msg = ComponentsV2Message()
            container = Container(color=0xFEE75C)  # 黄色

            container.add(TextDisplay(f"## ✏️ {before.author.display_name} がメッセージを編集しました"))
            container.add(Separator())
            container.add(TextDisplay(f"**編集前:**\n{before.content[:500] or '*内容なし*'}{'...' if len(before.content) > 500 else ''}"))
            container.add(Separator())
            container.add(TextDisplay(f"**編集後:**\n{after.content[:500] or '*内容なし*'}{'...' if len(after.content) > 500 else ''}"))

            cv2_msg.add(container)
            await self._send_cv2(channel_id, cv2_msg)
        except Exception as e:
            logger.error(f"DM編集通知エラー: {e}")

    async def _notify_dm_delete(self, message: discord.Message):
        """DM削除をサーバーに通知（CV2で表示）"""
        channel_id = self.user_to_channel.get(message.author.id)
        if not channel_id:
            return

        try:
            cv2_msg = ComponentsV2Message()
            container = Container(color=0xED4245)  # 赤色

            container.add(TextDisplay(f"## 🗑️ {message.author.display_name} がメッセージを削除しました"))
            container.add(Separator())
            container.add(TextDisplay(f"**削除された内容:**\n{message.content[:1000] or '*内容なし*'}{'...' if len(message.content) > 1000 else ''}"))

            # 添付ファイルがあった場合
            if message.attachments:
                files_text = "\n".join([f"• {a.filename}" for a in message.attachments])
                container.add(Separator())
                container.add(TextDisplay(f"**📎 添付ファイル:**\n{files_text}"))

            cv2_msg.add(container)
            await self._send_cv2(channel_id, cv2_msg)
        except Exception as e:
            logger.error(f"DM削除通知エラー: {e}")

    async def _add_memo_from_message(self, message: discord.Message, content: str):
        """メッセージからメモ追加"""
        if not content:
            await message.reply("❌ メモ内容を入力してください: `!!メモ内容`", delete_after=5)
            return

        session = self.active_sessions.get(message.channel.id)
        if not session:
            return

        try:
            async with (await get_db_pool()).acquire() as conn:
                await conn.execute("""
                    INSERT INTO anon_dm_memos (session_id, content, author_id)
                    VALUES ($1, $2, $3)
                """, session['id'], content, message.author.id)

            await message.delete()
            await message.channel.send(
                f"📝 **内部メモ** by {message.author.mention}\n>>> {content}",
                delete_after=30,
            )
        except Exception as e:
            logger.error(f"メモ追加エラー: {e}")

    async def _send_snippet(self, message: discord.Message, name: str):
        """スニペットプレビュー表示"""
        session = self.active_sessions.get(message.channel.id)
        if not session:
            return

        guild_snippets = self.snippets.get(message.guild.id, {})
        content = guild_snippets.get(name)

        if not content:
            await message.reply(f"❌ スニペット `{name}` が見つかりません", delete_after=5)
            return

        # プレビュー表示（送信前確認）
        await message.delete()
        embed = discord.Embed(
            title=f"📝 スニペット: `{name}`",
            description=f">>> {content[:1500]}{'...' if len(content) > 1500 else ''}",
            color=discord.Color.blue(),
        )
        embed.set_footer(text="送信前に内容を確認してください")

        await message.channel.send(
            embed=embed,
            view=SnippetPreviewView(name, content),
        )

    async def send_snippet_content(self, interaction: discord.Interaction, content: str, snippet_name: str):
        """スニペット内容をDMに送信（プレビュー後）"""
        session = self.active_sessions.get(interaction.channel_id)
        if not session:
            await interaction.response.send_message("❌ セッションが見つかりません", ephemeral=True)
            return

        try:
            # DMに送信
            user = await self.bot.fetch_user(session['user_id'])
            dm_msg = await user.send(content)

            # マッピング保存
            async with (await get_db_pool()).acquire() as conn:
                await conn.execute("""
                    INSERT INTO anon_dm_message_map (session_id, server_message_id, dm_message_id, direction)
                    VALUES ($1, $2, $3, 'outgoing')
                """, session['id'], interaction.message.id if interaction.message else 0, dm_msg.id)

            # サーバー側に通知
            cv2_msg = ComponentsV2Message()
            container = Container(color=0x57F287)
            container.add(TextDisplay(f"## ✅ スニペット送信完了: `{snippet_name}`"))
            container.add(Separator())
            container.add(TextDisplay(f"-# by {interaction.user.mention}"))
            cv2_msg.add(container)
            await self._send_cv2(interaction.channel_id, cv2_msg)

            # 対応者更新
            await self._update_last_responder(interaction.channel_id, interaction.user.id)

            await interaction.response.send_message("✅ 送信しました", ephemeral=True, delete_after=3)

        except Exception as e:
            logger.error(f"スニペット送信エラー: {e}")
            await interaction.response.send_message(f"❌ 送信エラー: {e}", ephemeral=True)

    async def _update_last_responder(self, channel_id: int, user_id: int):
        """対応者更新"""
        if channel_id in self.active_sessions:
            self.active_sessions[channel_id]['last_responder'] = user_id
            async with (await get_db_pool()).acquire() as conn:
                await conn.execute("""
                    UPDATE anon_dm_sessions_v2
                    SET last_responder_id = $1, last_activity_at = CURRENT_TIMESTAMP
                    WHERE channel_id = $2
                """, user_id, channel_id)

    async def _update_activity(self, channel_id: int):
        """アクティビティ更新"""
        async with (await get_db_pool()).acquire() as conn:
            await conn.execute("""
                UPDATE anon_dm_sessions_v2
                SET last_activity_at = CURRENT_TIMESTAMP
                WHERE channel_id = $1
            """, channel_id)

    # ========== ボタン/セレクト コールバック ==========

    async def set_priority(self, interaction: discord.Interaction, priority: str):
        """優先度設定"""
        channel_id = interaction.channel_id
        if channel_id not in self.active_sessions:
            await interaction.response.send_message("❌ セッションが見つかりません", ephemeral=True)
            return

        emoji_map = {'urgent': '🔴', 'high': '🟠', 'medium': '🟡', 'low': '🟢'}

        self.active_sessions[channel_id]['priority'] = priority
        async with (await get_db_pool()).acquire() as conn:
            await conn.execute(
                "UPDATE anon_dm_sessions_v2 SET priority = $1 WHERE channel_id = $2",
                priority, channel_id,
            )

        # チャンネル名更新
        channel = interaction.channel
        new_name = f"{emoji_map[priority]}dm-{channel.name.split('-', 1)[-1]}"
        await channel.edit(name=new_name)

        await interaction.response.send_message(f"✅ 優先度を {emoji_map[priority]} に設定", ephemeral=True)

    async def add_memo(self, interaction: discord.Interaction, content: str):
        """メモ追加（モーダルから）"""
        session = self.active_sessions.get(interaction.channel_id)
        if not session:
            await interaction.response.send_message("❌ セッションが見つかりません", ephemeral=True)
            return

        async with (await get_db_pool()).acquire() as conn:
            await conn.execute("""
                INSERT INTO anon_dm_memos (session_id, content, author_id)
                VALUES ($1, $2, $3)
            """, session['id'], content, interaction.user.id)

        await interaction.response.send_message(
            f"📝 **内部メモ追加**\n>>> {content}",
            ephemeral=False,
        )

    async def show_session_stats(self, interaction: discord.Interaction):
        """セッション統計"""
        session = self.active_sessions.get(interaction.channel_id)
        if not session:
            await interaction.response.send_message("❌ セッションが見つかりません", ephemeral=True)
            return

        async with (await get_db_pool()).acquire() as conn:
            # メッセージ数
            msg_stats = await conn.fetchrow("""
                SELECT
                    COUNT(*) FILTER (WHERE direction = 'outgoing') as sent,
                    COUNT(*) FILTER (WHERE direction = 'incoming') as received
                FROM anon_dm_message_map WHERE session_id = $1
            """, session['id'])

            # メモ数
            memo_count = await conn.fetchval(
                "SELECT COUNT(*) FROM anon_dm_memos WHERE session_id = $1",
                session['id'],
            )

            # セッション情報
            session_info = await conn.fetchrow("""
                SELECT created_at, last_activity_at, created_by
                FROM anon_dm_sessions_v2 WHERE id = $1
            """, session['id'])

        embed = discord.Embed(title="📊 セッション統計", color=discord.Color.blue())
        embed.add_field(name="📤 送信", value=f"{msg_stats['sent']}件", inline=True)
        embed.add_field(name="📥 受信", value=f"{msg_stats['received']}件", inline=True)
        embed.add_field(name="📝 メモ", value=f"{memo_count}件", inline=True)
        embed.add_field(
            name="⏰ 開始",
            value=session_info['created_at'].strftime('%Y/%m/%d %H:%M'),
            inline=True,
        )
        embed.add_field(
            name="🕐 最終",
            value=session_info['last_activity_at'].strftime('%Y/%m/%d %H:%M'),
            inline=True,
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def close_session_button(self, interaction: discord.Interaction):
        """セッション終了（ボタンから）"""
        channel_id = interaction.channel_id
        if channel_id not in self.active_sessions:
            await interaction.response.send_message("❌ セッションが見つかりません", ephemeral=True)
            return

        session = self.active_sessions[channel_id]
        user_id = session['user_id']

        # 相手に終了メッセージを送信
        try:
            user = await self.bot.fetch_user(user_id)
            await user.send(
                "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "本件の対応を終了させていただきます。\n"
                "ご協力ありがとうございました。\n\n"
                "今後も何かありましたら、お気軽にご連絡ください。\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━"
            )
        except Exception:
            pass  # DM送信失敗は無視

        async with (await get_db_pool()).acquire() as conn:
            await conn.execute("""
                UPDATE anon_dm_sessions_v2
                SET is_active = FALSE, closed_at = CURRENT_TIMESTAMP
                WHERE channel_id = $1
            """, channel_id)

        del self.active_sessions[channel_id]
        if user_id in self.user_to_channel:
            del self.user_to_channel[user_id]

        await interaction.response.send_message("✅ セッションを終了しました。終了メッセージを送信しました。\nチャンネルは手動で削除してください。")

    async def save_snippet(self, interaction: discord.Interaction, name: str, content: str):
        """スニペット保存"""
        guild_id = interaction.guild_id

        async with (await get_db_pool()).acquire() as conn:
            await conn.execute("""
                INSERT INTO anon_dm_snippets (guild_id, name, content, created_by)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (guild_id, name) DO UPDATE SET content = $3
            """, guild_id, name.lower(), content, interaction.user.id)

        if guild_id not in self.snippets:
            self.snippets[guild_id] = {}
        self.snippets[guild_id][name.lower()] = content

        await interaction.response.send_message(f"✅ スニペット `{name}` を保存しました", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(AnonymousDMv2(bot))
