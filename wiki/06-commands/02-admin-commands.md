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
