import asyncio
from enum import Enum
from typing import Any, Optional

import discord
from discord import app_commands
from discord.ext import commands

from config.setting import get_settings
from utils.commands_help import is_guild, is_owner, log_commands
from utils.db_manager import db
from utils.logging import setup_logging

logger = setup_logging()
settings = get_settings()

class InterviewStatus(Enum):
    """インタビュー状態の列挙型"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    PUBLISHED = "published"
    CANCELLED = "cancelled"

class HFSVoices(commands.Cog):
    """
    HFS Voices - メンバーインタビュー企画自動化システム

    HFSメンバーの多様性を可視化し、コミュニティの魅力を外部発信するための
    インタビュー自動化機能を提供します。
    """

    # インタビュー質問テンプレート
    INTERVIEW_QUESTIONS = [
        "お名前（HN）と、HFSではどんな活動をしていますか？",
        "HFSにはいつ頃参加しましたか？（覚えている範囲でOKです）",
        "普段よく使っているチャンネルや好きな場所はありますか？",
        "HFSに参加したきっかけや理由を教えてください。",
        "HFSに参加してよかったと思うこと・印象に残っている出来事はありますか？",
        "サーバーの雰囲気や文化で、好きだなと思うところがあれば教えてください。",
        "あなたにとって「ホロライブ」の存在とはどんなものですか？",
        "「ホロライブを好きでよかったな」と思う瞬間はありますか？",
        "HFSをまだ知らない人に、一言で紹介するとしたら？",
        "最後に、HFSのメンバーやnote読者に向けてメッセージをお願いします！"
    ]

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.active_interviews: dict[int, dict[str, Any]] = {}
        logger.info("HFS Voices インタビュー機能を初期化しました")
        # データベーステーブルを即座作成を試行
        asyncio.create_task(self._delayed_table_creation())
        # 永続化Viewを登録
        self.bot.add_view(InterviewControlView())
        self.bot.add_view(QuestionResponseView())

    async def cog_load(self) -> None:
        """Cogロード時の初期化処理"""
        try:
            await self._ensure_database_tables()
            logger.info("HFS Voices データベーステーブルを初期化しました")
        except Exception as e:
            logger.error(f"HFS Voices データベース初期化エラー: {e}")
            raise

    async def _ensure_database_tables(self) -> None:
        """必要なデータベーステーブルを作成"""
        try:
            logger.info("HFS Voicesテーブル作成を開始します...")

            if not hasattr(db, 'pool') or db.pool is None:
                logger.error("データベースプールが初期化されていません")
                return

            async with db.pool.acquire() as conn:
                # hfs_interviewsテーブルを作成
                logger.info("hfs_interviewsテーブルを作成中...")
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS hfs_interviews (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT NOT NULL,
                        interviewer_id BIGINT NOT NULL,
                        status VARCHAR(20) NOT NULL DEFAULT 'pending',
                        thread_id BIGINT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        started_at TIMESTAMP,
                        completed_at TIMESTAMP,
                        published_at TIMESTAMP,
                        note_url VARCHAR(500)
                    )
                """)

                # ユニーク制約を別途追加（PostgreSQLの部分インデックスを使用）
                logger.info("ユニーク制約を作成中...")
                await conn.execute("""
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_hfs_interviews_user_active_status
                    ON hfs_interviews (user_id, status)
                    WHERE status IN ('pending', 'in_progress')
                """)

                # hfs_interview_responsesテーブルを作成
                logger.info("hfs_interview_responsesテーブルを作成中...")
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS hfs_interview_responses (
                        id SERIAL PRIMARY KEY,
                        interview_id INTEGER REFERENCES hfs_interviews(id) ON DELETE CASCADE,
                        question_number INTEGER NOT NULL,
                        question_text TEXT NOT NULL,
                        response_text TEXT,
                        answered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(interview_id, question_number)
                    )
                """)

                logger.info("HFS Voicesテーブル作成完了")

        except Exception as e:
            logger.error(f"データベーステーブル作成エラー: {e}")
            raise

    async def _delayed_table_creation(self) -> None:
        """データベース初期化後にテーブル作成を実行"""
        try:
            # Botがレディ状態になるまで待機
            await self.bot.wait_until_ready()
            # データベース接続が初期化されるまで少し待機
            await asyncio.sleep(2)
            await self._ensure_database_tables()
        except Exception as e:
            logger.error(f"遅延テーブル作成エラー: {e}")

    async def _restore_active_interviews(self) -> None:
        """アクティブなインタビューを復元"""
        try:
            if not hasattr(db, 'pool') or db.pool is None:
                logger.warning("データベースプールが初期化されていません")
                return

            async with db.pool.acquire() as conn:
                # アクティブなインタビューを取得
                active_interviews = await conn.fetch(
                    "SELECT id, user_id, thread_id, status FROM hfs_interviews WHERE status IN ('pending', 'in_progress')"
                )

                for interview in active_interviews:
                    try:
                        # チャンネルを取得
                        channel = self.bot.get_channel(interview['thread_id'])
                        if channel:
                            # 進行中のインタビューにViewを再追加
                            if interview['status'] == 'pending':
                                InterviewControlView(interview['id'], interview['user_id'])
                                # 既存のメッセージを検索してViewを再追加（必要に応じて）
                                logger.info(f"インタビュー {interview['id']} のView復元準備完了")
                            elif interview['status'] == 'in_progress':
                                # 最後の未回答質問を取得
                                last_question = await conn.fetchrow(
                                    "SELECT question_number FROM hfs_interview_responses WHERE interview_id = $1 AND response_text IS NULL ORDER BY question_number LIMIT 1",
                                    interview['id']
                                )
                                if last_question:
                                    QuestionResponseView(interview['id'], last_question['question_number'])
                                    logger.info(f"インタビュー {interview['id']} の質問 {last_question['question_number']} View復元準備完了")

                    except Exception as e:
                        logger.error(f"インタビュー {interview['id']} の復元エラー: {e}")

                logger.info(f"アクティブなインタビュー {len(active_interviews)} 件の復元を完了")

        except Exception as e:
            logger.error(f"アクティブインタビュー復元エラー: {e}")

    @commands.hybrid_command(name="interview", description="HFS Voices インタビューを開始")
    @app_commands.describe(
        user="インタビュー対象のユーザー",
        method="インタビュー方式（dm: DM, thread: スレッド）"
    )
    @is_owner()
    @log_commands()
    @is_guild()
    async def start_interview(
        self,
        ctx: commands.Context,
        user: discord.Member,
        method: str = "thread"
    ) -> None:
        """
        インタビューを開始するコマンド

        Args:
            ctx: Discord コンテキスト
            user: インタビュー対象ユーザー
            method: インタビュー方式（dm または thread）
        """
        await ctx.defer()
        # 権限チェック
        if not await self._check_interviewer_permissions(ctx.author):
            await ctx.send(
                "❌ インタビューを開始する権限がありません。",
                ephemeral=True
            )
            return

        # アクティブなインタビューのチェック
        if await self._has_active_interview(user.id):
            await ctx.send(
                f"❌ {user.display_name} さんは既にアクティブなインタビューがあります。",
                ephemeral=True
            )
            return

        try:
            # 新しいインタビューをデータベースに作成
            interview_id = await self._create_interview(user.id, ctx.author.id)

            if method == "thread":
                await self._start_thread_interview(interview_id, user, ctx.author, ctx)
            else:
                # DM方式は将来実装
                await ctx.send(
                    "🚧 DM方式は現在開発中です。スレッド方式をご利用ください。",
                    ephemeral=True
                )
                return

            # 成功メッセージは_start_thread_interview内で送信される

        except Exception as e:
            logger.error(f"インタビュー開始エラー: {e}")
            await ctx.send(
                "❌ インタビューチャンネルの作成中にエラーが発生しました。",
                ephemeral=True
            )
            return

    @commands.hybrid_command(name="interview_list", description="インタビュー一覧を表示")
    @is_owner()
    @log_commands()
    @is_guild()
    async def interview_list(self, ctx: commands.Context):
        """過去20件のインタビューを一覧表示"""
        try:
            async with db.pool.acquire() as conn:
                interviews = await conn.fetch(
                    """
                    SELECT i.id, i.user_id, i.interviewer_id, i.status, i.created_at, i.completed_at, i.note_url,
                           COUNT(r.id) as total_responses,
                           COUNT(CASE WHEN r.response_text IS NOT NULL THEN 1 END) as answered_count
                    FROM hfs_interviews i
                    LEFT JOIN hfs_interview_responses r ON i.id = r.interview_id
                    GROUP BY i.id, i.user_id, i.interviewer_id, i.status, i.created_at, i.completed_at, i.note_url
                    ORDER BY i.created_at DESC
                    LIMIT 20
                    """
                )

            if not interviews:
                await ctx.send(
                    "📋 インタビューデータが見つかりませんでした。",
                    ephemeral=True
                )
                return

            embed = discord.Embed(
                title="📋 HFS Voices インタビュー一覧",
                description=f"過去20件のインタビュー（全{len(interviews)}件）",
                color=0x5865F2
            )

            for interview in interviews:
                # ユーザー情報を取得
                user = ctx.guild.get_member(interview['user_id'])
                user_name = user.display_name if user else f"ユーザーID: {interview['user_id']}"

                # ステータス絵文字
                status_emoji = {
                    "pending": "⏳",
                    "in_progress": "🔄",
                    "completed": "✅",
                    "published": "📰",
                    "cancelled": "❌"
                }.get(interview['status'], "❓")

                # 進捗情報
                progress = f"{interview['answered_count']}/{interview['total_responses']}"

                # 完了日またはnote URL
                extra_info = ""
                if interview['note_url']:
                    extra_info = f"\n🔗 [note記事]({interview['note_url']})"
                elif interview['completed_at']:
                    extra_info = f"\n📅 完了: {interview['completed_at'].strftime('%Y/%m/%d %H:%M')}"

                embed.add_field(
                    name=f"{status_emoji} ID: {interview['id']} - {user_name}",
                    value=f"ステータス: {interview['status']}\n回答進捗: {progress}問{extra_info}",
                    inline=True
                )

            await ctx.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"インタビュー一覧取得エラー: {e}")
            await ctx.send(
                "❌ インタビュー一覧の取得中にエラーが発生しました。",
                ephemeral=True
            )

    @commands.hybrid_command(name="interview_view", description="インタビュー詳細を表示")
    @is_owner()
    @log_commands()
    @is_guild()
    async def interview_view(self, ctx: commands.Context, interview_id: int):
        """特定のインタビューの詳細を表示"""
        try:
            async with db.pool.acquire() as conn:
                # インタビュー基本情報を取得
                interview = await conn.fetchrow(
                    "SELECT * FROM hfs_interviews WHERE id = $1",
                    interview_id
                )

                if not interview:
                    await ctx.send(
                        f"❌ インタビューID {interview_id} が見つかりませんでした。",
                        ephemeral=True
                    )
                    return

                # 回答データを取得
                responses = await conn.fetch(
                    "SELECT * FROM hfs_interview_responses WHERE interview_id = $1 ORDER BY question_number",
                    interview_id
                )

            # ユーザー情報を取得
            user = ctx.guild.get_member(interview['user_id'])
            interviewer = ctx.guild.get_member(interview['interviewer_id'])

            user_name = user.display_name if user else f"ユーザーID: {interview['user_id']}"
            interviewer_name = interviewer.display_name if interviewer else f"ユーザーID: {interview['interviewer_id']}"

            # 基本情報embed
            embed = discord.Embed(
                title=f"🎤 インタビュー詳細 (ID: {interview_id})",
                description=f"**対象者:** {user_name}\n**実施者:** {interviewer_name}",
                color=0x5865F2
            )

            # ステータス情報
            answered_count = sum(1 for r in responses if r['response_text'])
            total_count = len(responses)

            embed.add_field(
                name="📊 基本情報",
                value=f"ステータス: {interview['status']}\n"
                     f"回答進捗: {answered_count}/{total_count}問\n"
                     f"作成日: {interview['created_at'].strftime('%Y/%m/%d %H:%M')}",
                inline=True
            )

            if interview['completed_at']:
                embed.add_field(
                    name="🎯 完了情報",
                    value=f"完了日: {interview['completed_at'].strftime('%Y/%m/%d %H:%M')}",
                    inline=True
                )

            if interview['note_url']:
                embed.add_field(
                    name="📰 note記事",
                    value=f"[記事を見る]({interview['note_url']})",
                    inline=True
                )

            # 最初の5問の回答を表示
            embed.add_field(
                name="💬 回答内容（最初の5問）",
                value="以下に表示します",
                inline=False
            )

            for _i, response in enumerate(responses[:5]):
                if response['response_text']:
                    question_text = self.INTERVIEW_QUESTIONS[response['question_number'] - 1]
                    answer_text = response['response_text']

                    # 長い回答は切り詰める
                    if len(answer_text) > 200:
                        answer_text = answer_text[:200] + "..."

                    embed.add_field(
                        name=f"Q{response['question_number']}: {question_text[:50]}{'...' if len(question_text) > 50 else ''}",
                        value=answer_text,
                        inline=False
                    )
                else:
                    question_text = self.INTERVIEW_QUESTIONS[response['question_number'] - 1]
                    embed.add_field(
                        name=f"Q{response['question_number']}: {question_text[:50]}{'...' if len(question_text) > 50 else ''}",
                        value="未回答",
                        inline=False
                    )

            if len(responses) > 5:
                embed.set_footer(text=f"※ 全{len(responses)}問中、最初の5問のみ表示。完全版は /interview_export で取得可能")

            await ctx.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"インタビュー詳細取得エラー: {e}")
            await ctx.send(
                "❌ インタビュー詳細の取得中にエラーが発生しました。",
                ephemeral=True
            )

    @commands.hybrid_command(name="interview_export", description="インタビューをテキストファイルでエクスポート")
    @is_owner()
    @log_commands()
    @is_guild()
    async def interview_export(self, ctx: commands.Context, interview_id: int):
        """インタビューをテキストファイルでエクスポート"""
        try:
            async with db.pool.acquire() as conn:
                # インタビュー基本情報を取得
                interview = await conn.fetchrow(
                    "SELECT * FROM hfs_interviews WHERE id = $1",
                    interview_id
                )

                if not interview:
                    await ctx.send(
                        f"❌ インタビューID {interview_id} が見つかりませんでした。",
                        ephemeral=True
                    )
                    return

                # 回答データを取得
                responses = await conn.fetch(
                    "SELECT * FROM hfs_interview_responses WHERE interview_id = $1 ORDER BY question_number",
                    interview_id
                )

            # ユーザー情報を取得
            user = ctx.guild.get_member(interview['user_id'])
            user_name = user.display_name if user else f"ユーザーID: {interview['user_id']}"

            # テキストファイル内容を生成
            content_lines = [
                "# HFS Voices インタビュー結果",
                "",
                f"**対象者:** {user_name}",
                f"**インタビューID:** {interview_id}",
                f"**実施日:** {interview['created_at'].strftime('%Y年%m月%d日 %H:%M')}",
                f"**ステータス:** {interview['status']}",
                "",
                "---",
                ""
            ]

            for response in responses:
                question_text = self.INTERVIEW_QUESTIONS[response['question_number'] - 1]
                content_lines.append(f"## Q{response['question_number']}: {question_text}")
                content_lines.append("")

                if response['response_text']:
                    content_lines.append(response['response_text'])
                else:
                    content_lines.append("[未回答]")

                content_lines.append("")
                content_lines.append("---")
                content_lines.append("")

            # ファイル内容を結合
            file_content = "\n".join(content_lines)

            # ファイル名を生成
            safe_username = "".join(c for c in user_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            filename = f"interview_{interview_id}_{safe_username}.txt"

            # ファイルとして送信
            import io
            file_buffer = io.BytesIO(file_content.encode('utf-8'))
            file = discord.File(file_buffer, filename=filename)

            embed = discord.Embed(
                title="📄 インタビューエクスポート完了",
                description=f"インタビューID {interview_id} のデータをテキストファイルで出力しました。",
                color=0x00D4AA
            )

            await ctx.send(embed=embed, file=file, ephemeral=True)
            logger.info(f"インタビューエクスポート完了: {interview_id}")

        except Exception as e:
            logger.error(f"インタビューエクスポートエラー: {e}")
            await ctx.send(
                "❌ インタビューのエクスポート中にエラーが発生しました。",
                ephemeral=True
            )

    async def _check_interviewer_permissions(self, user: discord.Member) -> bool:
        """インタビュー実行権限をチェック"""
        # 管理者または特定のロールを持つユーザーのみ許可
        if user.guild_permissions.administrator:
            return True

        # 特定のロール名でチェック（設定で変更可能にする）
        allowed_roles = ["HFS運営", "スタッフ", "管理者"]
        user_roles = [role.name for role in user.roles]

        return any(role in allowed_roles for role in user_roles)

    async def _has_active_interview(self, user_id: int) -> bool:
        """ユーザーがアクティブなインタビューを持っているかチェック"""
        try:
            async with db.pool.acquire() as conn:
                result = await conn.fetchrow(
                    "SELECT id FROM hfs_interviews WHERE user_id = $1 AND status IN ('pending', 'in_progress')",
                    user_id
                )
                return result is not None
        except Exception as e:
            logger.error(f"アクティブインタビューチェックエラー: {e}")
            return False

    async def _get_interview_category(self, guild: discord.Guild) -> Optional[discord.CategoryChannel]:
        """インタビュー専用カテゴリーを取得"""
        try:
            # 設定ファイルからカテゴリーIDを取得（設定されていない場合は名前で検索）
            category_id = getattr(settings, 'interview_category_id', None)
            if category_id:
                category = guild.get_channel(category_id)
                if isinstance(category, discord.CategoryChannel):
                    return category

            # 名前でカテゴリーを検索
            category_names = ["🎙️┣Voice of HFS", "インタビュー", "interview"]
            for name in category_names:
                category = discord.utils.get(guild.categories, name=name)
                if category:
                    return category

            logger.warning("インタビュー専用カテゴリーが見つかりません")
            return None

        except Exception as e:
            logger.error(f"カテゴリー取得エラー: {e}")
            return None

    async def _create_interview(self, user_id: int, interviewer_id: int) -> int:
        """新しいインタビューをデータベースに作成"""
        try:
            async with db.pool.acquire() as conn:
                interview_id = await conn.fetchval(
                    "INSERT INTO hfs_interviews (user_id, interviewer_id) VALUES ($1, $2) RETURNING id",
                    user_id, interviewer_id
                )

                # 質問をテンプレートから追加
                for i, question in enumerate(self.INTERVIEW_QUESTIONS, 1):
                    await conn.execute(
                        "INSERT INTO hfs_interview_responses (interview_id, question_number, question_text) VALUES ($1, $2, $3)",
                        interview_id, i, question
                    )

                return interview_id
        except Exception as e:
            logger.error(f"インタビュー作成エラー: {e}")
            raise

    async def _start_thread_interview(
        self,
        interview_id: int,
        user: discord.Member,
        interviewer: discord.Member,
        ctx: commands.Context
    ) -> None:
        """専用カテゴリーにチャンネルを作成してインタビューを開始"""
        try:
            # 専用カテゴリーを取得
            category = await self._get_interview_category(ctx.guild)
            if not category:
                await ctx.send(
                    "❌ インタビュー専用カテゴリーが見つかりません。\n"
                    "'HFS Voices' という名前のカテゴリーを作成してください。",
                    ephemeral=True
                )
                return

            # インタビュー用チャンネルを作成
            channel = await ctx.guild.create_text_channel(
                name=f"🎤-{user.display_name}-interview",
                category=category,
                topic=f"HFS Voices インタビュー - {user.display_name} さん",
                overwrites={
                    ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                    user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                    interviewer: discord.PermissionOverwrite(read_messages=True, send_messages=True)
                }
            )

            # チャンネルIDをデータベースに保存
            async with db.pool.acquire() as conn:
                await conn.execute(
                    "UPDATE hfs_interviews SET thread_id = $1, status = 'in_progress', started_at = CURRENT_TIMESTAMP WHERE id = $2",
                    channel.id, interview_id
                )

            # 初期メッセージを送信
            embed = discord.Embed(
                title="🎤 HFS Voices インタビュー",
                description=f"こんにちは、{user.mention} さん！\n\nHFS Voices インタビューへようこそ！",
                color=0x00D4AA
            )

            embed.add_field(
                name="📝 このインタビューについて",
                value="HFS Voices は、メンバーの皆さんの声を届ける公式インタビュー企画です。\n"
                      "いただいた回答は、公式noteの「Voices of HFS」マガジンで紹介させていただく予定です。",
                inline=False
            )

            embed.add_field(
                name="🤖 進行方法",
                value="このチャンネルで質問を順番にお送りしますので、お時間のある時にご回答ください。\n"
                      "全10問の質問をご用意しています。",
                inline=False
            )

            view = InterviewControlView(interview_id, user.id)
            mention = user.mention
            await channel.send(embed=embed, view=view, content=mention)

            # 成功メッセージを送信
            await ctx.send(
                f"✅ {user.display_name} さんのインタビューを開始しました！\n"
                f"📍 専用チャンネル: {channel.mention}",
                ephemeral=True
            )

            logger.info(f"インタビューチャンネルを開始: {user.id} (チャンネル: {channel.id})")

        except Exception as e:
            logger.error(f"インタビューチャンネル開始エラー: {e}")
            await ctx.send(
                "❌ インタビューチャンネルの作成中にエラーが発生しました。",
                ephemeral=True
            )
            raise

class InterviewControlView(discord.ui.View):
    """インタビュー制御用のビュー"""

    def __init__(self, interview_id: int = None, user_id: int = None):
        super().__init__(timeout=None)
        self.interview_id = interview_id
        self.user_id = user_id

    @discord.ui.button(label="📝 インタビュー開始", style=discord.ButtonStyle.primary, emoji="📝", custom_id="hfs_voices:start_interview")
    async def start_questions(self, interaction: discord.Interaction, button: discord.ui.Button):
        """質問を開始するボタン"""
        # カスタムIDから情報を復元
        if not self.interview_id or not self.user_id:
            await self._restore_from_database(interaction)

        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ このボタンはインタビュー対象者のみが使用できます。",
                ephemeral=True
            )
            return

        button.disabled = True
        await interaction.response.edit_message(view=self)

        # 最初の質問を送信
        await self._send_next_question(interaction, 1)

    async def _restore_from_database(self, interaction: discord.Interaction) -> None:
        """データベースから情報を復元"""
        try:
            async with db.pool.acquire() as conn:
                result = await conn.fetchrow(
                    "SELECT id, user_id FROM hfs_interviews WHERE thread_id = $1 AND status IN ('pending', 'in_progress')",
                    interaction.channel.id
                )
                if result:
                    self.interview_id = result['id']
                    self.user_id = result['user_id']
                    logger.info(f"インタビュー情報を復元: {self.interview_id}, {self.user_id}")
        except Exception as e:
            logger.error(f"インタビュー情報復元エラー: {e}")

    async def _send_next_question(self, interaction: discord.Interaction, question_number: int):
        """次の質問を送信"""
        try:
            async with db.pool.acquire() as conn:
                question_data = await conn.fetchrow(
                    "SELECT question_text FROM hfs_interview_responses WHERE interview_id = $1 AND question_number = $2",
                    self.interview_id, question_number
                )

                if question_data:
                    embed = discord.Embed(
                        title=f"質問 {question_number}/10",
                        description=question_data['question_text'],
                        color=0x00D4AA
                    )

                    view = QuestionResponseView(self.interview_id, question_number)
                    await interaction.followup.send(embed=embed, view=view)

        except Exception as e:
            logger.error(f"質問送信エラー: {e}")

class QuestionResponseView(discord.ui.View):
    """質問回答用のビュー"""

    def __init__(self, interview_id: int = None, question_number: int = None):
        super().__init__(timeout=None)  # 永続化のためタイムアウト無効
        self.interview_id = interview_id
        self.question_number = question_number

    @discord.ui.button(label="💬 回答する", style=discord.ButtonStyle.secondary, emoji="💬", custom_id="hfs_voices:answer_question")
    async def answer_question(self, interaction: discord.Interaction, button: discord.ui.Button):
        """回答モーダルを開く"""
        # カスタムIDから情報を復元
        if not self.interview_id or not self.question_number:
            await self._restore_from_database(interaction)

        # 既存の回答を取得（修正時にプリセット用）
        existing_answer = ""
        try:
            async with db.pool.acquire() as conn:
                result = await conn.fetchrow(
                    "SELECT response_text FROM hfs_interview_responses WHERE interview_id = $1 AND question_number = $2",
                    self.interview_id, self.question_number
                )
                if result and result['response_text']:
                    existing_answer = result['response_text']
        except Exception as e:
            logger.warning(f"既存回答取得エラー: {e}")

        modal = AnswerModal(self.interview_id, self.question_number, existing_answer)
        await interaction.response.send_modal(modal)

    async def _restore_from_database(self, interaction: discord.Interaction) -> None:
        """データベースから情報を復元"""
        try:
            async with db.pool.acquire() as conn:
                # チャンネルから最新の未回答質問を取得
                result = await conn.fetchrow(
                    """SELECT i.id, r.question_number
                       FROM hfs_interviews i
                       JOIN hfs_interview_responses r ON i.id = r.interview_id
                       WHERE i.thread_id = $1 AND r.response_text IS NULL
                       ORDER BY r.question_number LIMIT 1""",
                    interaction.channel.id
                )
                if result:
                    self.interview_id = result['id']
                    self.question_number = result['question_number']
                    logger.info(f"質問回答情報を復元: {self.interview_id}, {self.question_number}")
        except Exception as e:
            logger.error(f"質問回答情報復元エラー: {e}")

class AnswerModal(discord.ui.Modal):
    """回答入力用のモーダル"""

    def __init__(self, interview_id: int, question_number: int, default_value: str = ""):
        super().__init__(title=f"質問 {question_number} の回答")
        self.interview_id = interview_id
        self.question_number = question_number

        # 質問テキストを取得（1-basedインデックスを0-basedに変換）
        try:
            question_text = HFSVoices.INTERVIEW_QUESTIONS[question_number - 1]
        except IndexError:
            question_text = "未知の質問"

        self.answer_input = discord.ui.TextInput(
            label=f"質問 {question_number}",
            placeholder=question_text,
            style=discord.TextStyle.paragraph,
            max_length=1000,
            required=True,
            default=default_value  # 修正時に前回の内容をプリセット
        )
        self.add_item(self.answer_input)

    async def on_submit(self, interaction: discord.Interaction):
        """回答を提出（確認画面へ）"""
        try:
            answer_text = self.answer_input.value.strip()

            if not answer_text:
                await interaction.response.send_message(
                    "❌ 回答が空です。再度入力してください。",
                    ephemeral=True
                )
                return

            # 確認画面を表示（DB保存はまだしない）
            try:
                question_text = HFSVoices.INTERVIEW_QUESTIONS[self.question_number - 1]
            except IndexError:
                question_text = "未知の質問"

            embed = discord.Embed(
                title=f"💬 質問 {self.question_number} の回答確認",
                description=f"**質問:** {question_text}",
                color=0x5865F2
            )

            # 回答が長い場合は切り詰めて表示
            display_answer = answer_text
            if len(answer_text) > 800:
                display_answer = answer_text[:800] + "..."

            embed.add_field(
                name="あなたの回答",
                value=display_answer,
                inline=False
            )

            embed.set_footer(text="この内容でよろしいでしょうか？")

            # 確認ビューを作成
            view = AnswerConfirmView(
                interview_id=self.interview_id,
                question_number=self.question_number,
                answer_text=answer_text
            )

            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        except Exception as e:
            logger.error(f"回答確認エラー: {e}")
            await interaction.response.send_message(
                "❌ 回答の保存中にエラーが発生しました。",
                ephemeral=True
            )

    async def _send_next_question(self, interaction: discord.Interaction, question_number: int):
        """次の質問を送信"""
        try:
            async with db.pool.acquire() as conn:
                question_data = await conn.fetchrow(
                    "SELECT question_text FROM hfs_interview_responses WHERE interview_id = $1 AND question_number = $2",
                    self.interview_id, question_number
                )

                if question_data:
                    embed = discord.Embed(
                        title=f"質問 {question_number}/10",
                        description=question_data['question_text'],
                        color=0x00D4AA
                    )

                    view = QuestionResponseView(self.interview_id, question_number)
                    await interaction.followup.send(embed=embed, view=view)

        except Exception as e:
            logger.error(f"質問送信エラー: {e}")

    async def _complete_interview(self, interaction: discord.Interaction):
        """インタビュー完了処理"""
        try:
            # ステータスを完了に更新
            async with db.pool.acquire() as conn:
                await conn.execute(
                    "UPDATE hfs_interviews SET status = 'completed', completed_at = CURRENT_TIMESTAMP WHERE id = $1",
                    self.interview_id
                )

            embed = discord.Embed(
                title="🎉 インタビュー完了",
                description="すべての質問にお答えいただき、ありがとうございました！\n"
                           "回答内容は運営チームで確認し、note記事として準備いたします。",
                color=0x00D4AA
            )

            await interaction.followup.send(embed=embed)
            logger.info(f"インタビュー完了: {self.interview_id}")

        except Exception as e:
            logger.error(f"インタビュー完了処理エラー: {e}")

class AnswerConfirmView(discord.ui.View):
    """回答確認用のビュー"""

    def __init__(self, interview_id: int, question_number: int, answer_text: str):
        super().__init__(timeout=300)  # 5分でタイムアウト
        self.interview_id = interview_id
        self.question_number = question_number
        self.answer_text = answer_text

    @discord.ui.button(label="✅ この内容で確定", style=discord.ButtonStyle.success, emoji="✅")
    async def confirm_answer(self, interaction: discord.Interaction, button: discord.ui.Button):
        """回答を確定してDBに保存"""
        try:
            # データベースに回答を保存（上書き）
            async with db.pool.acquire() as conn:
                await conn.execute(
                    """UPDATE hfs_interview_responses
                       SET response_text = $1, answered_at = CURRENT_TIMESTAMP
                       WHERE interview_id = $2 AND question_number = $3""",
                    self.answer_text, self.interview_id, self.question_number
                )

                # 次の未回答質問をチェック
                next_question = await conn.fetchrow(
                    """SELECT question_number, question_text
                       FROM hfs_interview_responses
                       WHERE interview_id = $1 AND response_text IS NULL
                       ORDER BY question_number LIMIT 1""",
                    self.interview_id
                )

            # 確定メッセージ
            embed = discord.Embed(
                title="✅ 回答を保存しました！",
                description=f"質問 {self.question_number} の回答が正常に保存されました。",
                color=0x00D4AA
            )

            # ボタンを無効化
            for item in self.children:
                item.disabled = True

            await interaction.response.edit_message(embed=embed, view=self)

            # 次の質問へ進むかチェック
            if next_question:
                # 次の質問へ
                await self._send_next_question(interaction, next_question['question_number'], next_question['question_text'])
            else:
                # 全て完了
                await self._complete_interview(interaction)

        except Exception as e:
            logger.error(f"回答確定エラー: {e}")
            await interaction.response.send_message(
                "❌ 回答の保存中にエラーが発生しました。",
                ephemeral=True
            )

    @discord.ui.button(label="📝 修正する", style=discord.ButtonStyle.secondary, emoji="📝")
    async def edit_answer(self, interaction: discord.Interaction, button: discord.ui.Button):
        """回答を修正（モーダルに前回の入力内容をプリセット）"""
        try:
            # 前回の入力内容をプリセットしたモーダルを表示
            modal = AnswerModal(self.interview_id, self.question_number, self.answer_text)
            await interaction.response.send_modal(modal)

        except Exception as e:
            logger.error(f"修正モーダルエラー: {e}")
            await interaction.response.send_message(
                "❌ 修正モーダルの表示中にエラーが発生しました。",
                ephemeral=True
            )

    async def _send_next_question(self, interaction: discord.Interaction, question_number: int, question_text: str):
        """次の質問を送信"""
        embed = discord.Embed(
            title=f"💬 質問 {question_number}",
            description=question_text,
            color=0x5865F2
        )

        view = QuestionResponseView(self.interview_id, question_number)
        await interaction.followup.send(embed=embed, view=view)

    async def _complete_interview(self, interaction: discord.Interaction):
        """インタビュー完了処理"""
        # インタビューステータスを完了に更新
        async with db.pool.acquire() as conn:
            await conn.execute(
                "UPDATE hfs_interviews SET status = 'completed', completed_at = CURRENT_TIMESTAMP WHERE id = $1",
                self.interview_id
            )

        embed = discord.Embed(
            title="🎉 インタビュー完了！",
            description="すべての質問にお答えいただき、ありがとうございました！\n"
                       "回答内容は運営チームで確認し、note記事として準備いたします。\n\n"
                       "このチャンネルはオーナーとインタビュー対象者のみ閲覧可能です。\n"
                       "インタビューされた発言等はお控えください。",
            color=0x00D4AA
        )

        await interaction.followup.send(embed=embed)
        logger.info(f"インタビュー完了: {self.interview_id}")

async def setup(bot: commands.Bot) -> None:
    """Cogをセットアップ"""
    await bot.add_cog(HFSVoices(bot))
