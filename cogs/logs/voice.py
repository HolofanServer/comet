import discord
from discord.ext import commands
import json
import os
from datetime import datetime, timedelta, timezone

class VoiceLoggingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_config_path(self, guild_id):
        config_dir = f"data/logs/{guild_id}/config"
        os.makedirs(config_dir, exist_ok=True)
        return os.path.join(config_dir, "voice.json")

    def load_config(self, guild_id):
        config_path = self.get_config_path(guild_id)
        if not os.path.exists(config_path):
            return {"log_voice": True, "log_channel": None, "form": None}
        with open(config_path, 'r') as f:
            return json.load(f)

    def save_config(self, guild_id, config):
        with open(self.get_config_path(guild_id), 'w') as f:
            json.dump(config, f, indent=4)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        guild_id = member.guild.id
        config = self.load_config(guild_id)
        if not config.get("log_voice"):
            return
        
        log_channel_id = config.get("log_channel")
        log_channel = self.bot.get_channel(log_channel_id) if log_channel_id else None
        
        logs_form_id = config.get("form")
        logs_form = None
        if logs_form_id:
            for channel in self.bot.get_guild(member.guild.id).channels:
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
            print("Voice Log channel is not set and no form thread is available.")
            return 
        
        JST = timezone(timedelta(hours=+9), 'JST')
        now = datetime.now(JST)
        embed = None

        if before.channel is None and after.channel is not None:
            embed = discord.Embed(description=f"{member.mention}が`{after.channel.name}`に参加しました", color=discord.Color.green(), timestamp=now)
            embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1104493356781940766/1158216598142845018/IMG_1002_adobe_express.png")
        elif before.channel is not None and after.channel is None:
            embed = discord.Embed(description=f"{member.mention}が`{before.channel.name}`から退出しました", color=discord.Color.red(), timestamp=now)
            embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1104493356781940766/1158216598553894982/IMG_1003_adobe_express.png")
        elif before.channel is not None and after.channel is not None and before.channel != after.channel:
            embed = discord.Embed(description=f"{member.mention}が`{before.channel.name}`から`{after.channel.name}`に移動しました", color=discord.Color.blue(), timestamp=now)
            embed.set_thumbnail(url="https://raw.githubusercontent.com/twitter/twemoji/master/assets/72x72/2195.png")

        if embed:
            embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
            embed.set_footer(text=member.guild.name, icon_url=member.guild.icon.url)

            try:
                await log_channel.send(embed=embed)
            except discord.Forbidden:
                return

async def setup(bot):
    await bot.add_cog(VoiceLoggingCog(bot))