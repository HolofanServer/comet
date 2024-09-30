import discord
from discord.ext import commands

import json
import os

class ChannelLoggingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_config_path(self, guild_id):
        config_dir = f"data/logs/{guild_id}/config"
        os.makedirs(config_dir, exist_ok=True)
        return os.path.join(config_dir, "channellog.json")

    def load_config(self, guild_id):
        config_path = self.get_config_path(guild_id)
        if not os.path.exists(config_path):
            return {"log_channellog": True, "log_channel": None, "form": None}
        with open(config_path, 'r') as f:
            return json.load(f)

    def save_config(self, guild_id, config):
        with open(self.get_config_path(guild_id), 'w') as f:
            json.dump(config, f, indent=4)
    
    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        guild_id = channel.guild.id
        config = self.load_config(guild_id)
        if not config.get("log_channellog"):
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
            print("Channel Log channel is not set and no form thread is available.")
            return 

        embed = discord.Embed(title="チャンネル作成", description=channel.mention, color=discord.Color.green())
        embed.add_field(name="チャンネル名", value=channel.name, inline=False)
        embed.add_field(name="カテゴリ", value=channel.category.name if channel.category else "なし", inline=False)
        embed.add_field(name="チャンネルタイプ", value=channel.type, inline=False)
        embed.set_footer(text=channel.guild.name, icon_url=channel.guild.icon.url)

        try:
            await log_channel.send(embed=embed)
        except discord.Forbidden:
            pass

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        guild_id = channel.guild.id
        config = self.load_config(guild_id)
        if not config.get("log_channellog"):
            return

        log_channel_id = config.get("log_channel")
        if not log_channel_id:
            return

        log_channel = self.bot.get_channel(log_channel_id)
        if not log_channel:
            return

        embed = discord.Embed(title="チャンネル削除", description=channel.name, color=discord.Color.red())
        embed.add_field(name="チャンネル名", value=channel.name, inline=False)
        embed.add_field(name="カテゴリ", value=channel.category.name if channel.category else "なし", inline=False)
        embed.add_field(name="チャンネルタイプ", value=channel.type, inline=False)
        embed.set_footer(text=channel.guild.name, icon_url=channel.guild.icon.url)

        try:
            await log_channel.send(embed=embed)
        except discord.Forbidden:
            pass

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before, after):
        guild_id = before.guild.id
        config = self.load_config(guild_id)
        if not config.get("log_channellog"):
            return

        log_channel_id = config.get("log_channel")
        if not log_channel_id:
            return

        log_channel = self.bot.get_channel(log_channel_id)
        if not log_channel:
            return

        embed = discord.Embed(title="チャンネル更新", description=after.mention, color=discord.Color.blue())
        embed.add_field(name="チャンネル名", value=after.name, inline=False)
        embed.add_field(name="カテゴリ", value=after.category.name if after.category else "なし", inline=False)
        embed.add_field(name="チャンネルタイプ", value=after.type, inline=False)
        embed.set_footer(text=before.guild.name, icon_url=before.guild.icon.url)

        try:
            await log_channel.send(embed=embed)
        except discord.Forbidden:
            pass

    @commands.Cog.listener()
    async def on_guild_thread_create(self, thread):
        guild_id = thread.guild.id
        config = self.load_config(guild_id)
        if not config.get("log_channellog"):
            return

        log_channel_id = config.get("log_channel")
        if not log_channel_id:
            return

        log_channel = self.bot.get_channel(log_channel_id)
        if not log_channel:
            return

        embed = discord.Embed(title="スレッド作成", description=thread.mention, color=discord.Color.green())
        embed.add_field(name="スレッド名", value=thread.name, inline=False)
        embed.add_field(name="カテゴリ", value=thread.category.name if thread.category else "なし", inline=False)
        embed.set_footer(text=thread.guild.name, icon_url=thread.guild.icon.url)

        try:
            await log_channel.send(embed=embed)
        except discord.Forbidden:
            pass

    @commands.Cog.listener()
    async def on_thread_delete(self, thread):
        guild_id = thread.guild.id
        config = self.load_config(guild_id)
        if not config.get("log_channellog"):
            return

        log_channel_id = config.get("log_channel")
        if not log_channel_id:
            return

        log_channel = self.bot.get_channel(log_channel_id)
        if not log_channel:
            return

        embed = discord.Embed(title="スレッド削除", description=thread.name, color=discord.Color.red())
        embed.add_field(name="スレッド名", value=thread.name, inline=False)
        embed.add_field(name="カテゴリ", value=thread.category.name if thread.category else "なし", inline=False)
        embed.set_footer(text=thread.guild.name, icon_url=thread.guild.icon.url)

        try:
            await log_channel.send(embed=embed)
        except discord.Forbidden:
            pass

async def setup(bot):
    await bot.add_cog(ChannelLoggingCog(bot))
