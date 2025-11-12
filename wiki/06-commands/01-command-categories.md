# コマンドカテゴリ

## C.O.M.E.T.について

**C.O.M.E.T.**の名前は以下の頭文字から構成されています：

- **C**ommunity of
- **O**shilove
- **M**oderation &
- **E**njoyment
- **T**ogether

HFS - ホロライブ非公式ファンサーバーのコミュニティを支える、推し愛とモデレーション、そして楽しさを一緒に提供するボットです。

## 概要

C.O.M.E.T.ボットは、HFS（ホロライブ非公式ファンサーバー）の運営を支援するための実装済みコマンドセットを提供します。以下は実際にコードベースに実装されているコマンドの一覧です。

## 実装済みコマンド一覧

### 🛡️ レポート機能
**目的**: コミュニティの安全性確保

| コマンド | タイプ | 説明 | 必要権限 |
|---------|------|-------------|-------------------|
| `メッセージを運営に通報` | コンテキストメニュー | メッセージを運営チームに通報 | メンバー |

### 🛠️ 管理コマンド
**目的**: サーバー管理とモデレーション

| コマンド | タイプ | 説明 | 必要権限 |
|---------|------|-------------|-------------------|
| `warning` | プレフィックス | ユーザー警告システム管理 | 管理者 |
| `bumpnotice` | プレフィックス | bump通知設定 | 管理者 |
| `welcome` | プレフィックス | ウェルカムメッセージ設定 | 管理者 |
| `set_welcome_channel` | プレフィックス | ウェルカムチャンネル設定 | 管理者 |

### 🔧 ツールコマンド
**目的**: ユーティリティと便利機能

| コマンド | タイプ | 説明 | 必要権限 |
|---------|------|-------------|-------------------|
| `bug_report` | プレフィックス | バグ報告（DM専用） | メンバー |
| `cv2panel` | プレフィックス | 推しロール選択パネル送信 | 特定ロール |
| `fortune` | プレフィックス | ホロ神社おみくじ | メンバー |
| `ranking` | プレフィックス | おみくじランキング表示 | メンバー |

### 📝 ノート機能
**目的**: HFS Voices インタビューシステム

| コマンド | タイプ | 説明 | 必要権限 |
|---------|------|-------------|-------------------|
| `interview` | プレフィックス | HFS Voices インタビュー開始 | 特定ロール |
| `interview_list` | プレフィックス | インタビュー一覧表示 | 特定ロール |
| `interview_export` | プレフィックス | インタビューエクスポート | 特定ロール |

### 📊 ステータス機能
**目的**: システム監視と情報表示

| コマンド | タイプ | 説明 | 必要権限 |
|---------|------|-------------|-------------------|
| `status` | プレフィックス | ステータスページ表示 | メンバー |

### 🏆 アチーブメント機能
**目的**: ユーザーエンゲージメントとゲーミフィケーション

| コマンド | タイプ | 説明 | 必要権限 |
|---------|------|-------------|-------------------|
| `achievements` | プレフィックス | アチーブメント一覧表示 | メンバー |
| `skills` | プレフィックス | スキルツリー管理 | メンバー |
| `prestige` | プレフィックス | プレステージシステム | メンバー |

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
