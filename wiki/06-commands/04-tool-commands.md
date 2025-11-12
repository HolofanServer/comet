# ツールコマンド

C.O.M.E.T. Discord botのツール・ユーティリティコマンドについて説明します。これらのコマンドは日常的な作業を効率化するための機能を提供します。

## 概要

ツールコマンドは、サーバー管理、ユーザー体験向上、開発支援など、様々なユーティリティ機能を提供します。実際に実装されているコマンドを中心に説明します。

## 実装されているツールコマンド

### サーバー管理ツール

#### `/bumpnotice` - Bump通知設定

**説明**: サーバーのBump通知を設定・管理します。

**使用法**:
```
/bumpnotice channel:<チャンネル> enable:<有効/無効>
```

**実装場所**: `cogs/tool/bump_notice.py`

**実装例**:
```python
@app_commands.command(name="bumpnotice", description="Bump通知を設定します")
@app_commands.describe(
    channel="通知を送信するチャンネル",
    enable="通知の有効/無効"
)
async def bump_notice(
    self,
    interaction: discord.Interaction,
    channel: discord.TextChannel,
    enable: bool
):
    if not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message("❌ サーバー管理権限が必要です。", ephemeral=True)
        return
    
    # 設定を保存
    await self.save_bump_settings(interaction.guild.id, channel.id, enable)
    
    embed = discord.Embed(
        title="📢 Bump通知設定",
        color=discord.Color.green() if enable else discord.Color.red()
    )
    embed.add_field(name="チャンネル", value=channel.mention, inline=True)
    embed.add_field(name="状態", value="有効" if enable else "無効", inline=True)
    
    await interaction.response.send_message(embed=embed)
```

#### `/oshirole` - 推しロールパネル管理

**説明**: 推しロール選択パネルを管理します。

**使用法**:
```
/oshirole setup
/oshirole update
/oshirole remove
```

**実装場所**: `cogs/tool/oshi_role_panel.py`

**実装例**:
```python
@app_commands.command(name="oshirole", description="推しロールパネルを管理します")
async def oshi_role_panel(
    self,
    interaction: discord.Interaction,
    action: Literal["setup", "update", "remove"]
):
    if not interaction.user.guild_permissions.manage_roles:
        await interaction.response.send_message("❌ ロール管理権限が必要です。", ephemeral=True)
        return
    
    if action == "setup":
        # ロールパネルのセットアップ
        view = OshiRoleSetupView()
        embed = discord.Embed(
            title="🎭 推しロールパネル設定",
            description="設定するロールを選択してください。",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, view=view)
    
    elif action == "update":
        # 既存パネルの更新
        await self.update_role_panel(interaction)
    
    elif action == "remove":
        # パネルの削除
        await self.remove_role_panel(interaction)
```

#### `/analytics` - ロールアナリティクス

**説明**: サーバーのロール統計を表示します。

**使用法**:
```
/analytics type:<daily/weekly/monthly>
```

**実装場所**: `cogs/tool/oshi_role_panel.py`

**実装例**:
```python
@app_commands.command(name="analytics", description="ロール統計を表示します")
async def role_analytics(
    self,
    interaction: discord.Interaction,
    type: Literal["daily", "weekly", "monthly"] = "weekly"
):
    await interaction.response.defer()
    
    # 統計データを取得
    analytics_data = await self.get_role_analytics(interaction.guild.id, type)
    
    embed = discord.Embed(
        title=f"📊 ロール統計 ({type})",
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    
    # 人気ロールトップ10
    top_roles = analytics_data["top_roles"][:10]
    for i, role_data in enumerate(top_roles, 1):
        embed.add_field(
            name=f"{i}. {role_data['name']}",
            value=f"{role_data['count']}人",
            inline=True
        )
    
    # 統計サマリー
    embed.add_field(
        name="📈 統計サマリー",
        value=f"総ロール数: {analytics_data['total_roles']}\n"
              f"アクティブユーザー: {analytics_data['active_users']}\n"
              f"平均ロール数/人: {analytics_data['avg_roles_per_user']:.1f}",
        inline=False
    )
    
    await interaction.followup.send(embed=embed)
```

### ウェルカムシステム

#### `/welcome` - ウェルカムメッセージ設定

**説明**: 新規メンバーのウェルカムメッセージを設定します。

**使用法**:
```
/welcome setup channel:<チャンネル>
```

**実装場所**: `cogs/tool/welcom_message.py`

#### `/set_welcome_channel` - ウェルカムチャンネル設定

**説明**: ウェルカムメッセージを送信するチャンネルを設定します。

**使用法**:
```
/set_welcome_channel channel:<チャンネル>
```

**実装場所**: `cogs/tool/welcom_message.py`

### コンテンツ作成ツール

#### `/カスタムアナウンス` - CV2アナウンス作成

**説明**: カスタムアナウンスメッセージを作成します。

**使用法**:
```
/カスタムアナウンス title:<タイトル> content:<内容>
```

**実装場所**: `cogs/tool/custom_announcement.py`

**実装例**:
```python
@app_commands.command(name="カスタムアナウンス", description="カスタムアナウンスを作成します")
@app_commands.describe(
    title="アナウンスのタイトル",
    content="アナウンスの内容",
    color="埋め込みの色（16進数）"
)
async def custom_announcement(
    self,
    interaction: discord.Interaction,
    title: str,
    content: str,
    color: str = "0x3498db"
):
    if not interaction.user.guild_permissions.manage_messages:
        await interaction.response.send_message("❌ メッセージ管理権限が必要です。", ephemeral=True)
        return
    
    try:
        # 色の変換
        embed_color = int(color.replace("0x", ""), 16) if color.startswith("0x") else int(color, 16)
    except ValueError:
        embed_color = 0x3498db  # デフォルト色
    
    embed = discord.Embed(
        title=title,
        description=content,
        color=embed_color,
        timestamp=datetime.now()
    )
    embed.set_footer(text=f"作成者: {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
    
    await interaction.response.send_message(embed=embed)
```

### 開発・テストツール

#### CV2テストコマンド

**実装場所**: `cogs/tool/cv2_test.py`

##### `/cv2panel` - CV2パネルテスト

**説明**: CV2パネル機能をテストします。

**使用法**:
```
/cv2panel
```

##### `/cv2media` - CV2メディアテスト

**説明**: CV2メディア機能をテストします。

**使用法**:
```
/cv2media
```

##### `/cv2demo` - CV2デモ実行

**説明**: CV2デモを実行します。

**使用法**:
```
/cv2demo
```

**実装例**:
```python
@app_commands.command(name="cv2demo", description="CV2デモを実行します")
async def cv2_demo(self, interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ 管理者権限が必要です。", ephemeral=True)
        return
    
    await interaction.response.defer()
    
    try:
        # CV2デモ処理
        demo_result = await self.run_cv2_demo()
        
        embed = discord.Embed(
            title="🎥 CV2デモ結果",
            description="CV2機能のデモが完了しました。",
            color=discord.Color.green()
        )
        embed.add_field(name="処理時間", value=f"{demo_result['duration']:.2f}秒", inline=True)
        embed.add_field(name="処理フレーム数", value=demo_result['frames'], inline=True)
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        await interaction.followup.send(f"❌ CV2デモエラー: {str(e)}", ephemeral=True)
```

## 基本的なユーティリティコマンド

以下のコマンドは一般的なDiscordボットの機能として実装されている可能性があります：

### 計算・変換ツール

#### `/calc` - 計算機

**説明**: 数式を計算して結果を表示します。

**使用法**:
```
/calc expression:<数式>
```

#### `/convert` - 単位変換

**説明**: 様々な単位間で値を変換します。

**使用法**:
```
/convert value:<値> from_unit:<変換元> to_unit:<変換先>
```

### テキスト処理ツール

#### `/encode` - テキストエンコード

**説明**: テキストを様々な形式でエンコード/デコードします。

**使用法**:
```
/encode text:<テキスト> format:<形式>
```

#### `/qr` - QRコード生成

**説明**: テキストからQRコードを生成します。

**使用法**:
```
/qr text:<テキスト> size:<サイズ>
```

### 開発者ツール

#### `/json` - JSON整形

**説明**: JSONデータを整形して表示します。

**使用法**:
```
/json data:<JSONデータ>
```

#### `/regex` - 正規表現テスト

**説明**: 正規表現のパターンマッチングをテストします。

**使用法**:
```
/regex pattern:<パターン> text:<テキスト> flags:<フラグ>
```

## エラーハンドリング

### ツールコマンド共通エラー

```python
async def handle_tool_error(self, interaction: discord.Interaction, error: Exception, tool_name: str):
    """ツールコマンドのエラーハンドリング"""
    
    error_messages = {
        "timeout": f"⏰ {tool_name}の処理がタイムアウトしました。",
        "invalid_input": f"❌ {tool_name}への入力が無効です。",
        "service_unavailable": f"🔧 {tool_name}サービスが一時的に利用できません。",
        "rate_limit": f"⏱️ {tool_name}の使用制限に達しました。しばらく待ってから再試行してください。",
        "file_too_large": f"📁 ファイルサイズが大きすぎます。",
        "unsupported_format": f"❌ サポートされていない形式です。"
    }
    
    # エラータイプの判定
    if isinstance(error, asyncio.TimeoutError):
        message = error_messages["timeout"]
    elif isinstance(error, ValueError):
        message = error_messages["invalid_input"]
    elif isinstance(error, aiohttp.ClientError):
        message = error_messages["service_unavailable"]
    else:
        message = f"❌ {tool_name}でエラーが発生しました。"
    
    try:
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)
    except:
        pass  # エラー通知の失敗は無視
    
    # ログに記録
    logger.error(f"Tool command error in {tool_name}: {error}")
```

## 使用制限とセキュリティ

### レート制限

```python
# ツールコマンドのレート制限
@app_commands.cooldown(3, 60, key=lambda i: i.user.id)  # 1分間に3回
async def resource_intensive_tool(self, interaction: discord.Interaction):
    pass

@app_commands.cooldown(10, 300, key=lambda i: i.user.id)  # 5分間に10回
async def light_tool(self, interaction: discord.Interaction):
    pass
```

### 入力検証

```python
def validate_url(url: str) -> bool:
    """URL の検証"""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def sanitize_filename(filename: str) -> str:
    """ファイル名のサニタイズ"""
    import re
    return re.sub(r'[<>:"/\\|?*]', '_', filename)
```

---

## 関連ドキュメント

- [コマンドカテゴリ](01-command-categories.md)
- [ユーザーコマンド](03-user-commands.md)
- [ツールCogs](../03-cogs/05-tool-cogs.md)
- [API統合](../04-utilities/02-api-integration.md)
