# cogs/OO.py
import discord
from discord.ext import commands
from discord.errors import ConnectionClosed

import asyncio

from aiohttp.client_exceptions import ClientConnectorDNSError

from utils.logging import setup_logging
from utils import presence

from config.setting import get_settings

settings = get_settings()

bot_token = settings.bot_token
logger = setup_logging("D")

class StatusManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info(f'Logged in as {self.bot.user}')
        asyncio.create_task(presence.update_presence(self.bot))

    async def connect_to_discord(self):
        try:
            await self.bot.start(bot_token)
        except ConnectionClosed as e:
            logger.error("ConnectionClosedエラーが発生しました。ステータスをidleに変更します。")
            await self.bot.change_presence(status=discord.Status.idle, activity=discord.Game("エラー発生中"), state=f"{e}")
        except ClientConnectorDNSError as e:
            logger.error("ClientConnectorDNSErrorが発生しました。ステータスをidleに変更します。")
            await self.bot.change_presence(status=discord.Status.idle, activity=discord.Game("DNSエラー発生中"), state=f"{e}")
        except Exception as e:
            logger.error(f"その他のエラーが発生しました: {e}")
            await self.bot.change_presence(status=discord.Status.idle, activity=discord.Game("不明なエラー発生中"), state=f"{e}")
        finally:
            logger.info("再接続を試みます...")
            asyncio.create_task(presence.update_presence(self.bot))
            await self.bot.start(bot_token)

async def setup(bot):
    await bot.add_cog(StatusManager(bot))