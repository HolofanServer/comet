# メインボットクラス (MyBot)

## 概要

`MyBot`クラスは、COMET Discord botの中核コンポーネントで、discord.pyの`AutoShardedBot`を拡張してGizmodo Woodsコミュニティ向けの拡張機能を提供します。

## クラス定義

**場所**: [`main.py:65-199`](../main.py#L65-L199)

```python
class MyBot(commands.AutoShardedBot):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.initialized: bool = False
        self.cog_classes: dict = {}
        self.ERROR_LOG_CHANNEL_ID: int = error_log_channel_id
        self.gagame_sessions: dict = {}
```

## 主要機能

### 1. 自動シャーディングサポート
- 複数のDiscordシャードを自動処理
- 大規模サーバー数での効率的なスケーリング
- シャード固有の操作を管理

### 2. 動的Cogローディング
- `cogs/`ディレクトリからCogsを自動ロード
- 本番環境で開発用Cogsをスキップ
- ロード失敗を優雅に処理

### 3. 包括的エラーハンドリング
- グローバルコマンドエラーハンドリング
- アプリケーションコマンドエラーハンドリング
- 構造化されたエラーログとレポート

### 4. セッション管理
- ボット初期化状態の追跡
- ログ用セッションIDの管理
- 再接続シナリオの処理

## コアメソッド

### `setup_hook()`
**目的**: 起動時にボットを初期化

```python
async def setup_hook(self) -> None:
    try:
        await self.auth()
        logger.info("認証に成功しました。Cogのロードを開始します。")
        await git_pull()
        await pip_install()
        await check_dev()
        await self.load_cogs('cogs')
        await self.load_extension('jishaku')
    except Exception as e:
        logger.error(f"認証に失敗しました。Cogのロードをスキップします。: {e}")
        return
    self.loop.create_task(self.after_ready())
```

**主要操作**:
1. **認証**: ボット認証情報を検証
2. **Git操作**: 最新のコード変更をプル
3. **依存関係**: 必要なパッケージをインストール
4. **環境チェック**: 開発/本番環境を検証
5. **Cogローディング**: すべての拡張モジュールを動的ロード
6. **Jishaku**: デバッグ拡張をロード

### `load_cogs(folder_name: str)`
**目的**: cogsディレクトリからすべてのPythonモジュールを動的ロード

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
- 再帰的ディレクトリスキャン
- 開発用Cogフィルタリング
- ロード失敗のエラーハンドリング
- インポート用パス正規化

### `on_ready()`
**目的**: ボット準備完了イベントと初期化を処理

```python
async def on_ready(self) -> None:
    logger.info(yokobou())
    logger.info("on_ready is called")
    log_data: dict = {
        "event": "BotReady",
        "description": f"{self.user} has successfully connected to Discord.",
        "timestamp": datetime.now(pytz.timezone('Asia/Tokyo')).strftime('%Y-%m-%d %H:%M:%S'),
        "session_id": session_id
    }
    save_log(log_data)
    if not self.initialized:
        try:
            await startup_send_webhook(self, guild_id=dev_guild_id)
            await startup_send_botinfo(self)
        except Exception as e:
            logger.error(f"Error during startup: {e}")
        self.initialized = True
```

**操作**:
- 接続成功をログ記録
- セッション情報を記録
- 起動通知を送信
- 初期化状態を更新

## エラーハンドリング

### コマンドエラーハンドラー
```python
@commands.Cog.listener()
async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
    if hasattr(ctx, 'handled') and ctx.handled:
        return

    error_context = {
        "command": {
            "name": ctx.command.name if ctx.command else "unknown",
            "content": ctx.message.content
        },
        "user": {
            "id": ctx.author.id,
            "name": str(ctx.author)
        }
    }
    
    if ctx.guild:
        error_context["guild"] = {
            "id": ctx.guild.id,
            "name": ctx.guild.name
        }

    handled: bool = await handle_command_error(ctx, error, self.ERROR_LOG_CHANNEL_ID)
    if handled:
        ctx.handled = True
```

### アプリケーションコマンドエラーハンドラー
```python
@commands.Cog.listener()
async def on_application_command_error(self, interaction: discord.Interaction, error: commands.CommandError) -> None:
    # Similar structure for slash command errors
    await handle_application_command_error(interaction, error)
```

## 設定

### ボット初期化
```python
intent: discord.Intents = discord.Intents.all()
bot: MyBot = MyBot(command_prefix=command_prefix, intents=intent, help_command=None)
```

**設定**:
- **Intents**: すべてのDiscord intentsを有効化
- **Prefix**: 設定可能なコマンドプレフィックス
- **Help Command**: 無効化（カスタム実装）

### 環境変数
- `TOKEN`: Discord botトークン
- `ADMIN_MAIN_GUILD_ID`: プライマリサーバーID
- `ADMIN_DEV_GUILD_ID`: 開発サーバーID
- `ADMIN_STARTUP_CHANNEL_ID`: 起動通知チャンネル
- `ADMIN_ERROR_LOG_CHANNEL_ID`: エラーログチャンネル

## インスタンス変数

| Variable | Type | Purpose |
|----------|------|---------|
| `initialized` | `bool` | Tracks initialization state |
| `cog_classes` | `dict` | Stores loaded cog references |
| `ERROR_LOG_CHANNEL_ID` | `int` | Channel for error reporting |
| `gagame_sessions` | `dict` | Game session management |

## ライフサイクル

1. **初期化**: 設定でボットインスタンスを作成
2. **セットアップフック**: 認証、Cogローディング、準備
3. **準備完了イベント**: 接続確立、通知送信
4. **ランタイム**: イベント処理とコマンドハンドリング
5. **シャットダウン**: 優雅なクリーンアップと切断

---

## 関連ドキュメント

- [認証システム](02-authentication-system.md)
- [エラーハンドリング](04-error-handling.md)
- [Cogsアーキテクチャ](../03-cogs/01-cogs-architecture.md)
- [アプリケーション起動フロー](../01-architecture/02-application-startup-flow.md)
