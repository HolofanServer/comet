import discord
from discord.ext import commands, tasks

import os
import json
import datetime
import logging
from datetime import timezone

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class RMForm(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.forum_channel_ids = []
        self.load_settings()
        self.check_posts.start()
        
        if not os.path.exists('data/rm_form/active'):
            os.makedirs('data/rm_form/active')
            logger.debug("ディレクトリ 'data/rm_form/active' を作成しました。")
        if not os.path.exists('data/rm_form/inactive'):
            os.makedirs('data/rm_form/inactive')
            logger.debug("ディレクトリ 'data/rm_form/inactive' を作成しました。")

    @commands.hybrid_group(name='rm_form', description='RMFormの設定を行うコマンド')
    async def rm_form(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send('サブコマンドを指定してください。')

    @rm_form.command(name='add')
    async def add_forum_channel(self, ctx, channel: discord.ForumChannel):
        """一定期間後にメッセージを送るフォーラムを設定するコマンド"""
        if channel.id not in self.forum_channel_ids:
            self.forum_channel_ids.append(channel.id)
            self.save_settings()
            await ctx.send(f"フォーラムチャンネルが追加されました: {channel.name}")
            logger.info(f"フォーラムチャンネルを追加しました: {channel.name}")
        else:
            await ctx.send(f"このチャンネルは既に追加されています: {channel.name}")

    @rm_form.command(name='remove')
    async def remove_forum_channel(self, ctx, channel: discord.ForumChannel):
        """一定期間後にメッセージを送るフォーラムを削除するコマンド"""
        if channel.id in self.forum_channel_ids:
            self.forum_channel_ids.remove(channel.id)
            self.save_settings()
            await ctx.send(f"フォーラムチャンネルが削除されました: {channel.name}")
            logger.info(f"フォーラムチャンネルを削除しました: {channel.name}")
        else:
            await ctx.send(f"このチャンネルはリストに存在しません: {channel.name}")

    @commands.Cog.listener()
    async def on_thread_create(self, thread):
        if thread.parent_id in self.forum_channel_ids:
            post_data = {
                "created_at": thread.created_at.isoformat(),
                "author_id": thread.owner_id
            }
            with open(f"data/rm_form/active/{thread.id}.json", 'w') as f:
                json.dump(post_data, f)
            logger.debug(f"スレッドデータを保存しました: {thread.id}")

    @commands.Cog.listener()
    async def on_thread_update(self, before, after):
        if before.archived and not after.archived:
            self.move_to_inactive(before.id)
            logger.debug(f"スレッドを非アクティブに移動しました: {before.id}")

    @tasks.loop(minutes=5)
    async def check_posts(self):
        now = datetime.datetime.utcnow().replace(tzinfo=timezone.utc)
        for filename in os.listdir('data/rm_form/active'):
            if filename.endswith('.json'):
                with open(f'data/rm_form/active/{filename}', 'r') as f:
                    post_data = json.load(f)
                
                created_at = datetime.datetime.fromisoformat(post_data['created_at']).replace(tzinfo=timezone.utc)
                if (now - created_at).days >= 7:
                    thread_id = int(filename.split('.')[0])
                    try:
                        thread = await self.bot.fetch_channel(thread_id)
                        author = await self.bot.fetch_user(post_data['author_id'])
                        e = discord.Embed(title="リマインダー", description="このメッセージは自動メッセージです。\n\nこのスレッドが作成されてから一週間経過しました。まだこのスレッドを使用していますか？", color=0x00ff00)
                        e.set_author(name=f"{author.name}さん", icon_url=author.avatar.url)
                        e.add_field(name="スレッド名", value=thread.name, inline=False)
                        e.add_field(name="スレッド作成日時", value=created_at.strftime("%Y-%m-%d %H:%M:%S"), inline=False)
                        await thread.send(embed=e)
                        self.move_to_inactive(thread_id)
                        logger.info(f"スレッドを非アクティブに移動しました: {thread_id}")
                    except discord.errors.NotFound:
                        logger.warning(f"スレッドが見つかりませんでした: {thread_id}")
                        self.move_to_inactive(thread_id)
    
    def move_to_inactive(self, thread_id):
        active_path = f"data/rm_form/active/{thread_id}.json"
        inactive_path = f"data/rm_form/inactive/{thread_id}.json"
        if os.path.exists(active_path):
            os.rename(active_path, inactive_path)
            logger.debug(f"スレッドデータを非アクティブに移動しました: {thread_id}")
    
    def save_settings(self):
        settings = {
            "forum_channel_ids": self.forum_channel_ids
        }
        with open('data/rm_form/settings.json', 'w') as f:
            json.dump(settings, f)
        logger.debug("設定を保存しました。")

    def load_settings(self):
        if os.path.exists('data/rm_form/settings.json'):
            with open('data/rm_form/settings.json', 'r') as f:
                settings = json.load(f)
                self.forum_channel_ids = settings.get("forum_channel_ids", [])
            logger.debug("設定を読み込みました。")

async def setup(bot):
    await bot.add_cog(RMForm(bot))