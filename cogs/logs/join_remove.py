import discord
from discord.ext import commands
import json
import os
from datetime import datetime, timedelta, timezone

class JoinLeaveLoggingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_config_path(self, guild_id):
        config_dir = f"data/logs/{guild_id}/config"
        os.makedirs(config_dir, exist_ok=True)
        return os.path.join(config_dir, "join_remove.json")

    def load_config(self, guild_id):
        config_path = self.get_config_path(guild_id)
        if not os.path.exists(config_path):
            return {"log_join_remove": True, "log_channel": None, "form": None}
        with open(config_path, 'r') as f:
            return json.load(f)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        config = self.load_config(member.guild.id)
        if not config.get("log_join_remove"):
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
            print("Join/Remove Log channel is not set and no form thread is available.")
            return 

        JST = timezone(timedelta(hours=+9))
        now = datetime.now(JST)
        created_at = member.created_at.replace(tzinfo=timezone.utc).astimezone(JST)
        account_age_seconds = int(created_at.timestamp())

        embed = discord.Embed(description=f"<@!{member.id}>が参加しました。", color=discord.Color.green(), timestamp=now)
        embed.set_author(name=member.display_name, icon_url=member.avatar.url)
        embed.add_field(name="アカウント年齢", value=f"<t:{account_age_seconds}:d>\n<t:{account_age_seconds}:R>", inline=True)
        embed.set_footer(text=member.guild.name)

        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        config = self.load_config(member.guild.id)
        if not config.get("log_join_remove"):
            return
        
        log_channel_id = config.get("log_channel")
        if log_channel_id is None:
            return
        log_channel = self.bot.get_channel(log_channel_id)
        if log_channel is None:
            return

        JST = timezone(timedelta(hours=+9))
        now = datetime.now(JST)

        embed = discord.Embed(description=f"<@!{member.id}>が脱退しました", color=discord.Color.red(), timestamp=now)
        embed.set_author(name=member.display_name, icon_url=member.avatar.url)
        embed.set_footer(text=member.guild.name)

        await log_channel.send(embed=embed)

async def setup(bot):
    await bot.add_cog(JoinLeaveLoggingCog(bot))