# ホームページCogs

## C.O.M.E.T.について

**C.O.M.E.T.**の名前は以下の頭文字から構成されています：

- **C**ommunity of
- **O**shilove
- **M**oderation &
- **E**njoyment
- **T**ogether

HFS - ホロライブ非公式ファンサーバーのコミュニティを支える、推し愛とモデレーション、そして楽しさを一緒に提供するボットです。

## 概要

ホームページCogsは、Discordサーバーとウェブサイト間の統合を管理し、スタッフ情報の同期とメンバーデータ管理を処理します。

## 利用可能なホームページCogs

### 1. スタッフマネージャー (`staff_manager.py`)

**目的**: Discordサーバーのロールとメンバー情報をウェブサイトAPIと同期します。

**主要機能**:
- **自動同期**: `@tasks.loop(hours=3)`により3時間ごとにスタッフデータを更新
- **ロールベースカテゴリ**: メンバーをスタッフ、スペシャルサンクス、テスターに分類
- **API統合**: ウェブサイトAPIエンドポイント（`https://hfs.jp/api`）にデータを送信
- **メンバーデータ**: アバター、参加日、ロール色、カスタムメッセージを収集
- **キャッシュシステム**: APIフォールバック付きローカルJSONキャッシュ

#### スタッフロール階層
```python
role_priority = {
    "Administrator": 1,
    "Moderator": 2, 
    "Staff": 3
}
```

#### メンバーデータ構造
```json
{
  "id": "123456789",
  "name": "DisplayName",
  "role": "Administrator",
  "avatar": "https://cdn.discordapp.com/avatars/...",
  "message": "Custom message",
  "joinedAt": "2024-01-01",
  "joinedAtJp": "2024年01月01日",
  "roleColor": "#ff0000",
  "socials": {}
}
```

#### 管理カテゴリ
1. **スタッフメンバー**: Administrator、Moderator、またはStaffロールを持つユーザー
2. **スペシャルサンクス**: "常連"で始まるロールを持つユーザー（常連）
3. **テスター**: "テスター"ロールを持つ特定のユーザーIDのハードコードリスト

#### API統合
- **エンドポイント**: `POST /api/members/update`
- **認証**: `STAFF_API_KEY`によるBearerトークン
- **データ形式**: staff、specialThanks、testersの配列を含むJSON
- **フォールバック**: API利用不可時のローカルJSONキャッシュ

#### 利用可能なコマンド

| コマンド | タイプ | 権限 | 説明 |
|---------|------|------------|-------------|
| `update_staff` | プレフィックス | Administrator | 手動スタッフデータ更新 |
| `/ひとこと` | ハイブリッド | 誰でも | 個人メッセージを設定 |
| `/ひとことリセット` | ハイブリッド | 誰でも | 個人メッセージをクリア |
| `staff_status` | プレフィックス | Administrator | 現在のスタッフデータ状態を表示 |

#### 実装詳細

**自動更新**:
```python
@tasks.loop(hours=3)
async def auto_update_staff(self):
    await self.update_staff_data()
```

**データ収集プロセス**:
1. すべてのサーバーメンバーをスキャン
2. スタッフロール（Administrator、Moderator、Staff）をチェック
3. スペシャルサンクスロール（"常連"で始まる）をチェック
4. ハードコードされたテスターメンバーを追加
5. メンバーデータ（アバター、参加日、ロール色）を収集
6. 既存のメッセージとソーシャルリンクを保持
7. APIに送信してローカルにキャッシュ

**エラーハンドリング**:
- API失敗時はローカルキャッシュにフォールバック
- 個別メンバーエラーはバッチ処理を停止しない
- デバッグ用の包括的ログ

**設定**:
```python
self.api_endpoint = "https://hfs.jp/api"
self.api_token = settings.staff_api_key
self.config_path = 'config/members.json'
```

---

### 2. メンバーズカード (`members_card.py`)

**目的**: HFS Members Card APIとの連携、メンバーカードURL管理機能を提供します。

**主要機能**:
- **プロフィール表示**: ユーザーのメンバーカード情報を表示
- **統計情報**: サーバー全体のメンバーカード統計を表示
- **リンク管理**: ユーザーのリンク一覧を表示
- **推し管理**: ユーザーの推しメンバー情報を表示
- **メンバー同期**: 10秒ごとにDiscordメンバーリストをAPIに同期
- **Members Card URL管理**: メンバーカードURLの設定・取得・削除

#### API設定
```python
# HFS Members Card API
self.api_base_url = settings.hfs_api_base_url  # https://card.hfs.jp/api/bot
self.api_key = settings.hfs_api_key
self.hfs_guild_id = settings.hfs_guild_id

# ウェブサイトAPI（Members Card URL管理用）
self.website_api_url = "https://hfs.jp"
self.website_api_token = settings.homepage_api_token
```

#### 利用可能なコマンド

##### プロフィール表示コマンド

| コマンド | タイプ | 権限 | 説明 |
|---------|------|------|------|
| `/card` | スラッシュ | 誰でも | ユーザーのプロフィールを表示 |
| `/cstats` | スラッシュ | 誰でも | サーバー全体の統計情報を表示 |
| `/links` | スラッシュ | 誰でも | ユーザーのリンク一覧を表示 |
| `/oshi` | スラッシュ | 誰でも | 推しメンバーの情報を表示 |
| `/cranking` | スラッシュ | 誰でも | 各種ランキングを表示（開発中） |

##### Members Card URL管理コマンド

| コマンド | タイプ | 権限 | 説明 |
|---------|------|------|------|
| `/set_card_url` | スラッシュ | 誰でも | HFS Members Card URLを設定 |
| `/get_card_url` | スラッシュ | 誰でも | HFS Members Card URLを取得 |
| `/delete_card_url` | スラッシュ | 誰でも | HFS Members Card URLを削除 |

#### `/card` - プロフィール表示

メンバーカード情報を詳細に表示します。

**パラメータ**:
- `ユーザー` (オプション): 表示するユーザー（省略で自分）
- `メンバー番号` (オプション): メンバー番号で検索
- `ユーザー名` (オプション): ユーザー名で検索

**表示内容**:
- メンバー番号（#0001形式）
- 表示名とプロフィール画像
- 自己紹介
- ロール（Admin, Mod, Staff, CMod）
- バッジ
- 推しメンバー
- リンク一覧（上位5件、クリック数付き）
- 統計情報（総リンク数、閲覧数、クリック数）
- 短縮URL

#### `/cstats` - 統計情報表示

サーバー全体のメンバーカード統計を表示します。

**表示内容**:
- 総ユーザー数
- プロフィール作成済みユーザー数
- 総リンク数
- 総閲覧数
- 最近登録したユーザー（上位5名）

#### `/links` - リンク一覧表示

ユーザーのリンク一覧を詳細に表示します。

**パラメータ**:
- `ユーザー` (オプション): 表示するユーザー（省略で自分）
- `メンバー番号` (オプション): メンバー番号で検索

**表示内容**:
- リンクタイトル
- リンクURL
- クリック数

#### `/oshi` - 推し情報表示

ユーザーの推しメンバー情報を表示します。

**パラメータ**:
- `ユーザー` (オプション): 表示するユーザー（省略で自分）

**表示内容**:
- 推しメンバーの絵文字と名前
- 推しの色（Embedカラーに反映）

#### Members Card URL管理機能

HFS Members Card URLの設定・取得・削除を行います。

**API詳細**:
- **エンドポイント**: `https://hfs.jp/api/members/update-card-url`
- **認証**: `HOMEPAGE_API_TOKEN`によるBearerトークン
- **対象**: スタッフ、スペシャルサンクス、テスターのメンバー

##### `/set_card_url` - URL設定

HFS Members Card URLを設定または更新します。

**パラメータ**:
- `url` (必須): HFS Members Card URL
  - 形式: `https://card.hfs.jp/members/[番号]` または `https://c.hfs.jp/[スラッグ]`

**使用例**:
```
/set_card_url url:https://card.hfs.jp/members/1
/set_card_url url:https://c.hfs.jp/freewifi
```

**レスポンス**:
- 成功: ✅ HFS Members Card URLを設定しました！
- エラー: ❌ エラーが発生しました: [エラー内容]

##### `/get_card_url` - URL取得

HFS Members Card URLを取得します。

**パラメータ**:
- `ユーザー` (オプション): URLを取得するユーザー（省略で自分）

**使用例**:
```
/get_card_url
/get_card_url ユーザー:@FreeWiFi
```

**レスポンス**:
- 設定済み: 📇 [名前] のHFS Members Card URL: [URL]
- 未設定: 📇 [名前] のHFS Members Card URLは未設定です。
- エラー: ❌ メンバーが見つかりませんでした。

##### `/delete_card_url` - URL削除

HFS Members Card URLを削除します。

**使用例**:
```
/delete_card_url
```

**レスポンス**:
- 成功: ✅ HFS Members Card URLを削除しました！
- エラー: ❌ エラーが発生しました: [エラー内容]

#### メンバー同期機能

**自動同期**:
```python
@tasks.loop(seconds=10)
async def sync_members_task(self):
    await self.sync_members_to_api()
```

**同期タイミング**:
- 10秒ごとの定期同期
- メンバー参加時（`on_member_join`）
- メンバー退出時（`on_member_remove`）

**送信データ**:
- ギルドID
- メンバーIDリスト（Bot除く）

#### エラーハンドリング

- API認証エラー: 設定不備を警告
- レート制限: 429ステータスを検出して待機を促す
- ユーザー未検出: 404エラーを適切に処理
- タイムアウト: 10秒のタイムアウトを設定

#### 環境変数

```bash
# HFS Members Card API
HFS_API_BASE_URL=https://card.hfs.jp/api/bot
HFS_API_KEY=your_api_key_here
HFS_GUILD_ID=1092138492173242430

# ウェブサイトAPI（Members Card URL管理用）
HOMEPAGE_API_URL=https://hfs.jp/api/
HOMEPAGE_API_TOKEN=your_api_token_here
```

---

### 3. サーバーアナライザー (`server_analyzer.py`)

**目的**: OpenAI APIを使用してサーバー情報を分析し、ホームページ用のコンテンツを自動生成します。

**主要機能**:
- **週次自動分析**: `@tasks.loop(hours=168)`により1週間ごとにサーバー分析を実行
- **チャンネルデータ収集**: メッセージ数、アクティブユーザー、頻出ワードを収集
- **ロールデータ収集**: ロール情報とメンバー数を収集
- **AI分析**: OpenAI GPT-4oによるサーバー特徴分析
- **コンテンツ生成**: キャッチコピー、スローガン、歓迎メッセージを自動生成
- **API連携**: 分析結果をウェブサイトAPIに送信

#### システムアーキテクチャ

```python
class ServerAnalyzer(commands.Cog):
    """OpenAI APIを使用してサーバー情報を分析し、ホームページ用の内容を生成するCog"""
    
    def __init__(self, bot):
        self.bot = bot
        self.openai_api_key = settings.etc_api_openai_api_key
        self.api_base_url = "https://hfs.jp/api"
        self.api_token = settings.homepage_api_token
        self.target_guild_id = settings.homepage_target_guild_id
        self.cache_dir = os.path.join(os.getcwd(), "cache", "server_analysis")
```

#### 分析機能

**チャンネルデータ収集** (`collect_channel_data`):
- 指定期間（デフォルト7日間）のメッセージを収集
- 最大300件のメッセージを分析
- アクティブユーザーの特定
- 頻出ワードの抽出（上位20個）

**ロールデータ収集** (`collect_roles_data`):
- 全ロールの情報を収集
- メンバー数、色、作成日時を記録

**サーバー要約生成** (`generate_server_summary`):
- サーバー基本情報の収集
- アクティブチャンネルランキング
- 人気ロールランキング
- OpenAI APIによる詳細分析

#### AI生成コンテンツ

1. **サーバー分析**: コミュニティの雰囲気、関心事、コミュニケーションスタイルを分析
2. **キャッチコピー・スローガン**: 4カテゴリ×3案を生成
   - 短いキャッチコピー（10文字程度）
   - 説明的なキャッチコピー（20〜30文字）
   - フレンドリーなスローガン
   - 特徴を表すフレーズ
3. **歓迎メッセージ**: 3つのバージョンを生成
   - 短い挨拶文（100文字程度）
   - 中程度の説明（300文字程度）
   - 詳細な案内（500文字程度）

#### 利用可能なコマンド

| コマンド | タイプ | 権限 | 説明 |
|---------|------|------|------|
| `/homepage` | スラッシュ | 誰でも | ホームページコマンドグループ |
| `/homepage analyze` | スラッシュ | Administrator | サーバー分析を手動実行 |

#### `/homepage analyze` - サーバー分析

サーバーの詳細分析を手動で実行します。

**動作**:
1. チャンネルデータを収集
2. ロールデータを収集
3. OpenAI APIで分析・コンテンツ生成
4. 結果をキャッシュに保存
5. ウェブサイトAPIに送信
6. 分析結果をDiscordに表示（長文は分割送信）

**出力内容**:
- サーバー基本情報（メンバー数、チャンネル数、ロール数など）
- サーバー分析結果
- キャッチコピー・スローガン案
- 歓迎メッセージ案

#### 環境変数

```bash
# OpenAI API
OPENAI_API_KEY=your_openai_api_key_here

# ホームページAPI
HOMEPAGE_API_URL=https://hfs.jp/api
HOMEPAGE_API_TOKEN=your_api_token_here
HOMEPAGE_TARGET_GUILD_ID=1092138492173242430
```

#### キャッシュ管理

- キャッシュディレクトリ: `cache/server_analysis/`
- ファイル形式: `server_analysis_YYYYMMDD_HHMMSS.json`
- 分析結果はJSON形式で保存

---

### 4. ウェブサイト連携 (`website_integration.py`)

**目的**: Discordサーバーの統計情報をウェブサイトと定期的に同期します。

**主要機能**:
- **定期統計更新**: `@tasks.loop(minutes=10)`により10分ごとにサーバー統計を更新
- **メンバー数同期**: オンライン/オフラインメンバー数を送信
- **バナー画像同期**: サーバーバナーをBase64エンコードして送信
- **ロール統計**: ロールごとのメンバー数を送信

#### システムアーキテクチャ

```python
class WebsiteIntegration(commands.Cog):
    """ウェブサイト連携機能を提供するCog"""
    
    def __init__(self, bot):
        self.bot = bot
        self.api_base_url = "https://hfs.jp/api"
        self.api_token = settings.homepage_api_token
        self.target_guild_id = settings.homepage_target_guild_id
        self.cache_dir = os.path.join(os.getcwd(), "cache", "website")
```

#### 自動同期機能

**サーバー統計更新** (`server_stats_update`):
```python
@tasks.loop(minutes=10)
async def server_stats_update(self):
    """サーバー統計情報を定期的に更新"""
    stats = {
        "member_count": guild.member_count,
        "online_count": len([m for m in guild.members if m.status != discord.Status.offline]),
        "updated_at": datetime.utcnow().isoformat(),
        "server_name": guild.name
    }
    await self.send_to_api("/server-stats", stats)
```

**バナー画像更新** (`update_server_banner`):
- サーバーバナーを取得
- ローカルにPNG形式で保存
- Base64エンコードしてAPIに送信

#### 利用可能なコマンド

| コマンド | タイプ | 権限 | 説明 |
|---------|------|------|------|
| `website` | プレフィックス | 誰でも | ウェブサイトコマンドグループ |
| `website update` | プレフィックス | Administrator | ウェブサイト情報を手動更新 |

#### `website update` - 手動更新

ウェブサイトの情報を手動で更新します。

**動作**:
1. サーバー統計情報を更新
2. ロール情報を収集・送信
3. 完了メッセージを表示

**送信データ**:
- サーバー統計（メンバー数、オンライン数）
- バナー画像（Base64）
- ロール統計（名前、色、メンバー数）

#### APIエンドポイント

| エンドポイント | メソッド | 説明 |
|--------------|--------|------|
| `/server-stats` | POST | サーバー統計情報 |
| `/server-banner` | POST | バナー画像（Base64） |
| `/role-stats` | POST | ロール統計情報 |

#### 環境変数

```bash
# ホームページAPI
HOMEPAGE_API_URL=https://hfs.jp/api
HOMEPAGE_API_TOKEN=your_api_token_here
HOMEPAGE_TARGET_GUILD_ID=1092138492173242430
```

#### キャッシュ管理

- キャッシュディレクトリ: `cache/website/`
- バナー画像: `server_banner.png`

---

## 関連ドキュメント

- [API統合](../04-utilities/02-api-integration.md)
- [データベース管理](../04-utilities/01-database-management.md)
- [設定管理](../01-architecture/04-configuration-management.md)
- [エラーハンドリング](../02-core/04-error-handling.md)
