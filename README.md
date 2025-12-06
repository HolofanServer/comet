# C.O.M.E.T. Discord Bot Wiki

<div align="center">
    <img src="https://images.frwi.net/data/images/ae990d92-087b-4500-955f-505c38bd33a6.png" alt="COMET Logo" width="200" height="200">
    <h1>C.O.M.E.T. Bot ドキュメント</h1>
    <h3> HFS専属BOT 総合ガイド</h3>
</div>

---

## 🌟 COMETについて

**COMET**の名前は以下の頭文字から構成されています：

- **C**ommunity of
- **O**shilove
- **M**oderation &
- **E**njoyment
- **T**ogether

HFS - ホロライブ非公式ファンサーバーのコミュニティを支える、推し愛とモデレーション、そして楽しさを一緒に提供するボットです。

---

## 📚 Wiki ナビゲーション

### 🏗️ アーキテクチャ & コアシステム
- [**ボットアーキテクチャ概要**](wiki/01-architecture/01-bot-architecture-overview.md) - 高レベルシステム設計とコンポーネント
- [**アプリケーション起動フロー**](wiki/01-architecture/02-application-startup-flow.md) - ボット初期化とセットアップ処理
- [**サービス層アーキテクチャ**](wiki/01-architecture/03-service-layer-architecture.md) - 依存性注入とコアサービス
- [**設定管理**](wiki/01-architecture/04-configuration-management.md) - 設定、環境変数、ボット設定

### 🔧 コアコンポーネント
- [**メインボットクラス**](wiki/02-core/01-main-bot-class.md) - MyBotクラスとコア機能
- [**認証システム**](wiki/02-core/02-authentication-system.md) - ボット認証とセキュリティ
- [**ログシステム**](wiki/02-core/03-logging-system.md) - 包括的なログとモニタリング
- [**エラーハンドリング**](wiki/02-core/04-error-handling.md) - エラー管理とレポート

### 🎯 Cogsシステム
- [**Cogsアーキテクチャ**](wiki/03-cogs/01-cogs-architecture.md) - 拡張システム概要
- [**イベントCogs**](wiki/03-cogs/02-events-cogs.md) - イベント処理とモニタリング
- [**ホームページCogs**](wiki/03-cogs/03-homepage-cogs.md) - ウェブサイト統合とサーバー分析
- [**管理Cogs**](wiki/03-cogs/04-management-cogs.md) - ボット管理と制御
- [**ツールCogs**](wiki/03-cogs/05-tool-cogs.md) - ユーティリティコマンドと機能
- [**通報Cogs**](wiki/03-cogs/06-report-cogs.md) - 通報システム
- [**ノートCogs**](wiki/03-cogs/07-note-cogs.md) - Note連携機能
- [**監視Cogs**](wiki/03-cogs/08-monitoring-cogs.md) - Uptime Kumaステータス監視
- [**AUS Cogs**](wiki/03-cogs/09-aus-cogs.md) - 無断転載検出システム
- [**ランクCogs**](wiki/03-cogs/10-rank-cogs.md) - レベリング・実績システム

### 🛠️ ユーティリティ & ヘルパー
- [**データベース管理**](wiki/04-utilities/01-database-management.md) - データ永続化とマイグレーション
- [**API統合**](wiki/04-utilities/02-api-integration.md) - 外部サービス接続
- [**ログシステム**](wiki/04-utilities/02-logging-system.md) - ロギング管理
- [**AI統合**](wiki/04-utilities/03-ai-integration.md) - AI機能統合
- [**プレゼンス管理**](wiki/04-utilities/03-presence-management.md) - ボットステータスとアクティビティ
- [**ファイル管理**](wiki/04-utilities/04-file-management.md) - ファイル操作
- [**起動ユーティリティ**](wiki/04-utilities/04-startup-utilities.md) - 初期化ヘルパー

### 🚀 開発 & デプロイ
- [**開発環境セットアップ**](wiki/05-development/01-development-setup.md) - ローカル開発環境
- [**モニタリング・デバッグ**](wiki/05-development/02-monitoring-debugging.md) - デバッグツール
- [**テストフレームワーク**](wiki/05-development/02-testing-framework.md) - テスト戦略とツール
- [**デプロイガイド**](wiki/05-development/03-deployment-guide.md) - 本番デプロイプロセス
- [**セキュリティガイドライン**](wiki/05-development/03-security-guidelines.md) - セキュリティベストプラクティス
- [**貢献ガイドライン**](wiki/05-development/04-contributing-guidelines.md) - コード標準と貢献プロセス

### 📖 コマンドリファレンス
- [**コマンドカテゴリ**](wiki/06-commands/01-command-categories.md) - 全ボットコマンド概要
- [**管理者コマンド**](wiki/06-commands/02-admin-commands.md) - 管理機能
- [**ユーザーコマンド**](wiki/06-commands/03-user-commands.md) - 公開ユーザーコマンド
- [**ツールコマンド**](wiki/06-commands/04-tool-commands.md) - ユーティリティと分析コマンド

---

## 🎯 クイックスタート

1. **ボットの理解**: [ボットアーキテクチャ概要](wiki/01-architecture/01-bot-architecture-overview.md)から始める
2. **開発環境セットアップ**: [開発環境セットアップ](wiki/05-development/01-development-setup.md)ガイドに従う
3. **機能の探索**: [Cogsシステム](wiki/03-cogs/01-cogs-architecture.md)ドキュメントを参照
4. **貢献**: [貢献ガイドライン](wiki/05-development/04-contributing-guidelines.md)を読む

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
- **プライマリギルド**: HFS - ホロライブ非公式ファンサーバー
- **言語**: Python 3.11+ with discord.py 2.5+
- **アーキテクチャ**: マルチCogモジュラーシステム
- **データベース**: PostgreSQL with asyncpg
- **バージョン**: 2.0.0

---

## 🔗 外部リンク

- [GitHubリポジトリ](https://github.com/HolofanServer/comet)
- [HFS Discord](https://discord.gg/hfs)
- [開発者プロフィール](https://github.com/HolofanServer)

---

*このWikiは、COMET (C.O.M.E.T.) Discord botの包括的なドキュメントを提供し、開発者がボットの機能を理解、保守、拡張するのに役立つように設計されています。*
