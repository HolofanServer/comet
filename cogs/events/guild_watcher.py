import asyncio

from discord.ext import commands

from config.setting import get_settings
from utils.commands_help import is_owner, log_commands
from utils.logging import setup_logging

settings = get_settings()
logger = setup_logging(__name__)

class GuildWatcher(commands.Cog):
    """許可されたサーバー以外からBotを自動退出させる機能"""

    def __init__(self, bot):
        self.bot = bot
        self.main_guild_id = int(settings.admin_main_guild_id)
        self.dev_guild_id = int(settings.admin_dev_guild_id)
        self.allowed_guild_ids = [self.main_guild_id, self.dev_guild_id]
        logger.info(f"許可サーバーID: メイン={self.main_guild_id}, 開発={self.dev_guild_id}")

    @commands.command(name="list_guilds")
    @is_owner()
    @log_commands()
    async def list_guilds(self, ctx):
        """参加しているサーバーを表示するコマンド"""
        guilds = self.bot.guilds
        guild_list = "\n".join([f"{guild.name} (ID: {guild.id})" for guild in guilds])
        await ctx.send(f"参加しているサーバー:\n{guild_list}")

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        """新しいサーバーに参加した際に呼ばれるイベント"""
        logger.info(f"サーバー参加: {guild.name} (ID: {guild.id})")

        if guild.id not in self.allowed_guild_ids:
            logger.warning(f"許可されていないサーバー {guild.name} (ID: {guild.id}) から自動退出します")

            # 少し待ってから退出（通知が確実に送信されるため）
            await asyncio.sleep(2)
            await guild.leave()
            logger.info(f"サーバー {guild.name} から退出しました")

    @commands.Cog.listener()
    async def on_ready(self):
        """Bot起動時に参加しているサーバーをチェック"""
        logger.info("サーバー所属チェックを開始")
        for guild in self.bot.guilds:
            if guild.id not in self.allowed_guild_ids:
                logger.warning(f"許可されていないサーバー {guild.name} (ID: {guild.id}) から自動退出します")

                # 少し待ってから退出（通知が確実に送信されるため）
                await asyncio.sleep(2)
                await guild.leave()
                logger.info(f"サーバー {guild.name} から退出しました")

        allowed_guilds = [guild for guild in self.bot.guilds if guild.id in self.allowed_guild_ids]
        logger.info(f"接続中の許可サーバー: {', '.join([f'{g.name} (ID: {g.id})' for g in allowed_guilds])}")

async def setup(bot):
    await bot.add_cog(GuildWatcher(bot))
