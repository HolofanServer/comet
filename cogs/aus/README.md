# AUS (Art Unauthorized-repost Shield) システム

無断転載ファンアート検出・絵師認証システム

## 概要

Discord コミュニティにおける無断転載ファンアートを自動検出し、絵師の権利を保護するシステムです。

### 主な機能

1. **画像検出システム**
   - 全チャンネル・スレッド・フォーラムの画像を自動監視
   - SauceNAO + Google Cloud Vision による2段階検出
   - Twitter出典URL自動検出
   - 認証済み絵師の投稿は自動スキップ

2. **絵師認証システム**
   - Discord Modal UIによる認証申請
   - 専用チケットチャンネル自動生成
   - Button UI（承認/却下）によるワークフロー
   - Discord User ⇔ Twitter紐付け管理

3. **モデレーション機能**
   - 運営専用チャンネルへの自動通知
   - Component V2 による直感的なUI
   - ワンクリック操作で迅速な対応

## セットアップ

### 1. データベースマイグレーション

```bash
# PostgreSQL に接続して実行
psql $DATABASE_URL -f migrations/create_aus_tables.sql
```

### 2. 環境変数設定

`.env` ファイルに以下の設定を追加：

```bash
# 必須設定
AUS_MOD_CHANNEL_ID=123456789  # 検出通知の送信先チャンネルID
SAUCENAO_API_KEY=your_api_key  # SauceNAO API Key

# オプション設定
AUS_TICKET_CATEGORY_ID=123456789  # 認証チケット用カテゴリID
AUS_MOD_ROLE_ID=123456789  # モデレーターロールID
AUS_EXCLUDED_CHANNEL_IDS=111,222,333  # 除外チャンネルID
AUS_EXCLUDED_CATEGORY_IDS=444,555  # 除外カテゴリID

# Google Cloud Vision API（オプション）
GOOGLE_APPLICATION_CREDENTIALS=/path/to/your/google-credentials.json
```

### 3. 依存ライブラリインストール

```bash
pip install -r requirements.txt
```

### 4. Bot起動時にCogsをロード

`main.py` に以下を追加：

```python
@bot.event
async def on_ready():
    # AUS System ロード
    await bot.load_extension('cogs.aus')
    
    # スラッシュコマンド同期
    await bot.tree.sync()
    
    print(f'{bot.user} is online!')
```

## 使用方法

### ユーザーコマンド

| コマンド | 説明 |
|---------|------|
| `/verify_artist` | 絵師認証を申請（Modal表示） |
| `/artist_info [@user]` | 認証情報を表示 |

### 運営コマンド

| コマンド | 説明 | 必要権限 |
|---------|------|---------|
| `/aus_stats` | システム統計表示 | `manage_guild` |
| `/aus_list_artists` | 認証済み絵師一覧 | `manage_guild` |
| `/aus_remove_artist` | 絵師認証解除 | `manage_guild` |
| `/aus_pending_tickets` | 未解決チケット一覧 | `manage_guild` |

### インタラクティブUI

#### 無断転載検出通知

- **🚨 即座に削除**: メッセージを削除
- **✓ 確認済み**: 手動確認完了をマーク
- **📝 補足/異議**: フィードバックModal表示

#### 認証チケット

- **✅ 承認**: 絵師認証を承認
- **❌ 却下**: 認証を却下（理由入力Modalを表示）

## API Keys取得方法

### SauceNAO API

1. [SauceNAO](https://saucenao.com/user.php) にアクセス
2. アカウント登録・ログイン
3. API Key を取得
4. プラン選択（Mega: $50/月 推奨）

### Google Cloud Vision API（オプション）

1. [Google Cloud Console](https://console.cloud.google.com/) にアクセス
2. プロジェクト作成
3. Vision API を有効化
4. サービスアカウント作成・認証情報JSONダウンロード
5. 環境変数 `GOOGLE_APPLICATION_CREDENTIALS` にパス設定

## システム構成

```
cogs/aus/
├── __init__.py                    # Cogs セットアップ
├── database.py                    # データベース管理
├── image_detection.py             # 画像検出ロジック
├── artist_verification.py         # 絵師認証
├── moderation.py                  # 運営管理
├── views/                         # Component V2 Views
│   ├── __init__.py
│   ├── notification_views.py     # 通知用View
│   └── verification_views.py     # 認証用View
└── README.md                      # このファイル
```

## データベーススキーマ

### `verified_artists` テーブル

認証済み絵師情報

| カラム | 型 | 説明 |
|-------|---|------|
| `user_id` | BIGINT | Discord User ID (主キー) |
| `twitter_handle` | TEXT | Twitterハンドルネーム |
| `twitter_url` | TEXT | Twitter プロフィールURL |
| `verified_at` | TIMESTAMP | 認証日時 |
| `verified_by` | BIGINT | 承認した運営のUser ID |
| `notes` | TEXT | 備考・メモ |

### `verification_tickets` テーブル

絵師認証申請チケット

| カラム | 型 | 説明 |
|-------|---|------|
| `ticket_id` | SERIAL | チケットID (主キー) |
| `user_id` | BIGINT | 申請者のDiscord User ID |
| `twitter_handle` | TEXT | Twitterハンドルネーム |
| `twitter_url` | TEXT | Twitter プロフィールURL |
| `proof_description` | TEXT | 本人確認方法の説明 |
| `status` | TEXT | pending/approved/rejected |
| `created_at` | TIMESTAMP | チケット作成日時 |
| `resolved_at` | TIMESTAMP | チケット解決日時 |
| `resolved_by` | BIGINT | 処理した運営のUser ID |
| `channel_id` | BIGINT | 専用チケットチャンネルID |
| `rejection_reason` | TEXT | 却下理由 |

## トラブルシューティング

### 画像検出が動作しない

- `AUS_MOD_CHANNEL_ID` が正しく設定されているか確認
- SauceNAO API Key が有効か確認
- Bot に `message_content` Intent が有効化されているか確認

### Persistent Viewsが動作しない

- `on_ready` イベントで `bot.add_view()` が呼ばれているか確認
- Bot再起動後も custom_id が保持されているか確認

### Google Cloud Vision エラー

- `GOOGLE_APPLICATION_CREDENTIALS` パスが正しいか確認
- サービスアカウントに Vision API 権限があるか確認
- 課金アカウントが有効化されているか確認

## ライセンス

このシステムは技術仕様書に基づいて実装されています。

## バージョン履歴

- **v1.0** (2025-11-06): 初回リリース
  - 画像検出システム（SauceNAO + Google Cloud Vision）
  - 絵師認証システム
  - Component V2 対応UI
  - Persistent Views実装
