# コマンドカテゴリ

## 概要

COMETボットは、論理的なカテゴリに整理された包括的なコマンドセットを提供します。コマンドは従来のプレフィックスコマンドと現代的なスラッシュコマンドの両方で利用できます。

## コマンドカテゴリ

### 🛠️ 管理コマンド
**目的**: ボット管理とサーバー管理

| コマンド | タイプ | 説明 | 必要権限 |
|---------|------|-------------|-------------------|
| `reload` | プレフィックス | 特定のCogを再読み込み | 管理者 |
| `load` | プレフィックス | 新しいCogを読み込み | 管理者 |
| `unload` | プレフィックス | Cogをアンロード | 管理者 |
| `sync` | プレフィックス | スラッシュコマンドを同期 | 管理者 |
| `shutdown` | プレフィックス | ボットを正常にシャットダウン | ボット所有者 |

### 📊 分析コマンド
**目的**: サーバーとユーザー分析

| コマンド | タイプ | 説明 | 必要権限 |
|---------|------|-------------|-------------------|
| `/analyze_user` | スラッシュ | ユーザー活動パターンを分析 | モデレーター |
| `/server_stats` | スラッシュ | サーバー統計を表示 | メンバー |
| `/message_analysis` | スラッシュ | メッセージパターンを分析 | モデレーター |
| `/activity_report` | スラッシュ | 活動レポートを生成 | モデレーター |

### 📢 アナウンスコマンド
**目的**: サーバーアナウンスと通知

| コマンド | タイプ | 説明 | 必要権限 |
|---------|------|-------------|-------------------|
| `/announce` | スラッシュ | サーバーアナウンスを作成 | モデレーター |
| `/custom_announce` | スラッシュ | カスタムアナウンスを作成 | モデレーター |
| `/announcement_new` | スラッシュ | 高度なアナウンスシステム | 管理者 |
| `/schedule_announce` | スラッシュ | 将来のアナウンスをスケジュール | モデレーター |

### 🎭 ロール管理コマンド
**目的**: ロール割り当てと管理

| コマンド | タイプ | 説明 | 必要権限 |
|---------|------|-------------|-------------------|
| `/oshi_panel` | スラッシュ | ロール選択パネルを表示 | メンバー |
| `/assign_role` | スラッシュ | ユーザーにロールを割り当て | モデレーター |
| `/remove_role` | スラッシュ | ユーザーからロールを削除 | モデレーター |
| `/role_info` | スラッシュ | ロール情報を表示 | メンバー |

### 🔍 ユーティリティコマンド
**目的**: 一般的なユーティリティと情報

| コマンド | タイプ | 説明 | 必要権限 |
|---------|------|-------------|-------------------|
| `/help` | スラッシュ | ヘルプ情報を表示 | メンバー |
| `/ping` | スラッシュ | ボットのレイテンシをチェック | メンバー |
| `/uptime` | スラッシュ | ボットの稼働時間を表示 | メンバー |
| `/version` | スラッシュ | ボットのバージョンを表示 | メンバー |

### 🎮 エンターテイメントコマンド
**目的**: 楽しくインタラクティブな機能

| コマンド | タイプ | 説明 | 必要権限 |
|---------|------|-------------|-------------------|
| `/cv2_test` | スラッシュ | コンピュータビジョンテスト | メンバー |
| `/recorder` | スラッシュ | 音声録音機能 | メンバー |
| `/game_stats` | スラッシュ | ゲーム統計 | メンバー |

### 🐛 デバッグコマンド
**目的**: デバッグと開発

| コマンド | タイプ | 説明 | 必要権限 |
|---------|------|-------------|-------------------|
| `/bug_report` | スラッシュ | 開発者にバグを報告 | メンバー |
| `/debug_info` | スラッシュ | デバッグ情報を表示 | 管理者 |
| `/test_feature` | スラッシュ | 新機能をテスト | 開発者 |

## コマンド構造

### スラッシュコマンド構造
```python
@discord.app_commands.command(name="command_name", description="Command description")
@discord.app_commands.describe(
    parameter1="Description of parameter 1",
    parameter2="Description of parameter 2"
)
async def command_name(
    self, 
    interaction: discord.Interaction, 
    parameter1: str, 
    parameter2: int = None
):
    await interaction.response.send_message("Response")
```

### プレフィックスコマンド構造
```python
@commands.command(name="command_name", help="Command help text")
@commands.has_permissions(administrator=True)
async def command_name(self, ctx, parameter1: str, parameter2: int = None):
    await ctx.send("Response")
```

## 権限システム

### 権限レベル
1. **ボット所有者**: すべてのコマンドへのフルアクセス
2. **管理者**: サーバー管理コマンド
3. **モデレーター**: モデレーションと分析コマンド
4. **メンバー**: 基本的なユーティリティとエンターテイメントコマンド
5. **ゲスト**: 限定的な読み取り専用コマンド

### 権限デコレーター
```python
# Discord.py permission checks
@commands.has_permissions(administrator=True)
@commands.has_role("Moderator")
@commands.has_any_role("Admin", "Moderator")

# Custom permission checks
@commands.check(is_bot_owner)
@commands.check(is_staff_member)
```

## コマンドエラーハンドリング

### 一般的なエラータイプ
- **権限不足**: ユーザーに必要な権限がない
- **引数不足**: 必要なパラメータが提供されていない
- **無効な引数**: パラメータが期待される型と一致しない
- **コマンドが見つからない**: コマンドが存在しない
- **コマンド無効**: コマンドが一時的に無効化されている

### エラーレスポンス例
```python
# 権限エラー
"❌ このコマンドを使用する権限がありません。"

# 引数不足エラー
"❌ 必要な引数が不足しています: `user`。使用法: `/analyze_user <user>`"

# 無効な引数エラー
"❌ 無効なユーザーが指定されました。有効なサーバーメンバーをメンションしてください。"

# コマンド無効エラー
"⚠️ このコマンドはメンテナンスのため一時的に無効化されています。"
```

## コマンド使用統計

### 最も使用されるコマンド
1. `/help` - ヘルプと情報
2. `/server_stats` - サーバー統計
3. `/oshi_panel` - ロール選択
4. `/ping` - ボットステータスチェック
5. `/announce` - アナウンス

### コマンド応答時間
- **シンプルなコマンド**: < 100ms
- **データベースクエリ**: < 500ms
- **分析コマンド**: < 2s
- **複雑な操作**: < 5s

## コマンドエイリアス

### 一般的なエイリアス
```python
# Multiple names for same command
@commands.command(aliases=['stats', 'info', 'status'])
async def server_stats(self, ctx):
    pass

# Short forms
@commands.command(aliases=['r'])
async def reload(self, ctx, cog):
    pass
```

## コマンドクールダウン

### クールダウン設定
```python
# Per-user cooldown
@commands.cooldown(1, 30, commands.BucketType.user)

# Per-guild cooldown
@commands.cooldown(5, 60, commands.BucketType.guild)

# Global cooldown
@commands.cooldown(1, 10, commands.BucketType.default)
```

### クールダウンバイパス
- ボット所有者はすべてのクールダウンをバイパス
- 管理者はクールダウンが短縮される
- プレミアムユーザーはクールダウンが短縮される場合がある

## コマンドドキュメント

### ヘルプシステム
ボットには包括的なヘルプシステムが含まれています:

```python
# General help
/help

# Category-specific help
/help category:administration

# Command-specific help
/help command:analyze_user
```

### コマンド例
各コマンドには使用例が含まれています:

```
/analyze_user user:@username
/announce title:"Server Update" message:"New features available!"
/oshi_panel category:"Gaming Roles"
```

## 国際化

### サポート言語
- **日本語 (ja)**: 主要言語
- **英語 (en)**: 副言語

### 言語選択
```python
# User can set preferred language
/settings language:ja
/settings language:en
```

## コマンドメトリクス

### パフォーマンス監視
- コマンド実行時間
- 成功/失敗率
- 使用頻度
- エラーパターン

### 分析ダッシュボード
- 最も人気のあるコマンド
- ピーク使用時間
- ユーザーエンゲージメント指標
- エラー率のトレンド

---

## 関連ドキュメント

- [管理コマンド](02-admin-commands.md)
- [ユーザーコマンド](03-user-commands.md)
- [ツールコマンド](04-tool-commands.md)
- [エラーハンドリング](../02-core/04-error-handling.md)
