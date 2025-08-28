import asyncio
import json
import os
from datetime import datetime
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands
from openai import AsyncOpenAI

from config.setting import get_settings
from utils.commands_help import is_guild_app, is_owner_app, log_commands
from utils.logging import setup_logging

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

    def _format_messages_for_analysis(self, messages: list[dict]) -> str:
        """メッセージを分析用にフォーマットする"""
        formatted = []

        for i, msg in enumerate(messages):
            # メッセージの基本情報
            formatted_msg = f"[{i+1}] {msg['timestamp']} ({msg['channel']}): {msg['content']}"

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

async def setup(bot):
    await bot.add_cog(UserAnalyzer(bot))
