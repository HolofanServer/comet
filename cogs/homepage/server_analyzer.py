import discord
from discord.ext import commands, tasks
import os
import aiohttp
import json
from datetime import datetime, timedelta
from collections import Counter
import re
from typing import Dict, Any, List

from utils.logging import setup_logging
from config.setting import get_settings

logger = setup_logging("D")
settings = get_settings()

class ServerAnalyzer(commands.Cog):
    """OpenAI APIを使用してサーバー情報を分析し、ホームページ用の内容を生成するCog"""
    
    def __init__(self, bot):
        self.bot = bot
        self.openai_api_key = settings.etc_api_openai_api_key
        # 設定ファイルの値が期待と異なるため、直接URLを指定
        self.api_base_url = "https://hfs.jp/api"
        self.api_token = settings.homepage_api_token
        
        # デバッグログ
        logger.info(f"ServerAnalyzer: 設定から読み込まれたAPI URL = {settings.homepage_api_url}")
        logger.info(f"ServerAnalyzer: 実際に使用するAPI URL = {self.api_base_url}")
        self.target_guild_id = settings.homepage_target_guild_id
        self.cache_dir = os.path.join(os.getcwd(), "cache", "server_analysis")
        self.ensure_cache_dir()
        
        # APIキーが設定されていればタスクを開始
        if self.openai_api_key:
            self.weekly_server_analysis.start()
            logger.info("サーバー分析タスクを開始しました")
    
    def ensure_cache_dir(self):
        """キャッシュディレクトリが存在することを確認"""
        os.makedirs(self.cache_dir, exist_ok=True)
    
    def cog_unload(self):
        """Cogがアンロードされるときにタスクを停止"""
        if self.openai_api_key:
            self.weekly_server_analysis.cancel()
    
    async def analyze_with_openai(self, 
                                 prompt: str, 
                                 system_prompt: str = "あなたはDiscordサーバーの分析を行う専門家です。",
                                 model: str = "gpt-4o"):
        """OpenAI APIを使用してテキスト分析を行う"""
        if not self.openai_api_key:
            return "OpenAI APIキーが設定されていません。"
            
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.openai_api_key}"
                }
                
                payload = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.7
                }
                
                async with session.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers=headers,
                    json=payload
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data["choices"][0]["message"]["content"]
                    else:
                        error_text = await response.text()
                        logger.error(f"OpenAI API呼び出しに失敗: {response.status} - {error_text}")
                        return f"APIエラー: {response.status}"
                        
        except Exception as e:
            logger.error(f"OpenAI API呼び出し中にエラーが発生: {e}")
            return f"エラー: {e}"
    
    async def collect_channel_data(self, guild: discord.Guild, days: int = 7) -> Dict[str, Any]:
        """指定した期間のチャンネルデータを収集"""
        channel_data = {}
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        for channel in guild.text_channels:
            try:
                # チャンネルの基本情報
                channel_info = {
                    "id": channel.id,
                    "name": channel.name,
                    "topic": channel.topic or "",
                    "position": channel.position,
                    "category": channel.category.name if channel.category else "カテゴリなし",
                    "messages": [],
                    "message_count": 0,
                    "active_users": set(),
                    "common_words": {},
                    "created_at": channel.created_at.isoformat()
                }
                
                # メッセージ収集（最大300件）
                message_count = 0
                message_texts = []
                async for message in channel.history(limit=300, after=cutoff_date):
                    if not message.author.bot:  # ボットメッセージを除外
                        message_count += 1
                        channel_info["active_users"].add(message.author.id)
                        
                        # メッセージ内容（最大100件のみ内容を保存）
                        if len(message_texts) < 100:
                            message_texts.append(message.content)
                        
                        # 単語の頻度分析
                        words = re.findall(r'\w+', message.content.lower())
                        for word in words:
                            if len(word) > 1:  # 1文字の単語を除外
                                channel_info["common_words"][word] = channel_info["common_words"].get(word, 0) + 1
                
                # 結果を更新
                channel_info["message_count"] = message_count
                channel_info["messages"] = message_texts
                channel_info["active_users"] = list(channel_info["active_users"])
                
                # 頻出単語を上位20個に絞る
                channel_info["common_words"] = dict(
                    sorted(channel_info["common_words"].items(), 
                           key=lambda x: x[1], 
                           reverse=True)[:20]
                )
                
                channel_data[str(channel.id)] = channel_info
                
            except discord.Forbidden:
                logger.warning(f"チャンネル {channel.name} へのアクセス権限がありません")
            except Exception as e:
                logger.error(f"チャンネル {channel.name} の分析中にエラーが発生: {e}")
        
        return channel_data
    
    async def collect_roles_data(self, guild: discord.Guild) -> Dict[str, Any]:
        """ロール情報を収集"""
        roles_data = {}
        
        for role in guild.roles:
            if not role.is_default():
                roles_data[str(role.id)] = {
                    "id": role.id,
                    "name": role.name,
                    "color": role.color.value,
                    "position": role.position,
                    "members_count": len(role.members),
                    "members": [m.id for m in role.members[:20]],  # 最大20人分のメンバーIDを保存
                    "created_at": role.created_at.isoformat()
                }
        
        return roles_data
    
    async def generate_server_summary(self, guild: discord.Guild, channel_data: Dict[str, Any], roles_data: Dict[str, Any]) -> Dict[str, Any]:
        """サーバーの情報を分析し、要約と特徴をまとめる"""
        # サーバー基本情報
        server_info = {
            "id": guild.id,
            "name": guild.name,
            "description": guild.description or "",
            "icon_url": str(guild.icon.url) if guild.icon else "",
            "banner_url": str(guild.banner.url) if guild.banner else "",
            "member_count": guild.member_count,
            "created_at": guild.created_at.isoformat(),
            "channel_count": len(guild.channels),
            "text_channel_count": len(guild.text_channels),
            "voice_channel_count": len(guild.voice_channels),
            "role_count": len(guild.roles) - 1,  # @everyoneを除く
            "emoji_count": len(guild.emojis),
            "premium_tier": guild.premium_tier,
            "premium_subscription_count": guild.premium_subscription_count
        }
        
        # アクティブチャンネルのランキング
        active_channels = sorted(
            [(channel_id, data["message_count"]) for channel_id, data in channel_data.items()],
            key=lambda x: x[1],
            reverse=True
        )[:10]  # 上位10チャンネル
        
        # アクティブユーザーの集計
        user_activity = Counter()
        for channel_id, data in channel_data.items():
            for user_id in data["active_users"]:
                user_activity[user_id] += 1
        
        active_users = [(user_id, count) for user_id, count in user_activity.most_common(10)]
        
        # 人気のロール
        popular_roles = sorted(
            [(role_id, data["members_count"]) for role_id, data in roles_data.items()],
            key=lambda x: x[1],
            reverse=True
        )[:10]  # 上位10ロール
        
        # 分析結果を格納する辞書
        analysis_results = {
            "server_info": server_info,
            "active_channels": active_channels,
            "active_users": active_users,
            "popular_roles": popular_roles,
            "analyzed_at": datetime.utcnow().isoformat()
        }
        
        # OpenAIによる分析
        
        # 1. サーバー全体の概要分析
        channel_texts = []
        for channel_id, data in channel_data.items():
            if data["message_count"] > 0:
                channel_name = discord.utils.get(guild.text_channels, id=int(channel_id)).name
                channel_texts.append(f"チャンネル「{channel_name}」の特徴:\n" + 
                                    f"メッセージ数: {data['message_count']}\n" +
                                    f"トピック: {data['topic']}\n" +
                                    f"アクティブユーザー数: {len(data['active_users'])}\n" +
                                    f"頻出ワード: {', '.join(list(data['common_words'].keys())[:10])}")
        
        channel_summary = "\n\n".join(channel_texts)
        
        server_analysis_prompt = f"""
以下は「{guild.name}」Discordサーバーの分析データです。
このサーバーの特徴を複数の視点から詳細に分析し、コミュニティの概要をまとめてください。

サーバー基本情報:
- メンバー数: {guild.member_count}人
- チャンネル数: {len(guild.text_channels)}個
- ロール数: {len(guild.roles) - 1}個
- サーバー作成日: {guild.created_at.strftime('%Y年%m月%d日')}
- ブースト数: {guild.premium_subscription_count}

最もアクティブなチャンネル:
{', '.join([discord.utils.get(guild.text_channels, id=int(c[0])).name for c in active_channels[:5]])}

チャンネル分析:
{channel_summary}

観点ごとに詳細に分析し、以下の点について具体的に説明してください:
1. サーバーの全体的な雰囲気と文化
2. コミュニティの主な関心事や話題
3. メンバー間のコミュニケーションスタイル
4. サーバーの特徴的な活動やイベント
5. 新規メンバーに向けたサーバーの魅力

JSONフォーマットで返答せず、自然な日本語で分析結果を提供してください。
"""
        
        server_analysis = await self.analyze_with_openai(
            prompt=server_analysis_prompt,
            system_prompt="あなたはDiscordコミュニティの分析専門家です。与えられた情報をもとに、サーバーの特徴を多角的に分析し、わかりやすく説明してください。",
            model="gpt-4o"
        )
        
        # 2. キャッチコピーとスローガン生成
        slogan_prompt = f"""
「{guild.name}」というDiscordサーバーのキャッチコピーとスローガンを複数考えてください。

サーバーの特徴:
- メンバー数: {guild.member_count}人
- 主な話題: {', '.join([k for k, v in Counter([word for data in channel_data.values() for word, count in data["common_words"].items()]).most_common(10)])}
- サーバーの雰囲気: {server_analysis[:200]}...

以下の4つのカテゴリでそれぞれ3つずつ案を提案してください:
1. 短くインパクトのあるキャッチコピー（10文字程度）
2. 説明的なキャッチコピー（20〜30文字）
3. フレンドリーで親しみやすいスローガン
4. コミュニティの特徴を表す魅力的なフレーズ

それぞれ日本語で作成し、なぜその案が良いかの簡単な説明も添えてください。
"""
        
        slogans = await self.analyze_with_openai(
            prompt=slogan_prompt,
            system_prompt="あなたはキャッチコピーやスローガンの作成に長けたマーケティングの専門家です。",
            model="gpt-4o"
        )
        
        # 3. 新規メンバー向け説明文
        welcome_prompt = f"""
「{guild.name}」Discordサーバーに新しく参加したメンバー向けの歓迎メッセージと説明文を作成してください。
以下の情報をもとに、サーバーの魅力や活用方法がわかりやすく伝わるような文章を書いてください。

サーバー情報:
- メンバー数: {guild.member_count}人
- 主なチャンネル: {', '.join([discord.utils.get(guild.text_channels, id=int(c[0])).name for c in active_channels[:5]])}
- 人気のロール: {', '.join([discord.utils.get(guild.roles, id=int(r[0])).name for r in popular_roles[:5]])}
- サーバーの特徴: {server_analysis[:300]}...

次の3つのバージョンを作成してください:
1. 短い挨拶文（100文字程度）
2. 中程度の説明（300文字程度）- チャンネルの使い方など基本情報を含む
3. 詳細な案内（500文字程度）- サーバーの目的、ルール、楽しみ方などを詳しく

すべて日本語で、親しみやすく、新規メンバーが参加したくなるような文章にしてください。
"""
        
        welcome_messages = await self.analyze_with_openai(
            prompt=welcome_prompt,
            system_prompt="あなたはコミュニティマネージャーであり、新規メンバーを温かく迎え入れることに長けています。",
            model="gpt-4o"
        )
        
        # 結果をまとめる
        analysis_results = {
            "server_info": server_info,
            "active_channels": active_channels,
            "active_users": active_users,
            "popular_roles": popular_roles,
            "server_analysis": server_analysis,
            "slogans": slogans,
            "welcome_messages": welcome_messages,
            "analyzed_at": datetime.utcnow().isoformat()
        }
        
        return analysis_results
    
    @tasks.loop(hours=168)  # 1週間（168時間）ごとに実行
    async def weekly_server_analysis(self):
        """1週間ごとにサーバー分析を実行するタスク"""
        try:
            guild = self.bot.get_guild(self.target_guild_id)
            if not guild:
                logger.error(f"ギルドID {self.target_guild_id} が見つかりません")
                return
            
            logger.info(f"サーバー '{guild.name}' の分析を開始します...")
            
            # データ収集
            channel_data = await self.collect_channel_data(guild)
            roles_data = await self.collect_roles_data(guild)
            
            # サーバー分析
            analysis_data = await self.generate_server_summary(guild, channel_data, roles_data)
            
            # 結果を保存
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            analysis_file = os.path.join(self.cache_dir, f"server_analysis_{timestamp}.json")
            
            with open(analysis_file, "w", encoding="utf-8") as f:
                json.dump(analysis_data, f, ensure_ascii=False, indent=2)
            
            # Webサイト用APIにデータを送信
            await self.send_to_api("discord/server-analysis", analysis_data)
            
            logger.info(f"サーバー分析が完了しました。結果を {analysis_file} に保存しました。")
            
        except Exception as e:
            logger.error(f"サーバー分析タスク実行中にエラーが発生しました: {e}")
    
    @weekly_server_analysis.before_loop
    async def before_weekly_server_analysis(self):
        """BOTが準備完了するまで待機"""
        await self.bot.wait_until_ready()
        logger.info("サーバー分析タスクの準備完了")
    
    @commands.hybrid_group(name="homepage_analyzer")
    async def homepage(self, ctx):
        """ホームページ関連のコマンドグループ"""
        if ctx.invoked_subcommand is None:
            await ctx.send("サブコマンドを指定してください。`analyze`など")

    @homepage.command(name="analyze", description="サーバーの情報を分析し、ホームページ用のコンテンツを生成します")
    @commands.has_permissions(administrator=True)
    async def analyze_server(self, ctx):
        """サーバーの情報を分析するコマンド"""
        await ctx.defer()
        
        try:
            if not self.openai_api_key:
                await ctx.send("OpenAI APIキーが設定されていません。環境変数 `OPENAI_API_KEY` を設定してください。")
                return
                
            guild = ctx.guild
            if guild.id != self.target_guild_id and self.target_guild_id != 0:
                await ctx.send("このコマンドは対象のサーバーでのみ使用できます。")
                return
                
            # データ収集
            await ctx.send("チャンネルデータを収集中...")
            channel_data = await self.collect_channel_data(guild)
            
            await ctx.send("ロール情報を収集中...")
            roles_data = await self.collect_roles_data(guild)
            
            # サーバー分析
            await ctx.send("サーバー分析を実行中（時間がかかります）...")
            analysis_data = await self.generate_server_summary(guild, channel_data, roles_data)
            
            # 結果を保存
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            analysis_file = os.path.join(self.cache_dir, f"server_analysis_{timestamp}.json")
            
            with open(analysis_file, "w", encoding="utf-8") as f:
                json.dump(analysis_data, f, ensure_ascii=False, indent=2)
            
            # Webサイト用APIにデータを送信
            await ctx.send("分析結果をWebサイトに送信中...")
            await self.send_to_api("discord/server-analysis", analysis_data)
            
            await ctx.send("サーバー分析が完了しました。結果を確認してください。")
            
            # 結果を分割して送信（Discordのメッセージ文字数制限対策）
            embed = discord.Embed(
                title=f"🔍 {guild.name} サーバー分析",
                description="サーバーの分析結果です。この内容はホームページにも反映されます。",
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="基本情報",
                value=f"メンバー数: {guild.member_count}\nチャンネル数: {len(guild.text_channels)}\nロール数: {len(guild.roles) - 1}",
                inline=False
            )
            
            embed.add_field(
                name="アクティブチャンネル TOP5",
                value="\n".join([f"<#{c[0]}>: {c[1]}メッセージ" for c in analysis_data["active_channels"][:5]]),
                inline=False
            )
            
            embed.add_field(
                name="人気ロール TOP5",
                value="\n".join([f"<@&{r[0]}>: {r[1]}メンバー" for r in analysis_data["popular_roles"][:5]]),
                inline=False
            )
            
            await ctx.send(embed=embed)
            
            # サーバー分析の要約（文字数制限のため分割）
            server_analysis = analysis_data["server_analysis"]
            segments = self.split_text(f"### サーバー分析結果\n\n{server_analysis}\n\n")
            
            for i, segment in enumerate(segments):
                if i == 0:
                    await ctx.send(segment)
                else:
                    await ctx.send(segment)
            
            # キャッチコピーの表示
            slogans = analysis_data["slogans"]
            await ctx.send(f"### キャッチコピー案\n\n{slogans}")
            
            # ウェルカムメッセージの表示
            welcome = analysis_data["welcome_messages"]
            await ctx.send(f"### ウェルカムメッセージ案\n\n{welcome}")
            
            # ウェブサイトへのデータ送信
            if self.api_token:
                await ctx.send("分析データをウェブサイトに送信中...")
                try:
                    await self.send_to_api("discord/server-analysis", analysis_data)
                    await ctx.send("✅ 分析データをウェブサイトに送信しました！ホームページでサーバー分析セクションを確認してください。")
                except Exception as e:
                    await ctx.send(f"⚠️ ウェブサイトへのデータ送信中にエラーが発生しました: {e}")
                    logger.error(f"ウェブサイトへのデータ送信中にエラーが発生: {e}")
            
            # 分析成功のお知らせ
            await ctx.send(f"✅ サーバー `{ctx.guild.name}` の分析が完了しました！分析データはBOTの`cache/server_analysis`フォルダに保存されました。")
            
        except Exception as e:
            await ctx.send(f"エラーが発生しました: {e}")
            logger.error(f"サーバー分析中にエラーが発生: {e}")
    
    def split_text(self, text: str, max_length: int = 1900) -> List[str]:
        """長いテキストを指定された最大文字数で分割する"""
        if len(text) <= max_length:
            return [text]
            
        # 行ごとに分割してから再構成
        lines = text.split('\n')
        chunks = []
        current_chunk = ""
        
        for line in lines:
            # 行自体が最大長を超える場合
            if len(line) > max_length:
                # 現在のチャンクが空でなければ追加
                if current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = ""
                
                # 長い行を単語単位で分割
                words = line.split(' ')
                word_chunk = ""
                
                for word in words:
                    if len(word_chunk) + len(word) + 1 <= max_length:
                        if word_chunk:
                            word_chunk += " " + word
                        else:
                            word_chunk = word
                    else:
                        chunks.append(word_chunk)
                        word_chunk = word
                
                if word_chunk:
                    current_chunk = word_chunk
            # 行を追加しても最大長を超えない場合
            elif len(current_chunk) + len(line) + 1 <= max_length:
                if current_chunk:
                    current_chunk += "\n" + line
                else:
                    current_chunk = line
            # 行を追加すると最大長を超える場合
            else:
                chunks.append(current_chunk)
                current_chunk = line
        
        # 最後のチャンクを追加
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks
        
    async def send_to_api(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """APIエンドポイントにデータを送信"""
        if not self.api_token:
            logger.error("APIトークンが設定されていません")
            return {"error": "APIトークンが設定されていません"}
            
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_token}"
                }
                
                # エンドポイントの先頭のスラッシュを削除して二重スラッシュを防ぐ
                clean_endpoint = endpoint.lstrip('/')
                url = f"{self.api_base_url}/{clean_endpoint}"
                logger.info(f"APIエンドポイントにデータを送信: {url}")
                
                async with session.post(url, headers=headers, json=data) as response:
                    if response.status not in (200, 201, 204):
                        response_text = await response.text()
                        logger.error(f"API呼び出しに失敗しました: {response.status} - {response_text}")
                        return False
                    return True
        except Exception as e:
            logger.error(f"API呼び出し中にエラーが発生しました: {e}")
            return False

async def setup(bot):
    """Cogをボットに追加"""
    await bot.add_cog(ServerAnalyzer(bot))
    logger.info("ServerAnalyzer Cogを読み込みました")
