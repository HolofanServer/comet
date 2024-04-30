import discord
from discord.ext import commands
import json
import os
from datetime import datetime, timezone, timedelta

class BanLoggingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_config_path(self, guild_id):
        config_dir = f"data/logs/{guild_id}/config"
        os.makedirs(config_dir, exist_ok=True)
        return os.path.join(config_dir, "ban.json")

    def load_config(self, guild_id):
        config_path = self.get_config_path(guild_id)
        if not os.path.exists(config_path):
            return {"log_ban": True, "log_channel": None, "form": None}
        with open(config_path, 'r') as f:
            return json.load(f)

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        config = self.load_config(guild.id)
        if not config.get("log_ban"):
            return
        
        JST = timezone(timedelta(hours=+9))
        now = datetime.now(JST)
        
        log_channel_id = config.get("log_channel")
        log_channel = self.bot.get_channel(log_channel_id) if log_channel_id else None
        
        logs_form_id = config.get("form")
        logs_form = None
        if logs_form_id:
            for channel in self.bot.get_guild(guild.id).channels:
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

        # 監査ログからBANイベントの実行者を取得
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.ban):
            if entry.target.id == user.id:
                executor = entry.user
                reason = entry.reason or "理由なし"
                break
        else:
            executor = "不明"
            reason = "不明"

        embed = discord.Embed(title="ユーザーBAN", description=f"{user}がBANされました。", color=discord.Color.red(), timestamp=now)
        embed.add_field(name="実行者", value=executor.mention, inline=True)
        embed.add_field(name="理由", value=reason, inline=False)
        embed.set_thumbnail(url=user.avatar.url)
        embed.set_footer(text=executor.name, icon_url=executor.avatar.url)

        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        config = self.load_config(guild.id)
        if not config.get("log_ban"):
            return
        JST = timezone(timedelta(hours=+9))
        now = datetime.now(JST)
        
        log_channel_id = config.get("log_channel")
        log_channel = self.bot.get_channel(log_channel_id)
        if log_channel is None:
            return

        embed = discord.Embed(title="ユーザーBAN解除", description=f"{user}のBANが解除されました。", color=discord.Color.green(), timestamp=now)
        embed.set_thumbnail(url=user.avatar.url)

        await log_channel.send(embed=embed)

async def setup(bot):
    await bot.add_cog(BanLoggingCog(bot))