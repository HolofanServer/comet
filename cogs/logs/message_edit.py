import discord
from discord.ext import commands
import json
import os
from datetime import datetime, timezone, timedelta

def shorten_text(text, max_length=1024):
    return (text[:max_length-3] + '...') if len(text) > max_length else text

class MessageEditLoggingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_config_path(self, guild_id):
        config_dir = f"data/logs/{guild_id}/config"
        os.makedirs(config_dir, exist_ok=True)
        return os.path.join(config_dir, "message_edit.json")

    def load_config(self, guild_id):
        config_path = self.get_config_path(guild_id)
        if not os.path.exists(config_path):
            return {"log_message_edit": True, "log_channel": None, "form": None}
        with open(config_path, 'r') as f:
            return json.load(f)

    def save_config(self, guild_id, config):
        with open(self.get_config_path(guild_id), 'w') as f:
            json.dump(config, f, indent=4)

    @commands.Cog.listener()
    async def on_message_edit(self, message_before, message_after):
        if message_before.author.bot or message_before.content == message_after.content:
            return

        guild_id = message_before.guild.id
        config = self.load_config(guild_id)
        if not config.get("log_message_edit"):
            return

        log_channel_id = config.get("log_channel")
        log_channel = self.bot.get_channel(log_channel_id) if log_channel_id else None
        
        logs_form_id = config.get("form")
        logs_form = None
        if logs_form_id:
            for channel in self.bot.get_guild(guild_id).channels:
                if hasattr(channel, 'threads'):
                    for thread in channel.threads:
                        if thread.id == logs_form_id:
                            logs_form = thread
                            break
                if logs_form:
                    break
        
        if logs_form:
            log_channel = logs_form
            print("Logging to thread.")
        elif not log_channel:
            print("MessageEdit Log channel is not set and no form thread is available.")
            return 

        JST = timezone(timedelta(hours=+9), 'JST')
        now = datetime.now(JST)

        embed = discord.Embed(title="メッセージ編集", description=message_after.jump_url, color=discord.Color.orange(), timestamp=now)
        embed.add_field(name="編集前", value=shorten_text(message_before.content), inline=False)
        embed.add_field(name="編集後", value=shorten_text(message_after.content), inline=False)
        embed.add_field(name="チャンネル", value=message_before.channel.mention, inline=False)
        embed.set_author(name=message_before.author.display_name, icon_url=message_before.author.avatar.url)
        embed.set_footer(text=f"メッセージID: {message_before.id} | 編集時刻: {now.strftime('%Y-%m-%d %H:%M:%S')} JST")

        try:
            await log_channel.send(embed=embed)
        except discord.Forbidden:
            return

async def setup(bot):
    await bot.add_cog(MessageEditLoggingCog(bot))