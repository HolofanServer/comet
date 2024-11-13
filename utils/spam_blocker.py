import discord
from discord.ext import commands

import json
import os

from collections import Counter, defaultdict
from typing import Union

from utils.logging import setup_logging
from config.setting import get_settings

log = setup_logging()
settings = get_settings()

class SpamBlocker:
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config_file = 'config/spam_blocker.json'
        self.config = self.load_config()

        self.spam_control = commands.CooldownMapping.from_cooldown(
            self.config['spam_limit'], 
            self.config['cooldown_period'], 
            commands.BucketType.user
        )
        self._auto_spam_count = Counter()
        self.blacklist = defaultdict(bool)
        self.blacklist_file = self.config['blacklist_path']
        self.load_blacklist()
        self.webhook = None

    def load_config(self):
        """スパムブロッカーの設定をファイルから読み込み"""
        if not os.path.exists(self.config_file):
            log.warning(f"Config file {self.config_file} does not exist. Creating default config.")
            default_config = {
                "spam_limit": 5,
                "cooldown_period": 12.0,
                "auto_blacklist_limit": 5,
                "blacklist_path": "data/mod/blacklist.json"
            }
            self.save_config(default_config)
            return default_config

        with open(self.config_file, 'r') as f:
            return json.load(f)

    def save_config(self, config):
        """スパムブロッカーの設定をファイルに保存"""
        if not os.path.exists(os.path.dirname(self.config_file)):
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        with open(self.config_file, 'w') as f:
            json.dump(config, f, indent=4)
        log.info("Config saved.")

    def save_blacklist(self):
        """ブラックリストをファイルに保存"""
        if not os.path.exists(os.path.dirname(self.blacklist_file)):
            os.makedirs(os.path.dirname(self.blacklist_file), exist_ok=True)
        with open(self.blacklist_file, 'w') as f:
            json.dump(self.blacklist, f)
        log.info("Blacklist saved.")

    def load_blacklist(self):
        """ファイルからブラックリストを読み込み"""
        if os.path.exists(self.blacklist_file):
            with open(self.blacklist_file, 'r') as f:
                self.blacklist.update(json.load(f))
        else:
            log.info("Blacklist file does not exist. Creating a new one.")
            self.save_blacklist()

    async def check_blacklist(self, ctx: commands.Context) -> bool:
        """ブラックリストに登録されているユーザーやサーバかどうかを確認"""
        if ctx.author.id in self.blacklist:
            return True
        if ctx.guild is not None and ctx.guild.id in self.blacklist:
            return True
        return False
    
    def is_not_blacklisted(self):
        async def predicate(ctx):
            if await self.check_blacklist(ctx):
                raise commands.CheckFailure("あなたはブラックリストに追加されています。")
            return True
        return commands.check(predicate)

    async def add_to_blacklist(self, object_id: int):
        """ブラックリストに追加"""
        self.blacklist[object_id] = True
        self.save_blacklist()
        log.info(f"Added {object_id} to blacklist.")

    async def remove_from_blacklist(self, object_id: int):
        """ブラックリストから削除"""
        if object_id in self.blacklist:
            self.load_blacklist()
            if object_id in self.blacklist:
                del self.blacklist[object_id]
                self.save_blacklist()
                log.info(f"Removed {object_id} from blacklist.")

    async def list_blacklist(self):
        """ブラックリストを表示"""
        return self.blacklist

    async def process_spam(self, ctx: commands.Context, obj):
        """スパム行のチェックと処理
        
        discord.Message と discord.Interaction に対応
        """
        if isinstance(obj, discord.Message):
            user_id = obj.author.id
            created_at = obj.created_at.timestamp()
        elif isinstance(obj, discord.Interaction):
            user_id = obj.user.id
            created_at = discord.utils.utcnow().timestamp()
        else:
            return False

        if isinstance(obj, discord.Message):
            bucket = self.spam_control.get_bucket(obj)
        else:
            bucket = None
        
        if bucket is not None:
            retry_after = bucket.update_rate_limit(created_at)
        else:
            retry_after = None

        if retry_after and user_id != self.bot.owner_id:
            self._auto_spam_count[user_id] += 1
            if self._auto_spam_count[user_id] >= self.config['auto_blacklist_limit']:
                await self.add_to_blacklist(user_id)
                del self._auto_spam_count[user_id]
                await self.log_spammer(ctx, obj, retry_after, autoblock=True)
                await self.send_webhook_notification(ctx, obj, retry_after)
            else:
                await self.log_spammer(ctx, obj, retry_after)
            return True
        else:
            self._auto_spam_count.pop(user_id, None)
        return False


    async def log_spammer(self, ctx: commands.Context, obj: Union[discord.Message, discord.Interaction], retry_after: float, autoblock: bool = False):
        """スパム行為のログ記録"""
        if isinstance(obj, discord.Message):
            user = obj.author
            guild_name = obj.guild.name if obj.guild else "DM"
        elif isinstance(obj, discord.Interaction):
            user = obj.user
            guild_name = obj.guild.name if obj.guild else "DM"

        log.warning(f"User {user} (ID {user.id}) spamming in guild {guild_name}. Retry after: {retry_after:.2f}s.")
        
        if autoblock:
            log.info(f"Auto-blocked {user.id}.")

    async def send_webhook_notification(self, ctx: commands.Context, obj: Union[discord.Message, discord.Interaction], retry_after: float):
        """スパムが発生した場合にWebHook通知を送信"""
        spam_notice_channel_id = settings.spam_notice_channel_id
        if spam_notice_channel_id is None:
            log.error("SPAM_NOTICE_CHANNEL_ID is not set in environment variables.")
            return

        channel = self.bot.get_channel(spam_notice_channel_id)
        if channel is None:
            log.error(f"Channel with ID {spam_notice_channel_id} not found.")
            return

        if self.webhook is None:
            self.webhook = await channel.create_webhook(name="Spam Alert Webhook")

        if isinstance(obj, discord.Message):
            user = obj.author
            guild_name = obj.guild.name if obj.guild else "DM"
        elif isinstance(obj, discord.Interaction):
            user = obj.user
            guild_name = obj.guild.name if obj.guild else "DM"

        embed = discord.Embed(
            title="スパム行為検出",
            description=f"{user.mention} がスパム行為を行いました。",
            color=discord.Color.red()
        )
        embed.add_field(name="ユーザーID", value=f"{user.id}")
        embed.add_field(name="リトライ後の制限", value=f"{retry_after:.2f} 秒後")
        embed.add_field(name="サーバー", value=guild_name)
        embed.set_thumbnail(url=user.display_avatar.url)
        await self.webhook.send(embed=embed)
