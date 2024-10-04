import discord
from discord.ext import commands

import os
import httpx
import json
import logging
from dotenv import load_dotenv
from datetime import datetime, timezone
load_dotenv()

logger = logging.getLogger(__name__)

class MessageForwardCheck(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot_token = os.getenv("BOT_TOKEN")
        self.config_path = 'data/manege/forward_check.json'

    async def get_message(self, channel_id, message_id):
        url = f"https://discord.com/api/v10/channels/{channel_id}/messages/{message_id}"
        headers = {
            "Authorization": f"Bot {self.bot_token}"
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)

        if response.status_code == 200:
            return response.json()
        else:
            return None
        
    def save_config(self, guild_id, channel_id):
        """ログチャンネルの設定を保存する"""

        dir_path = os.path.dirname(self.config_path)
        
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)

        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                config = json.load(f)
        else:
            config = {}

        config[str(guild_id)] = {"forward_log_channel": channel_id}

        with open(self.config_path, 'w') as f:
            json.dump(config, f, indent=4)

    def load_config(self, guild_id):
        """ログチャンネルの設定を読み込む"""
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                config = json.load(f)
        else:
            config = {}

        return config.get(str(guild_id), {}).get("forward_log_channel", None)
        

    @commands.hybrid_group(name="forward")
    async def forward(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @forward.command(name="set_channel")
    async def set_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        self.save_config(ctx.guild.id, ctx.channel.id)
        await ctx.send(f"{ctx.channel.mention}がログチャンネルとして設定されました。")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.id:
            original_message_data = await self.get_message(message.channel.id, message.id)

            if original_message_data and 'message_reference' in original_message_data:
                ref_message = original_message_data['message_reference']
                reference_message_id = ref_message.get('message_id')
                reference_channel_id = ref_message.get('channel_id')
                reference_guild_id = ref_message.get('guild_id')

                if reference_guild_id == str(message.guild.id):
                    return
                else:
                    await message.delete()
                    e = discord.Embed(
                        title="⚠️警告⚠️",
                        description="他サーバーから転送されたメッセージを削除しました。",
                        color=discord.Color.red(),
                        timestamp=datetime.now(timezone.utc)
                    )
                    e.add_field(name="メッセージ情報", value=f"メッセージ: {message.content}\nメッセージID: {message.id}\nチャンネル: <#{message.channel.id}>\nチャンネルID: {message.channel.id}\nギルド: {message.guild.name}\nギルドID: {message.guild.id}")
                    e.add_field(name="ユーザー", value=f"<@{message.author.id}>\n{message.author.id}")
                    log_channel_id = self.load_config(message.guild.id)
                    log_channel = self.bot.get_channel(log_channel_id)
                    if log_channel:
                        await log_channel.send(embed=e)
                    else:
                        logger.error(f"ログチャンネルが見つかりません: {log_channel_id}")
                    return
            else:
                return

async def setup(bot):
    await bot.add_cog(MessageForwardCheck(bot))
