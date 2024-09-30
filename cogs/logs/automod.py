import discord
from discord.ext import commands

import json
import os

class AutoModLogCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_config_path(self, guild_id):
        config_dir = f"data/logs/{guild_id}/config"
        os.makedirs(config_dir, exist_ok=True)
        return os.path.join(config_dir, "automod.json")

    def load_config(self, guild_id):
        config_path = self.get_config_path(guild_id)
        if not os.path.exists(config_path):
            return {"log_automod": True, "log_channel": None, "form": None}
        with open(config_path, 'r') as f:
            return json.load(f)

    def save_config(self, guild_id, config):
        with open(self.get_config_path(guild_id), 'w') as f:
            json.dump(config, f, indent=4)

    @commands.Cog.listener()
    async def on_auto_mod_action(self, action: discord.AutoModAction):
        print("Automod action detected")
        guild_id = action.guild_id
        config = self.load_config(guild_id)
        if not config.get("log_automod"):
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
            print("AutoMod Log channel is not set and no form thread is available.")
            return 

        embed = discord.Embed(title="Automodログ", color=discord.Color.red())
        embed.add_field(name="アクション", value=str(action.action), inline=False)
        embed.add_field(name="メッセージID", value=action.message_id or "N/A", inline=False)
        embed.add_field(name="ルールID", value=action.rule_id, inline=False)
        embed.add_field(name="トリガータイプ", value=str(action.rule_trigger_type), inline=False)
        embed.add_field(name="ギルドID", value=action.guild_id, inline=False)
        embed.add_field(name="ユーザーID", value=action.user_id, inline=False)
        embed.add_field(name="チャンネルID", value=action.channel_id, inline=False)
        embed.add_field(name="内容", value=action.content[:1024], inline=False)
        embed.add_field(name="マッチしたキーワード", value=action.matched_keyword or "N/A", inline=False)
        embed.add_field(name="マッチした内容", value=action.matched_content or "N/A", inline=False)

        try:
            await log_channel.send(embed=embed)
        except discord.Forbidden as e:
            print(f"Forbidden to send message to log channel. Error: {e}")
            return
        
async def setup(bot):
    await bot.add_cog(AutoModLogCog(bot))