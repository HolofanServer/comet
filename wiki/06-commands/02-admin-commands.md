# 管理者コマンド

C.O.M.E.T. Discord botの管理者専用コマンドについて説明します。これらのコマンドは適切な権限を持つユーザーのみが使用できます。

## 概要

管理者コマンドは、サーバーの運営と管理に必要な機能を提供します。すべてのコマンドは適切な権限チェックとログ記録を行います。

## 必要な権限

- **Administrator**: 全ての管理コマンドにアクセス可能
- **Manage Server**: サーバー設定関連のコマンド
- **Manage Members**: ユーザー管理コマンド
- **Manage Messages**: メッセージ管理コマンド
- **Manage Roles**: ロール管理コマンド

## 実装されているコマンド

### `/server_close` - HFS 閉鎖時の閲覧制限

**目的**: HFS (`1092138492173242430`) の閉鎖時に、例外チャンネル以外を一般メンバーから見えなくします。通常の起動・Cog 読み込みでは権限を変更しません。

```text
/server_close                # プレビューのみ。権限変更なし
/server_close execute:true   # バックアップ後に閉鎖を実行
```

**運用順序**: 運営が先に「今後のhfsについて」(`1556917166434164736`) の公開権限を手動設定し、オンボーディングを解除してから、プレビューを確認して実行します。このコマンドは例外チャンネルの権限を変更せず、オンボーディングやデフォルトチャンネルの設定も変更・事前条件化しません。

**保護対象**:

| 対象 | ID・扱い |
| --- | --- |
| Staff | `1093678152317935696` |
| bot | `1093387737840746646` |
| bot2 | `1092988310378512434` |
| Bot 固有ロール・Bot アカウント | 自動で保護 |
| 所有者・実行 Bot | 保護 |
| Staff を表示しない運営アカウント | `1092294459317833748`。依頼者の指定により保護 |

- 実行者には **管理者** 権限、Bot には各変更対象チャンネルの **チャンネルの管理・権限の管理** と実行チャンネルの **ファイルを添付** 権限が必要です。メンバー情報の完全取得に Server Members Intent が必要です（既存 Bot は全 Intent を利用）。対象サーバー以外・DM・同時実行は拒否します。
- テキスト・アナウンス・ボイス・ステージ・フォーラム・メディアチャンネルとカテゴリを処理します。スレッドとフォーラム投稿は親チャンネルの閲覧制限を継承します。例外チャンネル配下のスレッドは例外に含まれます。
- 各対象の `@everyone` の `view_channel` を拒否し、一般ロール・一般メンバーに明示された閲覧許可も拒否へ変更します。退会済み・キャッシュ外の個人上書きも対象です。サーバー全体のロール権限や、送信など他の上書きビットは変更しません。
- 保護対象は既存の実効閲覧権限を維持します。`@everyone` の拒否で失われるアクセスだけをロール・個人の許可で補います。従来見えていない非公開チャンネルを新しく公開する処理ではありません。
- 子チャンネルを先に、カテゴリを後に変更します。例外チャンネルに親カテゴリがある場合、そのカテゴリは同期による巻き込みを防ぐため変更しません。同じカテゴリの他のチャンネルは個別に閉鎖します。
- 指定済み運営アカウント以外に、保護対象外の管理者がいれば変更前に停止します。管理者権限・所有者権限はチャンネルの拒否を無視するためです。
- 実行前にロール・全チャンネルの元の上書きを `data/server_closure/<guild_id>_<uuid>.json` へ保存し、バックアップを応答に添付します。保存・添付に失敗した場合は変更しません。スラッシュコマンドの応答は実行者だけに表示されます。`comet/server_close` でもプレビューは可能ですが、権限バックアップを一般公開しないよう、実行はスラッシュコマンドに限定します。
- 更新直前に他の操作による権限変更を確認し、適用後にサーバー情報を再取得して検証します。途中で失敗した場合は更新成功数を通知し、完了扱いにしません。自動で再公開するロールバックは行いません。元の上書きを戻す場合はバックアップを使った管理者による復旧が必要です。
- 一度実行する閉鎖処理です。処理後の新規チャンネル作成、ロール付与、他の Bot による権限変更を継続監視する機能はありません。

**導入**: `cogs/manage/server_close.py` は既存の Cog 自動ロード対象です。デプロイ・再起動とコマンド同期後に利用できます。追加依存・DB・環境変数の移行はありません。サーバー固有 ID は同ファイルの定数に集約しています。

**根拠・確認**（2026-10-06）: [Discord 権限の優先順位と管理者例外](https://docs.discord.com/developers/topics/permissions)、[Discord スレッドの権限継承](https://docs.discord.com/developers/topics/threads)、[discord.py チャンネル権限 API](https://discordpy.readthedocs.io/en/stable/api.html#discord.abc.GuildChannel.overwrites)。Context7・DeepWiki・Firecrawl は調査環境で利用できず、公式 Web 資料と discord.py 実装で補完しました。

### `/export_emojis_temp` - 絵文字 ZIP 出力（一時用）

**説明**: 実行したサーバーのカスタム絵文字のうち、名前が `m_` で始まるものを除外して、画像入りの ZIP を実行チャンネルに送信します。絵文字の移行・バックアップ作業用に追加した一時コマンドです。

**使用法**:

```text
/export_emojis_temp
comet/export_emojis_temp
```

- 実行者にはサーバーの **管理者** 権限、Bot には実行チャンネルの **ファイルを添付** 権限が必要です。DM では使えません。同じサーバーでの同時実行はできません。
- `m_` は大文字小文字を区別します。`m_example` は除外し、`M_example` や `team_m_example` は含めます。
- 画像名は元の絵文字名のままです（例: `smile.png`）。取得画像の形式に合わせて `.png`・`.gif`・`.webp` を付け、画像データを変換せず保存します。
- 同名の絵文字（大文字小文字だけが違う名前も含む）は `<絵文字ID>/<絵文字名>.<拡張子>` に格納し、展開時の上書きを防ぎます。
- 通常は `emojis_<サーバーID>.zip` を1個送ります。添付上限を超える場合は `emojis_<サーバーID>_01.zip` などに分けて送ります。各 ZIP は単独で展開できます。
- 対象がなければメッセージのみ返します。取得・送信に失敗した場合は、全件の出力が未完了であることと送信済み ZIP 数を通知します。画像取得には1件30秒、全体600秒の制限があります。
- 一時ファイルは成功・失敗のどちらでも削除します。サーバー上の絵文字は変更・削除しません。

**導入・撤去**: `cogs/manage/emoji_export.py` は既存の Cog 自動ロード対象です。Bot を再起動してコマンド同期が完了すると利用できます。作業完了後はこのファイルを削除して再起動・同期するとコマンドを撤去できます。設定・DB の移行はありません。

**形式の根拠**: Discord は WebP / AVIF 由来の絵文字の形式変換に制約を設けているため、取得画像の実形式を保持します。[Discord 公式の画像形式仕様](https://docs.discord.com/developers/reference#image-formatting) を参照してください（確認日: 2026-10-05）。

### `/export_stickers_temp` - スタンプ ZIP 出力（一時用）

**説明**: 実行したサーバーに登録されたスタンプ全件を、移行・バックアップ用の ZIP にまとめて実行チャンネルへ送信します。

**権限**: サーバー管理者のみ。Bot に「ファイルを添付」の権限が必要です。

```text
/export_stickers_temp
comet/export_stickers_temp
```

- スタンプは `m_` から始まる名前も含めて全件対象です。Discord の標準スタンプパックは対象外です。
- PNG・APNG は `.png`、GIF は `.gif`、Lottie は `.json` として保存します。画像変換は行わず、アニメーションを含む元データを保持します。
- 日本語を含む元の名前をファイル名に使います。パス区切りやOSの禁止文字は `_` に置換し、前後の空白・ピリオドを除去します。Windowsの予約名には `_` を付け、空名は `sticker` にします。Unicodeの正規化・置換後に同名となる場合は、ID別フォルダに格納します。
- `_metadata/stickers.json` にスタンプID・変更前の名前・説明・関連絵文字・形式・ZIP内のファイルパスを記録します。移行先への登録時に参照してください。
- 通常は `stickers_<サーバーID>.zip`、添付上限を超える場合は `stickers_<サーバーID>_01.zip` などに分割します。各ZIPは単独で展開できます。分割時はメタデータが別のZIPに入る場合があるため、全ZIPを取得してください。
- 同じサーバーでは同時に1回まで実行できます。途中で失敗した場合は送信済みZIP数と未完了を通知します。一時ファイルは成功・失敗のどちらでも削除します。

**導入・移行**: 絵文字と共通の `cogs/manage/emoji_export.py` で提供します。既存の `/export_emojis_temp` の使い方は変わりません。Bot の再起動・コマンド同期で追加され、設定・DBの移行は不要です。ZIP取得後の移行先へのスタンプ登録は手動で行います。元サーバーのスタンプは変更・削除しません。Lottieを再登録できるのはDiscordが認める認証済み・パートナーサーバーです。

**形式の根拠**（確認日: 2026-10-07）: [Discord公式スタンプ仕様](https://docs.discord.com/developers/resources/sticker)、[discord.py公式実装](https://github.com/Rapptz/discord.py/blob/master/discord/sticker.py)、[Discord公式のアップロード案内](https://discord.com/blog/how-to-create-upload-your-own-stickers-on-discord)。discord.pyの `read()` はLottieを扱わないため、公開CDNからJSONを取得します。Context7・DeepWiki・Firecrawl Search MCPは利用できず、上記一次情報で補完しました。

### `/warning` - ユーザー警告システム

**説明**: ユーザーの警告を管理します。

**サブコマンド**:
- `add` - 警告を追加
- `remove` - 警告を削除
- `list` - 警告一覧を表示
- `clear` - 全警告をクリア

**使用法**:
```
/warning add user:<ユーザー> reason:<理由>
/warning list user:<ユーザー>
/warning remove warning_id:<ID>
/warning clear user:<ユーザー>
```

**実装場所**: `cogs/manage/user_warning_system.py`

**実装例**:
```python
@app_commands.command(name="warning", description="ユーザー警告システム")
async def warning_command(
    self,
    interaction: discord.Interaction,
    action: Literal["add", "remove", "list", "clear"],
    user: discord.Member = None,
    reason: str = None,
    warning_id: int = None
):
    if not interaction.user.guild_permissions.manage_members:
        await interaction.response.send_message("❌ メンバー管理権限がありません。", ephemeral=True)
        return
    
    if action == "add":
        if not user or not reason:
            await interaction.response.send_message("❌ ユーザーと理由を指定してください。", ephemeral=True)
            return
        
        warning_data = {
            "user_id": user.id,
            "moderator_id": interaction.user.id,
            "reason": reason,
            "timestamp": datetime.now(),
            "guild_id": interaction.guild.id
        }
        
        # データベースに保存
        await self.save_warning(warning_data)
        
        embed = discord.Embed(
            title="⚠️ 警告を追加しました",
            color=discord.Color.orange(),
            timestamp=datetime.now()
        )
        embed.add_field(name="対象ユーザー", value=user.mention, inline=True)
        embed.add_field(name="理由", value=reason, inline=True)
        embed.add_field(name="実行者", value=interaction.user.mention, inline=True)
        
        await interaction.response.send_message(embed=embed)
```

### `/bumpnotice` - Bump通知設定

**説明**: サーバーのBump通知を設定します。

**使用法**:
```
/bumpnotice channel:<チャンネル> enable:<有効/無効>
```

**実装場所**: `cogs/tool/bump_notice.py`

### `/oshirole` - 推しロールパネル管理

**説明**: 推しロール選択パネルを管理します。

**使用法**:
```
/oshirole setup
/oshirole update
```

**実装場所**: `cogs/tool/oshi_role_panel.py`

### `/analytics` - ロールアナリティクス

**説明**: サーバーのロール統計を表示します。

**使用法**:
```
/analytics type:<daily/weekly/monthly>
```

**実装場所**: `cogs/tool/oshi_role_panel.py`

### `/welcome` - ウェルカムメッセージ設定

**説明**: 新規メンバーのウェルカムメッセージを設定します。

**使用法**:
```
/welcome setup channel:<チャンネル>
/set_welcome_channel channel:<チャンネル>
```

**実装場所**: `cogs/tool/welcom_message.py`

### `/カスタムアナウンス` - CV2アナウンス作成

**説明**: カスタムアナウンスメッセージを作成します。

**使用法**:
```
/カスタムアナウンス title:<タイトル> content:<内容>
```

**実装場所**: `cogs/tool/custom_announcement.py`

## 開発・デバッグコマンド

### CV2テストコマンド

**実装場所**: `cogs/tool/cv2_test.py`

- `/cv2panel` - CV2パネルテスト
- `/cv2media` - CV2メディアテスト  
- `/cv2demo` - CV2デモ実行

## エラーハンドリング

### 共通エラーパターン

```python
@command.error
async def command_error(self, ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ このコマンドを実行する権限がありません。")
    elif isinstance(error, commands.BotMissingPermissions):
        await ctx.send("❌ ボットに必要な権限がありません。")
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("❌ 指定されたユーザーが見つかりません。")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ 引数が正しくありません。")
    else:
        await ctx.send(f"❌ エラーが発生しました: {str(error)}")
        logger.error(f"Command error: {error}")
```

## ログ記録

### モデレーションアクションのログ

```python
async def log_moderation_action(self, action: str, target: discord.Member, moderator: discord.Member, reason: str):
    """モデレーションアクションのログ記録"""
    log_channel = self.bot.get_channel(self.log_channel_id)
    if not log_channel:
        return
    
    embed = discord.Embed(
        title=f"🛡️ {action}",
        color=self.get_action_color(action),
        timestamp=datetime.now()
    )
    
    embed.add_field(name="対象ユーザー", value=f"{target.mention} ({target.id})", inline=False)
    embed.add_field(name="実行者", value=f"{moderator.mention} ({moderator.id})", inline=True)
    embed.add_field(name="理由", value=reason, inline=True)
    
    await log_channel.send(embed=embed)
```

---

## 関連ドキュメント

- [コマンドカテゴリ](01-command-categories.md)
- [ユーザーコマンド](03-user-commands.md)
- [管理Cogs](../03-cogs/04-management-cogs.md)
- [エラーハンドリング](../02-core/04-error-handling.md)
