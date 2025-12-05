"""
VC録音・文字起こし機能

discord-ext-voice-recv を使用してVCを録音し、
OpenAI Whisper API で文字起こしを行う
"""

from __future__ import annotations

import io
import tempfile
import wave
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from cogs.voice.models import voice_db
from config.setting import get_settings
from utils.logging import setup_logging

if TYPE_CHECKING:
    from discord.ext.voice_recv import VoiceRecvClient

logger = setup_logging(__name__)
settings = get_settings()


class UserAudioBuffer:
    """ユーザーごとの音声バッファ"""

    def __init__(self, user_id: int):
        self.user_id = user_id
        self.chunks: list[bytes] = []
        self.start_time = datetime.now(timezone.utc)

    def write(self, data: bytes):
        """音声データを追加"""
        self.chunks.append(data)

    def get_wav_bytes(self) -> bytes:
        """WAV形式のバイト列を取得"""
        audio_data = b"".join(self.chunks)

        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav:
            wav.setnchannels(2)  # ステレオ
            wav.setsampwidth(2)  # 16bit
            wav.setframerate(48000)  # 48kHz
            wav.writeframes(audio_data)

        buffer.seek(0)
        return buffer.read()

    @property
    def duration_seconds(self) -> float:
        """録音時間（秒）"""
        total_bytes = sum(len(c) for c in self.chunks)
        # 2ch * 2bytes * 48000Hz = 192000 bytes/sec
        return total_bytes / 192000


class RecordingSession:
    """録音セッション"""

    def __init__(self, guild_id: int, channel_id: int, started_by: int, db_session_id: int | None = None):
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.started_by = started_by
        self.start_time = datetime.now(timezone.utc)
        self.user_buffers: dict[int, UserAudioBuffer] = {}
        self.is_recording = True
        self.db_session_id = db_session_id  # DB上のセッションID

    def get_or_create_buffer(self, user_id: int) -> UserAudioBuffer:
        """ユーザーのバッファを取得または作成"""
        if user_id not in self.user_buffers:
            self.user_buffers[user_id] = UserAudioBuffer(user_id)
        return self.user_buffers[user_id]


class BasicSink:
    """シンプルな音声受信シンク"""

    def __init__(self, session: RecordingSession):
        self.session = session

    def write(self, user: discord.User | discord.Member | None, data: bytes):
        """音声データを受信"""
        if user is None or not self.session.is_recording:
            return
        buffer = self.session.get_or_create_buffer(user.id)
        buffer.write(data)

    def cleanup(self):
        """クリーンアップ"""
        self.session.is_recording = False


class VoiceRecording(commands.Cog):
    """VC録音・文字起こし機能"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.sessions: dict[int, RecordingSession] = {}  # guild_id -> session
        self._openai_client = None

    @property
    def openai_client(self):
        """OpenAIクライアント（遅延初期化）"""
        if self._openai_client is None:
            try:
                from openai import OpenAI
                self._openai_client = OpenAI(api_key=settings.etc_api_openai_api_key)
            except ImportError:
                logger.error("openaiパッケージがインストールされていません")
                return None
        return self._openai_client

    vc_record = app_commands.Group(
        name="vc-record",
        description="VC録音・文字起こし機能",
        guild_only=True,
    )

    @vc_record.command(name="start", description="VCの録音を開始します")
    @app_commands.describe(channel="録音するボイスチャンネル（省略時は自分がいるVC）")
    async def record_start(
        self,
        interaction: discord.Interaction,
        channel: discord.VoiceChannel | None = None,
    ):
        """録音開始"""
        # チャンネル決定
        if channel is None:
            if interaction.user.voice and interaction.user.voice.channel:
                channel = interaction.user.voice.channel
            else:
                await interaction.response.send_message(
                    "❌ ボイスチャンネルに参加するか、チャンネルを指定してください",
                    ephemeral=True,
                )
                return

        # 既存セッションチェック
        if interaction.guild_id in self.sessions:
            await interaction.response.send_message(
                "❌ このサーバーでは既に録音中です。先に `/vc-record stop` で停止してください",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            # VoiceRecvClientでVC接続
            from discord.ext import voice_recv

            vc: VoiceRecvClient = await channel.connect(cls=voice_recv.VoiceRecvClient)

            # DBにセッション作成
            now = datetime.now(timezone.utc)
            db_session_id = await voice_db.create_session(
                guild_id=interaction.guild_id,
                channel_id=channel.id,
                started_by=interaction.user.id,
                started_at=now,
            )

            # セッション作成
            session = RecordingSession(
                guild_id=interaction.guild_id,
                channel_id=channel.id,
                started_by=interaction.user.id,
                db_session_id=db_session_id,
            )
            self.sessions[interaction.guild_id] = session

            # シンク設定
            sink = BasicSink(session)
            vc.listen(voice_recv.BasicSink(sink.write))

            await interaction.followup.send(
                f"🎙️ **録音開始**\n"
                f"チャンネル: {channel.mention}\n"
                f"開始者: {interaction.user.mention}\n\n"
                f"⚠️ **注意**: 録音されることを参加者に伝えてください\n"
                f"停止: `/vc-record stop`",
                ephemeral=False,
            )
            logger.info(f"録音開始: {interaction.guild_id} - {channel.name}")

        except Exception as e:
            logger.error(f"録音開始エラー: {e}")
            await interaction.followup.send(
                f"❌ 録音の開始に失敗しました: {e}",
                ephemeral=True,
            )

    @vc_record.command(name="stop", description="録音を停止してファイルを出力します")
    async def record_stop(self, interaction: discord.Interaction):
        """録音停止"""
        session = self.sessions.get(interaction.guild_id)
        if not session:
            await interaction.response.send_message(
                "❌ 録音中のセッションがありません",
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        try:
            # 録音停止
            session.is_recording = False

            # VC切断
            if interaction.guild.voice_client:
                await interaction.guild.voice_client.disconnect()

            # ファイル生成
            files = []
            user_info = []

            for user_id, buffer in session.user_buffers.items():
                if buffer.duration_seconds < 1:
                    continue  # 1秒未満はスキップ

                user = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
                username = user.display_name if user else str(user_id)

                wav_bytes = buffer.get_wav_bytes()
                filename = f"{username}_{session.start_time.strftime('%Y%m%d_%H%M%S')}.wav"

                files.append(discord.File(io.BytesIO(wav_bytes), filename=filename))
                user_info.append(f"- {username}: {buffer.duration_seconds:.1f}秒")

            # セッション削除
            del self.sessions[interaction.guild_id]

            if not files:
                await interaction.followup.send(
                    "⚠️ 録音データがありませんでした（誰も発言していない可能性）"
                )
                return

            now = datetime.now(timezone.utc)
            duration = (now - session.start_time).total_seconds()

            # メッセージ送信
            msg = await interaction.followup.send(
                f"✅ **録音完了**\n"
                f"録音時間: {duration:.0f}秒\n"
                f"参加者:\n" + "\n".join(user_info) + "\n\n"
                "💡 文字起こし: `/vc-record transcribe` で添付ファイルを指定",
                files=files[:10],  # 最大10ファイル
            )

            # DBにセッション終了を記録
            if session.db_session_id:
                await voice_db.end_session(
                    session_id=session.db_session_id,
                    ended_at=now,
                    duration_seconds=int(duration),
                    participant_count=len(session.user_buffers),
                    status="completed",
                )

                # 各ユーザーの録音データを保存
                for i, (user_id, buffer) in enumerate(session.user_buffers.items()):
                    if buffer.duration_seconds >= 1:
                        attachment_url = msg.attachments[i].url if i < len(msg.attachments) else None
                        await voice_db.add_recording(
                            session_id=session.db_session_id,
                            user_id=user_id,
                            duration_seconds=buffer.duration_seconds,
                            file_size_bytes=len(buffer.get_wav_bytes()),
                            discord_message_id=msg.id,
                            discord_attachment_url=attachment_url,
                        )

            logger.info(f"録音完了: {interaction.guild_id} - {len(files)}ファイル")

        except Exception as e:
            logger.error(f"録音停止エラー: {e}")
            # セッションは削除
            self.sessions.pop(interaction.guild_id, None)
            await interaction.followup.send(f"❌ エラーが発生しました: {e}")

    @vc_record.command(name="transcribe", description="音声ファイルを文字起こしします")
    @app_commands.describe(
        audio_file="文字起こしする音声ファイル（WAV/MP3/M4A）",
        language="言語（デフォルト: 日本語）",
    )
    @app_commands.choices(
        language=[
            app_commands.Choice(name="日本語", value="ja"),
            app_commands.Choice(name="英語", value="en"),
            app_commands.Choice(name="自動検出", value="auto"),
        ]
    )
    async def transcribe(
        self,
        interaction: discord.Interaction,
        audio_file: discord.Attachment,
        language: str = "ja",
    ):
        """音声ファイルを文字起こし"""
        if not self.openai_client:
            await interaction.response.send_message(
                "❌ OpenAI APIが設定されていません",
                ephemeral=True,
            )
            return

        # ファイル形式チェック
        allowed_extensions = (".wav", ".mp3", ".m4a", ".webm", ".mp4", ".ogg", ".flac")
        if not audio_file.filename.lower().endswith(allowed_extensions):
            await interaction.response.send_message(
                f"❌ 対応形式: {', '.join(allowed_extensions)}",
                ephemeral=True,
            )
            return

        # サイズチェック（25MB制限）
        if audio_file.size > 25 * 1024 * 1024:
            await interaction.response.send_message(
                "❌ ファイルサイズは25MB以下にしてください",
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        try:
            # ファイルダウンロード
            audio_bytes = await audio_file.read()

            # 一時ファイルに保存
            with tempfile.NamedTemporaryFile(
                suffix=Path(audio_file.filename).suffix, delete=False
            ) as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name

            try:
                # Whisper API呼び出し
                with open(tmp_path, "rb") as f:
                    kwargs = {"model": "whisper-1", "file": f}
                    if language != "auto":
                        kwargs["language"] = language

                    transcript = self.openai_client.audio.transcriptions.create(**kwargs)

                text = transcript.text

                # 結果送信
                if len(text) > 1900:
                    # 長い場合はファイルで
                    await interaction.followup.send(
                        f"📝 **文字起こし完了** ({audio_file.filename})",
                        file=discord.File(
                            io.BytesIO(text.encode("utf-8")),
                            filename=f"transcript_{audio_file.filename}.txt",
                        ),
                    )
                else:
                    await interaction.followup.send(
                        f"📝 **文字起こし結果** ({audio_file.filename})\n\n{text}"
                    )

            finally:
                # 一時ファイル削除
                Path(tmp_path).unlink(missing_ok=True)

        except Exception as e:
            logger.error(f"文字起こしエラー: {e}")
            await interaction.followup.send(f"❌ 文字起こしに失敗しました: {e}")

    @vc_record.command(name="summarize", description="文字起こしテキストを要約します")
    @app_commands.describe(
        text="要約するテキスト（省略時は直前のメッセージから取得）",
    )
    async def summarize(
        self,
        interaction: discord.Interaction,
        text: str | None = None,
    ):
        """テキストを要約"""
        if not self.openai_client:
            await interaction.response.send_message(
                "❌ OpenAI APIが設定されていません",
                ephemeral=True,
            )
            return

        # テキストが指定されていない場合、直前のメッセージを取得
        if not text:
            async for msg in interaction.channel.history(limit=5):
                if msg.author.id == self.bot.user.id and "文字起こし" in msg.content:
                    # 文字起こし結果を抽出
                    lines = msg.content.split("\n\n", 1)
                    if len(lines) > 1:
                        text = lines[1]
                        break
                # 添付ファイルもチェック
                for attachment in msg.attachments:
                    if attachment.filename.startswith("transcript_"):
                        text = (await attachment.read()).decode("utf-8")
                        break
                if text:
                    break

        if not text:
            await interaction.response.send_message(
                "❌ 要約するテキストを指定するか、先に `/vc-record transcribe` を実行してください",
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "あなたは会議の議事録を作成するアシスタントです。"
                            "以下の会話の文字起こしを、簡潔で分かりやすい要約にまとめてください。"
                            "重要なポイント、決定事項、アクションアイテムがあれば箇条書きで記載してください。"
                        ),
                    },
                    {"role": "user", "content": text},
                ],
                max_tokens=1000,
            )

            summary = response.choices[0].message.content

            await interaction.followup.send(f"📋 **会話の要約**\n\n{summary}")

        except Exception as e:
            logger.error(f"要約エラー: {e}")
            await interaction.followup.send(f"❌ 要約に失敗しました: {e}")

    @vc_record.command(name="status", description="録音状態を確認します")
    async def record_status(self, interaction: discord.Interaction):
        """録音状態確認"""
        session = self.sessions.get(interaction.guild_id)

        if not session:
            await interaction.response.send_message(
                "📊 録音中のセッションはありません",
                ephemeral=True,
            )
            return

        channel = self.bot.get_channel(session.channel_id)
        duration = (datetime.now(timezone.utc) - session.start_time).total_seconds()
        users = len(session.user_buffers)

        await interaction.response.send_message(
            f"📊 **録音中**\n"
            f"チャンネル: {channel.mention if channel else 'Unknown'}\n"
            f"経過時間: {duration:.0f}秒\n"
            f"発言者数: {users}人\n"
            f"開始者: <@{session.started_by}>",
            ephemeral=True,
        )

    @vc_record.command(name="history", description="録音履歴を表示します")
    @app_commands.describe(limit="表示件数（デフォルト: 10）")
    async def record_history(
        self,
        interaction: discord.Interaction,
        limit: app_commands.Range[int, 1, 25] = 10,
    ):
        """録音履歴を表示"""
        sessions = await voice_db.get_guild_sessions(interaction.guild_id, limit)

        if not sessions:
            await interaction.response.send_message(
                "📜 録音履歴がありません",
                ephemeral=True,
            )
            return

        lines = ["📜 **録音履歴**\n"]
        for s in sessions:
            channel = self.bot.get_channel(s.channel_id)
            channel_name = channel.name if channel else "削除済み"
            duration = f"{s.duration_seconds // 60}分{s.duration_seconds % 60}秒" if s.duration_seconds else "不明"
            status_emoji = "✅" if s.status == "completed" else "❌" if s.status == "failed" else "🔴"

            lines.append(
                f"{status_emoji} **#{channel_name}** - {s.started_at.strftime('%m/%d %H:%M')}\n"
                f"　　時間: {duration} / 参加者: {s.participant_count}人"
            )

        await interaction.response.send_message(
            "\n".join(lines),
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    """Cog setup"""
    await bot.add_cog(VoiceRecording(bot))
