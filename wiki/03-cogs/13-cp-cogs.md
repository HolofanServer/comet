# Checkpoint システム (CP Cogs)

## 概要

Checkpoint (CP) システムは、Discordサーバー内のユーザー活動を追跡・統計化し、年間の活動レポートを提供する機能です。メッセージ数、リアクション数、VC時間、メンション統計、絵文字使用状況などを記録し、個人統計とサーバーランキングを表示します。

## システムアーキテクチャ

```
cogs/cp/
├── __init__.py                    # Cogs セットアップ・エントリーポイント
├── cp_commands.py                 # メインCog・コマンド実装
├── db.py                          # データベース操作
├── models.py                      # データモデル定義
├── stats.py                       # 統計計算ロジック
├── event_logging.py               # イベントログ収集
├── error_handler.py               # エラーハンドリング
└── tests/                         # テストスイート
```

## 主要機能

### 1. 活動統計追跡

#### 追跡対象

- **メッセージ数**: 送信したメッセージの総数
- **リアクション数**: 付与したリアクションの総数
- **VC時間**: ボイスチャンネルでの滞在時間
- **メンション送信**: 他ユーザーへのメンション回数
- **メンション受信**: 他ユーザーからのメンション回数
- **おみくじ回数**: おみくじコマンドの使用回数
- **絵文字使用**: よく使う絵文字の統計

### 2. イベントログシステム

#### EventLogging

```python
class EventLogging(commands.Cog):
    """イベントログ収集"""
    
    @commands.Cog.listener()
    async def on_message(self, message):
        """メッセージ送信を記録"""
        await checkpoint_db.increment_messages(
            user_id=message.author.id,
            guild_id=message.guild.id
        )
        
        # メンション統計
        for mention in message.mentions:
            await checkpoint_db.record_mention(
                sender_id=message.author.id,
                receiver_id=mention.id,
                guild_id=message.guild.id
            )
        
        # 絵文字統計
        for emoji in self._extract_emojis(message.content):
            await checkpoint_db.record_emoji_usage(
                user_id=message.author.id,
                guild_id=message.guild.id,
                emoji_data=emoji
            )
    
    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        """リアクション追加を記録"""
        await checkpoint_db.increment_reactions(
            user_id=user.id,
            guild_id=reaction.message.guild.id
        )
    
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """VC時間を記録"""
        # VC参加・退出を追跡
        ...
```

### 3. 統計計算

#### CheckpointStats

```python
class CheckpointStats:
    """統計計算ロジック"""
    
    async def get_user_stats(
        self,
        user_id: int,
        guild_id: int,
        year: int
    ) -> UserStats | None:
        """ユーザーの年間統計を取得"""
        return UserStats(
            total_messages=...,
            total_reactions=...,
            total_vc_seconds=...,
            total_mentions_sent=...,
            total_mentions_received=...,
            total_omikuji=...
        )
    
    async def get_top_emojis(
        self,
        user_id: int,
        guild_id: int,
        limit: int = 5
    ) -> list[dict]:
        """よく使う絵文字を取得"""
        ...
    
    async def get_mention_network(
        self,
        user_id: int,
        guild_id: int,
        limit: int = 3
    ) -> dict:
        """メンション相関を取得"""
        return {
            "sent_to": [...],      # よくメンションする人
            "received_from": [...]  # よくメンションされる人
        }
    
    async def get_rankings(
        self,
        guild_id: int,
        category: str,
        year: int,
        limit: int = 10
    ) -> list[RankingEntry]:
        """カテゴリ別ランキングを取得"""
        ...
```

### 4. Components V2 表示

#### CV2メッセージ構築

```python
from utils.cv2 import (
    ComponentsV2Message,
    Container,
    Section,
    Separator,
    SeparatorSpacing,
    send_components_v2_followup,
)

# 統計表示用メッセージ
msg = ComponentsV2Message()
container = Container(color=COLOR_CHECKPOINT)

# ヘッダー
header_section = (
    Section()
    .add_text(f"# {user.display_name}")
    .add_text(f"📊 {year}年 活動統計")
    .set_thumbnail(user.display_avatar.url)
)
container.add(header_section)
container.add_separator()

# 統計グリッド
container.add_text(
    f"💬 **メッセージ** {stats.total_messages:,} 件　　"
    f"🎉 **リアクション** {stats.total_reactions:,} 回　　"
    f"🎤 **VC** {format_vc_time(stats.total_vc_seconds)}"
)

await send_components_v2_followup(interaction, msg)
```

## コマンドリファレンス

### ユーザーコマンド

#### `/checkpoint [user] [year]`
ユーザーの活動統計を表示

**パラメータ**:
- `user` (オプション): 統計を表示するユーザー（省略時は自分）
- `year` (オプション): 対象年（省略時は今年）

**表示内容**:
- メッセージ数
- リアクション数
- VC時間
- メンション送信/受信数
- おみくじ回数
- よく使う絵文字（上位5個）
- よくメンションする人（上位3人）

#### `/checkpoint-rankings <category> [year]`
サーバー内のランキングを表示

**パラメータ**:
- `category` (必須): ランキングのカテゴリ
  - 💬 メッセージ数
  - 🎉 リアクション数
  - 🎤 VC時間
  - 📢 メンション送信
  - 📥 メンション受信
  - 🎲 おみくじ回数
- `year` (オプション): 対象年（省略時は今年）

**表示内容**:
- 上位10名のランキング
- 🥇🥈🥉 メダル表示
- カテゴリに応じた値表示

## データベーススキーマ

### checkpoint_stats テーブル

```sql
CREATE TABLE checkpoint_stats (
    user_id BIGINT,
    guild_id BIGINT,
    year INTEGER,
    total_messages INTEGER DEFAULT 0,
    total_reactions INTEGER DEFAULT 0,
    total_vc_seconds INTEGER DEFAULT 0,
    total_mentions_sent INTEGER DEFAULT 0,
    total_mentions_received INTEGER DEFAULT 0,
    total_omikuji INTEGER DEFAULT 0,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (guild_id, user_id, year)
);

CREATE INDEX idx_checkpoint_stats_guild_year ON checkpoint_stats (guild_id, year);
CREATE INDEX idx_checkpoint_stats_messages ON checkpoint_stats (guild_id, year, total_messages DESC);
CREATE INDEX idx_checkpoint_stats_reactions ON checkpoint_stats (guild_id, year, total_reactions DESC);
CREATE INDEX idx_checkpoint_stats_vc ON checkpoint_stats (guild_id, year, total_vc_seconds DESC);
```

### checkpoint_emoji_usage テーブル

```sql
CREATE TABLE checkpoint_emoji_usage (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    guild_id BIGINT NOT NULL,
    emoji_id BIGINT,
    emoji_name TEXT NOT NULL,
    emoji_animated BOOLEAN DEFAULT FALSE,
    count INTEGER DEFAULT 1,
    year INTEGER NOT NULL,
    UNIQUE (guild_id, user_id, emoji_id, emoji_name, year)
);

CREATE INDEX idx_emoji_usage_user ON checkpoint_emoji_usage (guild_id, user_id, year);
CREATE INDEX idx_emoji_usage_count ON checkpoint_emoji_usage (guild_id, user_id, year, count DESC);
```

### checkpoint_mentions テーブル

```sql
CREATE TABLE checkpoint_mentions (
    id SERIAL PRIMARY KEY,
    sender_id BIGINT NOT NULL,
    receiver_id BIGINT NOT NULL,
    guild_id BIGINT NOT NULL,
    count INTEGER DEFAULT 1,
    year INTEGER NOT NULL,
    UNIQUE (guild_id, sender_id, receiver_id, year)
);

CREATE INDEX idx_mentions_sender ON checkpoint_mentions (guild_id, sender_id, year);
CREATE INDEX idx_mentions_receiver ON checkpoint_mentions (guild_id, receiver_id, year);
```

### checkpoint_vc_sessions テーブル

```sql
CREATE TABLE checkpoint_vc_sessions (
    session_id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    guild_id BIGINT NOT NULL,
    channel_id BIGINT NOT NULL,
    start_time TIMESTAMP WITH TIME ZONE NOT NULL,
    end_time TIMESTAMP WITH TIME ZONE,
    duration_seconds INTEGER
);

CREATE INDEX idx_vc_sessions_user ON checkpoint_vc_sessions (guild_id, user_id);
CREATE INDEX idx_vc_sessions_active ON checkpoint_vc_sessions (user_id, guild_id) WHERE end_time IS NULL;
```

## データモデル

### UserStats

```python
@dataclass
class UserStats:
    """ユーザー統計データ"""
    total_messages: int
    total_reactions: int
    total_vc_seconds: int
    total_mentions_sent: int
    total_mentions_received: int
    total_omikuji: int
```

### RankingEntry

```python
@dataclass
class RankingEntry:
    """ランキングエントリ"""
    user_id: int
    rank: int
    value: int
```

## セットアップガイド

### 1. データベースマイグレーション

```bash
psql $DATABASE_URL -f migrations/create_checkpoint_tables.sql
```

### 2. Cogsロード

`main.py` で自動ロード:

```python
@bot.event
async def on_ready():
    await bot.load_extension('cogs.cp')
    await bot.tree.sync()
```

### 3. 初期化確認

```python
# checkpoint_db._initialized がTrueであることを確認
if not checkpoint_db._initialized:
    logger.error("Checkpoint DBが初期化されていません")
```

## パフォーマンス最適化

### バッチ更新

```python
# 高頻度イベントはバッチ処理
class EventBuffer:
    def __init__(self):
        self.buffer = []
        self.flush_interval = 60  # 60秒ごとにフラッシュ
    
    async def add(self, event):
        self.buffer.append(event)
        if len(self.buffer) >= 100:
            await self.flush()
    
    async def flush(self):
        if self.buffer:
            await checkpoint_db.batch_insert(self.buffer)
            self.buffer.clear()
```

### インデックス最適化

```sql
-- ランキング用の複合インデックス
CREATE INDEX idx_checkpoint_rankings 
ON checkpoint_stats (guild_id, year, total_messages DESC, total_reactions DESC);
```

## トラブルシューティング

### 統計が表示されない

**原因**:
- データベース接続の問題
- 対象年のデータが存在しない
- `checkpoint_db._initialized` がFalse

**解決方法**:
1. データベース接続を確認
2. 対象年を変更して試す
3. ログでDB初期化状態を確認

### ランキングが更新されない

**原因**:
- イベントリスナーが動作していない
- バッチ処理の遅延

**解決方法**:
1. Cogが正しくロードされているか確認
2. イベントリスナーのログを確認
3. バッファのフラッシュ状態を確認

### VC時間が記録されない

**原因**:
- `on_voice_state_update` リスナーの問題
- セッション終了処理の失敗

**解決方法**:
1. ボイス状態変更イベントのログを確認
2. アクティブセッションの状態を確認
3. 手動でセッションをクローズ

## ユーティリティ関数

### VC時間フォーマット

```python
def _format_vc_time(self, seconds: int) -> str:
    """VC時間をフォーマット"""
    if seconds < 60:
        return f"{seconds}秒"
    elif seconds < 3600:
        return f"{seconds // 60}分"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}時間{minutes}分"
```

### 絵文字フォーマット

```python
def _format_emoji(self, emoji_data: dict) -> str:
    """絵文字をフォーマット"""
    if emoji_data.get("id"):
        animated = "a" if emoji_data.get("animated") else ""
        return f"<{animated}:{emoji_data['name']}:{emoji_data['id']}>"
    return emoji_data["name"]
```

## 関連ドキュメント

- [ボットアーキテクチャ概要](../01-architecture/01-bot-architecture-overview.md)
- [データベース管理](../04-utilities/01-database-management.md)
- [ランクCogs](10-rank-cogs.md)

## バージョン履歴

- **v1.0** (2025-12): 初回リリース
  - 活動統計追跡（メッセージ、リアクション、VC時間）
  - メンション・絵文字統計
  - 年間ランキング機能
  - Components V2 表示
