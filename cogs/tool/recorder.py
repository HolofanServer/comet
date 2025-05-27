import discord
from discord.ext import commands, voice_recv
import whisper
import asyncio
import wave
import httpx
import traceback
import os
import ctypes
import ctypes.util
import soundfile as sf
from datetime import datetime
from typing import Dict

# Opusライブラリを明示的にロード
try:
    if not discord.opus.is_loaded():
        opus_path = ctypes.util.find_library('opus')
        if opus_path:
            discord.opus.load_opus(opus_path)
            print(f"Opusライブラリをロードしました: {opus_path}")
        else:
            # macOSでのHomebrewパスを試す
            brew_paths = [
                '/opt/homebrew/lib/libopus.dylib',
                '/usr/local/lib/libopus.dylib',
                '/usr/local/Cellar/opus/1.5.2/lib/libopus.dylib',  # バージョンは変わる可能性あり
            ]
            
            for path in brew_paths:
                if os.path.exists(path):
                    discord.opus.load_opus(path)
                    print(f"Opusライブラリをロードしました: {path}")
                    break
            else:
                print("Opusライブラリが見つかりませんでした。音声機能が利用できない可能性があります。")
except Exception as e:
    print(f"Opusライブラリのロード中にエラーが発生しました: {e}")


from utils.logging import setup_logging
from utils.commands_help import is_owner, log_commands, is_guild

from config.setting import get_settings

logger = setup_logging(__name__)
settings = get_settings()


class RecordingConsent:
    """録音同意管理クラス"""
    def __init__(self, bot, ctx):
        self.bot = bot
        self.ctx = ctx
        self.api_version = "v10"
        self.base_url = f"https://discord.com/api/{self.api_version}"
        self.client = httpx.AsyncClient(timeout=30.0)
        self.consent_users: Dict[int, bool] = {}
        self.original_message_id = None
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    async def send_consent_request(self, channel_id, users):
        """
        指定されたチャンネルに録音同意リクエストを送信する
        
        Parameters:
        -----------
        channel_id : int
            メッセージを送信するチャンネルID
        users : List[discord.Member]
            同意を求めるユーザーリスト
        """
        logger.info(f"録音同意リクエストを送信: チャンネルID={channel_id}, ユーザー数={len(users)}")
        
        endpoint = f"{self.base_url}/channels/{channel_id}/messages"
        
        # 全ユーザーを未同意状態で初期化
        self.consent_users = {user.id: False for user in users}
        
        # ユーザーリストテキストを作成
        user_list_text = "\n".join([f"- {user.display_name}: {'✅ 同意済み' if self.consent_users.get(user.id, False) else '⏳ 待機中'}" for user in users])
        
        # Discord APIの要件に合わせて構造を変更
        # テキスト部分をメッセージのコンテンツとして送信
        message_content = f"## 🎙️ 録音同意リクエスト\n\nボイスチャンネルの録音を開始するには、参加者全員の同意が必要です。\n録音に同意する場合は「同意する」ボタンを押してください。\n30秒以内に全員の同意が得られない場合、録音はキャンセルされます。\n\n### 参加者リスト\n{user_list_text}"
        
        # ボタンをActionRow内に配置
        action_row = {
            "type": 1,  # ActionRow
            "components": [
                {
                    "type": 2,  # ボタン
                    "style": 3,  # 緑色
                    "label": "同意する",
                    "custom_id": "recording_consent_agree",
                    "emoji": {"name": "✅"}
                },
                {
                    "type": 2,  # ボタン
                    "style": 4,  # 赤色
                    "label": "キャンセル",
                    "custom_id": "recording_consent_cancel",
                    "emoji": {"name": "❌"}
                }
            ]
        }
        
        payload = {
            "content": message_content,
            "components": [action_row]
        }
        
        headers = {
            "Authorization": f"Bot {self.bot.http.token}",
            "Content-Type": "application/json"
        }
        
        try:
            response = await self.client.post(
                endpoint,
                headers=headers,
                json=payload
            )
            
            if response.status_code in (200, 201):
                logger.info(f"録音同意リクエスト送信成功: チャンネルID={channel_id}")
                response_data = response.json()
                self.original_message_id = response_data.get("id")
                return response_data
            else:
                logger.error(f"録音同意リクエスト送信失敗: ステータス={response.status_code}, エラー={response.text}")
                return None
        except Exception as e:
            logger.error(f"録音同意リクエスト送信中にエラー: {e}\n{traceback.format_exc()}")
            return None
    
    async def update_consent_message(self, channel_id, users):
        """同意メッセージを更新する"""
        if not self.original_message_id:
            return False
        
        endpoint = f"{self.base_url}/channels/{channel_id}/messages/{self.original_message_id}"
        
        # ユーザーリストテキストを更新
        user_list_text = "\n".join([f"- {user.display_name}: {'✅ 同意済み' if self.consent_users.get(user.id, False) else '⏳ 待機中'}" for user in users])
        
        # Discord APIの要件に合わせて構造を変更
        # テキスト部分をメッセージのコンテンツとして送信
        message_content = f"## 🎙️ 録音同意リクエスト\n\nボイスチャンネルの録音を開始するには、参加者全員の同意が必要です。\n録音に同意する場合は「同意する」ボタンを押してください。\n30秒以内に全員の同意が得られない場合、録音はキャンセルされます。\n\n### 参加者リスト\n{user_list_text}"
        
        # ボタンをActionRow内に配置
        action_row = {
            "type": 1,  # ActionRow
            "components": [
                {
                    "type": 2,  # ボタン
                    "style": 3,  # 緑色
                    "label": "同意する",
                    "custom_id": "recording_consent_agree",
                    "emoji": {"name": "✅"}
                },
                {
                    "type": 2,  # ボタン
                    "style": 4,  # 赤色
                    "label": "キャンセル",
                    "custom_id": "recording_consent_cancel",
                    "emoji": {"name": "❌"}
                }
            ]
        }
        
        payload = {
            "content": message_content,
            "components": [action_row]
        }
        
        headers = {
            "Authorization": f"Bot {self.bot.http.token}",
            "Content-Type": "application/json"
        }
        
        try:
            response = await self.client.patch(
                endpoint,
                headers=headers,
                json=payload
            )
            
            if response.status_code in (200, 201):
                logger.info(f"録音同意メッセージ更新成功: メッセージID={self.original_message_id}")
                return True
            else:
                logger.error(f"録音同意メッセージ更新失敗: ステータス={response.status_code}, エラー={response.text}")
                return False
        except Exception as e:
            logger.error(f"録音同意メッセージ更新中にエラー: {e}\n{traceback.format_exc()}")
            return False
    
    async def complete_consent_message(self, channel_id, success=True):
        """同意プロセスの完了メッセージを表示する"""
        if not self.original_message_id:
            return False
        
        endpoint = f"{self.base_url}/channels/{channel_id}/messages/{self.original_message_id}"
        
        # ステータスと説明文を設定
        status_emoji = "✅" if success else "❌"
        status_text = "録音開始" if success else "録音キャンセル"
        description_text = "全員の同意が得られたため、録音を開始します。" if success else "録音がキャンセルされました。"
        
        # Discord APIの要件に合わせてメッセージコンテンツを設定
        message_content = f"## {status_emoji} {status_text}\n\n{description_text}"
        
        # ボタン等のコンポーネントが不要なため、空のActionRowを送信する
        # これは既存のボタンをクリアするため
        payload = {
            "content": message_content,
            "components": []
        }
        
        headers = {
            "Authorization": f"Bot {self.bot.http.token}",
            "Content-Type": "application/json"
        }
        
        try:
            response = await self.client.patch(
                endpoint,
                headers=headers,
                json=payload
            )
            
            if response.status_code in (200, 201):
                logger.info(f"録音同意完了メッセージ更新成功: メッセージID={self.original_message_id}")
                return True
            else:
                logger.error(f"録音同意完了メッセージ更新失敗: ステータス={response.status_code}, エラー={response.text}")
                return False
        except Exception as e:
            logger.error(f"録音同意完了メッセージ更新中にエラー: {e}\n{traceback.format_exc()}")
            return False
    
    async def handle_button_interaction(self, interaction):
        """ボタン押下時の処理"""
        custom_id = interaction.data.get("custom_id", "")
        user_id = interaction.user.id
        
        if custom_id == "recording_consent_agree":
            # 同意ボタンが押された場合
            if user_id in self.consent_users:
                self.consent_users[user_id] = True
                await interaction.response.defer(ephemeral=True)
                
                # メッセージを更新
                users = [interaction.guild.get_member(uid) for uid in self.consent_users.keys()]
                users = [u for u in users if u is not None]  # Noneをフィルタリング
                await self.update_consent_message(interaction.channel_id, users)
                
                # 全員の同意を確認
                all_consented = all(self.consent_users.values())
                return all_consented
            else:
                await interaction.response.send_message("あなたはボイスチャンネルに参加していないため、同意は必要ありません。", ephemeral=True)
                return False
        
        elif custom_id == "recording_consent_cancel":
            # キャンセルボタンが押された場合
            await interaction.response.defer(ephemeral=True)
            await self.complete_consent_message(interaction.channel_id, success=False)
            return None  # キャンセルを示すためにNoneを返す
        
        return False
    
class TranscriptionSink(voice_recv.AudioSink):
    def __init__(self, bot, ctx):
        super().__init__()
        self.bot = bot
        self.ctx = ctx
        self.model = None  # 遅延ロードのためNoneで初期化
        self.audio_buffers = {}
        self.users_info = {}  # ユーザー情報の保持
        self.model_loaded = False
        self.language = 'ja'
        self.output_dir = os.path.join(os.getcwd(), "data", "transcriptions")
        os.makedirs(self.output_dir, exist_ok=True)
        
        # CPU最適化設定
        self.chunk_duration_ms = 30000  # 30秒ごとに処理（CPU負荷軽減）
        self.last_chunk_time = datetime.now()
        
    async def load_model(self):
        """非同期でWhisperモデルを読み込む"""
        if not self.model_loaded:
            logger.info("Whisperモデルを読み込み中...")
            # CPU最適化のため、より小さなモデルを使用
            self.model = await asyncio.to_thread(whisper.load_model, "tiny")  # CPU向けに軽量モデル
            self.model_loaded = True
            logger.info("Whisperモデル読み込み完了")
    
    def wants_opus(self) -> bool:
        return False

    def write(self, user, data):
        if user is None:
            return
            
        current_time = datetime.now()
        # ユーザー情報を記録
        if user.id not in self.users_info:
            self.users_info[user.id] = {
                "display_name": user.display_name,
                "first_audio": current_time
            }
            
        # 音声データをバッファに追加
        self.audio_buffers.setdefault(user.id, bytearray()).extend(data.pcm)
        
        # 一定時間ごとに中間処理（CPU負荷分散）
        time_diff = (current_time - self.last_chunk_time).total_seconds() * 1000
        if time_diff > self.chunk_duration_ms and any(len(pcm) > 0 for pcm in self.audio_buffers.values()):
            self.last_chunk_time = current_time
            # 中間処理を非同期で実行
            asyncio.run_coroutine_threadsafe(
                self.process_audio_chunks(),
                self.bot.loop
            )

    async def process_audio_chunks(self):
        """一定間隔で音声データを処理"""
        if not self.model_loaded:
            await self.load_model()
            
        processed_users = []
        
        for user_id, pcm_bytes in self.audio_buffers.items():
            if len(pcm_bytes) < 8000:  # 短すぎる音声は処理しない（無音など）
                continue
                
            # WAVファイルとして保存
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            user_name = self.users_info.get(user_id, {}).get("display_name", "unknown")
            filename = f"{timestamp}_{user_name}_{user_id}.wav"
            file_path = os.path.join(self.output_dir, filename)
            
            with open(file_path, 'wb') as wf:
                with wave.open(wf, 'wb') as wav:
                    wav.setnchannels(1)
                    wav.setsampwidth(2)
                    wav.setframerate(48000)
                    wav.writeframes(pcm_bytes)
            
            # トランスクリプション処理（非同期）
            try:
                result = await asyncio.to_thread(
                    self.model.transcribe, 
                    file_path, 
                    language=self.language, 
                    fp16=False  # CPU使用時はFP16を無効化
                )
                
                text = result.get('text', '').strip()
                if text:
                    user = self.ctx.guild.get_member(user_id)
                    if user:
                        await self.ctx.send(f"{user.display_name} さんの発言: {text}")
                        
                    # トランスクリプト保存
                    transcript_path = os.path.join(self.output_dir, f"{timestamp}_{user_name}_{user_id}.txt")
                    with open(transcript_path, 'w', encoding='utf-8') as f:
                        f.write(text)
                        
                processed_users.append(user_id)
            except Exception as e:
                logger.error(f"文字起こし処理中にエラー: {e}\n{traceback.format_exc()}")
        
        # 処理済みユーザーのバッファをクリア
        for user_id in processed_users:
            self.audio_buffers[user_id] = bytearray()

    def cleanup(self):
        """録音終了時の処理"""
        for user_id, pcm in self.audio_buffers.items():
            if len(pcm) > 0:  # データがある場合のみ処理
                asyncio.run_coroutine_threadsafe(
                    self.transcribe_and_send(user_id, pcm),
                    self.bot.loop
                )
        # バッファをクリア
        self.audio_buffers.clear()

    async def transcribe_and_send(self, user_id, pcm_bytes):
        """音声を文字起こしして送信"""
        if len(pcm_bytes) < 8000:  # 短すぎる音声は処理しない
            return
            
        # モデルが未ロードの場合はロード
        if not self.model_loaded:
            await self.load_model()
        
        try:
            # 保存用
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            user = self.ctx.guild.get_member(user_id)
            user_name = user.display_name if user else "unknown"
            filename = f"{timestamp}_{user_name}_{user_id}.wav"
            file_path = os.path.join(self.output_dir, filename)
            
            # WAV形式に変換して保存
            with wave.open(file_path, 'wb') as wf:
                wf.setnchannels(1)  # モノラル
                wf.setsampwidth(2)  # 16bit
                wf.setframerate(48000)  # 48kHz
                wf.writeframes(pcm_bytes)
            
            # soundfileを使用してWAVファイルを読み込み、NumPy配列に変換
            audio_data, sample_rate = sf.read(file_path)
            
            # ステレオの場合はモノラルに変換（Whisperはモノラル入力を期待）
            if len(audio_data.shape) > 1 and audio_data.shape[1] > 1:
                audio_data = audio_data.mean(axis=1)
            
            # Whisperによる文字起こし（CPU最適化設定）
            result = await asyncio.to_thread(
                self.model.transcribe, 
                audio_data,  # NumPy配列を渡す
                language=self.language,
                fp16=False  # CPU使用時はFP16を無効化
            )
            
            text = result.get('text', '').strip()
            if text and user:
                await self.ctx.send(f"{user.display_name} さんの発言: {text}")
                
                # トランスクリプト保存
                transcript_path = os.path.join(self.output_dir, f"{timestamp}_{user_name}_{user_id}.txt")
                with open(transcript_path, 'w', encoding='utf-8') as f:
                    f.write(text)
        except Exception as e:
            logger.error(f"文字起こし処理中にエラー: {e}\n{traceback.format_exc()}")
                
class Recorder(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.voice_clients = {}
        self.consent_managers = {}
        self.audio_sinks = {}
        
        # インタラクションハンドラを登録
        bot.add_listener(self.on_interaction, "on_interaction")
        
    @commands.hybrid_group(name="recorder", description="録音コマンド")
    @is_guild()
    @is_owner()
    @log_commands()
    async def recorder(self, interaction: discord.Interaction):
        pass
    
    @recorder.command(name="join", description="ボイスチャンネルに接続")
    async def join(self, ctx):
        # ContextとInteractionの両方に対応
        if isinstance(ctx, discord.Interaction):
            # スラッシュコマンドの場合
            user = ctx.user
            guild_id = ctx.guild_id
            is_interaction = True
        else:
            # テキストコマンドの場合
            user = ctx.author
            guild_id = ctx.guild.id
            is_interaction = False
            
        if user.voice:
            channel = user.voice.channel
            vc = await channel.connect(cls=voice_recv.VoiceRecvClient)
            self.voice_clients[guild_id] = vc
            
            if is_interaction:
                await ctx.response.send_message("ボイスチャンネルに接続しました。")
            else:
                await ctx.send("ボイスチャンネルに接続しました。")
        else:
            if is_interaction:
                await ctx.response.send_message("ボイスチャンネルに参加してください。")
            else:
                await ctx.send("ボイスチャンネルに参加してください。")

    @recorder.command(name="leave", description="ボイスチャンネルから切断")
    async def leave(self, ctx):
        vc = self.voice_clients.get(ctx.guild.id)
        if vc:
            if vc.is_listening():
                vc.stop_listening()
                
            await vc.disconnect()
            del self.voice_clients[ctx.guild.id]
            
            # 関連リソースのクリーンアップ
            if ctx.guild.id in self.consent_managers:
                del self.consent_managers[ctx.guild.id]
                
            if ctx.guild.id in self.audio_sinks:
                del self.audio_sinks[ctx.guild.id]
                
            await ctx.send("切断しました。")
        else:
            await ctx.send("接続していません。")

    @recorder.command(name="start", description="録音と文字起こしを開始")
    async def start(self, ctx):
        # ContextとInteractionの両方に対応
        if isinstance(ctx, discord.Interaction):
            # スラッシュコマンドの場合
            user = ctx.user
            guild_id = ctx.guild_id
            channel_id = ctx.channel_id
            # レスポンスを一度送信してからフォローアップを使用
            await ctx.response.send_message("処理中...")
            # フォローアップ用のctxを作成
            original_message = await ctx.original_response()
            
            # lambdaの代わりにdefを使用
            async def send_message(content):
                await original_message.edit(content=content)
            send_func = send_message
        else:
            # テキストコマンドの場合
            user = ctx.author
            guild_id = ctx.guild.id
            channel_id = ctx.channel.id
            send_func = ctx.send
            
        vc = self.voice_clients.get(guild_id)
        if not vc:
            await send_func("接続していません。`/recorder join`を先に実行してください。")
            return
            
        if vc.is_listening():
            await send_func("すでに録音中です。")
            return
            
        # ボイスチャンネルのメンバーリストを取得
        if not user.voice:
            await send_func("ボイスチャンネルに参加してください。")
            return
            
        voice_members = user.voice.channel.members
        voice_members = [m for m in voice_members if not m.bot]  # ボットを除外
        
        if not voice_members:
            await send_func("録音対象のユーザーがいません。")
            return
            
        # 同意プロセスの開始
        consent_manager = RecordingConsent(self.bot, ctx)
        self.consent_managers[guild_id] = consent_manager
        
        await send_func("録音同意プロセスを開始します...")
        
        # 同意リクエスト送信
        await consent_manager.send_consent_request(channel_id, voice_members)
        
        # 同意待機（30秒タイムアウト）
        try:
            # 30秒間待機し、その間にボタン押下があれば handle_button_interaction で処理
            await asyncio.sleep(30)
            
            # タイムアウト時、全員が同意していない場合はキャンセル
            if not all(consent_manager.consent_users.values()):
                await consent_manager.complete_consent_message(ctx.channel.id, success=False)
                await ctx.send("30秒以内に全員の同意が得られなかったため、録音をキャンセルしました。")
                return
                
        except asyncio.CancelledError:
            # 同意プロセスがキャンセルされた場合
            return
            
        # 録音開始
        sink = TranscriptionSink(self.bot, ctx)
        self.audio_sinks[ctx.guild.id] = sink
        vc.listen(sink)
        
        # モデルのプリロード開始（バックグラウンド）
        asyncio.create_task(sink.load_model())
        
        await ctx.send("録音と文字起こしを開始しました。CPUに最適化された設定で動作しています。")

    @recorder.command(name="stop", description="録音と文字起こしを停止")
    async def stop(self, ctx):
        vc = self.voice_clients.get(ctx.guild.id)
        if vc and vc.is_listening():
            vc.stop_listening()
            await ctx.send("録音を停止しました。文字起こし処理中...")
            
            # 10秒後に処理完了メッセージ
            await asyncio.sleep(10)
            await ctx.send("文字起こし処理が完了しました。")
        else:
            await ctx.send("録音していません。")
    
    async def on_interaction(self, interaction):
        """ボタンのインタラクション処理"""
        if not interaction.data:
            return
            
        # カスタムIDが consent 関連かチェック
        custom_id = interaction.data.get("custom_id", "")
        if not custom_id.startswith("recording_consent_"):
            return
            
        guild_id = interaction.guild_id
        consent_manager = self.consent_managers.get(guild_id)
        
        if not consent_manager:
            await interaction.response.send_message("録音セッションがアクティブではありません。", ephemeral=True)
            return
            
        # ボタン処理を委譲
        result = await consent_manager.handle_button_interaction(interaction)
        
        if result is None:  # キャンセルの場合
            # 録音キャンセル
            await interaction.channel.send("録音がキャンセルされました。")
            return
            
        elif result:  # 全員の同意が得られた場合
            # 成功メッセージを表示
            await consent_manager.complete_consent_message(interaction.channel.id, success=True)
            
            # 録音開始
            vc = self.voice_clients.get(guild_id)
            if vc:
                ctx = await self.bot.get_context(interaction.message)
                sink = TranscriptionSink(self.bot, ctx)
                self.audio_sinks[guild_id] = sink
                vc.listen(sink)
                
                # モデルのプリロード開始（バックグラウンド）
                asyncio.create_task(sink.load_model())
                
                await interaction.channel.send("全員の同意が確認できました。録音と文字起こしを開始します。")
                
async def setup(bot):
    await bot.add_cog(Recorder(bot))