# ギルドウォッチャー

## C.O.M.E.T.について

**C.O.M.E.T.**の名前は以下の頭文字から構成されています：

- **C**ommunity of
- **O**shilove
- **M**oderation &
- **E**njoyment
- **T**ogether

HFS - ホロライブ非公式ファンサーバーのコミュニティを支える、推し愛とモデレーション、そして楽しさを一緒に提供するボットです。

## 概要

ギルドウォッチャーは、サーバー（ギルド）の状態変化を監視し、重要なイベントを記録・通知するシステムです。

## 機能

### サーバー監視

- メンバー参加・退出の監視
- ロール変更の追跡
- チャンネル作成・削除の監視
- サーバー設定変更の記録

### 通知システム

- 管理者への即座の通知
- ログチャンネルへの詳細記録
- 重要度に応じた通知レベル調整

## 実装例

```python
import discord
from discord.ext import commands
import logging

class GuildWatcher(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.log_channel_id = 123456789012345678
    
    @commands.Cog.listener()
    async def on_member_join(self, member):
        """メンバー参加イベント"""
        embed = discord.Embed(
            title="メンバー参加",
            description=f"{member.mention} がサーバーに参加しました",
            color=0x00ff00
        )
        embed.add_field(name="ユーザー名", value=str(member), inline=True)
        embed.add_field(name="ID", value=member.id, inline=True)
        embed.add_field(name="アカウント作成日", value=member.created_at.strftime("%Y-%m-%d"), inline=True)
        
        await self.send_log(embed)
    
    @commands.Cog.listener()
    async def on_member_remove(self, member):
        """メンバー退出イベント"""
        embed = discord.Embed(
            title="メンバー退出",
            description=f"{str(member)} がサーバーから退出しました",
            color=0xff0000
        )
        embed.add_field(name="ユーザー名", value=str(member), inline=True)
        embed.add_field(name="ID", value=member.id, inline=True)
        
        await self.send_log(embed)
    
    async def send_log(self, embed):
        """ログ送信"""
        channel = self.bot.get_channel(self.log_channel_id)
        if channel:
            await channel.send(embed=embed)
```

## 設定

### 監視対象の設定

```python
WATCH_EVENTS = {
    'member_join': True,
    'member_leave': True,
    'role_update': True,
    'channel_create': True,
    'channel_delete': True,
    'guild_update': True
}
```

### 通知レベル

- **INFO**: 一般的なイベント（メンバー参加など）
- **WARNING**: 注意が必要なイベント（大量退出など）
- **CRITICAL**: 緊急対応が必要なイベント（サーバー設定変更など）

## 関連ドキュメント

- [イベントCogs](../02-events-cogs.md)
- [ログシステム](../../02-core/03-logging-system.md)
