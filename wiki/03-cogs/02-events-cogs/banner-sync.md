# バナー同期

## C.O.M.E.T.について

**C.O.M.E.T.**の名前は以下の頭文字から構成されています：

- **C**ommunity of
- **O**shilove
- **M**oderation &
- **E**njoyment
- **T**ogether

HFS - ホロライブ非公式ファンサーバーのコミュニティを支える、推し愛とモデレーション、そして楽しさを一緒に提供するボットです。

## 概要

バナー同期機能は、サーバーのバナー画像を自動的に管理・更新するシステムです。特定の条件に基づいてバナーを変更し、コミュニティの雰囲気を演出します。

## 機能

### 自動バナー更新

- 時間帯に応じたバナー変更
- イベント連動バナー
- 季節・記念日対応バナー
- メンバー数に応じたバナー変更

### バナー管理

- バナー画像の登録・削除
- バナー変更履歴の記録
- バナー品質チェック

## 実装例

```python
import discord
from discord.ext import commands, tasks
import asyncio
from datetime import datetime
import aiohttp

class BannerSync(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.banner_rotation.start()
        self.banner_images = {
            'morning': 'https://example.com/morning_banner.png',
            'afternoon': 'https://example.com/afternoon_banner.png',
            'evening': 'https://example.com/evening_banner.png',
            'night': 'https://example.com/night_banner.png'
        }
    
    @tasks.loop(hours=1)
    async def banner_rotation(self):
        """バナー自動更新"""
        current_hour = datetime.now().hour
        
        if 6 <= current_hour < 12:
            banner_key = 'morning'
        elif 12 <= current_hour < 18:
            banner_key = 'afternoon'
        elif 18 <= current_hour < 22:
            banner_key = 'evening'
        else:
            banner_key = 'night'
        
        await self.update_banner(banner_key)
    
    async def update_banner(self, banner_key: str):
        """バナー更新"""
        try:
            banner_url = self.banner_images.get(banner_key)
            if not banner_url:
                return
            
            async with aiohttp.ClientSession() as session:
                async with session.get(banner_url) as response:
                    if response.status == 200:
                        banner_data = await response.read()
                        
                        for guild in self.bot.guilds:
                            if guild.me.guild_permissions.manage_guild:
                                await guild.edit(banner=banner_data)
                                
        except Exception as e:
            logging.error(f"バナー更新エラー: {e}")
    
    @commands.command(name='set_banner')
    @commands.has_permissions(manage_guild=True)
    async def set_banner_command(self, ctx, banner_type: str, *, url: str):
        """バナー設定コマンド"""
        if banner_type not in self.banner_images:
            await ctx.send("無効なバナータイプです")
            return
        
        # URL検証
        if not url.startswith(('http://', 'https://')):
            await ctx.send("有効なURLを指定してください")
            return
        
        self.banner_images[banner_type] = url
        await ctx.send(f"{banner_type}バナーを設定しました")
    
    @banner_rotation.before_loop
    async def before_banner_rotation(self):
        """バナーローテーション開始前の待機"""
        await self.bot.wait_until_ready()
```

## 設定

### バナー設定

```python
BANNER_CONFIG = {
    'auto_rotation': True,
    'rotation_interval': 3600,  # 1時間
    'max_file_size': 10 * 1024 * 1024,  # 10MB
    'allowed_formats': ['png', 'jpg', 'jpeg', 'gif'],
    'min_resolution': (960, 540),
    'max_resolution': (1920, 1080)
}
```

### イベントバナー

```python
EVENT_BANNERS = {
    'new_year': {
        'start_date': '01-01',
        'end_date': '01-07',
        'banner_url': 'https://example.com/new_year_banner.png'
    },
    'christmas': {
        'start_date': '12-20',
        'end_date': '12-26',
        'banner_url': 'https://example.com/christmas_banner.png'
    }
}
```

## バナー品質チェック

### 画像検証

```python
from PIL import Image
import io

async def validate_banner_image(image_data: bytes) -> bool:
    """バナー画像検証"""
    try:
        image = Image.open(io.BytesIO(image_data))
        
        # サイズチェック
        width, height = image.size
        if width < 960 or height < 540:
            return False
        
        # アスペクト比チェック
        aspect_ratio = width / height
        if not (1.5 <= aspect_ratio <= 2.0):
            return False
        
        # ファイルサイズチェック
        if len(image_data) > 10 * 1024 * 1024:  # 10MB
            return False
        
        return True
        
    except Exception:
        return False
```

## 関連ドキュメント

- [イベントCogs](../02-events-cogs.md)
- [ファイル管理](../../04-utilities/04-file-management.md)
- [API統合](../../04-utilities/02-api-integration.md)
