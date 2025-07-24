# 管理Cogs

## 概要

管理Cogsは、ボット制御、Cog管理、データベース操作、ヘルプシステムの管理機能を提供します。

## 利用可能な管理Cogs

### 1. Cog管理 (`manage_cogs.py`)

**目的**: ボット拡張の動的ロード、アンロード、リロード。

**主要機能**:
- **ホットリロード**: ボットを再起動せずにCogsをリロード
- **拡張管理**: 個別Cogのロード/アンロード
- **エラーハンドリング**: 拡張失敗の優雅な処理
- **インタラクティブインターフェース**: 簡単管理のためのスラッシュコマンド

**利用可能なコマンド**:
- `/reload_cog`: 特定のCogをリロード
- `/load_cog`: 新しいCogをロード
- `/unload_cog`: 既存のCogをアンロード
- `/list_cogs`: ロード済みのすべてのCogをリスト表示

### 2. データベースマイグレーションコマンド (`db_migration_commands.py`)

**目的**: データベーススキーマ管理とマイグレーション操作。

**主要機能**:
- **スキーマバージョニング**: データベーススキーマ変更を追跡
- **マイグレーションスクリプト**: データベース更新を安全に適用
- **ロールバックサポート**: 問題のあるマイグレーションを元に戻す
- **データ整合性**: マイグレーション中のデータ一貫性を確保

**利用可能なコマンド**:
- `/migrate`: 保留中のデータベースマイグレーションを適用
- `/rollback`: 最後のマイグレーションをロールバック
- `/migration_status`: 現在のマイグレーション状態をチェック

### 3. ヘルプシステム (`help.py`)

**目的**: 拡張フォーマット付きカスタムヘルプコマンド実装。

**主要機能**:
- **カテゴリ化されたコマンド**: 機能別にコマンドを整理
- **インタラクティブヘルプ**: 詳細なコマンド説明と使用法
- **権限認識**: アクセス可能なコマンドのみ表示
- **リッチフォーマット**: 拡張された視覚的プレゼンテーション

**利用可能なコマンド**:
- `/help`: 一般的なヘルプ情報を表示
- `/help <command>`: 特定のコマンドの詳細ヘルプを取得
- `/help <category>`: カテゴリ内のコマンドを表示

### 4. ボット管理 (`manage_bot.py`)

**目的**: コアボット管理と管理操作。

**主要機能**:
- **ボット制御**: 再起動、シャットダウン、ステータス操作
- **システム情報**: ボット統計と健全性を表示
- **設定管理**: ランタイム設定更新
- **メンテナンスモード**: 一時的なボットメンテナンス状態

**利用可能なコマンド**:
- `/bot_status`: ボットの健全性と統計を表示
- `/restart_bot`: ボットを再起動（オーナーのみ）
- `/shutdown_bot`: ボットを優雅にシャットダウン（オーナーのみ）
- `/maintenance`: メンテナンスモードを切り替え

## コマンド構造

### 権限レベル
管理コマンドは厳格な権限チェックを使用します:

```python
# Owner-only commands
@is_owner()

# Administrator permissions
@commands.has_permissions(administrator=True)

# Guild-specific commands
@is_guild()
```

### エラーハンドリング
すべての管理コマンドは包括的なエラーハンドリングを含みます:

```python
try:
    # Command logic
    await operation()
    await interaction.response.send_message("✅ Operation successful")
except Exception as e:
    logger.error(f"Management command failed: {e}")
    await interaction.response.send_message(f"❌ Operation failed: {e}")
```

### ログ統合
管理操作は監査目的でログに記録されます:

```python
@log_commands()
async def management_command(self, interaction):
    # Command execution is automatically logged
    pass
```

## セキュリティ考慮事項

### アクセス制御
- **オーナー検証**: 重要な操作にはボットオーナーステータスが必要
- **権限チェック**: コマンドはDiscord権限を検証
- **ギルド制限**: 一部のコマンドは特定のギルドに制限

### 監査証跡
- **コマンドログ**: すべての管理コマンドがログに記録
- **エラー追跡**: 失敗はコンテキストと共に記録
- **変更履歴**: データベースマイグレーションは履歴を維持

### 安全な操作
- **優雅な劣化**: 失敗した操作はボットをクラッシュさせない
- **ロールバック機能**: データベース変更は元に戻すことが可能
- **確認プロンプト**: 破壊的操作には確認が必要

## 使用例

### Cog管理
```
/reload_cog cog:user_analyzer
/load_cog cog:new_feature
/unload_cog cog:deprecated_feature
```

### データベース操作
```
/migrate
/migration_status
/rollback
```

### ボット制御
```
/bot_status
/maintenance mode:on
/restart_bot
```

---

## 関連ドキュメント

- [メインボットクラス](../02-core/01-main-bot-class.md)
- [データベース管理](../04-utilities/01-database-management.md)
- [エラーハンドリング](../02-core/04-error-handling.md)
- [セキュリティガイドライン](../05-development/03-security-guidelines.md)
