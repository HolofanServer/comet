import discord
from discord.ext import commands
import json
import os

class Setup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config_path = 'data/report/config.json'

    def save_config(self, guild_id, channel_id):
        """通報チャンネルの設定を保存する"""
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                config = json.load(f)
        else:
            config = {}

        config[str(guild_id)] = {"report_channel": channel_id}

        with open(self.config_path, 'w') as f:
            json.dump(config, f, indent=4)

    @commands.hybrid_command(name='setchannel')
    @commands.has_permissions(administrator=True)
    async def set_channel(self, ctx, channel: discord.TextChannel):
        """通報チャンネルを設定する"""
        self.save_config(ctx.guild.id, channel.id)
        await ctx.send(f'{channel.mention}が通報チャンネルとして設定されました。')

async def setup(bot):
    await bot.add_cog(Setup(bot))