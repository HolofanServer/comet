# Cogsアーキテクチャ

## C.O.M.E.T.について

**C.O.M.E.T.**の名前は以下の頭文字から構成されています：

- **C**ommunity of
- **O**shilove
- **M**oderation &
- **E**njoyment
- **T**ogether

HFS - ホロライブ非公式ファンサーバーのコミュニティを支える、推し愛とモデレーション、そして楽しさを一緒に提供するボットです。

## 概要

COMETボットは、Discord.pyのCogsシステムを使用して機能をモジュラーで再ロード可能な拡張に整理します。このアーキテクチャにより、関心の明確な分離と動的機能管理が可能になります。

## Cogカテゴリ

### 1. イベントCogs (`cogs/events/`)
**目的**: Discordイベントとサーバーモニタリングを処理

| Cog | ファイル | 説明 |
|-----|------|-------------|
| バナー同期 | `banner_sync.py` | サーバーバナーと視覚要素を同期 |
| ギルドウォッチャー | `guild_watcher.py` | ギルドイベントとメンバーアクティビティを監視 |

### 2. ホームページCogs (`cogs/homepage/`)
**目的**: ウェブサイト統合とサーバー分析

| Cog | ファイル | 説明 |
|-----|------|-------------|
| スタッフマネージャー | `staff_manager.py` | スタッフロールと権限を管理 |
| サーバーアナライザー | `server_analyzer.py` | サーバー統計とメトリクスを分析 |
| ウェブサイト統合 | `website_integration.py` | ボットを外部ウェブサイトと接続 |


### 4. 管理Cogs (`cogs/manage/`)
**目的**: ボット管理と制御

| Cog | ファイル | 説明 |
|-----|------|-------------|
| Cog管理 | `manage_cogs.py` | 動的Cogロード/アンロード |
| ボット管理 | `manage_bot.py` | ボット設定と制御 |
| DBマイグレーション | `db_migration_commands.py` | データベーススキーマ管理 |
| タグモデレーション | `tag_moderation.py` | サーバータグ管理・モデレーション |
| ユーザー警告システム | `user_warning_system.py` | ユーザー警告の記録・管理 |
| ヘルプシステム | `help.py` | カスタムヘルプコマンド実装 |

### 5. ツールCogs (`cogs/tool/`)
**目的**: ユーティリティコマンドと機能

| Cog | ファイル | 説明 |
|-----|------|-------------|
| 新アナウンス | `announcement_new.py` | 高度なアナウンスシステム |
| カスタムアナウンス | `custom_announcement.py` | カスタマイズ可能なアナウンス |
| 自動リアクション | `auto_reaction.py` | 自動リアクション機能 |
| Bump通知 | `bump_notice.py` | サーバーBump通知タイマー |
| ギブアウェイ | `giveaway.py` | 自動抽選システム |
| おみくじ | `omikuji.py` | ホロライブキャラクターおみくじ |
| 推しロールパネル | `oshi_role_panel.py` | インタラクティブロール選択 |
| ピン留め | `pin_message.py` | メッセージピン留め機能 |
| サーバー統計 | `server_stats.py` | リアルタイムサーバー統計 |
| サーバータグ | `server_tag.py` | サーバータグ管理システム |
| ユーザーアナライザー | `user_analyzer.py` | ユーザー行動分析 |
| VC通知 | `vc_notic.py` | ボイスチャット参加通知 |
| ウェルカムメッセージ | `welcom_message.py` | 新メンバー歓迎システム |
| FAQ自動送信 | `send_first_message_to_faq.py` | FAQ自動応答 |
| MSアナ | `ms_ana.py` | メッセージ分析ツール |
| CV2テスト | `cv2_test.py` | コンピュータビジョンテスト |
| バグレポーター | `bug.py` | バグ報告システム |

### 6. 通報Cogs (`cogs/report/`)
**目的**: 通報・モデレーションシステム

| Cog | ファイル | 説明 |
|-----|------|-------------|
| メッセージ通報 | `report_message.py` | 不適切なメッセージ通報 |
| ユーザー通報 | `report_user.py` | 問題ユーザー通報 |
| 通報設定 | `settings.py` | 通報システム設定管理 |

### 7. ノートCogs (`cogs/note/`)
**目的**: Note連携機能

| Cog | ファイル | 説明 |
|-----|------|-------------|
| HFSボイス | `hfs_voices.py` | HFSボイス連携 |
| ノート通知 | `note_notice.py` | Note記事通知システム |

### 8. 監視Cogs (`cogs/uptimekuma/`)
**目的**: ステータス監視

| Cog | ファイル | 説明 |
|-----|------|-------------|
| ステータス | `status.py` | Uptime Kuma統合・ステータス監視 |

### 9. AUS (無断転載検出) Cogs (`cogs/aus/`)
**目的**: 絵師保護・無断転載検出システム

| Cog | ファイル | 説明 |
|-----|------|-------------|
| 画像検出 | `image_detection.py` | SauceNAO + Google Vision画像検出 |
| 絵師認証 | `artist_verification.py` | 絵師認証システム |
| モデレーション | `moderation.py` | AUS管理コマンド |
| データベース | `database.py` | AUSデータベース管理 |
| 通知Views | `views/notification_views.py` | 検出通知UI |
| 認証Views | `views/verification_views.py` | 認証チケットUI |

### 10. ランクシステム (`rank/`)
**目的**: レベリング・実績システム

| Cog | ファイル | 説明 |
|-----|------|-------------|
| ランク | `rank.py` | メインランクシステム |
| 実績 | `achievements.py` | 実績・アチーブメント |
| ボイストラッカー | `voice_tracker.py` | ボイスアクティビティ追跡 |
| ランク設定 | `rank_config.py` | ランクシステム設定 |
| ボイス設定 | `voice_config.py` | ボイスXP設定 |
| 公式設定 | `formula_config.py` | レベル公式設定 |

## Cogローディングシステム

### 動的ローディングプロセス

```python
async def load_cogs(self, folder_name: str) -> None:
    cur: pathlib.Path = pathlib.Path('.')
    for p in cur.glob(f"{folder_name}/**/*.py"):
        if 'Dev' in p.parts:
            continue
        if p.stem == "__init__":
            continue
        try:
            cog_path: str = p.relative_to(cur).with_suffix('').as_posix().replace('/', '.')
            await self.load_extension(cog_path)
            logger.info(f"Loaded extension: {cog_path}")
        except commands.ExtensionFailed as e:
            traceback.print_exc()
            logger.error(f"Failed to load extension: {cog_path} | {e}")
```

**機能**:
- **再帰的発見**: cogsディレクトリ内のすべてのPythonファイルを自動検出
- **開発フィルタリング**: 本番環境で'Dev'ディレクトリのCogsをスキップ
- **エラー耐性**: 1つのCogが失敗しても他のCogのロードを継続
- **パス正規化**: ファイルパスをPythonインポートパスに変換

### ホットリロード

ボットを再起動せずにCogsを動的にリロードできます:

```python
# Reload a specific cog
await bot.reload_extension('cogs.tool.announcement_new')

# Unload a cog
await bot.unload_extension('cogs.events.banner_sync')

# Load a new cog
await bot.load_extension('cogs.manage.new_feature')
```

## Cog構造テンプレート

### 基本Cog構造
```python
import discord
from discord.ext import commands

class ExampleCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        
    @commands.Cog.listener()
    async def on_ready(self):
        print(f"{self.__class__.__name__} is ready!")
    
    @commands.command()
    async def example_command(self, ctx):
        await ctx.send("Hello from ExampleCog!")
    
    @discord.app_commands.command()
    async def example_slash(self, interaction: discord.Interaction):
        await interaction.response.send_message("Hello from slash command!")

async def setup(bot):
    await bot.add_cog(ExampleCog(bot))
```

### 高度なCog機能

#### 1. イベントリスナー
```python
@commands.Cog.listener()
async def on_member_join(self, member):
    # Handle new member events
    pass

@commands.Cog.listener()
async def on_message(self, message):
    # Process all messages
    pass
```

#### 2. スラッシュコマンド
```python
@discord.app_commands.command(name="example", description="Example slash command")
async def example_slash(self, interaction: discord.Interaction, param: str):
    await interaction.response.send_message(f"You said: {param}")
```

#### 3. コンテキストメニュー
```python
@discord.app_commands.context_menu(name="Analyze User")
async def analyze_user(self, interaction: discord.Interaction, member: discord.Member):
    # Right-click context menu on users
    pass
```

## Cog依存関係

### 共有ユーティリティ
Cogsは一般的に`utils/`ディレクトリの共有ユーティリティを使用します:

- **データベース**: `utils/database.py`, `utils/db_manager.py`
- **ログ**: `utils/logging.py`
- **API統合**: `utils/api.py`
- **設定**: `config/setting.py`

### Cog間通信
```python
# Access other cogs
other_cog = self.bot.get_cog('OtherCogName')
if other_cog:
    result = await other_cog.some_method()
```

## Cogでのエラーハンドリング

### ローカルエラーハンドリング
```python
@example_command.error
async def example_command_error(self, ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Missing required argument!")
    else:
        # Let global handler deal with it
        raise error
```

### グローバルエラー統合
Cogsはボットのグローバルエラーハンドリングシステムと自動的に統合されます。

## パフォーマンス考慮事項

### 1. 非同期ベストプラクティス
- すべてのDiscord API呼び出しで`await`を使用
- 適切な接続プールを実装
- レート制限を優雅に処理

### 2. メモリ管理
- Cog終了時にリソースをクリーンアップ
- 大きなオブジェクトをメモリに保存することを避ける
- 大量データ処理にはジェネレーターを使用

### 3. データベース最適化
- 接続プールを使用
- 適切なインデックスを実装
- 頻繁にアクセスされるデータをキャッシュ

## 開発ガイドライン

### 1. 命名規則
- Cogクラス: `PascalCase` (例: `UserAnalyzer`)
- ファイル名: `snake_case` (例: `user_analyzer.py`)
- コマンド: `snake_case` (例: `analyze_user`)

### 2. ドキュメント
- すべてのパブリックメソッドを文書化
- 使用例を含める
- 複雑なアルゴリズムを説明

### 3. テスト
- コア機能のユニットテストを作成
- エラー条件をテスト
- Discord API相互作用を検証

---

## 関連ドキュメント

- [イベントCogs](02-events-cogs.md)
- [ホームページCogs](03-homepage-cogs.md)
- [管理Cogs](04-management-cogs.md)
- [ツールCogs](05-tool-cogs.md)
- [通報Cogs](06-report-cogs.md)
- [ノートCogs](07-note-cogs.md)
- [監視Cogs](08-monitoring-cogs.md)
- [AUS (無断転載検出) Cogs](09-aus-cogs.md)
- [ランクシステム Cogs](10-rank-cogs.md)
- [メインボットクラス](../02-core/01-main-bot-class.md)
