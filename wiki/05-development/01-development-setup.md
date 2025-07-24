# 開発セットアップ

## 前提条件

### システム要件
- **オペレーティングシステム**: Linux (Ubuntu/Debian推奨)、macOS、またはWSL付きWindows
- **Python**: 3.8以上 (3.10+推奨)
- **Git**: 最新版
- **テキストエディタ**: VS Code、PyCharm、またはPythonサポート付きの類似エディタ

### 必要なアカウント
- **Discord開発者アカウント**: ボットトークンとアプリケーション管理用
- **GitHubアカウント**: リポジトリアクセスと貢献用

## インストールガイド

### 1. リポジトリのクローン
```bash
git clone https://github.com/FreeWiFi7749/hfs-homepage-mg-bot.git
cd hfs-homepage-mg-bot
```

### 2. Python環境セットアップ

#### venvを使用 (推奨)
```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# On Linux/macOS:
source venv/bin/activate
# On Windows:
venv\Scripts\activate
```

#### condaを使用 (代替)
```bash
# Create conda environment
conda create -n hfs-bot python=3.10
conda activate hfs-bot
```

### 3. 依存関係のインストール
```bash
# Install required packages
pip install -r requirements.txt

# For development dependencies (if available)
pip install -r requirements-dev.txt
```

### 4. 環境設定

#### 環境ファイルの作成
```bash
cp .env.example .env
```

#### 環境変数の設定
`.env`ファイルを設定で編集します:

```env
# Discord Bot Configuration
BOT_TOKEN=your_discord_bot_token_here
ADMIN_MAIN_GUILD_ID=your_main_guild_id
ADMIN_DEV_GUILD_ID=your_dev_guild_id
ADMIN_STARTUP_CHANNEL_ID=your_startup_channel_id
ADMIN_BUG_REPORT_CHANNEL_ID=your_bug_report_channel_id
ADMIN_ERROR_LOG_CHANNEL_ID=your_error_log_channel_id

# Authentication
AUTH_TOKEN=your_auth_token
AUTH_URL=your_auth_endpoint

# Optional: Sentry (Error Tracking)
SENTRY_DSN=your_sentry_dsn_here

# Optional: Prometheus (Monitoring)
PROMETHEUS_ENABLED=false
PROMETHEUS_PORT=8001
```

### 5. Discord Bot セットアップ

#### Discordアプリケーションの作成
1. [Discord Developer Portal](https://discord.com/developers/applications)にアクセス
2. "New Application"をクリック
3. アプリケーションに名前を付ける (例: "HFS Dev")
4. "Bot"セクションに移動
5. "Add Bot"をクリック
6. ボットトークンを`.env`ファイルにコピー

#### ボット権限
完全な機能に必要な権限:
- **一般権限**:
  - ロール管理
  - チャンネル管理
  - メンバーキック
  - メンバーBAN
  - 招待リンク作成
  - ニックネーム管理
  - 絵文字とスタンプ管理
  - 監査ログ表示

- **テキスト権限**:
  - メッセージ送信
  - スレッドでメッセージ送信
  - パブリックスレッド作成
  - プライベートスレッド作成
  - リンク埋め込み
  - ファイル添付
  - メッセージ履歴読み取り
  - @everyone/@hereメンション
  - 外部絵文字使用
  - リアクション追加
  - スラッシュコマンド使用

- **音声権限**:
  - 接続
  - 発言
  - 音声検出使用

#### ボットをサーバーに招待
1. "OAuth2" → "URL Generator"に移動
2. "bot"と"applications.commands"スコープを選択
3. 必要な権限を選択
4. 生成されたURLを使用してボットをテストサーバーに招待

## 開発ワークフロー

### 1. ブランチ管理
```bash
# Create feature branch
git checkout -b feature/your-feature-name

# Make changes and commit
git add .
git commit -m "feat: add new feature"

# Push to remote
git push origin feature/your-feature-name
```

### 2. ボットの実行

#### 開発モード
```bash
# Run with debug logging
python main.py
```

#### 本番モード
```bash
# Set production environment
export ENVIRONMENT=production
python main.py
```

### 3. テスト

#### 手動テスト
1. 開発モードでボットを起動
2. 検証用テストDiscordサーバーを使用
3. コマンドと機能をテスト
4. エラーのログを監視

#### 自動テスト (利用可能な場合)
```bash
# Run unit tests
python -m pytest tests/

# Run with coverage
python -m pytest tests/ --cov=.
```

## 開発ツール

### 1. コードフォーマット
```bash
# Install black (code formatter)
pip install black

# Format code
black .

# Check formatting
black --check .
```

### 2. リンティング
```bash
# Install flake8 (linter)
pip install flake8

# Run linting
flake8 .
```

### 3. 型チェック
```bash
# Install mypy (type checker)
pip install mypy

# Run type checking
mypy .
```

### 4. Pre-commitフック (推奨)
```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install

# Run hooks manually
pre-commit run --all-files
```

## IDE設定

### VS Code セットアップ

#### 推奨拡張機能
- Python
- Python Docstring Generator
- GitLens
- Discord.py Snippets
- JSON Tools

#### 設定 (`.vscode/settings.json`)
```json
{
    "python.defaultInterpreterPath": "./venv/bin/python",
    "python.linting.enabled": true,
    "python.linting.flake8Enabled": true,
    "python.formatting.provider": "black",
    "python.formatting.blackArgs": ["--line-length", "88"],
    "files.exclude": {
        "**/__pycache__": true,
        "**/*.pyc": true
    }
}
```

### PyCharm セットアップ

#### 設定
1. PyCharmでプロジェクトを開く
2. 仮想環境を使用するようにPythonインタープリターを設定
3. Python用コード検査を有効化
4. プロジェクト標準に合わせてコードスタイルを設定

## デバッグ

### 1. デバッグ設定

#### VS Code デバッグ設定 (`.vscode/launch.json`)
```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Python: Bot",
            "type": "python",
            "request": "launch",
            "program": "main.py",
            "console": "integratedTerminal",
            "env": {
                "PYTHONPATH": "${workspaceFolder}"
            }
        }
    ]
}
```

### 2. ログ設定
```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Discord.py debug logging
logging.getLogger('discord').setLevel(logging.DEBUG)
logging.getLogger('discord.http').setLevel(logging.INFO)
```

### 3. Jishaku (開発拡張)
ボットには実行時デバッグ用のJishakuが含まれています:

```python
# Load/reload cogs
>load cogs.tool.example
>reload cogs.tool.example

# Execute Python code
>py await ctx.send("Hello from Jishaku!")

# Shell commands
>sh git status

# SQL queries (if database available)
>sql SELECT * FROM users LIMIT 5
```

## よくある問題と解決策

### 1. インポートエラー
```bash
# Ensure PYTHONPATH is set correctly
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Or use relative imports in code
from .utils import helper_function
```

### 2. 権限エラー
- ボットがDiscordサーバーで必要な権限を持っていることを確認
- ロール階層を確認 (ボットロールは管理対象ロールより上位である必要)
- ボットが正しいチャンネルにいることを確認

### 3. トークン問題
- 漏洩した場合はボットトークンを再生成
- 環境変数にトークンが正しく設定されていることを確認
- トークンに余分なスペースや文字がないかチェック

### 4. データベース問題
```bash
# Reset database (development only)
rm -f config/*.json
python main.py  # Will recreate with defaults
```

## パフォーマンス監視

### 1. メモリ使用量
```python
import psutil
import os

def get_memory_usage():
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1024 / 1024  # MB
```

### 2. 応答時間
```python
import time
from functools import wraps

def measure_time(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start = time.time()
        result = await func(*args, **kwargs)
        end = time.time()
        print(f"{func.__name__} took {end - start:.2f} seconds")
        return result
    return wrapper
```

## 貢献ガイドライン

### 1. コード標準
- PEP 8スタイルガイドラインに従う
- 可能な限り型ヒントを使用
- 説明的なコミットメッセージを書く
- 関数とクラスにdocstringを追加

### 2. プルリクエストプロセス
1. `main`から機能ブランチを作成
2. 適切なテストと共に変更を行う
3. 必要に応じてドキュメントを更新
4. 明確な説明と共にプルリクエストを提出
5. レビューフィードバックに対応

### 3. 問題報告
- GitHubイシューテンプレートを使用
- 明確な再現手順を提供
- 関連するログとエラーメッセージを含める
- 適切にイシューをタグ付け

---

## 関連ドキュメント

- [ボットアーキテクチャ概要](../01-architecture/01-bot-architecture-overview.md)
- [設定管理](../01-architecture/04-configuration-management.md)
- [テストフレームワーク](02-testing-framework.md)
- [貢献ガイドライン](04-contributing-guidelines.md)
