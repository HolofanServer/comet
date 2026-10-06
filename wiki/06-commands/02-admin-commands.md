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
