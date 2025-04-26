import discord
from discord import opus
from discord.ext import commands, tasks, voice_recv
import io
from openai import OpenAI
from utils.logging import setup_logging
from config.setting import get_settings

# ログと設定の初期化
logger = setup_logging("D")
settings = get_settings()

# OpenAI API クライアント
ai_client = OpenAI(api_key=settings.etc_api_openai_api_key)

class CustomVoiceRecvClient(voice_recv.VoiceRecvClient):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.encryption_mode = "xsalsa20_poly1305"

class RealTimeUserTranscriptionSink(voice_recv.AudioSink):
    def __init__(self):
        super().__init__()
        self.audio_buffers = {}
        logger.info("RealTimeUserTranscriptionSink initialized.")

    def write(self, user, data):
        """音声データを受信してユーザーごとのバッファに保存"""
        if data.pcm:
            if user not in self.audio_buffers:
                self.audio_buffers[user] = io.BytesIO()
                logger.debug(f"New audio buffer created for user: {user.display_name}")
            self.audio_buffers[user].write(data.pcm)

    def get_audio_and_clear(self):
        """各ユーザーの音声データを取得してバッファをクリア"""
        audio_data = {}
        for user, buffer in self.audio_buffers.items():
            audio_data[user] = buffer.getvalue()
            self.audio_buffers[user] = io.BytesIO()  # バッファをクリア
            logger.debug(f"Audio buffer cleared for user: {user.display_name}")
        return audio_data

    def cleanup(self):
        """終了時のクリーンアップ処理"""
        self.audio_buffers.clear()
        logger.info("All audio buffers cleared.")

    def wants_opus(self):
        """Opus形式を使用するか指定"""
        logger.debug("wants_opus called. Returning False.")
        return False


class VoiceTranscriber(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.voice_client = None  # 初期化時に voice_client を None に設定

        # Opusのロードを確認
        if not opus.is_loaded():
            opus_path = "/opt/homebrew/opt/opus/lib/libopus.dylib"
            logger.info(f"Loading Opus from {opus_path}")
            opus.load_opus(opus_path)
            if opus.is_loaded():
                logger.info("Opus loaded successfully.")
            else:
                logger.error("Failed to load Opus.")

    @commands.command()
    async def t_join(self, ctx):
        """ボイスチャンネルに参加し、リアルタイム文字起こしを開始します"""
        if ctx.author.voice:
            voice_channel = ctx.author.voice.channel
            logger.info(f"Joining voice channel: {voice_channel.name}")
            try:
                # 既存接続を切断
                if self.voice_client and self.voice_client.is_connected():
                    await self.voice_client.disconnect()

                # 新しい接続を確立
                self.voice_client = await voice_channel.connect(
                    cls=CustomVoiceRecvClient,
                    self_deaf=True  # ボットが自分の声を聞かないようにする
                )
                self.sink = RealTimeUserTranscriptionSink()
                self.voice_client.listen(self.sink)

                await ctx.send(f"✅ `{voice_channel.name}` に接続しました！ リアルタイム文字起こしを開始します。")

            except Exception as e:
                logger.error(f"Failed to join voice channel: {e}")
                await ctx.send("⚠️ ボイスチャンネルへの接続に失敗しました。")
                if self.voice_client:
                    await self.voice_client.disconnect()
                self.voice_client = None
        else:
            await ctx.send("⚠️ ボイスチャンネルに参加してからコマンドを使ってください！")

    @commands.command()
    async def t_leave(self, ctx):
        """ボイスチャンネルから退出し、文字起こしを終了します"""
        if self.voice_client and self.voice_client.is_connected():
            logger.info("Leaving voice channel and stopping transcription.")
            await self.voice_client.disconnect()
            self.voice_client = None
            await ctx.send("👋 ボイスチャンネルから退出しました！")
        else:
            await ctx.send("⚠️ ボイスチャンネルに接続していません！")

    async def cog_unload(self):
        """Cogがアンロードされる際にクリーンアップ"""
        if self.voice_client and self.voice_client.is_connected():
            await self.voice_client.disconnect()
            self.voice_client = None


async def setup(bot):
    await bot.add_cog(VoiceTranscriber(bot))
