# ユーザーコマンド

C.O.M.E.T. Discord botの一般ユーザー向けコマンドについて説明します。これらのコマンドはすべてのサーバーメンバーが使用できます。

## 概要

ユーザーコマンドは、サーバーメンバーが日常的に使用する機能を提供します。エンターテイメント、情報取得、ユーティリティ機能が含まれます。

## 実装されているコマンド

### エンターテイメントコマンド

#### `/fortune` - ホロ神社おみくじ

**説明**: ホロ神社のおみくじを引きます。

**使用法**:
```
/fortune
```

**実装場所**: `cogs/tool/omikuji.py`

**実装例**:
```python
@app_commands.command(name="fortune", description="ホロ神社でおみくじを引きます")
async def fortune(self, interaction: discord.Interaction):
    user_id = interaction.user.id
    
    # クールダウンチェック
    if await self.is_on_cooldown(user_id):
        await interaction.response.send_message("⏰ おみくじは1日1回までです！", ephemeral=True)
        return
    
    # おみくじ結果を生成
    fortune_result = await self.generate_fortune()
    
    embed = discord.Embed(
        title="🎋 ホロ神社おみくじ",
        description=fortune_result["description"],
        color=fortune_result["color"]
    )
    embed.add_field(name="運勢", value=fortune_result["luck"], inline=True)
    embed.add_field(name="ラッキーアイテム", value=fortune_result["lucky_item"], inline=True)
    
    await interaction.response.send_message(embed=embed)
    await self.save_fortune_result(user_id, fortune_result)
```

#### `/ranking` - おみくじランキング

**説明**: おみくじの結果ランキングを表示します。

**使用法**:
```
/ranking
```

**実装場所**: `cogs/tool/omikuji.py`

### ユーティリティコマンド

#### `/bug_report` - バグ報告

**説明**: バグを報告します。

**使用法**:
```
/bug_report description:<説明> steps:<再現手順>
```

**実装場所**: `cogs/tool/bug.py`

**実装例**:
```python
@app_commands.command(name="bug_report", description="バグを報告します")
@app_commands.describe(
    description="バグの詳細説明",
    steps="再現手順（オプション）"
)
async def bug_report(
    self, 
    interaction: discord.Interaction, 
    description: str, 
    steps: str = None
):
    embed = discord.Embed(
        title="🐛 バグ報告",
        description=description,
        color=discord.Color.red(),
        timestamp=datetime.now()
    )
    
    embed.add_field(name="報告者", value=interaction.user.mention, inline=True)
    embed.add_field(name="サーバー", value=interaction.guild.name, inline=True)
    
    if steps:
        embed.add_field(name="再現手順", value=steps, inline=False)
    
    # 開発チームに通知
    await self.send_to_dev_channel(embed)
    
    await interaction.response.send_message(
        "✅ バグ報告を受け付けました。開発チームが確認いたします。",
        ephemeral=True
    )
```

#### `/status` - ステータスページ

**説明**: サーバーのステータス情報を表示します。

**使用法**:
```
/status
```

**実装場所**: `cogs/uptimekuma/status.py`

**実装例**:
```python
@app_commands.command(name="status", description="サーバーステータスを表示します")
async def status(self, interaction: discord.Interaction):
    await interaction.response.defer()
    
    # UptimeKumaからステータス情報を取得
    status_data = await self.fetch_status_data()
    
    embed = discord.Embed(
        title="📊 サーバーステータス",
        color=discord.Color.green() if status_data["all_up"] else discord.Color.red(),
        timestamp=datetime.now()
    )
    
    for service in status_data["services"]:
        status_emoji = "🟢" if service["status"] == "up" else "🔴"
        embed.add_field(
            name=f"{status_emoji} {service['name']}",
            value=f"応答時間: {service['response_time']}ms",
            inline=True
        )
    
    embed.set_footer(text="最終更新")
    
    await interaction.followup.send(embed=embed)
```

### インタビューシステム

#### `/interview` - HFS Voices インタビュー開始

**説明**: HFS Voices のインタビューを開始します。

**使用法**:
```
/interview
```

**実装場所**: `cogs/note/hfs_voices.py`

#### `/interview_list` - インタビュー一覧

**説明**: 過去のインタビュー一覧を表示します。

**使用法**:
```
/interview_list
```

**実装場所**: `cogs/note/hfs_voices.py`

#### `/interview_export` - インタビューエクスポート

**説明**: インタビューデータをエクスポートします。

**使用法**:
```
/interview_export interview_id:<ID>
```

**実装場所**: `cogs/note/hfs_voices.py`

### 開発・テストコマンド

#### CV2テストコマンド

**実装場所**: `cogs/tool/cv2_test.py`

- `/cv2panel` - CV2パネルテスト
- `/cv2media` - CV2メディアテスト  
- `/cv2demo` - CV2デモ実行

**使用法**:
```
/cv2panel
/cv2media
/cv2demo
```

## 基本的なユーザー情報コマンド

以下のコマンドは一般的なDiscordボットの機能として実装されている可能性があります：

### `/avatar` - アバター表示

**説明**: 指定したユーザーのアバター画像を表示します。

**使用法**:
```
/avatar [user]
```

### `/userinfo` - ユーザー情報

**説明**: 指定したユーザーの詳細情報を表示します。

**使用法**:
```
/userinfo [user]
```

### `/serverinfo` - サーバー情報

**説明**: 現在のサーバーの詳細情報を表示します。

**使用法**:
```
/serverinfo
```

## エラーハンドリング

### ユーザーコマンド共通エラー

```python
@commands.Cog.listener()
async def on_application_command_error(self, interaction: discord.Interaction, error):
    if isinstance(error, app_commands.CommandOnCooldown):
        await interaction.response.send_message(
            f"⏰ このコマンドはクールダウン中です。{error.retry_after:.1f}秒後に再試行してください。",
            ephemeral=True
        )
    elif isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(
            "❌ このコマンドを使用する権限がありません。",
            ephemeral=True
        )
    elif isinstance(error, app_commands.BotMissingPermissions):
        await interaction.response.send_message(
            "❌ ボットに必要な権限がありません。管理者にお問い合わせください。",
            ephemeral=True
        )
    else:
        await interaction.response.send_message(
            "❌ コマンド実行中にエラーが発生しました。",
            ephemeral=True
        )
        logger.error(f"Application command error: {error}")
```

## 使用制限

### クールダウン設定

```python
# ユーザーごとのクールダウン
@app_commands.cooldown(1, 30, key=lambda i: i.user.id)

# ギルドごとのクールダウン
@app_commands.cooldown(3, 60, key=lambda i: i.guild.id)

# チャンネルごとのクールダウン
@app_commands.cooldown(5, 120, key=lambda i: i.channel.id)
```

### 使用回数制限

```python
# 1日の使用回数制限
daily_usage = {}

async def check_daily_limit(user_id: int, command: str, limit: int = 10) -> bool:
    today = datetime.now().date()
    key = f"{user_id}:{command}:{today}"
    
    if key not in daily_usage:
        daily_usage[key] = 0
    
    if daily_usage[key] >= limit:
        return False
    
    daily_usage[key] += 1
    return True
```

---

## 関連ドキュメント

- [コマンドカテゴリ](01-command-categories.md)
- [管理者コマンド](02-admin-commands.md)
- [ツールコマンド](04-tool-commands.md)
- [エンターテイメントCogs](../03-cogs/05-tool-cogs.md)
