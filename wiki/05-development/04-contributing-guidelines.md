# 貢献ガイドライン

## C.O.M.E.T.について

**C.O.M.E.T.**の名前は以下の頭文字から構成されています：

- **C**ommunity of
- **O**shilove
- **M**oderation &
- **E**njoyment
- **T**ogether

HFS - ホロライブ非公式ファンサーバーのコミュニティを支える、推し愛とモデレーション、そして楽しさを一緒に提供するボットです。

## 概要

このガイドでは、COMETボットプロジェクトへの貢献方法について詳しく説明します。コード標準、開発プロセス、プルリクエストの作成方法、コミュニティガイドラインを含む包括的な貢献フレームワークを提供します。

## 貢献の種類

### 1. コード貢献

- **新機能の実装**: 新しいCogやコマンドの追加
- **バグ修正**: 既存の問題の解決
- **パフォーマンス改善**: 最適化とリファクタリング
- **セキュリティ強化**: セキュリティ脆弱性の修正

### 2. ドキュメント貢献

- **Wiki更新**: ドキュメントの改善と追加
- **コメント追加**: コードの可読性向上
- **チュートリアル作成**: 使用方法の説明
- **翻訳**: 多言語対応

### 3. テスト貢献

- **テストケース追加**: カバレッジの向上
- **バグレポート**: 問題の報告
- **品質保証**: 機能テストの実行
- **パフォーマンステスト**: 負荷テストの実施

### 4. コミュニティ貢献

- **Issue対応**: 質問への回答
- **レビュー**: プルリクエストのレビュー
- **メンタリング**: 新規貢献者のサポート
- **イベント企画**: コミュニティ活動の企画

## 開発環境のセットアップ

### 1. 前提条件

- Python 3.8 以上
- Git
- GitHub アカウント
- Discord Developer Portal アカウント

### 2. リポジトリのフォーク

```bash
# 1. GitHubでリポジトリをフォーク
# https://github.com/HolofanServer/comet をフォーク

# 2. フォークしたリポジトリをクローン
git clone https://github.com/YOUR_USERNAME/comet.git
cd comet

# 3. 上流リポジトリを追加
git remote add upstream https://github.com/HolofanServer/comet.git

# 4. 上流の変更を取得
git fetch upstream
```

### 3. 開発環境の構築

```bash
# 仮想環境の作成
python -m venv venv

# 仮想環境の有効化
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

# 依存関係のインストール
pip install -r requirements.txt

# 開発用依存関係のインストール
pip install -r requirements-dev.txt

# pre-commitフックの設定
pre-commit install
```

### 4. 設定ファイルの準備

```bash
# 環境変数ファイルのコピー
cp .env.example .env

# 設定ファイルの編集
# .envファイルに必要な値を設定
```

## コード標準

### 1. Python コーディング規約

#### PEP 8 準拠

```python
# ✅ 良い例
class ExampleCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session_cache = {}
    
    async def process_user_data(self, user_id: int, data: Dict[str, Any]) -> bool:
        """ユーザーデータの処理"""
        if not self._validate_data(data):
            return False
        
        processed_data = self._transform_data(data)
        return await self._save_data(user_id, processed_data)

# ❌ 悪い例
class exampleCog(commands.Cog):
    def __init__(self,bot):
        self.bot=bot
        self.sessionCache={}
    
    async def processUserData(self,userId,data):
        if not self._validateData(data):return False
        processedData=self._transformData(data)
        return await self._saveData(userId,processedData)
```

#### 型ヒントの使用

```python
from typing import Dict, List, Optional, Union, Any
from discord.ext import commands
import discord

class TypedCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.cache: Dict[int, str] = {}
    
    async def get_user_info(self, user_id: int) -> Optional[Dict[str, Any]]:
        """ユーザー情報の取得"""
        user = self.bot.get_user(user_id)
        if not user:
            return None
        
        return {
            "id": user.id,
            "name": user.name,
            "discriminator": user.discriminator,
            "avatar_url": str(user.avatar.url) if user.avatar else None
        }
    
    @commands.command()
    async def example_command(self, ctx: commands.Context, target: discord.Member) -> None:
        """例示コマンド"""
        info = await self.get_user_info(target.id)
        if info:
            await ctx.send(f"ユーザー情報: {info['name']}")
        else:
            await ctx.send("ユーザー情報が見つかりません。")
```

#### docstring の記述

```python
class DocumentedCog(commands.Cog):
    """
    ドキュメント化されたCogの例
    
    このCogは例示目的で作成されており、
    適切なdocstringの書き方を示しています。
    """
    
    def __init__(self, bot: commands.Bot) -> None:
        """
        Cogの初期化
        
        Args:
            bot: Discordボットインスタンス
        """
        self.bot = bot
    
    async def process_message(self, message: discord.Message) -> bool:
        """
        メッセージの処理
        
        Args:
            message: 処理対象のDiscordメッセージ
            
        Returns:
            bool: 処理が成功した場合True、失敗した場合False
            
        Raises:
            ValueError: メッセージが無効な場合
            discord.HTTPException: Discord APIエラーが発生した場合
        """
        if not message.content:
            raise ValueError("メッセージ内容が空です")
        
        try:
            # メッセージ処理ロジック
            await self._internal_process(message)
            return True
        except discord.HTTPException as e:
            logger.error(f"Discord API error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return False
    
    async def _internal_process(self, message: discord.Message) -> None:
        """
        内部処理メソッド
        
        Note:
            このメソッドは内部使用のみを想定しています。
        """
        pass
```

### 2. ファイル構造規約

```
cogs/
├── category_name/          # カテゴリごとのディレクトリ
│   ├── __init__.py        # カテゴリ初期化
│   ├── main_feature.py    # メイン機能
│   ├── helper_functions.py # ヘルパー関数
│   └── models.py          # データモデル
├── shared/                # 共有コンポーネント
│   ├── __init__.py
│   ├── base_cog.py       # ベースCogクラス
│   └── decorators.py     # 共通デコレータ
utils/
├── __init__.py
├── database.py           # データベース関連
├── logging.py           # ログ関連
├── helpers.py           # 汎用ヘルパー
└── validators.py        # バリデーション関数
```

### 3. 命名規約

#### ファイル名

```python
# ✅ 良い例
user_management.py
message_handler.py
database_manager.py

# ❌ 悪い例
UserManagement.py
messagehandler.py
db_mgr.py
```

#### クラス名

```python
# ✅ 良い例
class UserManagementCog(commands.Cog):
    pass

class DatabaseManager:
    pass

class MessageValidator:
    pass

# ❌ 悪い例
class userManagementCog(commands.Cog):
    pass

class database_manager:
    pass

class messagevalidator:
    pass
```

#### 関数・メソッド名

```python
# ✅ 良い例
async def get_user_permissions(user_id: int) -> List[str]:
    pass

async def validate_message_content(content: str) -> bool:
    pass

def calculate_user_score(activities: List[Dict]) -> float:
    pass

# ❌ 悪い例
async def GetUserPermissions(user_id: int) -> List[str]:
    pass

async def validateMessageContent(content: str) -> bool:
    pass

def calcUsrScr(activities: List[Dict]) -> float:
    pass
```

#### 定数名

```python
# ✅ 良い例
MAX_MESSAGE_LENGTH = 2000
DEFAULT_TIMEOUT_SECONDS = 300
ERROR_CHANNEL_ID = 123456789

# ❌ 悪い例
maxMessageLength = 2000
default_timeout_seconds = 300
errorChannelId = 123456789
```

## 開発プロセス

### 1. ブランチ戦略

```bash
# メインブランチ
main                    # 本番環境用の安定版
develop                 # 開発統合ブランチ

# 機能ブランチ
feature/user-management # 新機能開発
feature/message-filter  # 新機能開発

# 修正ブランチ
bugfix/memory-leak     # バグ修正
hotfix/security-patch  # 緊急修正

# リリースブランチ
release/v2.1.0         # リリース準備
```

### 2. 開発ワークフロー

```bash
# 1. 最新の変更を取得
git checkout develop
git pull upstream develop

# 2. 新しい機能ブランチを作成
git checkout -b feature/new-awesome-feature

# 3. 開発作業
# コードの実装、テストの追加

# 4. 変更をコミット
git add .
git commit -m "feat: add awesome new feature

- Implement user preference system
- Add database migration
- Include comprehensive tests
- Update documentation

Closes #123"

# 5. プッシュ
git push origin feature/new-awesome-feature

# 6. プルリクエストの作成
# GitHubでプルリクエストを作成
```

### 3. コミットメッセージ規約

#### Conventional Commits 形式

```bash
# 基本形式
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

#### コミットタイプ

```bash
feat:     # 新機能
fix:      # バグ修正
docs:     # ドキュメント更新
style:    # コードスタイル修正（機能に影響なし）
refactor: # リファクタリング
test:     # テスト追加・修正
chore:    # ビルドプロセスや補助ツールの変更
perf:     # パフォーマンス改善
ci:       # CI設定の変更
```

#### 例

```bash
# ✅ 良い例
feat(auth): add OAuth2 authentication support

Implement OAuth2 flow for user authentication with Discord.
Includes token refresh mechanism and secure storage.

Closes #45

fix(database): resolve connection pool exhaustion

- Increase connection pool size
- Add connection timeout handling
- Implement proper connection cleanup

Fixes #67

docs(wiki): update installation guide

Add Docker installation instructions and troubleshooting section.

# ❌ 悪い例
added new feature
fix bug
update docs
```

## プルリクエストガイドライン

### 1. プルリクエスト作成前チェックリスト

```markdown
## プルリクエスト作成前チェックリスト

- [ ] コードが動作することを確認
- [ ] 全てのテストが通過
- [ ] コードスタイルチェックが通過
- [ ] 適切なdocstringを追加
- [ ] 必要に応じてテストを追加
- [ ] ドキュメントを更新
- [ ] 破壊的変更がある場合は明記
- [ ] 関連するIssueを参照
```

### 2. プルリクエストテンプレート

```markdown
## 概要
<!-- 変更内容の簡潔な説明 -->

## 変更内容
<!-- 具体的な変更点をリストアップ -->
- [ ] 新機能の追加
- [ ] バグの修正
- [ ] パフォーマンスの改善
- [ ] ドキュメントの更新
- [ ] テストの追加

## 関連Issue
<!-- 関連するIssue番号を記載 -->
Closes #123
Fixes #456

## テスト
<!-- テスト方法や確認事項 -->
- [ ] ユニットテストが通過
- [ ] 統合テストが通過
- [ ] 手動テストを実施

## スクリーンショット
<!-- UIに関する変更がある場合 -->

## 破壊的変更
<!-- 破壊的変更がある場合は詳細を記載 -->
- [ ] 破壊的変更なし
- [ ] 破壊的変更あり（詳細: ）

## チェックリスト
- [ ] コードレビューの準備完了
- [ ] ドキュメント更新済み
- [ ] テスト追加済み
- [ ] CI/CDが通過
```

### 3. レビュープロセス

#### レビュー観点

```markdown
## コードレビュー観点

### 機能性
- [ ] 要件を満たしているか
- [ ] エッジケースが考慮されているか
- [ ] エラーハンドリングが適切か

### 品質
- [ ] コードが読みやすいか
- [ ] 適切な抽象化がされているか
- [ ] 重複コードがないか

### セキュリティ
- [ ] 入力検証が適切か
- [ ] 認証・認可が正しく実装されているか
- [ ] 機密情報が漏洩していないか

### パフォーマンス
- [ ] 効率的なアルゴリズムを使用しているか
- [ ] メモリリークがないか
- [ ] 不要な処理がないか

### テスト
- [ ] 十分なテストカバレッジがあるか
- [ ] テストが意味のあるものか
- [ ] テストが保守しやすいか
```

#### レビューコメント例

```markdown
# ✅ 建設的なコメント
## 提案
この部分は`functools.lru_cache`を使用することで
パフォーマンスを改善できそうです。

```python
@lru_cache(maxsize=128)
def expensive_calculation(param):
    # 処理
```

## 質問
この条件分岐の意図を教えてください。
コメントがあると理解しやすくなります。

## 賞賛
エラーハンドリングが非常に丁寧で素晴らしいです！

# ❌ 建設的でないコメント
これは間違っています。
なぜこんなコードを書いたのですか？
```

## テストガイドライン

### 1. テスト作成規約

```python
# tests/test_example_cog.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from cogs.example.example_cog import ExampleCog

class TestExampleCog:
    """ExampleCogのテストクラス"""
    
    @pytest.fixture
    async def example_cog(self, mock_bot):
        """ExampleCogのフィクスチャ"""
        cog = ExampleCog(mock_bot)
        await mock_bot.add_cog(cog)
        return cog
    
    @pytest.mark.asyncio
    async def test_command_success(self, example_cog, mock_context):
        """正常系のテスト"""
        # Arrange
        mock_context.send = AsyncMock()
        
        # Act
        await example_cog.example_command(mock_context)
        
        # Assert
        mock_context.send.assert_called_once_with("Expected message")
    
    @pytest.mark.asyncio
    async def test_command_error_handling(self, example_cog, mock_context):
        """エラーハンドリングのテスト"""
        # Arrange
        mock_context.send = AsyncMock(side_effect=Exception("Test error"))
        
        # Act & Assert
        with pytest.raises(Exception):
            await example_cog.example_command(mock_context)
    
    @pytest.mark.parametrize("input_value,expected", [
        ("valid_input", True),
        ("invalid_input", False),
        ("", False),
    ])
    def test_validation_function(self, example_cog, input_value, expected):
        """バリデーション関数のパラメータ化テスト"""
        result = example_cog.validate_input(input_value)
        assert result == expected
```

### 2. テスト実行

```bash
# 全テストの実行
pytest

# 特定のテストファイルの実行
pytest tests/test_example_cog.py

# 特定のテストメソッドの実行
pytest tests/test_example_cog.py::TestExampleCog::test_command_success

# カバレッジ付きでテスト実行
pytest --cov=cogs --cov-report=html

# 並列実行
pytest -n auto
```

## ドキュメント貢献

### 1. Wiki更新ガイドライン

```markdown
# Wiki更新時の注意点

## 構造
- 階層構造を維持する
- 適切なヘッダーレベルを使用
- 目次を更新する

## 内容
- 正確で最新の情報を記載
- 例示コードを含める
- スクリーンショットを適切に使用

## スタイル
- 一貫した文体を使用
- 専門用語は説明を追加
- 読みやすい文章構成
```

### 2. コードコメント

```python
class WellDocumentedCog(commands.Cog):
    """
    適切にドキュメント化されたCogの例
    
    このCogは以下の機能を提供します：
    - ユーザー管理
    - メッセージフィルタリング
    - 統計情報の収集
    """
    
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        # ユーザーセッションのキャッシュ（user_id -> session_data）
        self.user_sessions: Dict[int, Dict[str, Any]] = {}
        
        # 設定の読み込み
        self.config = self._load_config()
    
    @commands.command()
    async def manage_user(self, ctx: commands.Context, user: discord.Member, action: str) -> None:
        """
        ユーザー管理コマンド
        
        Args:
            ctx: コマンドコンテキスト
            user: 対象ユーザー
            action: 実行するアクション（warn, kick, ban）
        
        Examples:
            !manage_user @user warn
            !manage_user @user kick
        """
        # 権限チェック
        if not ctx.author.guild_permissions.manage_members:
            await ctx.send("このコマンドを実行する権限がありません。")
            return
        
        # アクションの実行
        if action == "warn":
            await self._warn_user(user, ctx.author)
        elif action == "kick":
            await self._kick_user(user, ctx.author)
        elif action == "ban":
            await self._ban_user(user, ctx.author)
        else:
            await ctx.send("無効なアクションです。")
    
    async def _warn_user(self, user: discord.Member, moderator: discord.Member) -> None:
        """
        ユーザーに警告を発行
        
        Note:
            警告はデータベースに記録され、累積警告数が
            設定値を超えた場合は自動的にキックされます。
        """
        # 実装...
        pass
```

## セキュリティガイドライン

### 1. セキュリティベストプラクティス

```python
# ✅ セキュアなコード例
import os
import hashlib
import secrets
from typing import Optional

class SecureUserManager:
    def __init__(self):
        # 環境変数から秘密鍵を取得
        self.secret_key = os.getenv("SECRET_KEY")
        if not self.secret_key:
            raise ValueError("SECRET_KEY environment variable is required")
    
    def hash_password(self, password: str) -> str:
        """パスワードのハッシュ化"""
        # ソルトの生成
        salt = secrets.token_hex(16)
        
        # パスワードのハッシュ化
        password_hash = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000  # 反復回数
        )
        
        return f"{salt}:{password_hash.hex()}"
    
    def validate_input(self, user_input: str) -> bool:
        """入力検証"""
        # 長さチェック
        if len(user_input) > 1000:
            return False
        
        # 危険な文字列のチェック
        dangerous_patterns = ['<script', 'javascript:', 'on\w+\s*=']
        for pattern in dangerous_patterns:
            if re.search(pattern, user_input, re.IGNORECASE):
                return False
        
        return True

# ❌ セキュリティ上問題のあるコード例
class InsecureUserManager:
    def __init__(self):
        # ハードコードされた秘密鍵（危険）
        self.secret_key = "hardcoded_secret_123"
    
    def hash_password(self, password: str) -> str:
        # 弱いハッシュ化（危険）
        return hashlib.md5(password.encode()).hexdigest()
    
    def execute_query(self, user_input: str) -> str:
        # SQLインジェクション脆弱性（危険）
        query = f"SELECT * FROM users WHERE name = '{user_input}'"
        return self.db.execute(query)
```

### 2. 機密情報の取り扱い

```python
# ✅ 適切な機密情報の取り扱い
import os
from typing import Optional

class ConfigManager:
    @staticmethod
    def get_bot_token() -> str:
        """ボットトークンの取得"""
        token = os.getenv("BOT_TOKEN")
        if not token:
            raise ValueError("BOT_TOKEN environment variable is required")
        return token
    
    @staticmethod
    def get_database_url() -> str:
        """データベースURLの取得"""
        return os.getenv("DATABASE_URL", "sqlite:///default.db")
    
    def log_config(self) -> None:
        """設定のログ出力（機密情報は除外）"""
        safe_config = {
            "environment": os.getenv("ENVIRONMENT", "development"),
            "log_level": os.getenv("LOG_LEVEL", "INFO"),
            "database_type": "sqlite" if "sqlite" in self.get_database_url() else "other"
        }
        logger.info(f"Configuration loaded: {safe_config}")

# ❌ 機密情報の不適切な取り扱い
class BadConfigManager:
    def __init__(self):
        # ログに機密情報を出力（危険）
        self.bot_token = os.getenv("BOT_TOKEN")
        logger.info(f"Bot token: {self.bot_token}")
        
        # ファイルに機密情報を保存（危険）
        with open("config.txt", "w") as f:
            f.write(f"TOKEN={self.bot_token}")
```

## コミュニティガイドライン

### 1. 行動規範

#### 歓迎される行動

- 建設的なフィードバックの提供
- 他の貢献者への敬意
- 多様な視点の受け入れ
- 学習意欲の表示
- コミュニティの改善への貢献

#### 受け入れられない行動

- 攻撃的または侮辱的な言動
- ハラスメントや差別
- 個人情報の無断公開
- スパムや宣伝
- 破壊的な行為

### 2. コミュニケーションガイドライン

```markdown
## Issue作成時

### バグレポート
- 明確なタイトル
- 再現手順の詳細
- 期待される動作と実際の動作
- 環境情報（OS、Pythonバージョンなど）
- エラーメッセージやログ

### 機能要求
- 機能の概要と目的
- 具体的な使用例
- 実装の提案（あれば）
- 代替案の検討

## プルリクエスト時

### 説明
- 変更の目的と背景
- 実装方法の説明
- テスト方法
- 破壊的変更の有無

### レビュー対応
- 迅速な対応
- 建設的な議論
- 必要に応じた修正
- 感謝の表明
```

### 3. メンタリング

#### 新規貢献者向け

```markdown
## 初回貢献者へのサポート

### Good First Issues
- 簡単な修正やドキュメント更新
- 明確な要件と期待値
- 詳細な説明とガイダンス

### メンタリングプロセス
1. 歓迎メッセージの送信
2. 開発環境セットアップの支援
3. コード作成のガイダンス
4. レビューでの丁寧な説明
5. 継続的なサポート
```

## リリースプロセス

### 1. バージョニング

```bash
# セマンティックバージョニング
MAJOR.MINOR.PATCH

# 例
2.1.0  # メジャーリリース
2.1.1  # パッチリリース
2.2.0  # マイナーリリース
```

### 2. リリース手順

```bash
# 1. リリースブランチの作成
git checkout develop
git pull upstream develop
git checkout -b release/v2.1.0

# 2. バージョン番号の更新
# config/version.json を更新

# 3. CHANGELOG.md の更新
# 新機能、修正、破壊的変更を記載

# 4. テストの実行
pytest
python -m pytest --cov=cogs --cov=utils

# 5. リリースブランチのプッシュ
git add .
git commit -m "chore: prepare release v2.1.0"
git push origin release/v2.1.0

# 6. プルリクエストの作成
# develop -> main

# 7. リリースタグの作成
git tag -a v2.1.0 -m "Release version 2.1.0"
git push upstream v2.1.0

# 8. GitHub Releaseの作成
# リリースノートの作成と公開
```

---

## 関連ドキュメント

- [開発環境セットアップ](01-development-setup.md)
- [テストフレームワーク](02-testing-framework.md)
- [デプロイガイド](03-deployment-guide.md)
- [Cogsアーキテクチャ](../03-cogs/01-cogs-architecture.md)
