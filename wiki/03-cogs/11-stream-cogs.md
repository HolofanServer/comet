# ストリーム通知システム (Stream Cogs)

## 概要

ストリーム通知システムは、Holodex APIを使用してホロライブメンバーの配信情報を自動取得し、Discordサーバーに通知する機能を提供します。ライブ配信の開始・終了通知、予定配信の一覧表示、チャンネル名の自動更新などを行います。

## システムアーキテクチャ

```
cogs/stream/
├── __init__.py                    # Cogs セットアップ・エントリーポイント
├── stream_notifier.py             # メインCog・定期チェックタスク
├── holodex.py                     # Holodex APIクライアント
├── channel_manager.py             # チャンネル名更新管理
├── live_notification.py           # ライブ配信通知管理
├── upcoming.py                    # 予定配信一覧管理
└── constants.py                   # 定数・設定値
```

## 主要機能

### 1. Holodex API連携

#### HolodexClient

```python
class HolodexClient:
    """Holodex APIとの通信を担当するクライアント"""
    
    async def get_live_and_upcoming(
        self,
        org: str = "Hololive",
        max_upcoming_hours: int = 48
    ) -> dict[str, list[dict]]:
        """
        ライブ配信とupcoming配信を取得
        
        Returns:
            {"live": [...], "upcoming": [...]} 形式の辞書
        """
        
    async def get_live_quick(self, channel_ids: list[str]) -> list[dict]:
        """特定チャンネルのライブ配信を高速取得"""
```

#### API仕様

- **エンドポイント**: `https://holodex.net/api/v2/live`
- **認証**: `X-APIKEY` ヘッダー
- **パラメータ**:
  - `org`: 組織名（デフォルト: "Hololive"）
  - `max_upcoming_hours`: 予定配信の取得範囲（時間）

### 2. 定期チェックシステム

#### StreamNotifier

```python
class StreamNotifier(commands.Cog):
    """配信通知システムのメインCog"""
    
    @tasks.loop(seconds=300)  # 5分間隔
    async def check_streams(self):
        """
        定期的に配信情報をチェックして更新
        
        処理内容:
        1. Holodex APIから配信情報取得
        2. 配信開始・終了通知を更新
        3. チャンネル名を更新
        4. Upcomingメッセージを更新
        """
```

#### エラーハンドリング

- 連続エラーカウント機能
- 最大エラー回数（5回）でクリティカルログ出力
- API障害時の自動リカバリー

### 3. チャンネル名自動更新

#### StreamChannelManager

ブランチごとにチャンネル名を自動更新：

- **JP**: ホロライブJPメンバー
- **EN**: ホロライブENメンバー
- **ID**: ホロライブIDメンバー
- **DEV_IS**: DEV_ISメンバー

```python
class StreamChannelManager:
    """チャンネル名更新管理"""
    
    async def update_channels(
        self,
        live_streams: list[dict],
        upcoming_streams: list[dict]
    ):
        """
        配信状況に応じてチャンネル名を更新
        
        - ライブ中: 絵文字付きでメンバー名表示
        - 配信なし: デフォルト名に戻す
        """
```

### 4. ライブ配信通知

#### LiveNotificationManager

```python
class LiveNotificationManager:
    """ライブ配信通知管理"""
    
    async def update_notifications(
        self,
        current_live: list[dict],
        previous_live: list[dict]
    ):
        """
        配信開始・終了を検出して通知
        
        - 新規配信: 開始通知を送信
        - 終了配信: 終了通知を送信
        """
```

### 5. 予定配信一覧

#### UpcomingStreamsManager

```python
class UpcomingStreamsManager:
    """予定配信一覧管理"""
    
    async def update_all_branches(self, upcoming_streams: list[dict]):
        """
        全ブランチの予定配信メッセージを更新
        
        - 埋め込みメッセージの自動更新
        - ブランチごとの分類表示
        """
```

## コマンドリファレンス

### 管理者コマンド

#### `/streamcheck`
配信情報を手動で即座に更新

**必要権限**: `administrator`

**機能**:
- Holodex APIから最新情報を取得
- チャンネル名・通知・予定一覧を即座に更新
- 結果をEmbedで表示

### ユーザーコマンド

#### `/streamstatus`
現在の配信状況を表示

**必要権限**: なし

**表示内容**:
- ブランチごとの配信中メンバー一覧
- JP / EN / ID / DEV_IS の分類表示

## セットアップガイド

### 1. 環境変数設定

`.env` ファイルに以下を追加:

```bash
# 必須設定
HOLODEX_API_KEY=your_holodex_api_key_here

# オプション設定
STREAM_CHECK_INTERVAL=300  # チェック間隔（秒）
MAX_UPCOMING_HOURS=48      # 予定配信の取得範囲（時間）
```

### 2. Holodex API Key取得

1. [Holodex](https://holodex.net/) にアクセス
2. アカウント登録・ログイン
3. Settings → API から API Key を取得

### 3. チャンネル設定

`constants.py` でチャンネルIDを設定:

```python
# ブランチごとのチャンネルID
BRANCH_CHANNELS = {
    "jp": 123456789012345678,
    "en": 123456789012345679,
    "id": 123456789012345680,
    "dev_is": 123456789012345681,
}

# 通知チャンネルID
NOTIFICATION_CHANNEL_ID = 123456789012345682
```

### 4. Cogsロード

`main.py` で自動ロード:

```python
@bot.event
async def on_ready():
    await bot.load_extension('cogs.stream')
    await bot.tree.sync()
```

## パフォーマンス最適化

### レート制限対応

```python
# Holodex APIのレート制限
# - 無料プラン: 60 requests/minute
# - 5分間隔のチェックで十分余裕あり
```

### キャッシング

```python
# 前回のライブ配信リストをキャッシュ
self.previous_live_streams: list[dict] = []

# 差分検出で不要な通知を防止
```

## トラブルシューティング

### 配信情報が更新されない

**原因**:
- `HOLODEX_API_KEY` の設定ミス
- API Keyの無効化/制限
- ネットワーク接続の問題

**解決方法**:
1. 環境変数を確認
2. Holodexダッシュボードでキーの状態を確認
3. ログで連続エラーを確認

### チャンネル名が更新されない

**原因**:
- ボットの権限不足
- チャンネルIDの設定ミス

**解決方法**:
1. ボットに `Manage Channels` 権限を付与
2. `constants.py` のチャンネルIDを確認

### 通知が送信されない

**原因**:
- 通知チャンネルIDの設定ミス
- Webhookの設定問題

**解決方法**:
1. `NOTIFICATION_CHANNEL_ID` を確認
2. ボットの送信権限を確認

## 関連ドキュメント

- [ボットアーキテクチャ概要](../01-architecture/01-bot-architecture-overview.md)
- [API統合](../04-utilities/02-api-integration.md)
- [監視Cogs](08-monitoring-cogs.md)

## バージョン履歴

- **v1.0** (2025-12): 初回リリース
  - Holodex API連携
  - 5分間隔の定期チェック
  - ブランチ別チャンネル名更新
  - ライブ配信通知
  - 予定配信一覧
