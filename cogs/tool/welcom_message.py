import discord
from discord.ext import commands
from openai import OpenAI
import json
import os
import traceback
from utils.logging import setup_logging
from config.setting import get_settings
import httpx
import uuid
import random
import asyncio
import time
from utils.commands_help import is_guild, is_owner, log_commands

logger = setup_logging("D")
settings = get_settings()

# OpenAI APIキーを環境変数から取得
OPENAI_API_KEY = settings.etc_api_openai_api_key
logger.info(f"OpenAI APIキー設定状況: {'設定済み' if OPENAI_API_KEY else '未設定'}")
client_ai = OpenAI(api_key=OPENAI_API_KEY)

class UserJoinQueue:
    def __init__(self, bot):
        self.bot = bot
        self.queue = {}  # ユーザーID -> 参加情報のマッピング
        self.processing = set()  # 処理中のユーザーID
        self.lock = asyncio.Lock()  # 同時アクセス防止用ロック
        
    async def add_user(self, member, channel_id, welcome_text):
        """ユーザーを待機キューに追加"""
        async with self.lock:
            user_id = str(member.id)
            join_time = time.time()
            self.queue[user_id] = {
                'member': member,
                'channel_id': channel_id,
                'welcome_text': welcome_text,
                'join_time': join_time,
                'processed': False
            }
            logger.info(f"ユーザー {member.name}({member.id}) を参加キューに追加しました")
            
    async def process_queue(self):
        """キューを処理（定期的に呼び出す）"""
        async with self.lock:
            current_time = time.time()
            # キューに入っているがまだ処理されていないユーザーを処理
            for user_id, data in list(self.queue.items()):
                if data['processed'] or user_id in self.processing:
                    continue
                    
                # 参加から3秒以上経過したユーザーを処理
                if current_time - data['join_time'] >= 3:
                    self.processing.add(user_id)
                    # ロックの外で非同期処理を実行
                    asyncio.create_task(self._process_user(user_id, data))
    
    async def _process_user(self, user_id, data):
        """ユーザー個別の処理"""
        try:
            member = data['member']
            channel_id = data['channel_id']
            welcome_text = data['welcome_text']
            
            logger.info(f"ユーザー {member.name}({member.id}) の参加処理を開始します")
            
            # 画像取得処理
            image_data = await self._get_user_image(member.name)
            
            # ウェルカムメッセージ送信処理
            try:
                cv2_sender = CV2MessageSender(self.bot)
                await cv2_sender.send_welcome_message(
                    channel_id=channel_id,
                    member_mention=member.mention,
                    welcome_text=welcome_text,
                    image_data=image_data
                )
                logger.info(f"ユーザー {member.name}({member.id}) へのウェルカムメッセージを送信しました")
            except Exception as e:
                logger.error(f"ウェルカムメッセージ送信中にエラー: {e}\n{traceback.format_exc()}")
            
            # 処理完了をマーク
            async with self.lock:
                self.queue[user_id]['processed'] = True
                self.processing.remove(user_id)
                
            logger.info(f"ユーザー {member.name}({member.id}) の処理を完了しました")
            
        except Exception as e:
            logger.error(f"ユーザー {user_id} の処理中にエラー: {e}\n{traceback.format_exc()}")
            # エラーが発生しても処理完了をマークして次に進む
            async with self.lock:
                self.queue[user_id]['processed'] = True
                if user_id in self.processing:
                    self.processing.remove(user_id)
    
    async def _get_user_image(self, username, max_retries=2):
        """ユーザー名に対応する画像を取得"""
        image_channel_id = 1373853775235649639
        image_channel = self.bot.get_channel(image_channel_id)
        if not image_channel:
            logger.warning(f"画像チャンネル(ID:{image_channel_id})が見つかりません")
            return None
            
        for retry in range(max_retries):
            if retry > 0:
                await asyncio.sleep(1)
                
            try:
                async for msg in image_channel.history(limit=30):
                    msg_content = (msg.content or '').strip()
                    if msg_content == username and msg.attachments:
                        for att in msg.attachments:
                            if self._is_image(att):
                                image_data = await att.read()
                                logger.info(f"ユーザー {username} の画像 {att.filename} を取得しました")
                                return image_data
            except Exception as e:
                logger.warning(f"画像取得時にエラー（試行 {retry+1}/{max_retries}）: {e}")
        
        logger.info(f"ユーザー {username} の画像が見つかりませんでした")
        return None
    
    def _is_image(self, attachment):
        """添付ファイルが画像かどうかを判定"""
        return (
            (attachment.content_type and attachment.content_type.startswith('image')) or
            attachment.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp'))
        )

class CountryBasedWelcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.channel = None
        self.welcome_channels = {}
        logger.info("CountryBasedWelcome Cogを初期化中...")
        self.load_all_configs()
        logger.info(f"ウェルカムチャンネル設定: {self.welcome_channels}")
        self.cv2_sender = CV2MessageSender(bot)
        # 参加キューの初期化
        self.join_queue = UserJoinQueue(bot)
        # 定期的にキューを処理するタスクを開始
        self.queue_task = bot.loop.create_task(self._process_queue_periodically())
        logger.info("参加キューシステムを初期化しました")

    async def _process_queue_periodically(self):
        """定期的にキューを処理"""
        logger.info("参加キュー処理タスクを開始しました")
        while not self.bot.is_closed():
            try:
                await self.join_queue.process_queue()
            except Exception as e:
                logger.error(f"キュー処理中にエラー: {e}\n{traceback.format_exc()}")
            await asyncio.sleep(1)  # 1秒ごとに処理

    def save_config(self, guild_id, channel_id):
        logger.info(f"設定保存: ギルドID={guild_id}, チャンネルID={channel_id}")
        config_file_path = os.path.join(os.getcwd(), "data", "config.json")
        
        # dataディレクトリが存在しない場合は作成
        os.makedirs(os.path.dirname(config_file_path), exist_ok=True)
        
        try:
            if os.path.exists(config_file_path):
                with open(config_file_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    config[str(guild_id)] = {"welcome_channel": channel_id}
                with open(config_file_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=4)
                logger.info(f"既存の設定ファイルを更新しました: {config_file_path}")
            else:
                config = {str(guild_id): {"welcome_channel": channel_id}}
                with open(config_file_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=4)
                logger.info(f"新しい設定ファイルを作成しました: {config_file_path}")
            
            # メモリにも保存
            self.welcome_channels[str(guild_id)] = channel_id
        except Exception as e:
            logger.error(f"設定保存中にエラーが発生しました: {e}\n{traceback.format_exc()}")
                
    def load_all_configs(self):
        config_file_path = os.path.join(os.getcwd(), "data", "config.json")
        logger.info(f"設定ファイルをロード: {config_file_path}")
        
        if os.path.exists(config_file_path):
            try:
                with open(config_file_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    logger.info(f"設定ファイルの内容: {config}")
                    for guild_id, settings in config.items():
                        if "welcome_channel" in settings:
                            self.welcome_channels[guild_id] = settings["welcome_channel"]
                            logger.info(f"ギルド {guild_id} のウェルカムチャンネルを設定: {settings['welcome_channel']}")
            except Exception as e:
                logger.error(f"設定ファイルの読み込みに失敗しました: {e}\n{traceback.format_exc()}")
        else:
            logger.warning(f"設定ファイルが見つかりませんでした: {config_file_path}")

    def load_config(self, guild_id):
        logger.info(f"ギルド {guild_id} の設定をロード")
        
        # 既にキャッシュされている場合はそれを返す
        if str(guild_id) in self.welcome_channels:
            logger.info(f"キャッシュから設定を取得: ギルド {guild_id}, チャンネル {self.welcome_channels[str(guild_id)]}")
            return self.welcome_channels[str(guild_id)]
            
        config_file_path = os.path.join(os.getcwd(), "data", "config.json")
        if os.path.exists(config_file_path):
            try:
                with open(config_file_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    channel_id = config.get(str(guild_id), {}).get("welcome_channel", None)
                    if channel_id:
                        logger.info(f"ファイルから設定を取得: ギルド {guild_id}, チャンネル {channel_id}")
                        self.welcome_channels[str(guild_id)] = channel_id
                    else:
                        logger.warning(f"ギルド {guild_id} の設定が見つかりませんでした")
                    return channel_id
            except Exception as e:
                logger.error(f"設定ファイルの読み込み中にエラーが発生しました: {e}\n{traceback.format_exc()}")
                return None
        else:
            logger.warning(f"設定ファイルが見つかりませんでした: {config_file_path}")
        
        return None

    @commands.hybrid_group(name="welcome")
    @is_guild()
    @is_owner()
    @log_commands()
    async def welcome(self, ctx):
        await ctx.send("Welcome to the server!")
        
    @welcome.command(name="set_channel")
    @is_guild()
    @is_owner()
    @log_commands()
    async def set_channel(self, ctx, channel: discord.TextChannel):
        logger.info(f"ウェルカムチャンネル設定コマンド実行: ユーザー={ctx.author}, ギルド={ctx.guild.name}({ctx.guild.id}), チャンネル={channel.name}({channel.id})")
        self.channel = channel
        self.save_config(ctx.guild.id, channel.id)
        await ctx.send(f"ウェルカムチャンネルは{channel.mention}に設定されました。")
        logger.info(f"ウェルカムチャンネル設定完了: {channel.name}({channel.id})")
        
    @welcome.command(name="test_welcome_message")
    @is_guild()
    @is_owner()
    @log_commands()
    async def test_welcome_message(self, ctx):
        logger.info(f"新メンバー参加イベント: {ctx.author.display_name}({ctx.author.id}) がギルド {ctx.guild.name}({ctx.guild.id}) に参加")
        # ユーザーの表示名とグローバル名（バイオは取得不可）
        name = ctx.author.display_name
        global_name = ctx.author.name or ""
        logger.info(f"ユーザー情報: 表示名={name}, グローバル名={global_name}")

        # 設定を取得
        channel_id = self.load_config(ctx.guild.id)
        if not channel_id:
            logger.warning(f"ギルド {ctx.guild.id} のウェルカムチャンネルが設定されていません")
            await ctx.send("ウェルカムチャンネルが設定されていません。`/welcome set_channel`で設定してください。")
            return

        channel = self.bot.get_channel(channel_id)
        if not channel:
            logger.error(f"設定されたチャンネル(ID:{channel_id})が見つかりません")
            await ctx.send("設定されたチャンネルが見つかりません。チャンネルが削除された可能性があります。")
            return
        
        logger.info(f"ウェルカムチャンネルが見つかりました: {channel.name}({channel_id})")

        # 日本語のウェルカムメッセージ（構造化）
        welcome_message = (
            "## 🪄 WELCOME TO HOLOLIVE FAN SERVER\n"
            "**~つながる絆、ひろがる推し活~**\n\n"
            "🎉 サーバーにようこそ！ホロライブ好きが集まるこの場所で、たくさんの仲間と楽しい時間を過ごしましょう！\n\n"
            "📖 まずは [サーバールール](https://discord.com/channels/1092138492173242430/1120609874158563419) を最後まで読んで、サーバーのルールや使い方を確認してください。\n\n"
            "📝 自己紹介は <#1092682540986408990> へどうぞ！\n"
            "🗨️ ホロライブの話や好きなメンバーについては <#1092138493582520355> で気軽にどうぞ！"
        )

        # キューに追加して待機メッセージを表示
        await self.join_queue.add_user(ctx.author, channel_id, welcome_message)
        await ctx.send(f"テスト: {ctx.author.mention} のウェルカムメッセージを3秒後に {channel.mention} に送信します...")
    
    @welcome.command(name="test_cv2_welcome")
    @is_guild()
    @is_owner()
    @log_commands()
    async def test_cv2_welcome(self, ctx):
        """CV2形式のウェルカムメッセージをテスト送信します"""
        logger.info(f"CV2ウェルカムメッセージテスト: {ctx.author.display_name}({ctx.author.id}) がギルド {ctx.guild.name}({ctx.guild.id}) に参加")
        
        # 設定を取得
        channel_id = self.load_config(ctx.guild.id)
        if not channel_id:
            logger.warning(f"ギルド {ctx.guild.id} のウェルカムチャンネルが設定されていません")
            await ctx.send("ウェルカムチャンネルが設定されていません。`/welcome set_channel`で設定してください。")
            return

        channel = self.bot.get_channel(channel_id)
        if not channel:
            logger.error(f"設定されたチャンネル(ID:{channel_id})が見つかりません")
            await ctx.send("設定されたチャンネルが見つかりません。チャンネルが削除された可能性があります。")
            return
        
        logger.info(f"ウェルカムチャンネルが見つかりました: {channel.name}({channel_id})")

        # 日本語のウェルカムメッセージ
        welcome_message = (
            "## 🪄 WELCOME TO HOLOLIVE FAN SERVER\n"
            "**~つながる絆、ひろがる推し活~**\n"
            "━━━━━━━━━━━━━\n"
            "🎉 サーバーにようこそ！ホロライブ好きが集まるこの場所で、たくさんの仲間と楽しい時間を過ごしましょう！\n\n"
            "📖 まずは [サーバールール](https://discord.com/channels/1092138492173242430/1120609874158563419) を最後まで読んで、サーバーのルールや使い方を確認してください。\n\n"
            "📝 自己紹介は <#1092682540986408990> へどうぞ！\n"
            "🗨️ ホロライブの話や好きなメンバーについては <#1092138493582520355> で気軽にどうぞ！\n\n"
            "━━━━━━━━━━━━━\n"
        )

        # キューに追加して待機メッセージを表示
        await self.join_queue.add_user(ctx.author, channel_id, welcome_message)
        await ctx.send(f"テスト: CV2形式のウェルカムメッセージを3秒後に {channel.mention} に送信します...")
    
    @welcome.command(name="cv2")
    @is_guild()
    @is_owner()
    @log_commands()
    async def welcome_cv2(self, ctx):
        """シンプルなCV2形式のウェルカムメッセージをテスト送信します"""
        await ctx.send("CV2形式のウェルカムメッセージをテスト送信中...")
        
        # 設定を取得
        channel_id = self.load_config(ctx.guild.id)
        if not channel_id:
            await ctx.send("ウェルカムチャンネルが設定されていません。`/welcome set_channel`で設定してください。")
            return

        channel = self.bot.get_channel(channel_id)
        if not channel:
            await ctx.send("設定されたチャンネルが見つかりません。チャンネルが削除された可能性があります。")
            return
        
        # 元のウェルカムメッセージ（区切り線を削除）
        welcome_message = (
            "## 🪄 WELCOME TO HOLOLIVE FAN SERVER\n"
            "**~つながる絆、ひろがる推し活~**\n\n"
            "🎉 サーバーにようこそ！ホロライブ好きが集まるこの場所で、たくさんの仲間と楽しい時間を過ごしましょう！\n\n"
            "📖 まずは [サーバールール](https://discord.com/channels/1092138492173242430/1120609874158563419) を最後まで読んで、サーバーのルールや使い方を確認してください。\n\n"
            "📝 自己紹介は <#1092682540986408990> へどうぞ！\n"
            "🗨️ ホロライブの話や好きなメンバーについては <#1092138493582520355> で気軽にどうぞ！"
        )

        # キューに追加
        await self.join_queue.add_user(ctx.author, channel_id, welcome_message)
        await ctx.send(f"テスト: シンプルなCV2形式のウェルカムメッセージを3秒後に {channel.mention} に送信します...")
            
    @welcome.command(name="cv2_file")
    @is_guild()
    @is_owner()
    @log_commands()
    async def welcome_cv2_file(self, ctx, file_path: str = None):
        """指定したファイルパスの画像を使ってCV2形式ウェルカムメッセージをテスト送信します"""
        if not file_path:
            await ctx.send("ファイルパスを指定してください。例: `/welcome cv2_file ./images/welcome.png`")
            return
            
        # ファイルの存在確認と読み込み
        try:
            with open(file_path, 'rb') as f:
                image_data = f.read()
            logger.info(f"ファイル読み込み成功: {file_path}")
        except Exception as e:
            logger.error(f"ファイル読み込み失敗: {file_path}, エラー: {e}")
            await ctx.send(f"ファイルの読み込みに失敗しました: {e}")
            return
            
        # 設定を取得
        channel_id = self.load_config(ctx.guild.id)
        if not channel_id:
            await ctx.send("ウェルカムチャンネルが設定されていません。`/welcome set_channel`で設定してください。")
            return

        channel = self.bot.get_channel(channel_id)
        if not channel:
            await ctx.send("設定されたチャンネルが見つかりません。チャンネルが削除された可能性があります。")
            return
        
        # 元のウェルカムメッセージ（区切り線を削除）
        welcome_message = (
            "## 🪄 WELCOME TO HOLOLIVE FAN SERVER\n"
            "**~つながる絆、ひろがる推し活~**\n\n"
            "🎉 サーバーにようこそ！ホロライブ好きが集まるこの場所で、たくさんの仲間と楽しい時間を過ごしましょう！\n\n"
            "📖 まずは [サーバールール](https://discord.com/channels/1092138492173242430/1120609874158563419) を最後まで読んで、サーバーのルールや使い方を確認してください。\n\n"
            "📝 自己紹介は <#1092682540986408990> へどうぞ！\n"
            "🗨️ ホロライブの話や好きなメンバーについては <#1092138493582520355> で気軽にどうぞ！"
        )

        # CV2形式のメッセージを送信
        await ctx.send(f"ファイル {file_path} を使ってCV2形式のウェルカムメッセージを {channel.mention} に送信中...")
        result = await self.cv2_sender.send_welcome_message(
            channel_id=channel_id,
            member_mention=ctx.author.mention,
            welcome_text=welcome_message,
            image_data=image_data
        )
        
        if result:
            await ctx.send("CV2形式のウェルカムメッセージを送信しました。")
        else:
            await ctx.send("CV2形式ウェルカムメッセージの送信に失敗しました。ログを確認してください。")

    @welcome.command(name="cv2_attach")
    @is_guild()
    @is_owner()
    @log_commands()
    async def welcome_cv2_attach(self, ctx):
        """添付した画像を使ってCV2形式ウェルカムメッセージをテスト送信します"""
        if not ctx.message.attachments:
            await ctx.send("画像を添付してください。コマンドと一緒に画像をアップロードしてください。")
            return
            
        # 添付ファイルから画像データを取得
        attachment = ctx.message.attachments[0]
        if not attachment.content_type or not attachment.content_type.startswith('image'):
            await ctx.send("添付ファイルが画像ではありません。")
            return
            
        # 画像データを読み込み
        try:
            image_data = await attachment.read()
            logger.info(f"添付画像読み込み成功: {attachment.filename}")
        except Exception as e:
            logger.error(f"添付画像読み込み失敗: {attachment.filename}, エラー: {e}")
            await ctx.send(f"画像の読み込みに失敗しました: {e}")
            return
            
        # 設定を取得
        channel_id = self.load_config(ctx.guild.id)
        if not channel_id:
            await ctx.send("ウェルカムチャンネルが設定されていません。`/welcome set_channel`で設定してください。")
            return

        channel = self.bot.get_channel(channel_id)
        if not channel:
            await ctx.send("設定されたチャンネルが見つかりません。チャンネルが削除された可能性があります。")
            return
        
        # 元のウェルカムメッセージ（区切り線を削除）
        welcome_message = (
            "## 🪄 WELCOME TO HOLOLIVE FAN SERVER\n"
            "**~つながる絆、ひろがる推し活~**\n\n"
            "🎉 サーバーにようこそ！ホロライブ好きが集まるこの場所で、たくさんの仲間と楽しい時間を過ごしましょう！\n\n"
            "📖 まずは [サーバールール](https://discord.com/channels/1092138492173242430/1120609874158563419) を最後まで読んで、サーバーのルールや使い方を確認してください。\n\n"
            "📝 自己紹介は <#1092682540986408990> へどうぞ！\n"
            "🗨️ ホロライブの話や好きなメンバーについては <#1092138493582520355> で気軽にどうぞ！"
        )

        # CV2形式のメッセージを送信
        await ctx.send(f"添付画像 {attachment.filename} を使ってCV2形式のウェルカムメッセージを {channel.mention} に送信中...")
        result = await self.cv2_sender.send_welcome_message(
            channel_id=channel_id,
            member_mention=ctx.author.mention,
            welcome_text=welcome_message,
            image_data=image_data
        )
        
        if result:
            await ctx.send("CV2形式のウェルカムメッセージを送信しました。")
        else:
            await ctx.send("CV2形式ウェルカムメッセージの送信に失敗しました。")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        logger.info(f"新メンバー参加イベント: {member.display_name}({member.id}) がギルド {member.guild.name}({member.guild.id}) に参加")
        # ユーザーの表示名とグローバル名（バイオは取得不可）
        name = member.display_name
        global_name = member.name or ""
        logger.info(f"ユーザー情報: 表示名={name}, グローバル名={global_name}")

        # 設定を取得
        channel_id = self.load_config(member.guild.id)
        if not channel_id:
            logger.warning(f"ギルド {member.guild.id} のウェルカムチャンネルが設定されていません")
            return

        channel = self.bot.get_channel(channel_id)
        if not channel:
            logger.error(f"設定されたチャンネル(ID:{channel_id})が見つかりません")
            return
        
        logger.info(f"ウェルカムチャンネルが見つかりました: {channel.name}({channel_id})")

        # 日本語のウェルカムメッセージ（構造化）
        welcome_message = (
            "## 🪄 WELCOME TO HOLOLIVE FAN SERVER\n"
            "**~つながる絆、ひろがる推し活~**\n\n"
            "🎉 サーバーにようこそ！ホロライブ好きが集まるこの場所で、たくさんの仲間と楽しい時間を過ごしましょう！\n\n"
            "📖 まずは [サーバールール](https://discord.com/channels/1092138492173242430/1120609874158563419) を最後まで読んで、サーバーのルールや使い方を確認してください。\n\n"
            "📝 自己紹介は <#1092682540986408990> へどうぞ！\n"
            "🗨️ ホロライブの話や好きなメンバーについては <#1092138493582520355> で気軽にどうぞ！"
        )

        # キューにユーザーを追加（3秒後に処理される）
        await self.join_queue.add_user(member, channel_id, welcome_message)
        logger.info(f"ユーザー {member.name}({member.id}) をウェルカムキューに追加しました")

    @commands.Cog.listener()
    async def on_interaction(self, interaction):
        """ボタン押下時のインタラクション処理"""
        if not interaction.data:
            return
            
        custom_id = interaction.data.get("custom_id", "")
        if custom_id.startswith("welcome_"):
            logger.info(f"ウェルカムボタン押下: {custom_id}, ユーザー={interaction.user.display_name}({interaction.user.id})")
            await self.cv2_sender.handle_welcome_button(interaction)

    def cog_unload(self):
        """Cogがアンロードされる際にタスクをキャンセル"""
        if hasattr(self, 'queue_task') and self.queue_task:
            self.queue_task.cancel()
            logger.info("参加キュー処理タスクを停止しました")

# --- 多言語案内ボタンViewクラス ---
class WelcomeLanguageView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="English", style=discord.ButtonStyle.primary, emoji="🇬🇧")
    async def english_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "## 🪄 WELCOME TO HOLOLIVE FAN SERVER\n"
            "**~Connecting bonds, expanding oshi life~**\n"
            "━━━━━━━━━━━━━\n"
            "🎉 Welcome to the server! We hope you have a great time here!\n\n"
            "📖 Please read [Terms of Use](https://discord.com/channels/1092138492173242430/1271236088769413120) first!\n\n"
            "📝 Introduce yourself in <#1092682540986408990>!\n"
            "🗨️ Feel free to chat about Hololive and your favorite members in <#1092138493582520355>!\n\n"
            "━━━━━━━━━━━━━\n"
            "Note: This is a Japanese-language server. We encourage communication in Japanese.\n"
            "Feel free to use translation tools to help with communication!\n\n"
            "━━━━━━━━━━━━━",
            ephemeral=True
        )

    @discord.ui.button(label="한국어", style=discord.ButtonStyle.primary, emoji="🇰🇷")
    async def korean_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "## 🪄 HOLOLIVE FAN 서버에 오신 것을 환영합니다\n"
            "**~연결되는 인연, 확장되는 오시 활동~**\n"
            "━━━━━━━━━━━━━\n"
            "🎉 서버에 오신 것을 환영합니다! 많은 친구들과 즐거운 시간을 보내세요!\n\n"
            "📖 먼저 [서버 이용 규칙](https://discord.com/channels/1092138492173242430/1372718717489909781) 를 읽어 주세요!\n\n"
            "📝 자기소개는 <#1092682540986408990> 에서 해주세요!\n"
            "🗨️ 홀로라이브 이야기나 좋아하는 멤버에 대해서는 <#1092138493582520355> 에서 자유롭게 대화하세요!\n\n"
            "━━━━━━━━━━━━━"
            "※이 서버는 일본어가 주 언어입니다. 일본어로 대화하시는 것을 권장합니다.\n"
            "번역기 사용은 자유입니다!\n\n"
            "━━━━━━━━━━━━━",
            ephemeral=True
        )

    @discord.ui.button(label="中文", style=discord.ButtonStyle.primary, emoji="🇨🇳")
    async def chinese_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "## 🪄 欢迎来到 HOLOLIVE FAN 服务器\n"
            "**~连接的羁绊，扩展的推活~**\n"
            "━━━━━━━━━━━━━\n"
            "🎉 欢迎加入服务器！希望你在这里度过愉快的时光！\n\n"
            "📖 请先阅读 [服务器使用条款](https://discord.com/channels/1092138492173242430/1372718428015693956) ！\n\n"
            "📝 自我介绍请前往 <#1092682540986408990> ！\n"
            "🗨️ 你可以在 <#1092138493582520355> 畅谈你的推和喜欢的成员！\n\n"
            "━━━━━━━━━━━━━\n"
            "※本服务器主要使用日语。建议使用日语进行交流。\n"
            "可以随意使用翻译工具帮助交流！\n\n"
            "━━━━━━━━━━━━━",
            ephemeral=True
        )

# --- CV2形式のメッセージ送信ユーティリティ ---
class CV2MessageSender:
    def __init__(self, bot):
        self.bot = bot
        self.api_version = "v10"
        self.base_url = f"https://discord.com/api/{self.api_version}"
        self.client = httpx.AsyncClient(timeout=30.0)
        
    async def send_welcome_message(self, channel_id, member_mention, welcome_text, image_data=None):
        """
        CV2形式のウェルカムメッセージを送信する
        
        Parameters:
        -----------
        channel_id : int
            メッセージを送信するチャンネルID
        member_mention : str
            メンションするメンバー文字列（例: "<@123456789>")
        welcome_text : str
            ウェルカムメッセージテキスト
        image_data : bytes, optional
            添付する画像データ（バイナリ）
        """
        logger.info(f"CV2形式のウェルカムメッセージを送信: チャンネルID={channel_id}")
        
        endpoint = f"{self.base_url}/channels/{channel_id}/messages"
        
        # 虹色のカラーコード（Discord用の整数値）
        rainbow_colors = [
            15158332,  # 赤色 (0xE74C3C)
            16754470,  # オレンジ色 (0xFFA726) 
            15844367,  # 黄色 (0xF1C40F)
            5763719,   # 緑色 (0x57F287)
            3447003,   # 青色 (0x3498DB)
            7506394,   # 藍色 (0x7289DA)
            10181046   # 紫色 (0x9B59B6)
        ]
        
        # ランダムに色を選択
        accent_color = random.choice(rainbow_colors)
        
        # ウェルカムメッセージを解析してタイトルと本文に分割
        message_parts = welcome_text.split('\n\n', 2)
        header_parts = message_parts[0].split('\n')
        title = header_parts[0].replace('#', '').strip()  # "## 🪄 WELCOME TO HOLOLIVE FAN SERVER"から#を削除
        subtitle = message_parts[1].replace('*', '').strip()  # "**~つながる絆、ひろがる推し活~**"から*を削除
        body = '\n\n'.join(message_parts[2:])  # 本文内容
        
        # メンション用テキスト表示
        mention_component = {
            "type": 10,  # Text Display
            "content": member_mention
        }
        
        # Container内のコンポーネント構築
        container_components = []
        
        # 画像がある場合はMedia Galleryをcontainer内の先頭に追加
        attachments = []
        if image_data:
            # 一意のIDを生成
            attachment_id = str(uuid.uuid4())
            filename = f"welcome_image_{attachment_id}.png"
            
            # attachmentsを追加
            attachments = [{
                "id": "0",
                "filename": filename
            }]
            
            # Media Galleryをcontainer_componentsに追加
            container_components.append({
                "type": 12,  # Media Gallery
                "items": [
                    {
                        "media": {"url": f"attachment://{filename}"}
                    }
                ]
            })
        
        # Section: タイトルとサブタイトル（横並びにはしない）
        container_components.append({
            "type": 10,  # Text Display
            "content": f"## {title}"
        })
        
        container_components.append({
            "type": 10,  # Text Display
            "content": f"**{subtitle}**"
        })
        
        # 区切り線
        container_components.append({
            "type": 14,  # Separator
            "divider": True,
            "spacing": 1
        })
        
        # 本文
        container_components.append({
            "type": 10,  # Text Display
            "content": f"{body}"
        })
        
        # ボタンセクション前の区切り線
        container_components.append({
            "type": 14,  # Separator
            "divider": True,
            "spacing": 2  # 大きめの余白
        })
        
        # Section: サーバールールへのリンク
        container_components.append({
            "type": 9,  # Section
            "components": [
                {
                    "type": 10,  # Text Display
                    "content": "📖 サーバールールを確認:"
                }
            ],
            "accessory": {
                "type": 2,  # Button
                "style": 5,  # Link
                "label": "ルール",
                "url": "https://discord.com/channels/1092138492173242430/1120609874158563419"
            }
        })
        
        # Section: 自己紹介チャンネル
        container_components.append({
            "type": 9,  # Section
            "components": [
                {
                    "type": 10,  # Text Display
                    "content": "📝 自己紹介はこちら:"
                }
            ],
            "accessory": {
                "type": 2,  # Button
                "style": 5,  # Link
                "label": "自己紹介",
                "url": "https://discord.com/channels/1092138492173242430/1092682540986408990"
            }
        })
        
        # Section: 雑談チャンネル
        container_components.append({
            "type": 9,  # Section
            "components": [
                {
                    "type": 10,  # Text Display
                    "content": "🗨️ ホロライブの話題はこちら:"
                }
            ],
            "accessory": {
                "type": 2,  # Button
                "style": 5,  # Link
                "label": "雑談",
                "url": "https://discord.com/channels/1092138492173242430/1092138493582520355"
            }
        })
        
        # 言語選択部分の前の区切り線
        container_components.append({
            "type": 14,  # Separator
            "divider": True,
            "spacing": 2  # 大きめの余白
        })
        
        # 言語選択の見出し
        container_components.append({
            "type": 10,  # Text Display
            "content": "### 言語選択 / Language / 언어 / 语言"
        })
        
        # 言語選択の説明
        container_components.append({
            "type": 10,  # Text Display
            "content": "If you need a language other than Japanese, please click one of the buttons below👇\n" +
                     "한국어/중국어 안내가 필요하신 분은 아래 버튼을 눌러주세요👇\n" +
                     "如需其他语言的欢迎信息，请点击下方按钮👇"
        })
        
        # 言語選択ボタンを横並びに配置
        container_components.append({
            "type": 1,  # Action Row
            "components": [
                {
                    "type": 2,  # Button
                    "style": 1,
                    "label": "English",
                    "custom_id": "welcome_english",
                    "emoji": {"name": "🇬🇧"}
                },
                {
                    "type": 2,  # Button
                    "style": 1,
                    "label": "한국어",
                    "custom_id": "welcome_korean",
                    "emoji": {"name": "🇰🇷"}
                },
                {
                    "type": 2,  # Button
                    "style": 1,
                    "label": "中文",
                    "custom_id": "welcome_chinese",
                    "emoji": {"name": "🇨🇳"}
                }
            ]
        })
        
        # Containerコンポーネント（言語に応じた色に変更）
        container = {
            "type": 17,  # Container
            "accent_color": accent_color,
            "components": container_components
        }
        
        # CV2形式の構造化されたコンポーネント
        components = [mention_component, container]
        
        # リクエストのベースとなるJSONデータ
        payload = {
            "flags": 32768,  # IS_COMPONENTS_V2 フラグ
            "components": components
        }
        
        # 共通のヘッダー
        headers = {
            "Authorization": f"Bot {self.bot.http.token}"
        }
        
        # 画像を添付する場合
        if image_data:
            try:
                # multipart/form-dataリクエストの準備
                files = {
                    "files[0]": (filename, image_data, "image/png")
                }
                
                # attachmentsを設定
                payload["attachments"] = attachments
                
                # multipart/form-dataリクエスト
                form = {"payload_json": json.dumps(payload)}
                
                # HTTP POSTリクエスト送信
                response = await self.client.post(
                    endpoint,
                    headers=headers,
                    data=form,
                    files=files
                )
                
                if response.status_code in (200, 201):
                    logger.info(f"CV2メッセージ送信成功: チャンネルID={channel_id}")
                    return response.json()
                else:
                    logger.error(f"CV2メッセージ送信失敗: ステータス={response.status_code}, エラー={response.text}")
                    return None
                    
            except Exception as e:
                logger.error(f"CV2画像付きメッセージ送信中にエラー: {e}\n{traceback.format_exc()}")
                # 画像添付でエラーが発生した場合はテキストのみで再送信を試みる
                image_data = None
        
        # 画像がない場合やエラー後の再試行: JSONのみの送信
        if not image_data:
            try:
                headers["Content-Type"] = "application/json"
                
                # HTTP POSTリクエスト送信
                response = await self.client.post(
                    endpoint,
                    headers=headers,
                    json=payload
                )
                
                if response.status_code in (200, 201):
                    logger.info(f"CV2メッセージ送信成功: チャンネルID={channel_id}")
                    return response.json()
                else:
                    logger.error(f"CV2メッセージ送信失敗: ステータス={response.status_code}, エラー={response.text}")
                    return None
            except Exception as e:
                logger.error(f"CV2メッセージ送信中にエラー: {e}\n{traceback.format_exc()}")
                return None

    async def handle_welcome_button(self, interaction):
        """
        CV2形式のウェルカムボタンが押された時の処理
        
        Parameters:
        -----------
        interaction : discord.Interaction
            ボタン押下時のインタラクション
        """
        custom_id = interaction.data.get("custom_id", "")
        
        # 虹色のカラーコード（Discord用の整数値）
        rainbow_colors = [
            15158332,  # 赤色 (0xE74C3C)
            16754470,  # オレンジ色 (0xFFA726) 
            15844367,  # 黄色 (0xF1C40F)
            5763719,   # 緑色 (0x57F287)
            3447003,   # 青色 (0x3498DB)
            7506394,   # 藍色 (0x7289DA)
            10181046   # 紫色 (0x9B59B6)
        ]
        
        # ランダムに色を選択
        accent_color = random.choice(rainbow_colors)
        
        # 言語に応じたウェルカムメッセージを取得（テキスト区切り線を削除）
        if custom_id == "welcome_english":
            title = "🪄 WELCOME TO HOLOLIVE FAN SERVER"
            subtitle = "~Connecting bonds, expanding oshi life~"
            content = (
                "🎉 Welcome to the server! We hope you have a great time here!\n\n"
                "📖 Please read [Terms of Use](https://discord.com/channels/1092138492173242430/1271236088769413120) first!\n\n"
                "📝 Introduce yourself in <#1092682540986408990>!\n"
                "🗨️ Feel free to chat about Hololive and your favorite members in <#1092138493582520355>!\n\n"
                "Note: This is a Japanese-language server. We encourage communication in Japanese.\n"
                "Feel free to use translation tools to help with communication!"
            )
        elif custom_id == "welcome_korean":
            title = "🪄 HOLOLIVE FAN 서버에 오신 것을 환영합니다"
            subtitle = "~연결되는 인연, 확장되는 오시 활동~"
            content = (
                "🎉 서버에 오신 것을 환영합니다! 많은 친구들과 즐거운 시간을 보내세요!\n\n"
                "📖 먼저 [서버 이용 규칙](https://discord.com/channels/1092138492173242430/1372718717489909781) 를 읽어 주세요!\n\n"
                "📝 자기소개는 <#1092682540986408990> 에서 해주세요!\n"
                "🗨️ 홀로라이브 이야기나 좋아하는 멤버에 대해서는 <#1092138493582520355> 에서 자유롭게 대화하세요!\n\n"
                "※이 서버는 일본어가 주 언어입니다. 일본어로 대화하시는 것을 권장합니다.\n"
                "번역기 사용은 자유입니다!"
            )
        elif custom_id == "welcome_chinese":
            title = "🪄 欢迎来到 HOLOLIVE FAN 服务器"
            subtitle = "~连接的羁绊，扩展的推活~"
            content = (
                "🎉 欢迎加入服务器！希望你在这里度过愉快的时光！\n\n"
                "📖 请先阅读 [服务器使用条款](https://discord.com/channels/1092138492173242430/1372718428015693956) ！\n\n"
                "📝 自我介绍请前往 <#1092682540986408990> ！\n"
                "🗨️ 你可以在 <#1092138493582520355> 畅谈你的推和喜欢的成员！\n\n"
                "※本服务器主要使用日语。建议使用日语进行交流。\n"
                "可以随意使用翻译工具帮助交流！"
            )
        else:
            # 未知のカスタムIDの場合
            logger.warning(f"未知のウェルカムボタンID: {custom_id}")
            return
            
        # インタラクションに応答
        try:
            endpoint = f"{self.base_url}/interactions/{interaction.id}/{interaction.token}/callback"
            
            # Container内のコンポーネント
            container_components = []
            
            # タイトルとサブタイトル
            container_components.append({
                "type": 10,  # Text Display
                "content": f"## {title}"
            })
            
            container_components.append({
                "type": 10,  # Text Display
                "content": f"**{subtitle}**"
            })
            
            # 区切り線
            container_components.append({
                "type": 14,  # Separator
                "divider": True,
                "spacing": 1
            })
            
            # 本文
            container_components.append({
                "type": 10,  # Text Display
                "content": content
            })
            
            # ボタンセクション前の区切り線
            container_components.append({
                "type": 14,  # Separator
                "divider": True,
                "spacing": 2  # 大きめの余白
            })
            
            # 各言語に合わせたサーバールール、自己紹介、雑談チャンネルのリンクをSection形式で追加
            if custom_id == "welcome_english":
                # 英語版のリンクセクション
                container_components.append({
                    "type": 9,  # Section
                    "components": [
                        {
                            "type": 10,  # Text Display
                            "content": "📖 Terms of Use:"
                        }
                    ],
                    "accessory": {
                        "type": 2,  # Button
                        "style": 5,  # Link
                        "label": "Rules",
                        "url": "https://discord.com/channels/1092138492173242430/1271236088769413120"
                    }
                })
            elif custom_id == "welcome_korean":
                # 韓国語版のリンクセクション
                container_components.append({
                    "type": 9,  # Section
                    "components": [
                        {
                            "type": 10,  # Text Display
                            "content": "📖 이용 규칙:"
                        }
                    ],
                    "accessory": {
                        "type": 2,  # Button
                        "style": 5,  # Link
                        "label": "규칙",  # 「規則」를 의미하는 한국어
                        "url": "https://discord.com/channels/1092138492173242430/1372718717489909781"
                    }
                })
            elif custom_id == "welcome_chinese":
                # 中国語版のリンクセクション
                container_components.append({
                    "type": 9,  # Section
                    "components": [
                        {
                            "type": 10,  # Text Display
                            "content": "📖 服务器使用条款:"
                        }
                    ],
                    "accessory": {
                        "type": 2,  # Button
                        "style": 5,  # Link
                        "label": "规则",  # 「規則」を意味する中国語
                        "url": "https://discord.com/channels/1092138492173242430/1372718428015693956"
                    }
                })
            
            # 言語に応じた自己紹介チャンネルリンク
            intro_labels = {
                "welcome_english": "Intro",
                "welcome_korean": "자기소개",  # 「自己紹介」를 의미하는 한국어
                "welcome_chinese": "自我介绍"   # 「自己紹介」를 의미하는 中国語
            }
            
            container_components.append({
                "type": 9,  # Section
                "components": [
                    {
                        "type": 10,  # Text Display
                        "content": "📝 " + ("Introduce yourself:" if custom_id == "welcome_english" else 
                                          "자기소개:" if custom_id == "welcome_korean" else 
                                          "自我介绍:")
                    }
                ],
                "accessory": {
                    "type": 2,  # Button
                    "style": 5,  # Link
                    "label": intro_labels.get(custom_id, "Intro"),
                    "url": "https://discord.com/channels/1092138492173242430/1092682540986408990"
                }
            })
            
            # 言語に応じた雑談チャンネルリンク
            chat_labels = {
                "welcome_english": "Chat",
                "welcome_korean": "채팅",  # 「チャット」를 의미하는 한국어
                "welcome_chinese": "聊天"   # 「チャット」를 의미하는 中国語
            }
            
            container_components.append({
                "type": 9,  # Section
                "components": [
                    {
                        "type": 10,  # Text Display
                        "content": "🗨️ " + ("Chat about Hololive:" if custom_id == "welcome_english" else 
                                          "홀로라이브 이야기:" if custom_id == "welcome_korean" else 
                                          "讨论话题:")
                    }
                ],
                "accessory": {
                    "type": 2,  # Button
                    "style": 5,  # Link
                    "label": chat_labels.get(custom_id, "Chat"),
                    "url": "https://discord.com/channels/1092138492173242430/1092138493582520355"
                }
            })
            
            # フッター
            container_components.append({
                "type": 14,  # Separator
                "divider": True,
                "spacing": 1
            })
            
            container_components.append({
                "type": 10,  # Text Display
                "content": "© Hololive Fan Server • This message is ephemeral (only visible to you)"
            })
            
            # Containerコンポーネント（言語に応じた色に変更）
            container = {
                "type": 17,  # Container
                "accent_color": accent_color,
                "components": container_components
            }
            
            # CV2形式の構造化されたコンポーネント
            components = [container]
            
            response_data = {
                "type": 4,  # CHANNEL_MESSAGE_WITH_SOURCE
                "data": {
                    "flags": 32768 | 64,  # IS_COMPONENTS_V2 | EPHEMERAL
                    "components": components
                }
            }
            
            headers = {
                "Authorization": f"Bot {self.bot.http.token}",
                "Content-Type": "application/json"
            }
            
            # HTTP POSTリクエスト送信
            response = await self.client.post(
                endpoint,
                headers=headers,
                json=response_data
            )
            
            if response.status_code in (200, 201, 204):
                logger.info(f"CV2インタラクション応答成功: カスタムID={custom_id}")
            else:
                logger.error(f"CV2インタラクション応答失敗: ステータス={response.status_code}, エラー={response.text}")
        except Exception as e:
            logger.error(f"CV2インタラクション応答中にエラー: {e}\n{traceback.format_exc()}")
            
    def __del__(self):
        # クライアントのクローズ処理
        # 非同期操作はデストラクタで直接実行できないため、ログだけ出しておく
        if hasattr(self, 'client'):
            logger.info("CV2MessageSender instance is being destroyed, but client.aclose() cannot be awaited in __del__")
            
    async def close(self):
        """リソースを明示的に解放するための非同期メソッド"""
        if hasattr(self, 'client'):
            await self.client.aclose()
            logger.info("CV2MessageSender client closed successfully")

async def setup(bot):
    logger.info("CountryBasedWelcome Cogをセットアップ中...")
    try:
        await bot.add_cog(CountryBasedWelcome(bot))
        logger.info("CountryBasedWelcome Cogの登録が完了しました")
    except Exception as e:
        logger.error(f"CountryBasedWelcome Cogの登録に失敗しました: {e}\n{traceback.format_exc()}")