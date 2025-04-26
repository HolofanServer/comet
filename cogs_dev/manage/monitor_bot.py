import discord
from discord.ext import commands

import asyncio
import httpx

from utils.logging import setup_logging
from config.setting import get_settings

# ログ設定
logger = setup_logging("D")
settings = get_settings()

api_secret = settings.monitor_bot_api_secret
api_url = settings.monitor_bot_api_url

class MonitorBot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    #     self.api_url = api_url  # 監視Botのエンドポイント
    #     self.api_secret = api_secret  # シークレットキー（監視Bot側と一致）
    #     self.ping_interval = 10  # Pingを送信する間隔（秒）

    # @commands.Cog.listener()
    # async def on_ready(self):
    #     """Botが起動した際にPing送信タスクを開始"""
    #     logger.info(f"monitor: Bot {self.bot.user.id} - {self.bot.user.name} としてログインしました")
    #     self.bot.loop.create_task(self.send_ping())

    # async def send_ping(self):
    #     """監視Botに定期的にPingを送信"""
    #     async with httpx.AsyncClient() as client:
    #         while True:
    #             try:
    #                 headers = {"Authorization": self.api_secret}
    #                 response = await client.post(self.api_url, headers=headers)
    #                 if response.status_code == 200:
    #                     logger.info("monitor: Ping送信成功")
    #                 else:
    #                     logger.warning(f"monitor: Ping送信失敗: {response.status_code} - {response.text}")
    #             except httpx.RequestError as e:
    #                 logger.error(f"monitor: Ping送信中にエラー発生: {e}")
    #             await asyncio.sleep(self.ping_interval)


async def setup(bot):
    await bot.add_cog(MonitorBot(bot))