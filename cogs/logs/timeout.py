import discord
from discord.ext import commands
import os
import json
import datetime

class TimeoutLoggingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_config_path(self, guild_id):
        config_dir = f"data/logs/{guild_id}/config"
        os.makedirs(config_dir, exist_ok=True)
        return os.path.join(config_dir, "timeout.json")

    def load_config(self, guild_id):
        config_path = self.get_config_path(guild_id)
        if not os.path.exists(config_path):
            return {"log_timeout": True, "log_channel": None, "form": None}
        with open(config_path, 'r') as f:
            return json.load(f)

    def save_config(self, guild_id, config):
        with open(self.get_config_path(guild_id), 'w') as f:
            json.dump(config, f, indent=4)
    
    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.timed_out_until != after.timed_out_until:
            guild_id = before.guild.id
            config = self.load_config(guild_id)
            if not config.get("log_timeout"):
                return

            log_channel_id = config.get("log_channel")
            log_channel = self.bot.get_channel(log_channel_id) if log_channel_id else None
            
            logs_form_id = config.get("form")
            logs_form = None
            if logs_form_id:
                for channel in self.bot.get_guild(after.guild.id).channels:
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
                print("Log channel is not set and no form thread is available.")
                return 

            if after.timed_out_until is not None:
                timeout_time = after.timed_out_until.timestamp()
                timeout_time_stamp = "<t:{}> | <t:{}:R>".format(int(timeout_time), int(timeout_time))

                embed = discord.Embed(title=f"{after.display_name} がタイムアウトされました", color=discord.Color.red())
                embed.set_thumbnail(url=after.avatar.url)
                embed.set_author(name=after.display_name, icon_url=after.avatar.url)
                embed.add_field(name="タイムアウト期限", value=timeout_time_stamp, inline=False)
                embed.add_field(name="理由", value=after.timed_out_reason, inline=False)
                embed.add_field(name="タイムアウトを実行したユーザー", value=after.timed_out_by.mention, inline=False)
                embed.set_footer(text=before.guild.name, icon_url=before.guild.icon.url)
                
                await log_channel.send(embed=embed)

            if after.timed_out_until is None:
                embed = discord.Embed(title=f"{after.display_name} のタイムアウトが解除されました", color=discord.Color.green())
                embed.set_thumbnail(url=after.avatar.url)
                embed.set_author(name=after.display_name, icon_url=after.avatar.url)
                if before.timed_out_by is not None:
                    embed.add_field(name="タイムアウトを解除したユーザー", value=before.timed_out_by.mention, inline=False)
                embed.set_footer(text=before.guild.name, icon_url=before.guild.icon.url)

                await log_channel.send(embed=embed)

async def setup(bot):
    await bot.add_cog(TimeoutLoggingCog(bot))
