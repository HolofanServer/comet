import json
import os
import asyncio
import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
from typing import Optional, List
from openai import AsyncOpenAI
from config.setting import get_settings
from utils.logging import setup_logging
from utils.commands_help import is_guild_app, is_owner_app, log_commands

# 設定を取得
settings = get_settings()
OPENAI_API_KEY = settings.etc_api_openai_api_key

# OpenAIクライアントを初期化（非同期）
async_client_ai = AsyncOpenAI(api_key=OPENAI_API_KEY)

# ロガーを取得
logger = setup_logging("D")

class UserAnalyzer(commands.Cog):
    """特定のユーザーのメッセージを収集し、傾向や好みを分析するCog"""

    def __init__(self, bot):
        self.bot = bot
        self.analysis_tasks = {}  # 進行中の分析タスクを追跡

    @app_commands.command(
        name="user_analyze",
        description="特定のユーザーのメッセージを収集し、AIで傾向分析を行います"
    )
    @app_commands.describe(
        user="分析対象のユーザー",
        channel_limit="検索するチャンネル数の上限（指定しない場合はすべて）",
        message_limit="収集するメッセージ数の上限（大きな値は処理に時間がかかります）"
    )
    @is_guild_app()
    @is_owner_app()
    @log_commands()
    async def analyze_user(
        self, 
        interaction: discord.Interaction, 
        user: discord.Member,
        channel_limit: Optional[int] = None,
        message_limit: Optional[int] = None
    ):
        """特定のユーザーのメッセージを収集し、AIで傾向を分析します"""
        
        logger.info(f"ユーザー分析コマンドが実行されました: 対象ユーザー {user.name} (ID: {user.id}), 実行者 {interaction.user.name}")
        
        # 権限チェック（管理者権限があるかどうか）
        if not interaction.user.guild_permissions.administrator:
            logger.warning(f"権限のないユーザーによる分析コマンドの実行試行: {interaction.user.name}")
            await interaction.response.send_message("このコマンドを使用するには管理者権限が必要です。", ephemeral=True)
            return
            
        # デフォルト値の設定
        if not message_limit or message_limit > 1000:
            message_limit = 1000
            
        # 応答を開始
        await interaction.response.send_message(f"<@{user.id}> のメッセージ収集と分析を開始します。これには時間がかかる場合があります...")
        message = await interaction.original_response()
        
        # すでに分析中のタスクがある場合はキャンセル
        if user.id in self.analysis_tasks:
            if not self.analysis_tasks[user.id].done():
                logger.info(f"既存の分析タスクをキャンセル: ユーザーID {user.id}")
                self.analysis_tasks[user.id].cancel()
        
        # 非同期で分析タスクを開始
        task = asyncio.create_task(
            self._analyze_user_messages(message, interaction.guild, user, channel_limit, message_limit)
        )
        self.analysis_tasks[user.id] = task

    @app_commands.command(
        name="user_analyze_complete",
        description="【全メッセージ収集】特定のユーザーの全メッセージを収集し、超詳細分析を行います"
    )
    @app_commands.describe(
        user="分析対象のユーザー",
        channel_limit="検索するチャンネル数の上限（指定しない場合はすべて）",
        enable_message_limit="メッセージ制限を有効にする（デフォルト：無効=全メッセージ収集）"
    )
    @is_guild_app()
    @is_owner_app()
    @log_commands()
    async def analyze_user_complete(
        self, 
        interaction: discord.Interaction, 
        user: discord.Member,
        channel_limit: Optional[int] = None,
        enable_message_limit: bool = False
    ):
        """特定のユーザーの全メッセージを収集し、超詳細分析を行います"""
        
        logger.info(f"完全分析コマンドが実行されました: 対象ユーザー {user.name} (ID: {user.id}), 実行者 {interaction.user.name}")
        
        # 権限チェック
        if not interaction.user.guild_permissions.administrator:
            logger.warning(f"権限のないユーザーによる完全分析コマンドの実行試行: {interaction.user.name}")
            await interaction.response.send_message("このコマンドを使用するには管理者権限が必要です。", ephemeral=True)
            return
            
        # 応答を開始
        if enable_message_limit:
            await interaction.response.send_message(
                f"🔍 **完全分析を開始します（制限あり）**\n"
                f"📊 対象ユーザー: <@{user.id}>\n"
                f"📈 収集モード: 制限あり（最大1000件）\n"
                f"⏱️ 処理には時間がかかります..."
            )
        else:
            await interaction.response.send_message(
                f"🔍 **完全分析を開始します（全メッセージ）**\n"
                f"📊 対象ユーザー: <@{user.id}>\n"
                f"📈 収集モード: 制限なし（全履歴）\n"
                f"⚠️ 全メッセージ収集のため、処理に相当時間がかかります..."
            )
        message = await interaction.original_response()
        
        # 既存タスクのキャンセル
        task_key = f"complete_{user.id}"
        if task_key in self.analysis_tasks:
            if not self.analysis_tasks[task_key].done():
                logger.info(f"既存の完全分析タスクをキャンセル: ユーザーID {user.id}")
                self.analysis_tasks[task_key].cancel()
        
        # 完全分析タスクを開始
        task = asyncio.create_task(
            self._analyze_user_complete_messages(
                message, interaction.guild, user, 
                channel_limit, enable_message_limit
            )
        )
        self.analysis_tasks[task_key] = task

    @app_commands.command(
        name="user_analyze_dual",
        description="特定のユーザーの分析と直近1000件のメッセージ分析を並列実行します"
    )
    @app_commands.describe(
        user="分析対象のユーザー",
        channel_limit="検索するチャンネル数の上限（指定しない場合はすべて）",
        user_message_limit="ユーザーのメッセージ収集数の上限",
        recent_message_limit="直近メッセージの収集数の上限（デフォルト1000件）"
    )
    @is_guild_app()
    @is_owner_app()
    @log_commands()
    async def analyze_user_dual(
        self, 
        interaction: discord.Interaction, 
        user: discord.Member,
        channel_limit: Optional[int] = None,
        user_message_limit: Optional[int] = None,
        recent_message_limit: Optional[int] = 1000
    ):
        """特定のユーザー分析と直近メッセージ分析を並列実行します"""
        
        logger.info(f"デュアル分析コマンドが実行されました: 対象ユーザー {user.name} (ID: {user.id}), 実行者 {interaction.user.name}")
        
        # 権限チェック
        if not interaction.user.guild_permissions.administrator:
            logger.warning(f"権限のないユーザーによるデュアル分析コマンドの実行試行: {interaction.user.name}")
            await interaction.response.send_message("このコマンドを使用するには管理者権限が必要です。", ephemeral=True)
            return
            
        # デフォルト値の設定
        if not user_message_limit or user_message_limit > 1000:
            user_message_limit = 1000
        if not recent_message_limit or recent_message_limit > 1000:
            recent_message_limit = 1000
            
        # 応答を開始
        await interaction.response.send_message(
            f"**並列分析を開始します**\n"
            f"📊 ユーザー分析: <@{user.id}> のメッセージ（最大{user_message_limit}件）\n"
            f"📈 サーバー分析: 直近のメッセージ（最大{recent_message_limit}件）\n"
            f"⏱️ これには時間がかかる場合があります..."
        )
        message = await interaction.original_response()
        
        # 既存タスクのキャンセル
        task_key = f"dual_{user.id}"
        if task_key in self.analysis_tasks:
            if not self.analysis_tasks[task_key].done():
                logger.info(f"既存のデュアル分析タスクをキャンセル: ユーザーID {user.id}")
                self.analysis_tasks[task_key].cancel()
        
        # 並列分析タスクを開始
        task = asyncio.create_task(
            self._analyze_dual_messages(
                message, interaction.guild, user, 
                channel_limit, user_message_limit, recent_message_limit
            )
        )
        self.analysis_tasks[task_key] = task

    async def _analyze_user_complete_messages(
        self, 
        message: discord.Message, 
        guild: discord.Guild, 
        user: discord.Member,
        channel_limit: Optional[int],
        enable_message_limit: bool
    ):
        """完全分析を実行するメソッド（全メッセージ収集対応）"""
        
        try:
            # 進捗更新
            await message.edit(content="🔍 **完全分析を開始しています...**\n📊 全チャンネルをスキャン中...")
            
            # 全メッセージ収集
            all_messages = await self._collect_all_user_messages(
                guild, user, channel_limit, enable_message_limit, message
            )
            
            if not all_messages:
                await message.edit(content=f"<@{user.id}> のメッセージが見つかりませんでした。")
                return
            
            # 進捗更新
            await message.edit(
                content=f"📊 **メッセージ収集完了**\n"
                       f"収集件数: {len(all_messages)}件\n"
                       f"🧠 超詳細AI分析を開始します..."
            )
            
            # 超詳細分析を実行
            analysis_result = await self._analyze_messages_with_ultra_detail(all_messages, user)
            
            # 結果の出力
            await self._output_complete_analysis_results(message, user, analysis_result, len(all_messages))
            
        except asyncio.CancelledError:
            logger.info(f"完全分析タスクがキャンセルされました: ユーザーID {user.id}")
            await message.edit(content="**完全分析がキャンセルされました。**")
            return
            
        except Exception as e:
            logger.error(f"完全分析中にエラーが発生しました: {e}")
            await message.edit(content=f"**エラー**: 完全分析中に予期しない問題が発生しました。\n```{str(e)}```")
            return

    async def _collect_all_user_messages(
        self, 
        guild: discord.Guild, 
        user: discord.Member, 
        channel_limit: Optional[int], 
        enable_message_limit: bool,
        progress_message: discord.Message
    ) -> List[dict]:
        """ユーザーの全メッセージを収集する（制限なしオプション）"""
        
        all_messages = []
        total_found = 0
        max_limit = 1000 if enable_message_limit else float('inf')
        
        # 検索対象チャンネルの取得
        text_channels = guild.text_channels
        if channel_limit and channel_limit < len(text_channels):
            text_channels = text_channels[:channel_limit]
        
        logger.info(f"全メッセージ収集開始: {len(text_channels)}チャンネル, 制限={'あり' if enable_message_limit else 'なし'}")
        
        # 各チャンネルをスキャン
        for ch_index, channel in enumerate(text_channels):
            try:
                channel_messages = []
                
                # 定期的に進捗を更新
                if ch_index % 3 == 0 or ch_index == len(text_channels) - 1:
                    await progress_message.edit(
                        content=f"🔍 **メッセージ収集中...**\n"
                               f"チャンネル: {ch_index + 1}/{len(text_channels)} ({channel.name})\n"
                               f"収集済み: {total_found}件"
                               f"{'' if not enable_message_limit else f'/{max_limit}'}"
                    )
                
                # そのチャンネルの全履歴を取得（制限なし）
                async for msg in channel.history(limit=None):
                    if msg.author.id == user.id:
                        # より詳細な情報を収集
                        message_data = {
                            "author": user.display_name,
                            "channel": channel.name,
                            "channel_id": channel.id,
                            "message_id": msg.id,
                            "timestamp": msg.created_at.isoformat(),
                            "content": msg.content or "[内容なし]",
                            "reactions": [f"{reaction.emoji}({reaction.count})" for reaction in msg.reactions],
                            "has_attachment": bool(msg.attachments),
                            "attachment_types": [att.content_type for att in msg.attachments if att.content_type],
                            "reference": msg.reference.message_id if msg.reference else None,
                            "edited_at": msg.edited_at.isoformat() if msg.edited_at else None,
                            "is_pinned": msg.pinned,
                            "mentions_count": len(msg.mentions),
                            "embeds_count": len(msg.embeds),
                            "thread_id": msg.thread.id if hasattr(msg, 'thread') and msg.thread else None
                        }
                        channel_messages.append(message_data)
                        total_found += 1
                        
                        # 制限チェック
                        if enable_message_limit and total_found >= max_limit:
                            logger.info(f"メッセージ制限に達しました: {total_found}件")
                            all_messages.extend(channel_messages)
                            return all_messages
                
                all_messages.extend(channel_messages)
                logger.info(f"チャンネル {channel.name}: {len(channel_messages)}件のメッセージ収集")
                
            except discord.Forbidden:
                logger.warning(f"チャンネル {channel.name} へのアクセス権限がありません")
                continue
            except Exception as e:
                logger.error(f"チャンネル {channel.name} でメッセージ取得に失敗: {e}")
                continue
        
        logger.info(f"ユーザー {user.name} の全メッセージ収集完了: {len(all_messages)}件")
        return all_messages

    async def _analyze_messages_with_ultra_detail(
        self, 
        messages: List[dict], 
        user: discord.Member
    ) -> str:
        """超詳細分析でメッセージを分析する"""
        
        if not messages:
            return "分析対象のメッセージが見つかりませんでした。"
        
        # より詳細な統計情報を作成
        stats = self._generate_detailed_statistics(messages)
        
        # 分析用にメッセージを整形（より詳細）
        conversation_text = self._format_messages_for_ultra_analysis(messages)
        
        # ユーザープロファイル情報（詳細版）
        user_info = {
            "name": user.name,
            "display_name": user.display_name,
            "id": user.id,
            "created_at": user.created_at.isoformat(),
            "joined_at": user.joined_at.isoformat() if user.joined_at else None,
            "roles": [role.name for role in user.roles if role.name != "@everyone"],
            "avatar": str(user.avatar.url) if user.avatar else None,
            "premium_since": user.premium_since.isoformat() if user.premium_since else None,
            "is_timed_out": user.is_timed_out() if hasattr(user, 'is_timed_out') else False,
        }
        
        # 超詳細分析用のシステムプロンプト
        system_prompt = self._get_ultra_detailed_analysis_system_prompt()
        
        # ユーザープロンプト（統計情報込み）
        user_prompt = f"""
# ユーザー情報
```json
{json.dumps(user_info, ensure_ascii=False, indent=2)}
```

# 統計サマリー
```json
{json.dumps(stats, ensure_ascii=False, indent=2)}
```

# 詳細メッセージデータ
以下は{len(messages)}件のメッセージデータです。この大量のデータを基に、超詳細で包括的な分析を行ってください。

{conversation_text[:40000]}  # APIの制限を考慮して切り詰め
"""

        try:
            # API呼び出し（より長いmax_tokensを設定）
            response = await async_client_ai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=8000  # より詳細な分析のため増量
            )
            
            analysis_text = response.choices[0].message.content
            logger.info(f"超詳細分析完了: {len(analysis_text)}文字")
            
            return analysis_text
            
        except Exception as e:
            logger.error(f"超詳細分析中にAPIエラーが発生: {e}")
            return f"分析中にエラーが発生しました: {str(e)}"

    def _generate_detailed_statistics(self, messages: List[dict]) -> dict:
        """詳細な統計情報を生成する"""
        from collections import Counter
        from datetime import datetime
        
        # 基本統計
        total_messages = len(messages)
        
        # チャンネル別統計
        channel_stats = Counter(msg['channel'] for msg in messages)
        
        # 時間帯別統計
        hour_stats = Counter()
        day_stats = Counter()
        month_stats = Counter()
        
        for msg in messages:
            try:
                dt = datetime.fromisoformat(msg['timestamp'].replace('Z', '+00:00'))
                hour_stats[dt.hour] += 1
                day_stats[dt.strftime('%A')] += 1
                month_stats[dt.strftime('%Y-%m')] += 1
            except:
                continue
        
        # メッセージ長の統計
        message_lengths = [len(msg['content']) for msg in messages if msg['content'] != "[内容なし]"]
        avg_length = sum(message_lengths) / len(message_lengths) if message_lengths else 0
        
        # リアクション統計
        total_reactions = sum(len(msg['reactions']) for msg in messages)
        
        # 添付ファイル統計
        attachment_count = sum(1 for msg in messages if msg['has_attachment'])
        
        # 返信統計
        reply_count = sum(1 for msg in messages if msg['reference'])
        
        # 編集統計
        edited_count = sum(1 for msg in messages if msg.get('edited_at'))
        
        return {
            "total_messages": total_messages,
            "channels_used": len(channel_stats),
            "most_active_channels": dict(channel_stats.most_common(5)),
            "hourly_activity": dict(hour_stats.most_common()),
            "daily_activity": dict(day_stats),
            "monthly_activity": dict(month_stats),
            "average_message_length": round(avg_length, 2),
            "total_reactions_received": total_reactions,
            "messages_with_attachments": attachment_count,
            "reply_messages": reply_count,
            "edited_messages": edited_count,
            "attachment_rate": round(attachment_count/total_messages*100, 2) if total_messages > 0 else 0,
            "reply_rate": round(reply_count/total_messages*100, 2) if total_messages > 0 else 0,
            "edit_rate": round(edited_count/total_messages*100, 2) if total_messages > 0 else 0
        }

    def _format_messages_for_ultra_analysis(self, messages: List[dict]) -> str:
        """超詳細分析用にメッセージをフォーマットする"""
        formatted = []
        
        # 最新から古い順にソート
        sorted_messages = sorted(messages, key=lambda x: x['timestamp'], reverse=True)
        
        # 詳細度を上げてフォーマット
        for i, msg in enumerate(sorted_messages[:2000]):  # 最大2000件まで詳細分析
            # メッセージの詳細情報
            author_name = msg.get("author", "不明なユーザー")
            formatted_msg = f"[{i+1}] {msg['timestamp']} #{msg['channel']} | {author_name}"
            
            # メッセージ内容
            formatted_msg += f"\n内容: {msg['content']}"
            
            # 追加情報
            extras = []
            if msg['reactions']:
                extras.append(f"リアクション: {', '.join(msg['reactions'])}")
            if msg['has_attachment']:
                types = ', '.join(msg.get('attachment_types', ['不明']))
                extras.append(f"添付: {types}")
            if msg['reference']:
                extras.append(f"返信: {msg['reference']}")
            if msg.get('edited_at'):
                extras.append(f"編集済み: {msg['edited_at']}")
            if msg.get('is_pinned'):
                extras.append("ピン留め")
            if msg.get('mentions_count', 0) > 0:
                extras.append(f"メンション: {msg['mentions_count']}人")
            if msg.get('embeds_count', 0) > 0:
                extras.append(f"埋め込み: {msg['embeds_count']}個")
                
            if extras:
                formatted_msg += f"\n補足: {' | '.join(extras)}"
                
            formatted.append(formatted_msg)
            
        return "\n\n".join(formatted)

    async def _output_complete_analysis_results(
        self, 
        message: discord.Message, 
        user: discord.Member,
        analysis_result: str,
        message_count: int
    ):
        """完全分析の結果を出力する"""
        
        try:
            # フォルダがなければ作成
            os.makedirs("cache/user_analysis", exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # 完全分析結果を保存
            if not isinstance(analysis_result, Exception) and analysis_result != "分析対象のメッセージが見つかりませんでした。":
                filename = f"cache/user_analysis/complete_analysis_{user.id}_{timestamp}.md"
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(f"# {user.display_name} の超詳細分析（完全版）\n\n")
                    f.write(f"分析日時: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}\n")
                    f.write(f"分析対象メッセージ数: {message_count}件（全履歴）\n")
                    f.write(f"分析タイプ: 超詳細分析\n\n")
                    f.write("---\n\n")
                    f.write(analysis_result)
            
            # 結果をDiscordに送信
            await message.edit(content="🎉 **超詳細分析が完了しました！結果を送信中...**")
            
            if not isinstance(analysis_result, Exception) and analysis_result != "分析対象のメッセージが見つかりませんでした。":
                # タイトルメッセージ
                await message.channel.send(
                    f"## 🔬 超詳細分析結果 (<@{user.id}>)\n"
                    f"**📊 分析対象**: {message_count}件の全メッセージ\n"
                    f"**🧠 分析レベル**: 超詳細（Complete Analysis）"
                )
                
                # 結果を分割して送信
                if len(analysis_result) > 1800:
                    chunks = [analysis_result[i:i+1800] for i in range(0, len(analysis_result), 1800)]
                    for i, chunk in enumerate(chunks):
                        await message.channel.send(f"**📋 分析結果 ({i+1}/{len(chunks)})**\n\n{chunk}")
                else:
                    await message.channel.send(analysis_result)
                
                # ファイルとして送信
                await message.channel.send(
                    f"📁 **完全分析レポート**（{message_count}件のメッセージを超詳細分析）",
                    file=discord.File(filename)
                )
            else:
                await message.channel.send(f"## 🔬 超詳細分析結果 (<@{user.id}>)\n{analysis_result}")
            
        except Exception as e:
            logger.error(f"完全分析結果出力中にエラーが発生: {e}")
            await message.channel.send(f"**エラー**: 結果出力中に問題が発生しました。\n```{str(e)}```")

    async def _analyze_dual_messages(
        self, 
        message: discord.Message, 
        guild: discord.Guild, 
        user: discord.Member,
        channel_limit: Optional[int],
        user_message_limit: int,
        recent_message_limit: int
    ):
        """並列分析を実行するメソッド"""
        
        try:
            # 進捗更新
            await message.edit(content="**並列分析を開始しています...**\n📊 ユーザーメッセージ収集中\n📈 直近メッセージ収集中")
            
            # 二つのタスクを並列実行
            user_task = asyncio.create_task(
                self._collect_user_messages(guild, user, channel_limit, user_message_limit)
            )
            recent_task = asyncio.create_task(
                self._collect_recent_messages(guild, channel_limit, recent_message_limit)
            )
            
            # 両方の結果を待つ
            user_result, recent_result = await asyncio.gather(user_task, recent_task, return_exceptions=True)
            
            # エラーチェック
            if isinstance(user_result, Exception):
                logger.error(f"ユーザーメッセージ収集でエラー: {user_result}")
                user_messages = []
            else:
                user_messages = user_result
                
            if isinstance(recent_result, Exception):
                logger.error(f"直近メッセージ収集でエラー: {recent_result}")
                recent_messages = []
            else:
                recent_messages = recent_result
            
            # 進捗更新
            await message.edit(
                content=f"**メッセージ収集完了**\n"
                       f"📊 ユーザーメッセージ: {len(user_messages)}件\n"
                       f"📈 直近メッセージ: {len(recent_messages)}件\n"
                       f"🧠 AI分析を開始します..."
            )
            
            # 両方の分析を並列実行
            user_analysis_task = asyncio.create_task(
                self._analyze_messages_with_ai(user_messages, user, analysis_type="user")
            )
            recent_analysis_task = asyncio.create_task(
                self._analyze_messages_with_ai(recent_messages, None, analysis_type="recent")
            )
            
            # 分析結果を待つ
            user_analysis, recent_analysis = await asyncio.gather(
                user_analysis_task, recent_analysis_task, return_exceptions=True
            )
            
            # 結果の処理と出力
            await self._output_dual_analysis_results(
                message, user, user_analysis, recent_analysis,
                len(user_messages), len(recent_messages)
            )
            
        except asyncio.CancelledError:
            logger.info(f"デュアル分析タスクがキャンセルされました: ユーザーID {user.id}")
            await message.edit(content="**並列分析がキャンセルされました。**")
            return
            
        except Exception as e:
            logger.error(f"デュアル分析中にエラーが発生しました: {e}")
            await message.edit(content=f"**エラー**: 並列分析中に予期しない問題が発生しました。\n```{str(e)}```")
            return

    async def _collect_user_messages(
        self, 
        guild: discord.Guild, 
        user: discord.Member, 
        channel_limit: Optional[int], 
        message_limit: int
    ) -> List[dict]:
        """特定ユーザーのメッセージを収集する"""
        
        messages = []
        found_msg_count = 0
        
        # 検索対象チャンネルの取得
        text_channels = guild.text_channels
        if channel_limit and channel_limit < len(text_channels):
            text_channels = text_channels[:channel_limit]
        
        # 各チャンネルをスキャン
        for channel in text_channels:
            try:
                async for msg in channel.history(limit=500):
                    if msg.author.id == user.id:
                        messages.append({
                            "author": user.display_name,
                            "channel": channel.name,
                            "timestamp": msg.created_at.isoformat(),
                            "content": msg.content or "[内容なし]",
                            "reactions": [f"{reaction.emoji}" for reaction in msg.reactions],
                            "has_attachment": bool(msg.attachments),
                            "reference": msg.reference.message_id if msg.reference else None
                        })
                        
                        found_msg_count += 1
                        if found_msg_count >= message_limit:
                            break
                
                if found_msg_count >= message_limit:
                    break
                    
            except discord.Forbidden:
                logger.warning(f"チャンネル {channel.name} へのアクセス権限がありません")
                continue
            except Exception as e:
                logger.error(f"チャンネル {channel.name} でメッセージ取得に失敗: {e}")
                continue
        
        logger.info(f"ユーザー {user.name} のメッセージを {len(messages)}件 収集しました")
        return messages

    async def _collect_recent_messages(
        self, 
        guild: discord.Guild, 
        channel_limit: Optional[int], 
        message_limit: int
    ) -> List[dict]:
        """直近のメッセージを収集する"""
        
        # 検索対象チャンネルの取得
        text_channels = guild.text_channels
        if channel_limit and channel_limit < len(text_channels):
            text_channels = text_channels[:channel_limit]
        
        # 各チャンネルから直近メッセージを時系列順で収集
        all_messages = []
        
        for channel in text_channels:
            try:
                async for msg in channel.history(limit=200):  # 各チャンネルから最大200件
                    if msg.content:  # 内容があるメッセージのみ
                        all_messages.append({
                            "author": msg.author.display_name,
                            "channel": channel.name,
                            "timestamp": msg.created_at.isoformat(),
                            "content": msg.content,
                            "reactions": [f"{reaction.emoji}" for reaction in msg.reactions],
                            "has_attachment": bool(msg.attachments),
                            "reference": msg.reference.message_id if msg.reference else None,
                            "created_at": msg.created_at
                        })
                        
            except discord.Forbidden:
                logger.warning(f"チャンネル {channel.name} へのアクセス権限がありません")
                continue
            except Exception as e:
                logger.error(f"チャンネル {channel.name} でメッセージ取得に失敗: {e}")
                continue
        
        # 時系列順にソートして上限まで取得
        all_messages.sort(key=lambda x: x["created_at"], reverse=True)
        messages = all_messages[:message_limit]
        
        # created_atフィールドを削除（JSONシリアライズのため）
        for msg in messages:
            del msg["created_at"]
        
        logger.info(f"直近のメッセージを {len(messages)}件 収集しました")
        return messages

    async def _analyze_messages_with_ai(
        self, 
        messages: List[dict], 
        user: Optional[discord.Member] = None, 
        analysis_type: str = "user"
    ) -> str:
        """AIでメッセージを分析する"""
        
        if not messages:
            return "分析対象のメッセージが見つかりませんでした。"
        
        # 分析用にメッセージを整形
        conversation_text = self._format_messages_for_analysis(messages)
        
        if analysis_type == "user":
            # ユーザー分析
            user_info = {
                "name": user.name,
                "display_name": user.display_name,
                "id": user.id,
                "created_at": user.created_at.isoformat(),
                "joined_at": user.joined_at.isoformat() if user.joined_at else None,
                "roles": [role.name for role in user.roles if role.name != "@everyone"],
                "avatar": str(user.avatar.url) if user.avatar else None,
            }
            
            system_prompt = self._get_analysis_system_prompt()
            user_prompt = f"""
# ユーザー情報
```json
{json.dumps(user_info, ensure_ascii=False, indent=2)}
```

# メッセージデータ
以下のメッセージデータを分析して、ユーザーの傾向を把握してください。
約{len(messages)}件のメッセージデータがあります。

{conversation_text}
"""
        else:
            # 直近メッセージ分析
            system_prompt = self._get_recent_analysis_system_prompt()
            user_prompt = f"""
# 直近メッセージ分析
以下は Discordサーバーの直近のメッセージデータです。
約{len(messages)}件のメッセージデータがあります。

サーバー全体の雰囲気、話題の傾向、活発なユーザー、コミュニティの特徴などを分析してください。

{conversation_text}
"""
        
        try:
            # API呼び出し
            response = await async_client_ai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=4000
            )
            
            analysis_text = response.choices[0].message.content
            logger.info(f"{analysis_type}分析完了: {len(analysis_text)}文字")
            
            return analysis_text
            
        except Exception as e:
            logger.error(f"{analysis_type}分析中にAPIエラーが発生: {e}")
            return f"分析中にエラーが発生しました: {str(e)}"

    async def _output_dual_analysis_results(
        self, 
        message: discord.Message, 
        user: discord.Member,
        user_analysis: str,
        recent_analysis: str,
        user_msg_count: int,
        recent_msg_count: int
    ):
        """並列分析の結果を出力する"""
        
        try:
            # フォルダがなければ作成
            os.makedirs("cache/user_analysis", exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # ユーザー分析結果を保存
            if not isinstance(user_analysis, Exception) and user_analysis != "分析対象のメッセージが見つかりませんでした。":
                user_filename = f"cache/user_analysis/user_analysis_{user.id}_{timestamp}.md"
                with open(user_filename, "w", encoding="utf-8") as f:
                    f.write(f"# {user.display_name} のユーザー分析\n\n")
                    f.write(f"分析日時: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}\n")
                    f.write(f"分析対象メッセージ数: {user_msg_count}件\n\n")
                    f.write(user_analysis)
            
            # 直近メッセージ分析結果を保存
            if not isinstance(recent_analysis, Exception) and recent_analysis != "分析対象のメッセージが見つかりませんでした。":
                recent_filename = f"cache/user_analysis/recent_analysis_{timestamp}.md"
                with open(recent_filename, "w", encoding="utf-8") as f:
                    f.write("# サーバー直近メッセージ分析\n\n")
                    f.write(f"分析日時: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}\n")
                    f.write(f"分析対象メッセージ数: {recent_msg_count}件\n\n")
                    f.write(recent_analysis)
            
            # 結果をDiscordに送信
            await message.edit(content="**並列分析が完了しました！結果を送信中...**")
            
            # ユーザー分析結果
            if not isinstance(user_analysis, Exception) and user_analysis != "分析対象のメッセージが見つかりませんでした。":
                await message.channel.send(f"## 📊 ユーザー分析結果 (<@{user.id}>)")
                if len(user_analysis) > 1900:
                    chunks = [user_analysis[i:i+1900] for i in range(0, len(user_analysis), 1900)]
                    for i, chunk in enumerate(chunks):
                        await message.channel.send(f"**ユーザー分析 ({i+1}/{len(chunks)}):**\n\n{chunk}")
                else:
                    await message.channel.send(user_analysis)
                
                # ファイルとして送信
                await message.channel.send(
                    f"ユーザー分析結果ファイル（{user_msg_count}件のメッセージを分析）",
                    file=discord.File(user_filename)
                )
            else:
                await message.channel.send(f"## 📊 ユーザー分析結果 (<@{user.id}>)\n{user_analysis}")
            
            # 直近メッセージ分析結果
            if not isinstance(recent_analysis, Exception) and recent_analysis != "分析対象のメッセージが見つかりませんでした。":
                await message.channel.send("## 📈 サーバー直近メッセージ分析結果")
                if len(recent_analysis) > 1900:
                    chunks = [recent_analysis[i:i+1900] for i in range(0, len(recent_analysis), 1900)]
                    for i, chunk in enumerate(chunks):
                        await message.channel.send(f"**直近分析 ({i+1}/{len(chunks)}):**\n\n{chunk}")
                else:
                    await message.channel.send(recent_analysis)
                
                # ファイルとして送信
                await message.channel.send(
                    f"直近メッセージ分析結果ファイル（{recent_msg_count}件のメッセージを分析）",
                    file=discord.File(recent_filename)
                )
            else:
                await message.channel.send(f"## 📈 サーバー直近メッセージ分析結果\n{recent_analysis}")
            
        except Exception as e:
            logger.error(f"結果出力中にエラーが発生: {e}")
            await message.channel.send(f"**エラー**: 結果出力中に問題が発生しました。\n```{str(e)}```")
        
    async def _analyze_user_messages(
        self, 
        message: discord.Message, 
        guild: discord.Guild, 
        user: discord.Member,
        channel_limit: Optional[int],
        message_limit: int
    ):
        """ユーザーのメッセージを非同期で収集・分析するメソッド"""
        
        try:
            await message.edit(content=f"<@{user.id}> のメッセージ収集を開始します... 🔍")
            
            # 進捗追跡用の変数
            messages = []
            channel_count = 0
            found_msg_count = 0
            
            # 検索対象チャンネルの取得
            text_channels = guild.text_channels
            if channel_limit and channel_limit < len(text_channels):
                text_channels = text_channels[:channel_limit]
                
            # 各チャンネルをスキャン
            for channel in text_channels:
                try:
                    channel_count += 1
                    logger.info(f"チャンネルをスキャン中: {channel.name} ({channel_count}/{len(text_channels)})")
                    
                    # 定期的に進捗を更新
                    if channel_count % 5 == 0 or channel_count == len(text_channels):
                        await message.edit(
                            content=f"<@{user.id}> の分析中...\n"
                                   f"チャンネル: {channel_count}/{len(text_channels)}\n"
                                   f"見つかったメッセージ: {found_msg_count}/{message_limit}"
                        )
                    
                    # チャンネルの履歴を取得
                    async for msg in channel.history(limit=500):  # 各チャンネルでの上限を設定
                        if msg.author.id == user.id:
                            # メッセージ内容を保存
                            messages.append({
                                "channel": channel.name,
                                "timestamp": msg.created_at.isoformat(),
                                "content": msg.content or "[内容なし]",  # 内容がない場合のフォールバック
                                "reactions": [f"{reaction.emoji}" for reaction in msg.reactions],
                                "has_attachment": bool(msg.attachments),
                                "reference": msg.reference.message_id if msg.reference else None
                            })
                            
                            found_msg_count += 1
                            
                            # メッセージ制限に達したら終了
                            if found_msg_count >= message_limit:
                                break
                    
                    # メッセージ制限に達したら終了
                    if found_msg_count >= message_limit:
                        logger.info(f"メッセージ制限({message_limit})に達しました")
                        break
                        
                except discord.Forbidden:
                    logger.warning(f"チャンネル {channel.name} へのアクセス権限がありません")
                    continue
                except Exception as e:
                    logger.error(f"チャンネル {channel.name} でメッセージ取得に失敗: {e}")
                    continue
            
            # メッセージが見つからなかった場合
            if not messages:
                await message.edit(content=f"<@{user.id}> のメッセージが見つかりませんでした。")
                return
            
            # 進捗更新
            await message.edit(
                content=f"<@{user.id}> のメッセージを {found_msg_count}件 収集しました。分析を開始します... 🧠"
            )
            
            # 分析用にメッセージを整形
            conversation_text = self._format_messages_for_analysis(messages)
            
            # ユーザープロファイル情報を追加
            user_info = {
                "name": user.name,
                "display_name": user.display_name,
                "id": user.id,
                "created_at": user.created_at.isoformat(),
                "joined_at": user.joined_at.isoformat() if user.joined_at else None,
                "roles": [role.name for role in user.roles if role.name != "@everyone"],
                "avatar": str(user.avatar.url) if user.avatar else None,
            }
            
            # システムプロンプト
            system_prompt = self._get_analysis_system_prompt()
            
            # ユーザープロンプト
            user_prompt = f"""
# ユーザー情報
```json
{json.dumps(user_info, ensure_ascii=False, indent=2)}
```

# メッセージデータ
以下のメッセージデータを分析して、ユーザーの傾向を把握してください。
約{found_msg_count}件のメッセージデータがあります。

{conversation_text}
"""

            # OpenAI APIによる分析開始
            try:
                logger.info(f"OpenAI APIにリクエストを送信します: ユーザー={user.name}, メッセージ数={found_msg_count}")
                
                # API呼び出し
                response = await async_client_ai.chat.completions.create(
                    model="gpt-4o",  # 最新のモデルを指定
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.7,
                    max_tokens=4000
                )
                
                analysis_text = response.choices[0].message.content
                logger.info(f"OpenAI APIから応答を受け取りました: {len(analysis_text)}文字")
                
                # フォルダがなければ作成
                os.makedirs("cache/user_analysis", exist_ok=True)
                
                # 結果を保存
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                md_filename = f"cache/user_analysis/analysis_{user.id}_{timestamp}.md"
                
                with open(md_filename, "w", encoding="utf-8") as f:
                    f.write(f"# {user.display_name} の分析\n\n")
                    f.write(f"分析日時: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}\n\n")
                    f.write(analysis_text)
                
                logger.info(f"分析結果を保存しました: {md_filename}")
                
                # 分析結果の報告（2000文字を超える場合は分割）
                if len(analysis_text) > 1900:
                    # 最初のメッセージで概要とファイルを送信
                    await message.edit(
                        content=f"<@{user.id}> の分析が完了しました。詳細な結果を分割して送信します。"
                    )
                    
                    # 結果を複数のメッセージに分割
                    chunks = [analysis_text[i:i+1900] for i in range(0, len(analysis_text), 1900)]
                    for i, chunk in enumerate(chunks):
                        await message.channel.send(f"**分析結果 ({i+1}/{len(chunks)}):**\n\n{chunk}")
                    
                    # ファイルとして送信
                    await message.channel.send(
                        "分析結果の全文がファイルとして保存されました。",
                        file=discord.File(md_filename)
                    )
                else:
                    # 1つのメッセージで送信可能な場合
                    await message.edit(
                        content=f"<@{user.id}> の分析が完了しました。結果は以下の通りです:\n\n{analysis_text}"
                    )
                    
                    # ファイルとして送信
                    await message.channel.send(
                        "分析結果がファイルとして保存されました。",
                        file=discord.File(md_filename)
                    )
                
            except Exception as e:
                logger.error(f"OpenAI API呼び出し中にエラーが発生しました: {e}")
                await message.edit(
                    content=f"エラー: <@{user.id}> の分析中に問題が発生しました。\n```{str(e)}```"
                )
                return
                
        except asyncio.CancelledError:
            logger.info(f"ユーザーID {user.id} の分析タスクがキャンセルされました")
            await message.edit(content=f"<@{user.id}> の分析タスクがキャンセルされました。")
            return
            
        except Exception as e:
            logger.error(f"ユーザー分析中にエラーが発生しました: {e}")
            await message.edit(content=f"エラー: <@{user.id}> の分析中に予期しない問題が発生しました。")
            return
    
    def _format_messages_for_analysis(self, messages: List[dict]) -> str:
        """メッセージを分析用にフォーマットする"""
        formatted = []
        
        for i, msg in enumerate(messages):
            # メッセージの基本情報
            author_name = msg.get("author", "不明なユーザー")
            formatted_msg = f"[{i+1}] {msg['timestamp']} ({msg['channel']}) {author_name}: {msg['content']}"
            
            # リアクションがある場合は追加
            if msg['reactions']:
                reactions_text = ", ".join(msg['reactions'])
                formatted_msg += f"\n  リアクション: {reactions_text}"
                
            # 添付ファイルがある場合は記載
            if msg['has_attachment']:
                formatted_msg += "\n  [添付ファイルあり]"
                
            # 返信の場合は記載
            if msg['reference']:
                formatted_msg += f"\n  [返信: メッセージID {msg['reference']}]"
                
            formatted.append(formatted_msg)
            
        return "\n\n".join(formatted)
    
    def _get_analysis_system_prompt(self) -> str:
        """分析用のシステムプロンプトを取得"""
        return """
あなたはDiscordメッセージ分析の専門家です。提供されたユーザーのメッセージ履歴を分析し、そのユーザーの傾向、好み、コミュニケーションスタイルなどを詳細に分析してください。分析結果は日本語で、以下のセクションを含むMarkdown形式でまとめてください。

## 分析セクション

1. **全体的な傾向と特徴**
   - コミュニケーションスタイル（フォーマル/カジュアル、長文/短文など）
   - メッセージの頻度や時間帯のパターン
   - 特徴的な表現や言い回し

2. **話題の傾向**
   - よく話題にするテーマやトピック
   - 特に熱心に語る話題
   - 避ける傾向がある話題

3. **感情と態度**
   - 全体的な感情の傾向（ポジティブ/ネガティブ）
   - ユーモアのセンスや使用頻度
   - 批判的/協力的な態度のバランス

4. **対人関係とコミュニケーション**
   - 他のユーザーとの関わり方
   - グループディスカッションでの役割
   - 質問/回答/提案などの行動パターン

5. **言語使用と表現**
   - 語彙の豊富さと専門性
   - 文法や構文の特徴
   - 絵文字や特殊記号の使用パターン

6. **総合的なユーザープロフィール**
   - 性格特性の推測
   - コミュニティ内での位置づけや役割
   - ユーザーとの効果的なコミュニケーション方法の提案

## 分析の注意点

1. メッセージ内容を逐語的に引用せず、傾向とパターンに焦点を当ててください。
2. 個人を尊重し、否定的な評価や判断は控えめに、建設的な視点で分析してください。
3. データが限られている場合は、確実な傾向のみを報告し、推測は控えめにしてください。
4. メッセージのコンテキストや返信関係を考慮して、より深い理解を示してください。
5. 分析は客観的かつ詳細に、具体的な例や根拠を示しながら行ってください。

あなたの分析はユーザー理解とコミュニケーション改善のための貴重な情報として使用されます。専門的かつ尊重的な分析を提供してください。
"""

    def _get_recent_analysis_system_prompt(self) -> str:
        """直近メッセージ分析用のシステムプロンプトを取得"""
        return """
あなたはDiscordサーバー分析の専門家です。提供されたサーバーの直近メッセージデータを分析し、コミュニティの全体的な雰囲気、傾向、特徴などを詳細に分析してください。分析結果は日本語で、以下のセクションを含むMarkdown形式でまとめてください。

## 分析セクション

1. **サーバー全体の雰囲気**
   - コミュニティの全体的な雰囲気（活発/静穏、友好的/厳格など）
   - メンバー間の交流の特徴
   - 新規メンバーへの接し方

2. **話題とコンテンツの傾向**
   - 頻繁に話題に上がるテーマ
   - 人気のあるコンテンツタイプ
   - 議論が活発になる話題

3. **活発なユーザーとリーダーシップ**
   - よく発言するアクティブなメンバーの特徴
   - コミュニティを牽引するユーザーの存在
   - 影響力のあるメンバーの行動パターン

4. **コミュニケーションスタイル**
   - 一般的な会話のトーン
   - 絵文字やリアクションの使用傾向
   - 返信や議論の活発さ

5. **チャンネル利用パターン**
   - 各チャンネルの利用状況
   - チャンネル別の話題の傾向
   - メンバーの行動パターン

6. **コミュニティの健全性と特徴**
   - サーバーの健全性（荒らしやトラブルの有無）
   - メンバー同士の関係性
   - コミュニティとしての成熟度

## 分析の注意点

1. 個人を特定できる情報は避け、全体的な傾向に焦点を当ててください。
2. 客観的で建設的な分析を心がけ、否定的な評価は控えめにしてください。
3. データが限られている場合は、確実な傾向のみを報告してください。
4. サーバー運営やコミュニティ改善に役立つ洞察を提供してください。

あなたの分析はサーバー運営とコミュニティ理解のための貴重な情報として使用されます。専門的かつ尊重的な分析を提供してください。
"""

    def _get_ultra_detailed_analysis_system_prompt(self) -> str:
        """超詳細分析用のシステムプロンプトを取得"""
        return """
あなたは高度なDiscordメッセージ分析AIエキスパートです。大量のメッセージデータと詳細統計を基に、ユーザーの深層心理、行動パターン、コミュニケーション特性を超詳細に分析してください。分析結果は日本語で、以下の包括的なセクションを含むMarkdown形式でまとめてください。

# 超詳細分析レポート構成

## 1. 【エグゼクティブサマリー】
- ユーザーの核心的特徴（3行要約）
- 主要な発見事項とユニークな特性
- 総合的な人物像評価

## 2. 【統計的プロファイル分析】
- 活動パターンの詳細解析（時間帯、曜日、月間推移）
- メッセージ特性の定量分析（長さ、頻度、応答率）
- エンゲージメント指標（リアクション、返信、編集率）
- チャンネル利用パターンと優先度分析

## 3. 【コミュニケーションスタイル詳細分析】
### 3.1 言語使用パターン
- 語彙の豊富さと専門性レベル
- 文体の特徴（敬語使用、カジュアル度、文章構造）
- 頻用語句と特徴的表現の抽出
- 絵文字・顔文字・スタンプ使用傾向

### 3.2 感情表現の分析
- 感情極性の傾向（ポジティブ/ネガティブ/中性の比率）
- 感情の表現方法と強度
- ユーモアのセンスと使用頻度
- ストレス表現や不満の表出パターン

### 3.3 対話スタイル
- 会話の主導性（リーダーシップ/フォロワー傾向）
- 質問の頻度と種類
- 意見表明の積極性
- 議論への参加スタイル

## 4. 【社会的インタラクション分析】
### 4.1 人間関係構築パターン
- 他ユーザーとの関係性構築方法
- グループ内での役割と立ち位置
- 新規参加者への接し方
- 衝突回避・解決パターン

### 4.2 コミュニティ貢献度
- 情報提供・共有の頻度と質
- 他者支援行動の傾向
- コミュニティイベントへの参加度
- ルール遵守とモデレーション協力度

## 5. 【興味・関心領域の深掘り分析】
### 5.1 主要関心分野
- 最も言及頻度の高いトピック（定量分析）
- 専門知識を持つ分野の特定
- 趣味・娯楽の嗜好パターン
- 学習・成長への関心度

### 5.2 話題転換パターン
- 話題提起の頻度と種類
- トレンドへの感度
- ニッチな話題への関心度
- 継続的関心 vs 一時的関心の分析

## 6. 【行動予測とペルソナ分析】
### 6.1 心理的特性推定
- 性格特性（Big Five等の枠組みでの分析）
- 価値観と優先順位
- 意思決定パターン
- ストレス対処法

### 6.2 行動予測
- 今後の活動パターン予測
- 興味を持ちそうな新しいトピック
- コミュニティでの成長可能性
- 潜在的な課題や懸念事項

## 7. 【コミュニケーション最適化提案】
### 7.1 効果的なアプローチ方法
- このユーザーとの理想的な会話スタイル
- 情報提供時の最適な形式
- モチベーション向上のアプローチ
- 注意喚起時の配慮事項

### 7.2 コミュニティ運営への提言
- このユーザーの活用可能な強み
- 適切な役割や責任の提案
- 成長支援のための具体的提案
- 潜在的問題の予防策

## 8. 【詳細データ分析結果】
- 時系列での変化トレンド
- 特異値や異常パターンの検出
- 他の典型的ユーザーとの比較
- 統計的有意性のある発見事項

## 9. 【総合評価と将来展望】
- ユーザーの総合的価値評価
- コミュニティへの貢献度評価
- 成長ポテンシャル
- 長期的な関係性構築の見通し

---

## 分析実行時の重要指針

1. **データドリブン**: 統計データを基にした客観的分析を重視
2. **多角的視点**: 複数の角度からの分析で偏りを防止
3. **建設的アプローチ**: 成長と改善に繋がる洞察を提供
4. **プライバシー尊重**: 個人の尊厳を保ちつつ専門的分析を実施
5. **実用性重視**: コミュニケーション改善に直結する具体的提案
6. **継続性考慮**: 長期的な関係性を見据えた分析

この超詳細分析は、ユーザー理解の深化とコミュニティ運営の質向上を目的としています。人間の複雑性を尊重しつつ、科学的なアプローチで実用的な洞察を提供してください。
"""

async def setup(bot):
    await bot.add_cog(UserAnalyzer(bot))
