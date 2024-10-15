import discord
from discord.ext import commands

import os
import re
import pathlib
import logging
import asyncio
import traceback
import json
import pytz

from datetime import datetime
from dotenv import load_dotenv

from utils import presence
from utils.logging import save_log
from utils.startup import startup_send_webhook, startup_send_botinfo, startup_message, yokobou
from utils.startup_status import update_status
from utils.logging import setup_logging
from utils.error import handle_command_error, handle_application_command_error

logger = setup_logging()

load_dotenv()

with open('config/bot.json', 'r') as f:
    bot_config = json.load(f)

session_id = None

class SessionIDHandler(logging.Handler):
    def emit(self, record):
        global session_id
        message = record.getMessage()
        match = re.search(r'Session ID: ([a-f0-9]+)', message)
        if match:
            session_id = match.group(1)
            print(f"セッションIDを検出しました: {session_id}")

logger_session = logging.getLogger('discord.gateway')
logger_session.setLevel(logging.INFO)
logger_session.addHandler(SessionIDHandler())

TOKEN = os.getenv('BOT_TOKEN')
command_prefix = [bot_config['prefix']]
main_guild_id = int(os.getenv('MAIN_GUILD_ID'))
dev_guild_id = int(os.getenv('DEV_GUILD_ID'))
startup_channel_id = int(os.getenv('STARTUP_CHANNEL_ID'))
main_dev_channel_id = int(os.getenv('BUG_REPORT_CHANNLE_ID'))

class MyBot(commands.AutoShardedBot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initialized = False
        self.cog_classes = {}
        self.ERROR_LOG_CHANNEL_ID = int(os.getenv('ERROR_LOG_CHANNEL_ID'))
        self.gagame_sessions = {} 

    async def setup_hook(self):
        self.loop.create_task(self.after_ready())

    async def after_ready(self):
        await self.wait_until_ready()
        logger.info("setup_hook is called")
        logger.info(startup_message())
        await update_status(self, "Bot Startup...")
        logger.info("status: Bot Startup...")
        logger.error(yokobou())
        await self.load_cogs('cogs')
        await self.load_extension('jishaku')
        await self.tree.sync()
        await update_status(self, "現在の処理: tree sync")
        logger.error(yokobou())
        logger.info("status: 現在の処理: tree sync")
        if not self.initialized:
            logger.info("Initializing...")
            self.initialized = True
            logger.info('------')
            logger.info('All cogs have been loaded and bot is ready.')
            logger.info('------')
            asyncio.create_task(presence.update_presence(self))

    async def on_ready(self):
        logger.error(yokobou())
        logger.info("on_ready is called")
        log_data = {
            "event": "BotReady",
            "description": f"{self.user} has successfully connected to Discord.",
            "timestamp": datetime.now(pytz.timezone('Asia/Tokyo')).strftime('%Y-%m-%d %H:%M:%S'),
            "session_id": session_id
        }
        save_log(log_data)
        if not self.initialized:
            try:
                await startup_send_webhook(self, guild_id=dev_guild_id)
                await startup_send_botinfo(self)
            except Exception as e:
                logger.error(f"Error during startup: {e}")
            self.initialized = True

    async def load_cogs(self, folder_name: str):
        cur = pathlib.Path('.')
        for p in cur.glob(f"{folder_name}/**/*.py"):
            if 'Dev' in p.parts:
                logger.info(f"skip: {p}")
                continue

            if p.stem in ["__init__"]:
                logger.info(f"skip: {p.stem}")
                continue
            try:
                cog_path = p.relative_to(cur).with_suffix('').as_posix().replace('/', '.')
                await self.load_extension(cog_path)
                logger.info(f'Cog loaded successfully: {cog_path}')
            except commands.ExtensionFailed as e:
                traceback.print_exc()
                logger.error(f'Failed to load extension {p.stem}: {e}\nFull error: {e.__cause__}')


    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if hasattr(ctx, 'handled') and ctx.handled:
            return

        handled = await handle_command_error(ctx, error, self.ERROR_LOG_CHANNEL_ID)
        if handled:
            ctx.handled = True

    @commands.Cog.listener()
    async def on_application_command_error(self, interaction: discord.Interaction, error):
        if hasattr(interaction, 'handled') and interaction.handled:
            return

        await handle_application_command_error(interaction, error)

intent: discord.Intents = discord.Intents.all()
bot = MyBot(command_prefix=command_prefix, intents=intent, help_command=None)

bot.run(TOKEN)
