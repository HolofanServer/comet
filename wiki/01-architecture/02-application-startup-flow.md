# アプリケーション起動フロー

## C.O.M.E.T.について

**C.O.M.E.T.**の名前は以下の頭文字から構成されています：

- **C**ommunity of
- **O**shilove
- **M**oderation &
- **E**njoyment
- **T**ogether

HFS - ホロライブ非公式ファンサーバーのコミュニティを支える、推し愛とモデレーション、そして楽しさを一緒に提供するボットです。

## 概要

COMETボットの起動プロセスは、認証、設定読み込み、Cogローディング、サービス初期化の段階的なフローに従います。このドキュメントでは、ボット起動時の詳細な処理フローを説明します。

## 起動フローダイアグラム

```
┌─────────────────────────────────────────────────────────────┐
│                    COMET Bot 起動フロー                      │
├─────────────────────────────────────────────────────────────┤
│  1. メインプロセス開始                                        │
│     ├── Python環境初期化                                     │
│     ├── 環境変数読み込み                                      │
│     └── ログシステム初期化                                    │
├─────────────────────────────────────────────────────────────┤
│  2. ボットインスタンス作成                                    │
│     ├── Discord Intents設定                                  │
│     ├── MyBotクラス初期化                                    │
│     └── コマンドプレフィックス設定                            │
├─────────────────────────────────────────────────────────────┤
│  3. setup_hook() 実行                                        │
│     ├── 認証処理 (auth())                                    │
│     ├── Git更新 (git_pull())                                │
│     ├── 依存関係インストール (pip_install())                  │
│     ├── 環境チェック (check_dev())                           │
│     ├── Cogローディング (load_cogs())                        │
│     └── Jishaku拡張ロード                                    │
├─────────────────────────────────────────────────────────────┤
│  4. Discord接続                                              │
│     ├── WebSocket接続確立                                    │
│     ├── ギルド情報同期                                        │
│     └── on_ready() イベント発火                              │
├─────────────────────────────────────────────────────────────┤
│  5. 初期化完了処理                                           │
│     ├── 起動通知送信                                          │
│     ├── ボット情報送信                                        │
│     ├── プレゼンス設定                                        │
│     └── バックグラウンドタスク開始                            │
└─────────────────────────────────────────────────────────────┘
```

## 詳細な起動ステップ

### 1. メインプロセス開始

**場所**: [`main.py:1-20`](../main.py)

```python
# 環境変数とログの初期化
from utils.logging import setup_logging
from config.setting import *

logger = setup_logging()
```

**処理内容**:
- Python環境の初期化
- 環境変数の読み込み（`.env`ファイルから）
- ログシステムのセットアップ
- 必要なモジュールのインポート

### 2. ボットインスタンス作成

**場所**: [`main.py:182-184`](../main.py)

```python
intent: discord.Intents = discord.Intents.all()
bot: MyBot = MyBot(command_prefix=command_prefix, intents=intent, help_command=None)
```

**処理内容**:
- Discord Intentsの設定（全権限有効化）
- MyBotクラスのインスタンス化
- コマンドプレフィックスの設定
- ヘルプコマンドの無効化（カスタム実装のため）

### 3. setup_hook() 実行

**場所**: [`main.py:65-74`](../main.py)

#### 3.1 認証処理
```python
await self.auth()
```
- ボット認証情報の検証
- 必要な権限の確認
- 認証失敗時のエラーハンドリング

#### 3.2 Git更新
```python
await git_pull()
```
- リモートリポジトリから最新コードを取得
- マージコンフリクトの自動解決
- 更新ログの記録

#### 3.3 依存関係インストール
```python
await pip_install()
```
- `requirements.txt`から依存関係を確認
- 新しいパッケージの自動インストール
- バージョン競合の解決

#### 3.4 環境チェック
```python
await check_dev()
```
- 開発環境と本番環境の判定
- 環境固有の設定適用
- デバッグモードの設定

#### 3.5 Cogローディング
```python
await self.load_cogs('cogs')
```
- `cogs/`ディレクトリの再帰的スキャン
- 各Cogファイルの動的ロード
- ロード失敗時のエラー処理とログ記録

#### 3.6 Jishaku拡張ロード
```python
await self.load_extension('jishaku')
```
- 開発用デバッグ拡張の読み込み
- 実行時コマンド実行機能の有効化

### 4. Discord接続

**場所**: Discord.pyライブラリ内部処理

#### 4.1 WebSocket接続確立
- Discord APIへの認証
- WebSocket接続の確立
- ハートビート開始

#### 4.2 ギルド情報同期
- 参加ギルドの情報取得
- メンバー情報の同期
- チャンネル・ロール情報の取得

#### 4.3 on_ready() イベント発火
```python
async def on_ready(self) -> None:
    logger.info(yokobou())
    logger.info("on_ready is called")
```

### 5. 初期化完了処理

**場所**: [`main.py:114-131`](../main.py)

#### 5.1 起動通知送信
```python
await startup_send_webhook(self, guild_id=dev_guild_id)
```
- 指定チャンネルへの起動通知
- ボット情報とタイムスタンプの送信
- エラー時の代替通知方法

#### 5.2 ボット情報送信
```python
await startup_send_botinfo(self)
```
- システム情報の収集と送信
- メモリ使用量、CPU情報
- 接続ギルド数とユーザー数

#### 5.3 プレゼンス設定
- ボットステータスの設定
- アクティビティ情報の更新
- 動的ステータス変更の開始

#### 5.4 バックグラウンドタスク開始
- 定期実行タスクの開始
- データベースクリーンアップ
- 統計情報の収集

## エラーハンドリング

### 起動時エラーの種類

#### 1. 認証エラー
```python
except Exception as e:
    logger.error(f"認証に失敗しました。Cogのロードをスキップします。: {e}")
    return
```
- 無効なボットトークン
- 権限不足
- ネットワーク接続問題

#### 2. Cogロードエラー
```python
except commands.ExtensionFailed as e:
    traceback.print_exc()
    logger.error(f"Failed to load extension: {cog_path} | {e}")
```
- 構文エラー
- 依存関係の欠如
- インポートエラー

#### 3. 接続エラー
- Discord APIの障害
- ネットワーク問題
- レート制限

### エラー回復戦略

#### 1. 部分的起動
- 重要でないCogのロード失敗は無視
- 基本機能は維持
- エラーログの詳細記録

#### 2. 再試行メカニズム
- 接続エラー時の自動再試行
- 指数バックオフによる再試行間隔
- 最大再試行回数の制限

#### 3. 代替モード
- 最小限の機能での起動
- 管理者への通知
- 手動復旧の案内

## パフォーマンス最適化

### 1. 並列処理
```python
# 複数Cogの並列ロード
tasks = [self.load_extension(cog_path) for cog_path in cog_paths]
await asyncio.gather(*tasks, return_exceptions=True)
```

### 2. キャッシュ戦略
- 設定情報のメモリキャッシュ
- ギルド情報の事前読み込み
- 頻繁にアクセスされるデータの最適化

### 3. リソース管理
- メモリ使用量の監視
- 不要なオブジェクトの早期解放
- ガベージコレクションの最適化

## 起動時間の測定

```python
import time

start_time = time.time()
# 起動処理
end_time = time.time()
startup_duration = end_time - start_time
logger.info(f"Bot startup completed in {startup_duration:.2f} seconds")
```

## 設定可能な起動オプション

### 環境変数による制御
- `SKIP_GIT_PULL`: Git更新をスキップ
- `SKIP_PIP_INSTALL`: 依存関係インストールをスキップ
- `DEBUG_MODE`: デバッグモードの有効化
- `MINIMAL_STARTUP`: 最小限の機能での起動

### 起動モード
- **開発モード**: 全機能有効、詳細ログ
- **本番モード**: 最適化された設定、エラー通知
- **メンテナンスモード**: 管理者のみアクセス可能

---

## 関連ドキュメント

- [ボットアーキテクチャ概要](01-bot-architecture-overview.md)
- [設定管理](04-configuration-management.md)
- [メインボットクラス](../02-core/01-main-bot-class.md)
- [エラーハンドリング](../02-core/04-error-handling.md)
