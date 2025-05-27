import json
import os
import asyncio
import discord
from discord.ext import commands
from datetime import datetime
from openai import OpenAI, AsyncOpenAI
from config.setting import get_settings
from utils.logging import setup_logging
from utils.commands_help import is_guild, is_owner, log_commands

# 設定を取得
settings = get_settings()
OPENAI_API_KEY = settings.etc_api_openai_api_key
TARGET_USER_ID = settings.bot_owner_id
TARGET_GUILD_ID = settings.admin_main_guild_id

# OpenAIクライアントを初期化（同期と非同期の両方）
client_ai = OpenAI(api_key=OPENAI_API_KEY)
async_client_ai = AsyncOpenAI(api_key=OPENAI_API_KEY)

# ロガーを取得
logger = setup_logging("D")

class MessageAnalyzer(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="analyze")
    @is_guild()
    @is_owner()
    @log_commands()
    async def analyze_messages(self, ctx):
        logger.info(f"メッセージ分析コマンドが実行されました: 使用者 {ctx.author.name} (ID: {ctx.author.id})")
        
        # コマンド送信者が対象ユーザーか確認
        if ctx.author.id != TARGET_USER_ID:
            logger.warning(f"不正なユーザーによる分析コマンドの実行試行: {ctx.author.name} (ID: {ctx.author.id})")
            await ctx.send("このコマンドは指定されたユーザーのみが使用できます。")
            return

        # メッセージ取得開始
        logger.info(f"メッセージ取得プロセスを開始: ギルドID {TARGET_GUILD_ID}, ターゲットユーザーID {TARGET_USER_ID}")
        await ctx.send("メッセージの取得を開始します…🔍")
        
        messages = []
        guild = self.bot.get_guild(TARGET_GUILD_ID)
        
        if not guild:
            logger.error(f"ギルドが見つかりませんでした: ID {TARGET_GUILD_ID}")
            await ctx.send("エラー: ギルドが見つかりませんでした。設定を確認してください。")
            return
        
        # 進捗メッセージ
        progress_msg = await ctx.send("チャンネルをスキャン中: 0/{}...".format(len(guild.text_channels)))
        channel_count = 0
        found_msg_count = 0
        
        for channel in guild.text_channels:
            try:
                channel_count += 1
                logger.info(f"チャンネルをスキャン中: {channel.name} ({channel_count}/{len(guild.text_channels)})")
                
                # 定期的に進捗を更新
                if channel_count % 5 == 0 or channel_count == len(guild.text_channels):
                    await progress_msg.edit(content=f"チャンネルをスキャン中: {channel_count}/{len(guild.text_channels)}... 見つかったメッセージ: {found_msg_count}")
                
                async for message in channel.history(limit=None):
                    if message.author.id == TARGET_USER_ID:
                        messages.append({
                            "channel": channel.name,
                            "timestamp": message.created_at.isoformat(),
                            "content": message.content
                        })
                        found_msg_count += 1
                        
                        # 100メッセージごとに進捗を表示
                        if found_msg_count % 100 == 0:
                            logger.info(f"{found_msg_count}件のメッセージを発見")
                            await progress_msg.edit(content=f"チャンネルをスキャン中: {channel_count}/{len(guild.text_channels)}... 見つかったメッセージ: {found_msg_count}💬")
                            
            except Exception as e:
                logger.error(f"チャンネル {channel.name} でメッセージ取得に失敗: {e}")
                await ctx.send(f"警告: チャンネル `{channel.name}` のメッセージ取得中にエラーが発生しました。")

        # 進捗報告を更新
        await progress_msg.edit(content=f"取得完了: 合計{found_msg_count}件のメッセージを見つけました。JSONファイルを作成中...")
        
        # メッセージをJSONで保存
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_filename = f"messages_{timestamp}.json"
        logger.info(f"JSONファイルにメッセージを保存します: {json_filename} ({found_msg_count}件)")
        
        try:
            with open(json_filename, "w", encoding="utf-8") as f:
                json.dump(messages, f, ensure_ascii=False, indent=4)
            logger.info(f"JSONファイルの保存が完了しました: {json_filename}")
        except Exception as e:
            logger.error(f"JSONファイルの保存中にエラーが発生しました: {e}")
            await ctx.send(f"エラー: JSONファイルの保存中に問題が発生しました: {e}")
            return

        # メッセージを一括で結合
        logger.info("分析用にメッセージを結合しています...")
        conversation_text = "\n".join([f"[{msg['timestamp']}] {msg['channel']}: {msg['content']}" for msg in messages])
        await progress_msg.edit(content=f"取得完了: {found_msg_count}件のメッセージを保存しました。分析準備中...🧠")

        # システムプロンプト強化（コミュニティマネージャー視点）
        system_prompt = """
あなたは経験豊富なテキスト分析の専門家であり、以下のDiscordメッセージ履歴をもとに、ユーザーの性格、思考傾向、リーダーシップ特性、コミュニティ管理能力を詳細に分析します。特にコミュニティマネージャーとして求められる以下の要素に重点を置いてください。

1. **コミュニケーション能力**
   - 多様なユーザーとのやり取りで見られる言葉遣いやトーン
   - 冷静さ、礼儀正しさ、共感力の度合い
   - 短文・長文の使い分けや文脈に応じた適応力

2. **リーダーシップと影響力**
   - 他者を鼓舞する力や困難な状況での判断力
   - 指示やフィードバックの明確さ、他者への指導力
   - 突発的なトラブルへの対応力

3. **共感とユーザー理解**
   - 他者の視点に立った発言や、異なる意見に対する寛容さ
   - ユーザーのニーズや感情を理解し、それに応じた対応

4. **問題解決と判断力**
   - 効率的な意思決定、状況判断の正確さ
   - 問題解決に向けた積極的な提案や実行力

5. **コミュニティ構築能力**
   - ファン同士のつながりを促進する能力
   - メンバーが安心して発言できる環境作り
   - 長期的なコミュニティビジョンの有無

6. **自己認識と成長**
   - 自身の強みと弱みの理解、自己改善の意識
   - 過去の経験から学んだ教訓や成長の跡

7. **データドリブンな考え方**
   - メンバーのフィードバックやトレンドをデータとして捉える視点
   - 定量的・定性的な評価への理解

8. **文化と共感の形成**
   - ファンカルチャーや独自の文化を理解し、それを尊重する姿勢
   - コミュニティにおけるポジティブな文化形成への貢献

これらの要素に基づき、ユーザーのメッセージ履歴を詳細に分析し、Markdown形式で結果を出力してください。各セクションには具体的な観察とその根拠を含め、明確な文章で構成してください。
"""

        # OpenAI APIリクエスト
        logger.info(f"OpenAI APIにリクエストを送信します: モデル=gpt-4o, メッセージ数={found_msg_count}")
        await progress_msg.edit(content="AI分析中... これには時間がかかる場合があります。お待ちください⚙️")
        
        try:
            # 最新のOpenAI SDKの書き方を使用
            response = client_ai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": conversation_text}
                ]
            )
            logger.info("OpenAI APIから応答を受け取りました")
        except Exception as e:
            logger.error(f"OpenAI APIリクエスト中にエラーが発生しました: {e}")
            await progress_msg.edit(content="AI分析中にエラーが発生しました。")
            await ctx.send(f"エラー: OpenAI APIの呼び出し中に問題が発生しました: {e}")
            return

        await progress_msg.edit(content="分析が完了しました。結果を保存中...")

        # 分析結果をMarkdown形式で保存
        try:
            # 最新のSDKではレスポンスの取得方法が変更されています
            analysis_text = response.choices[0].message.content
            md_filename = f"analysis_{timestamp}.md"
            logger.info(f"Markdownファイルに分析結果を保存します: {md_filename}")
            
            with open(md_filename, "w", encoding="utf-8") as f:
                f.write(analysis_text)
            logger.info(f"Markdownファイルの保存が完了しました: {md_filename}")
        except Exception as e:
            logger.error(f"Markdownファイルの保存中にエラーが発生しました: {e}")
            await ctx.send(f"エラー: 分析結果の保存中に問題が発生しました: {e}")
            return

        await progress_msg.edit(content="完了しました！ 結果をDMで送信します...")

        # 分析結果をDMで送信
        try:
            await ctx.author.send(f"メッセージの分析結果を保存しました。\n\nJSONファイル: `{json_filename}`\nMarkdownファイル: `{md_filename}`")
            logger.info(f"DMに結果を送信しました: {ctx.author.name} (ID: {ctx.author.id})")
            await ctx.send("✅ メッセージの分析が完了しました。結果はDMで送信されました。")
        except Exception as e:
            logger.error(f"DM送信中にエラーが発生しました: {e}")
            await ctx.send(f"警告: DMを送信できませんでした。結果は次のファイルに保存されました: `{json_filename}`, `{md_filename}`")
        
        logger.info("メッセージ分析プロセスが正常に完了しました")

        files = [
            discord.File(json_filename),
            discord.File(md_filename)
        ]
        await ctx.send("メッセージの分析が完了しました。結果はDMで送信されました。")
        await ctx.author.send(files=files)

    @commands.command(name="analyze_file")
    @is_guild()
    @is_owner()
    @log_commands()
    async def analyze_file(self, ctx, file_path: str = None):
        """既存のJSONファイルをGPT-4.1モデルで解析するコマンド"""
        logger.info(f"JSONファイル分析コマンドが実行されました: 使用者 {ctx.author.name} (ID: {ctx.author.id})")
        
        # コマンド送信者が対象ユーザーか確認
        if ctx.author.id != TARGET_USER_ID:
            logger.warning(f"不正なユーザーによるファイル分析コマンドの実行試行: {ctx.author.name} (ID: {ctx.author.id})")
            await ctx.send("このコマンドは指定されたユーザーのみが使用できます。")
            return

        # ファイルパスが指定されていない場合
        if not file_path:
            await ctx.send("分析するJSONファイルのパスを指定してください。\n例: `!analyze_file messages_20250511_143402.json`")
            return

        # 実行内容を説明
        await ctx.send(f"\u2714️ JSONファイル `{file_path}` をGPT-4.1で分析します。これには時間がかかる場合があります...")
        
        # ファイルが存在するか確認
        try:
            if not os.path.exists(file_path):
                logger.error(f"ファイルが見つかりません: {file_path}")
                await ctx.send(f"エラー: ファイル `{file_path}` が見つかりません。パスを確認してください。")
                return
                
            # JSONファイルを読み込み
            logger.info(f"JSONファイルを読み込み: {file_path}")
            progress_msg = await ctx.send("ファイルを読み込み中...📚")
            
            with open(file_path, 'r', encoding='utf-8') as f:
                messages = json.load(f)
            
            message_count = len(messages)
            logger.info(f"JSONファイルから {message_count} 件のメッセージを読み込みました")
            await progress_msg.edit(content=f"\u2714️ {message_count} 件のメッセージを読み込みました。分析のためにデータを整形しています...")
            
            # メッセージを時系列順に並べ替え
            sorted_messages = sorted(messages, key=lambda x: x['timestamp'])
            
            # チャンクサイズを設定
            chunk_size = 1000  # 一度に処理するメッセージ数
            total_chunks = (len(sorted_messages) + chunk_size - 1) // chunk_size  # 切り上げて必要なチャンク数を計算
            
            logger.info(f"全{len(sorted_messages)}件のメッセージを{total_chunks}チャンクに分割します。各チャンクは最大{chunk_size}件です。")
            await progress_msg.edit(content=f"\u2714️ {message_count} 件のメッセージを読み込みました。{total_chunks}チャンクに分割して分析します...")
            
            # システムプロンプト設定
            system_prompt = """
あなたは経験豊富なテキスト分析の専門家であり、以下のDiscordメッセージ履歴をもとに、ユーザーの性格、思考傾向、リーダーシップ特性、コミュニティ管理能力を詳細に分析します。特にコミュニティマネージャーとして求められる以下の要素に重点を置いてください。

1. **コミュニケーション能力**
   - 多様なユーザーとのやり取りで見られる言葉遣いやトーン
   - 冷静さ、礼儀正しさ、共感力の度合い
   - 短文・長文の使い分けや文脈に応じた適応力

2. **リーダーシップと影響力**
   - 他者を鼓舞する力や困難な状況での判断力
   - 指示やフィードバックの明確さ、他者への指導力
   - 突発的なトラブルへの対応力

3. **共感とユーザー理解**
   - 他者の視点に立った発言や、異なる意見に対する宽容さ
   - ユーザーのニーズや感情を理解し、それに応じた対応

4. **問題解決と判断力**
   - 効率的な意思決定、状況判断の正確さ
   - 問題解決に向けた積極的な提案や実行力

5. **コミュニティ構築能力**
   - ファン同士のつながりを促進する能力
   - メンバーが安心して発言できる環境作り
   - 長期的なコミュニティビジョンの有無

6. **自己認識と成長**
   - 自身の強みと弱みの理解、自己改善の意識
   - 過去の経験から学んだ教訓や成長の跡

7. **データドリブンな考え方**
   - メンバーのフィードバックやトレンドをデータとして捕える視点
   - 定量的・定性的な評価への理解

8. **文化と共感の形成**
   - ファンカルチャーや独自の文化を理解し、それを尊重する姿勢
   - コミュニティにおけるポジティブな文化形成への貢献

これらの要素に基づき、ユーザーのメッセージ履歴を詳細に分析し、Markdown形式で結果を出力してください。各セクションには具体的な観察とその根拠を含め、明確な文章で構成してください。
"""
            
            # OpenAI APIリクエスト
            await progress_msg.edit(content="GPT-4.1を使用して分析中... これには数分かかる場合があります。お待ちください⚙️")
            logger.info(f"GPT-4.1で分析を開始: メッセージ数={message_count}")
            
            try:
                # 処理状態を更新
                await progress_msg.edit(content="GPT-4.1を使用して分析中... バックグラウンドで処理しています。処理が完了すると通知されます⚙️")
                
                # 非同期タスクでOpenAI APIリクエストを実行する関数
                async def run_analysis():
                    try:
                        all_analyses = []
                        
                        # 各チャンクを処理
                        for chunk_index in range(total_chunks):
                            start_idx = chunk_index * chunk_size
                            end_idx = min(start_idx + chunk_size, len(sorted_messages))
                            current_chunk = sorted_messages[start_idx:end_idx]
                            
                            # チャンクの情報を作成
                            chunk_info = f"チャンク {chunk_index + 1}/{total_chunks}: メッセージ番号 {start_idx + 1}-{end_idx} ({len(current_chunk)}件)"
                            logger.info(f"{chunk_info}の分析を開始")
                            await progress_msg.edit(content=f"チャンク {chunk_index + 1}/{total_chunks} を分析中... お待ちください⚙️")
                            
                            # チャンクメッセージを結合
                            chunk_text = "\n".join([f"[{msg['timestamp']}] {msg['channel']}: {msg['content']}" for msg in current_chunk])
                            
                            # チャンクスペシフィックなプロンプトを作成
                            chunk_system_prompt = system_prompt + f"\n\n\n注意: これは全メッセージのチャンク {chunk_index + 1}/{total_chunks} です。全部で {len(sorted_messages)} 件のメッセージがあり、現在はそのうち {len(current_chunk)} 件のメッセージを分析しています。各チャンクを個別に分析し、後で結果を統合します。"
                            
                            # GPT-4.1を使用する（非同期クライアントを使用）と再試行ロジック
                            try:
                                max_retries = 3  # 最大再試行回数
                                retry_count = 0
                                retry_delay = 5  # 初期再試行遅延（秒）
                                
                                # ディスコードのイベントループを阻害しないよう少し待機
                                if chunk_index > 0:  # 最初のチャンク以外は待機を入れる
                                    await asyncio.sleep(2)  # 2秒待機してディスコードのハートビートを許可
                                
                                # 再試行ループ
                                success = False
                                while retry_count <= max_retries and not success:
                                    try:
                                        # 非同期クライアントを使用
                                        logger.info(f"{chunk_info}の分析を試行中... (試行回数: {retry_count + 1}/{max_retries + 1})")
                                        
                                        # 再試行中であることをユーザーに通知
                                        if retry_count > 0:
                                            await progress_msg.edit(content=f"チャンク {chunk_index + 1}/{total_chunks} の分析を再試行中... ({retry_count}/{max_retries})⚙️")
                                        
                                        response = await async_client_ai.chat.completions.create(
                                            model="gpt-4.1",  # GPT-4.1を指定
                                            messages=[
                                                {"role": "system", "content": chunk_system_prompt},
                                                {"role": "user", "content": chunk_text}
                                            ]
                                        )
                                        
                                        chunk_analysis = response.choices[0].message.content
                                        all_analyses.append(f"## {chunk_info}\n\n{chunk_analysis}\n\n---\n\n")
                                        logger.info(f"{chunk_info}のGPT-4.1分析が完了しました")
                                        
                                        # ステータスメッセージの更新
                                        await progress_msg.edit(content=f"チャンク {chunk_index + 1}/{total_chunks} の分析が完了しました。次のチャンクを処理中...⚙️")
                                        
                                        # 成功フラグを設定してループを抜ける
                                        success = True
                                        
                                    except Exception as e:
                                        retry_count += 1
                                        if retry_count <= max_retries:
                                            error_msg = f"{chunk_info}の分析中にエラーが発生しました: {e} - 再試行します ({retry_count}/{max_retries})"
                                            logger.warning(error_msg)
                                            await ctx.send(f"警告: APIエラーが発生しましたが、{retry_delay}秒後に再試行します... ({retry_count}/{max_retries})")
                                            
                                            # 指数バックオフで待機時間を増やす
                                            await asyncio.sleep(retry_delay)
                                            retry_delay *= 2  # 次回の待機時間を2倍に
                                        else:
                                            # 最大再試行回数を超えた場合は例外を投げる
                                            error_msg = f"{chunk_info}の分析中にエラーが発生しました: {e}"
                                            logger.error(error_msg)
                                            all_analyses.append(f"## {chunk_info}\n\n再試行後もエラー: {error_msg}\n\n---\n\n")
                                            await ctx.send(f"エラー: {chunk_info}の分析に失敗しましたが、処理を続行します。")

                                
                            except Exception as e:
                                error_msg = f"{chunk_info}の分析中にエラーが発生しました: {e}"
                                logger.error(error_msg)
                                all_analyses.append(f"## {chunk_info}\n\nエラー: {error_msg}\n\n---\n\n")
                                await ctx.send(f"警告: {chunk_info}の分析中にエラーが発生しましたが、他のチャンクの処理を続行します。")
                        
                        # 全チャンクの分析結果を結合
                        combined_analysis = "# メッセージ分析結果 - チャンク分析方式\n\n"
                        combined_analysis += f"全{len(sorted_messages)}件のメッセージを{total_chunks}チャンクに分割して分析しました。\n\n"
                        combined_analysis += "\n".join(all_analyses)
                        
                        logger.info("GPT-4.1から全チャンクの分析結果を受け取りました")
                        
                        # 分析結果をMarkdown形式で保存
                        try:
                            # 元のファイル名からベース名を取得
                            base_name = os.path.splitext(os.path.basename(file_path))[0]
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            md_filename = f"analysis_{base_name}_{timestamp}.md"
                            
                            analysis_text = combined_analysis
                            logger.info(f"Markdownファイルに分析結果を保存します: {md_filename}")
                            
                            with open(md_filename, "w", encoding="utf-8") as f:
                                f.write(analysis_text)
                            logger.info(f"Markdownファイルの保存が完了しました: {md_filename}")
                            
                            # 分析結果を送信
                            try:
                                await ctx.send(f"✅ 分析が完了しました。結果ファイル: `{md_filename}`")
                                
                                # ファイルサイズが8MBを超えないか確認
                                if os.path.getsize(md_filename) < 8 * 1024 * 1024:
                                    file = discord.File(md_filename)
                                    await ctx.send(file=file)
                                    logger.info(f"分析結果を送信しました: {md_filename}")
                                else:
                                    await ctx.send(f"⚠️ 結果ファイルのサイズが大きすぎるため、ディスコードに直接送信できません。ファイルは `{md_filename}` に保存されています。")
                                    logger.warning(f"ファイルサイズが大きすぎるため、送信をスキップしました: {md_filename}")
                            except Exception as e:
                                logger.error(f"ファイル送信中にエラーが発生しました: {e}")
                                await ctx.send(f"警告: ファイルを送信できませんでしたが、結果は `{md_filename}` に保存されました。")
                            
                            logger.info("メッセージファイル分析プロセスが正常に完了しました")
                            
                        except Exception as e:
                            logger.error(f"Markdownファイルの保存中にエラーが発生しました: {e}")
                            await ctx.send(f"エラー: 分析結果の保存中に問題が発生しました: {e}")
                            return
                            
                    except Exception as e:
                        logger.error(f"OpenAI APIリクエスト中にエラーが発生しました: {e}")
                        await ctx.send(f"エラー: OpenAI APIの呼び出し中に問題が発生しました: {e}")
                
                # バックグラウンドタスクとして分析を実行
                self.bot.loop.create_task(run_analysis())
                
                # すぐに応答を返す
                return
            
            except Exception as e:
                logger.error(f"バックグラウンドタスクの作成中にエラーが発生しました: {e}")
                await progress_msg.edit(content="AI分析タスクの開始中にエラーが発生しました。")
                await ctx.send(f"エラー: 分析タスクの開始中に問題が発生しました: {e}")
                return
            except Exception as e:
                logger.error(f"OpenAI APIリクエスト中にエラーが発生しました: {e}")
                await progress_msg.edit(content="AI分析中にエラーが発生しました。")
                await ctx.send(f"エラー: OpenAI APIの呼び出し中に問題が発生しました: {e}")
                return

            # 非同期処理に移行したため、ここでは何もしない
            
        except Exception as e:
            logger.error(f"ファイル分析中に予期しないエラーが発生しました: {e}")
            await ctx.send(f"エラー: 分析中に予期しないエラーが発生しました: {e}")

async def setup(bot):
    await bot.add_cog(MessageAnalyzer(bot))