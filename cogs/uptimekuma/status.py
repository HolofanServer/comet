import discord
from discord.ext import commands, tasks

import httpx
import os
from dotenv import load_dotenv

from utils.logging import setup_logging
from utils.commands_help import is_guild

logger = setup_logging()

load_dotenv()

puth_url = os.getenv("PUTH_URL")
status_url = os.getenv("STATUS_URL")

class UptimeKumaStatus(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    @commands.hybrid_group(name="status", description="ステータス感れのコマンドです。")
    async def status(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @status.command(name="link", description="ステータスページのURLを送信します。")
    @is_guild()
    async def link(self, ctx: commands.Context):
        await ctx.defer()
        await ctx.send(f"ステータスは[こちら]({status_url})を確認してください")
        

    @tasks.loop(seconds=60)
    async def push_status(self):
        url = f"{puth_url}"
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url)
                if response.status_code == 200:
                    logger.info("Status pushed successfully.")
                else:
                    logger.error(f"Failed to push status: {response.status_code}")
            except Exception as e:
                logger.error(f"Error pushing status: {e}")

async def setup(bot):
    await bot.add_cog(UptimeKumaStatus(bot))
