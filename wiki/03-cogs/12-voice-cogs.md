# ボイス録音システム (Voice Cogs)

## 概要

ボイス録音システムは、Discord VCの音声を録音し、OpenAI Whisper APIを使用して文字起こしを行う機能を提供します。ユーザーごとの個別録音、一括文字起こし、録音履歴管理などの機能を備えています。

## システムアーキテクチャ

```
cogs/voice/
├── __init__.py                    # Cogs セットアップ・エントリーポイント
├── recording.py                   # メインCog・録音・文字起こし機能
├── models.py                      # データモデル定義
└── db.py                          # データベース操作
```

## 主要機能

### 1. VC録音システム

#### discord-ext-voice-recv

`discord-ext-voice-recv` ライブラリを使用してVCの音声を受信：

```python
from discord.ext import voice_recv

# VoiceRecvClientでVC接続
vc: VoiceRecvClient = await channel.connect(cls=voice_recv.VoiceRecvClient)

# シンク設定で音声受信
sink = BasicSink(session)
vc.listen(voice_recv.BasicSink(sink.write))
```

#### UserAudioBuffer

```python
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
        # 2ch, 16bit, 48kHz
```

#### RecordingSession

```python
class RecordingSession:
    """録音セッション"""
    
    def __init__(self, guild_id: int, channel_id: int, started_by: int):
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.started_by = started_by
        self.start_time = datetime.now(timezone.utc)
        self.user_buffers: dict[int, UserAudioBuffer] = {}
        self.is_recording = True
        self.db_session_id = None  # DB上のセッションID
```

### 2. OpenAI Whisper文字起こし

#### Whisper API連携

```python
class VoiceRecording(commands.Cog):
    """VC録音・文字起こし機能"""
    
    @property
    def openai_client(self):
        """OpenAIクライアント（遅延初期化）"""
        if self._openai_client is None:
            from openai import OpenAI
            self._openai_client = OpenAI(api_key=settings.etc_api_openai_api_key)
        return self._openai_client
```

#### 対応フォーマット

- WAV
- MP3
- M4A
- WebM
- MP4
- OGG
- FLAC

#### サイズ制限

- 最大ファイルサイズ: 25MB（Whisper API制限）

### 3. データベース管理

#### セッション管理

```python
# セッション作成
db_session_id = await voice_db.create_session(
    guild_id=guild_id,
    channel_id=channel_id,
    started_by=user_id,
    started_at=now,
)

# セッション終了
await voice_db.end_session(
    session_id=db_session_id,
    ended_at=now,
    duration_seconds=duration,
    participant_count=len(user_buffers),
    status="completed",
)
```

#### 録音データ保存

```python
await voice_db.add_recording(
    session_id=session_id,
    user_id=user_id,
    duration_seconds=duration,
    file_size_bytes=file_size,
    discord_message_id=message_id,
    discord_attachment_url=attachment_url,
)
```

#### 文字起こし保存

```python
await voice_db.add_transcript(
    content=text,
    session_id=session_id,
    user_id=user_id,
    language=language,
)
```

## コマンドリファレンス

### 録音コマンド

#### `/vc-record start [channel]`
VCの録音を開始

**パラメータ**:
- `channel` (オプション): 録音するボイスチャンネル（省略時は自分がいるVC）

**動作**:
1. VoiceRecvClientでVC接続
2. DBにセッション作成
3. 音声受信開始
4. 開始通知を送信

**注意事項**:
- 1サーバーにつき1セッションのみ
- 参加者への録音通知を推奨

#### `/vc-record stop`
録音を停止してファイルを出力

**動作**:
1. 録音停止・VC切断
2. ユーザーごとのWAVファイル生成
3. DBにセッション終了を記録
4. ファイルをDiscordに送信

**出力**:
- ユーザーごとの個別WAVファイル
- 録音時間・参加者情報

### 文字起こしコマンド

#### `/vc-record transcribe <audio_file> [language]`
音声ファイルを文字起こし

**パラメータ**:
- `audio_file` (必須): 文字起こしする音声ファイル
- `language` (オプション): 言語（日本語/英語/自動検出）

**出力**:
- プレビュー（最大500文字）
- 完全なテキストファイル（.txt）

#### `/vc-record transcribe-all [message_url] [language]`
録音完了メッセージの全ファイルを一括文字起こし

**パラメータ**:
- `message_url` (オプション): 録音完了メッセージのURL
- `language` (オプション): 言語

**動作**:
1. 録音完了メッセージを検索（または指定）
2. 全音声ファイルを順次文字起こし
3. 結果をまとめて送信

### その他のコマンド

#### `/vc-record summarize <text_file>`
文字起こしテキストを要約

**パラメータ**:
- `text_file` (必須): 要約するテキストファイル

**機能**:
- OpenAI GPTによる要約生成
- 主要なポイントの抽出

#### `/vc-record status`
現在の録音状況を表示

**表示内容**:
- 録音中かどうか
- 録音チャンネル
- 開始時刻
- 経過時間

#### `/vc-record history [limit]`
録音履歴を表示

**パラメータ**:
- `limit` (オプション): 表示件数（デフォルト: 10）

**表示内容**:
- 過去の録音セッション一覧
- 日時・参加者数・録音時間

## データベーススキーマ

### voice_sessions テーブル

```sql
CREATE TABLE voice_sessions (
    session_id SERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    channel_id BIGINT NOT NULL,
    started_by BIGINT NOT NULL,
    started_at TIMESTAMP WITH TIME ZONE NOT NULL,
    ended_at TIMESTAMP WITH TIME ZONE,
    duration_seconds INTEGER,
    participant_count INTEGER,
    status TEXT DEFAULT 'recording'
);

CREATE INDEX idx_voice_sessions_guild ON voice_sessions (guild_id);
CREATE INDEX idx_voice_sessions_status ON voice_sessions (status);
```

### voice_recordings テーブル

```sql
CREATE TABLE voice_recordings (
    recording_id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES voice_sessions(session_id),
    user_id BIGINT NOT NULL,
    duration_seconds FLOAT NOT NULL,
    file_size_bytes INTEGER,
    discord_message_id BIGINT,
    discord_attachment_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_voice_recordings_session ON voice_recordings (session_id);
CREATE INDEX idx_voice_recordings_user ON voice_recordings (user_id);
```

### voice_transcripts テーブル

```sql
CREATE TABLE voice_transcripts (
    transcript_id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES voice_sessions(session_id),
    user_id BIGINT NOT NULL,
    content TEXT NOT NULL,
    language TEXT DEFAULT 'ja',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_voice_transcripts_session ON voice_transcripts (session_id);
```

## セットアップガイド

### 1. 依存パッケージ

```bash
# discord-ext-voice-recv のインストール
pip install discord-ext-voice-recv

# OpenAI パッケージ
pip install openai

# FFmpeg（音声処理に必要）
sudo apt install ffmpeg
```

### 2. 環境変数設定

`.env` ファイルに以下を追加:

```bash
# OpenAI API Key（文字起こし用）
OPENAI_API_KEY=your_openai_api_key_here
```

### 3. Cogsロード

`main.py` で自動ロード:

```python
@bot.event
async def on_ready():
    await bot.load_extension('cogs.voice')
    await bot.tree.sync()
```

### 4. 権限設定

ボットに以下の権限が必要:

- `Connect`: VCに接続
- `Speak`: VCで発言（録音には不要だが推奨）
- `Use Voice Activity`: 音声アクティビティの使用

## パフォーマンス最適化

### メモリ管理

```python
# 1秒未満の録音はスキップ
if buffer.duration_seconds < 1:
    continue

# 最大10ファイルまで送信
files=files[:10]
```

### 遅延初期化

```python
@property
def openai_client(self):
    """OpenAIクライアント（遅延初期化）"""
    if self._openai_client is None:
        from openai import OpenAI
        self._openai_client = OpenAI(...)
    return self._openai_client
```

## トラブルシューティング

### 録音が開始できない

**原因**:
- `discord-ext-voice-recv` のインストール不足
- FFmpegのインストール不足
- ボットの権限不足

**解決方法**:
1. `pip install discord-ext-voice-recv` を実行
2. `sudo apt install ffmpeg` を実行
3. ボットの権限を確認

### 文字起こしが失敗する

**原因**:
- OpenAI API Keyの設定ミス
- ファイルサイズが25MBを超過
- 対応していないファイル形式

**解決方法**:
1. 環境変数 `OPENAI_API_KEY` を確認
2. ファイルサイズを確認
3. 対応形式（WAV/MP3/M4A等）を使用

### 音声データが空

**原因**:
- 誰も発言していない
- マイクがミュートされている
- 音声受信の問題

**解決方法**:
1. 参加者がミュート解除しているか確認
2. ログで音声受信状況を確認

## セキュリティ考慮事項

### プライバシー保護

```python
# 録音開始時に参加者への通知を推奨
await interaction.followup.send(
    "⚠️ **注意**: 録音されることを参加者に伝えてください"
)
```

### データ保持

- 録音ファイルはDiscordの添付ファイルとして保存
- DBには参照URLのみ保存
- 定期的なクリーンアップを推奨

## 関連ドキュメント

- [ボットアーキテクチャ概要](../01-architecture/01-bot-architecture-overview.md)
- [データベース管理](../04-utilities/01-database-management.md)
- [API統合](../04-utilities/02-api-integration.md)

## バージョン履歴

- **v1.0** (2025-12): 初回リリース
  - discord-ext-voice-recv による録音
  - OpenAI Whisper API 文字起こし
  - ユーザーごとの個別録音
  - 一括文字起こし機能
  - 録音履歴管理
