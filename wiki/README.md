# COMET (C.O.M.E.T.) Discord Bot Wiki

<div align="center">
    <img src="https://images.frwi.net/data/images/f573f557-1cd7-4f4e-b21b-22aa6f911634.png" alt="COMET Logo" width="200" height="200">
    <h1>COMET Bot ドキュメント</h1>
    <h3>HFS専属BOT 総合ガイド</h3>
</div>

---

## 📚 Wiki ナビゲーション

### 🏗️ アーキテクチャ & コアシステム
- [**ボットアーキテクチャ概要**](01-architecture/01-bot-architecture-overview.md) - 高レベルシステム設計とコンポーネント
- [**アプリケーション起動フロー**](01-architecture/02-application-startup-flow.md) - ボット初期化とセットアップ処理
- [**サービス層アーキテクチャ**](01-architecture/03-service-layer-architecture.md) - 依存性注入とコアサービス
- [**設定管理**](01-architecture/04-configuration-management.md) - 設定、環境変数、ボット設定

### 🔧 コアコンポーネント
- [**メインボットクラス**](02-core/01-main-bot-class.md) - MyBotクラスとコア機能
- [**認証システム**](02-core/02-authentication-system.md) - ボット認証とセキュリティ
- [**ログシステム**](02-core/03-logging-system.md) - 包括的なログとモニタリング
- [**エラーハンドリング**](02-core/04-error-handling.md) - エラー管理とレポート

### 🎯 Cogsシステム

#### コア機能
- [**Cogsアーキテクチャ**](03-cogs/01-cogs-architecture.md) - 拡張システム概要

#### イベントシステム
- [**イベントCogs**](03-cogs/02-events-cogs.md) - イベント処理とモニタリング
  - [バナー同期](03-cogs/02-events-cogs/banner-sync.md)
  - [ギルドウォッチャー](03-cogs/02-events-cogs/guild-watcher.md)

#### ウェブサイト統合
- [**ホームページCogs**](03-cogs/03-homepage-cogs.md) - ウェブサイト統合とサーバー分析
  - サーバーアナライザー
  - スタッフマネージャー
  - API統合

#### 管理機能
- [**管理Cogs**](03-cogs/04-management-cogs.md) - ボット管理と制御
  - ボット管理
  - Cog管理
  - ヘルプシステム
  - データベースマイグレーション
  - タグモデレーション
  - ユーザー警告システム

#### ユーティリティツール
- [**ツールCogs**](03-cogs/05-tool-cogs.md) - ユーティリティコマンドと機能
  - アナウンスメント（新規・カスタム）
  - 自動リアクション
  - Bump通知
  - ギブアウェイ
  - おみくじ（ホロライブ対応）
  - 推しロールパネル
  - ピン留め機能
  - サーバー統計
  - サーバータグ管理
  - ユーザーアナライザー
  - ボイスチャット通知
  - ウェルカムメッセージ
  - FAQ自動送信

#### 通報・モデレーション
- [**通報Cogs**](03-cogs/06-report-cogs.md) - 通報システム
  - メッセージ通報
  - ユーザー通報
  - 通報設定管理

#### ノート機能
- [**ノートCogs**](03-cogs/07-note-cogs.md) - ノート統合
  - HFSボイス連携
  - ノート通知システム

#### 監視システム
- [**監視Cogs**](03-cogs/08-monitoring-cogs.md) - モニタリング
  - Uptime Kumaステータス連携

#### AUSシステム
- [**AUS (無断転載検出) Cogs**](03-cogs/09-aus-cogs.md) - 絵師保護システム
  - 画像検出（SauceNAO + Google Vision）
  - 絵師認証システム
  - モデレーション機能
  - チケット管理

#### ランクシステム
- [**ランクCogs**](03-cogs/10-rank-cogs.md) - レベリング・実績システム
  - 高度なXP計算
  - カスタムレベル公式
  - ボイスアクティビティ追跡
  - 実績システム
  - AI品質分析

#### ストリーム通知システム
- [**ストリームCogs**](03-cogs/11-stream-cogs.md) - VTuber配信通知
  - Holodex API連携
  - ライブ配信通知
  - 予定配信管理
  - チャンネル名自動更新

#### ボイス機能
- [**ボイスCogs**](03-cogs/12-voice-cogs.md) - ボイス録音・管理
  - VC録音機能
  - Whisper APIによる文字起こし
  - 録音データ管理

#### CPシステム
- [**CP Cogs**](03-cogs/13-cp-cogs.md) - CPコマンドシステム
  - CPコマンド管理
  - イベントログ
  - 統計機能

#### Linked Roles
- [**Linked Roles Cogs**](03-cogs/14-linked-roles-cogs.md) - Discord Linked Roles連携
  - MyHFS API連携
  - メタデータスキーマ管理
  - バッチ更新処理

### 🛠️ ユーティリティ & ヘルパー
- [**データベース管理**](04-utilities/01-database-management.md) - データ永続化とマイグレーション
- [**API統合**](04-utilities/02-api-integration.md) - 外部サービス接続
- [**ログシステム**](04-utilities/02-logging-system.md) - ロギング管理
- [**AI統合**](04-utilities/03-ai-integration.md) - AI機能統合
- [**プレゼンス管理**](04-utilities/03-presence-management.md) - ボットステータスとアクティビティ
- [**ファイル管理**](04-utilities/04-file-management.md) - ファイル操作
- [**起動ユーティリティ**](04-utilities/04-startup-utilities.md) - 初期化ヘルパー

### 🚀 開発 & デプロイ
- [**開発環境セットアップ**](05-development/01-development-setup.md) - ローカル開発環境
- [**モニタリング・デバッグ**](05-development/02-monitoring-debugging.md) - デバッグツール
- [**テストフレームワーク**](05-development/02-testing-framework.md) - テスト戦略とツール
- [**デプロイガイド**](05-development/03-deployment-guide.md) - 本番デプロイプロセス
- [**セキュリティガイドライン**](05-development/03-security-guidelines.md) - セキュリティベストプラクティス
- [**貢献ガイドライン**](05-development/04-contributing-guidelines.md) - コード標準と貢献プロセス

### 📖 コマンドリファレンス
- [**コマンドカテゴリ**](06-commands/01-command-categories.md) - 全ボットコマンド概要
- [**管理者コマンド**](06-commands/02-admin-commands.md) - 管理機能
- [**ユーザーコマンド**](06-commands/03-user-commands.md) - 公開ユーザーコマンド
- [**ツールコマンド**](06-commands/04-tool-commands.md) - ユーティリティと分析コマンド

### 🔧 運用ガイド
- [**サーバーセットアップ**](07-operations/01-server-setup.md) - サーバー初期設定
- [**モニタリング・アラート**](07-operations/02-monitoring-alerts.md) - 監視とアラート設定
- [**バックアップ・リカバリ**](07-operations/03-backup-recovery.md) - データバックアップ
- [**トラブルシューティング**](07-operations/04-troubleshooting.md) - 問題解決ガイド

---

## 🎯 クイックスタート

1. **ボットの理解**: [ボットアーキテクチャ概要](01-architecture/01-bot-architecture-overview.md)から始める
2. **開発環境セットアップ**: [開発環境セットアップ](05-development/01-development-setup.md)ガイドに従う
3. **機能の探索**: [Cogsシステム](03-cogs/01-cogs-architecture.md)ドキュメントを参照
4. **貢献**: [貢献ガイドライン](05-development/04-contributing-guidelines.md)を読む

---

## 🌟 主要機能

### 🛡️ セキュリティ & モデレーション
- **AUS (無断転載検出)**: AI搭載の画像検出・絵師認証システム
- **通報システム**: メッセージ・ユーザー通報機能
- **警告システム**: ユーザー警告の記録・管理
- **タグモデレーション**: 不適切なタグの管理

### 🎮 コミュニティエンゲージメント
- **ランク/レベルシステム**: 高度なXP計算・カスタム公式対応
- **実績システム**: ゲーミフィケーション要素
- **おみくじ**: ホロライブキャラクター対応
- **ギブアウェイ**: 自動抽選機能
- **推しロールパネル**: インタラクティブなロール管理

### 🌐 ウェブサイト統合
- **サーバーアナライザー**: リアルタイム統計
- **スタッフマネージャー**: スタッフ管理システム
- **API統合**: 外部サービス連携

### 📊 分析 & モニタリング
- **ユーザーアナライザー**: ユーザー行動分析
- **サーバー統計**: 詳細な統計情報
- **Uptime Kuma**: ステータス監視
- **ボイスアクティビティ追跡**: VC利用統計

### 🔔 通知システム
- **Bump通知**: タイマー機能付き
- **VC通知**: ボイスチャット参加通知
- **ノート通知**: Note記事通知
- **カスタムアナウンスメント**: 多機能アナウンス

---

## 🔍 検索 & ナビゲーションのヒント

- 上記のナビゲーションメニューを使用して特定のセクションにジャンプ
- 各ページには関連コンポーネントへの相互参照が含まれています
- コード例にはソースファイルへの直接リンクが含まれています
- インタラクティブな図でシステム関係を表示

---

## 📊 ボット統計

- **メインボット**: COMET #6472
- **開発ボット**: COMET Dev #9786
- **プライマリギルド**: Holofan Server (HFS) Discord
- **言語**: Python 3.11+ with discord.py 2.x
- **アーキテクチャ**: マルチCogモジュラーシステム
- **データベース**: PostgreSQL with asyncpg
- **キャッシング**: Redis (オプション)

---

## 🔗 外部リンク

- [GitHubリポジトリ](https://github.com/HolofanServer/comet)
- [HFS Discord](https://discord.gg/hfs)
- [開発者プロフィール](https://github.com/HolofanServer)

---

## 📝 最新の更新

### 2025年12月
- **ストリーム通知システム**: Holodex API連携によるVTuber配信通知
- **ボイス録音システム**: VC録音・Whisper文字起こし機能
- **CPシステム**: CPコマンド・統計機能の追加
- **ドキュメント更新**: Wiki・README全面改訂

### 2025年11月
- **AUSシステム**: 無断転載検出・絵師認証システムの実装
- **ランクシステム**: 高度なレベリングシステムの追加
- **実績システム**: ゲーミフィケーション要素の実装
- **ユーザー警告システム**: 警告管理機能の追加
- **サーバータグ**: タグ管理・モデレーション機能

### 2025年6月
- **Uptime Kuma統合**: ステータス監視機能
- **ノートシステム**: Note連携強化
- **推しロールパネル**: インタラクティブUI実装

---

*このWikiは、COMET (C.O.M.E.T.) Discord botの包括的なドキュメントを提供し、開発者がボットの機能を理解、保守、拡張するのに役立つように設計されています。*
