import discord
from discord.ext import commands
# from discord.ext.prometheus import PrometheusCog

import re
import pathlib
import logging
import asyncio
import traceback
import json
# import sentry_sdk
import pytz
from datetime import datetime
from dotenv import load_dotenv


from utils import presence
from utils.logging import save_log
from utils.startup import startup_send_webhook, startup_send_botinfo, startup_message, yokobou, git_pull, pip_install
from utils.startup_status import update_status
from utils.logging import setup_logging
from utils.error import handle_command_error, handle_application_command_error
from utils.auth import verify_auth, load_auth
# from utils.prometheus_config import add_bot_endpoint, reload_prometheus
from config.setting import get_settings

logger: logging.Logger = setup_logging("D")
load_dotenv()

with open('config/bot.json', 'r') as f:
    bot_config: dict[str, str] = json.load(f)

session_id: str = None

class SessionIDHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        global session_id
        message: str = record.getMessage()
        match = re.search(r'Session ID: ([a-f0-9]+)', message)
        if match:
            session_id = match.group(1)
            print(f"セッションIDを検出しました: {session_id}")

logger_session: logging.Logger = logging.getLogger('discord.gateway')
logger_session.setLevel(logging.INFO)
logger_session.addHandler(SessionIDHandler())

settings = get_settings()

TOKEN: str = settings.bot_token
command_prefix: list[str] = bot_config["prefix"]
main_guild_id: int = settings.admin_main_guild_id
dev_guild_id: int = settings.admin_dev_guild_id
startup_channel_id: int = settings.admin_startup_channel_id
bug_report_channel_id: int = settings.admin_bug_report_channel_id
error_log_channel_id: int = settings.admin_error_log_channel_id

# sentry_dsn: str = settings.sentry_dsn

# sentry_sdk.init(
#    dsn=sentry_dsn,
#    traces_sample_rate=1.0,
# )

class MyBot(commands.AutoShardedBot):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.initialized: bool = False
        self.cog_classes: dict = {}
        self.ERROR_LOG_CHANNEL_ID: int = error_log_channel_id
        self.gagame_sessions: dict = {}

    async def setup_hook(self) -> None:
        try:
            await self.auth()
            logger.info("認証に成功しました。データベースの初期化を開始します。")
            from utils.db_manager import db
            await db.initialize()
            logger.info("データベースの初期化が完了しました。Cogのロードを開始します。")
            await git_pull()
            await pip_install()
            await self.load_cogs('cogs')
            await self.load_extension('jishaku')

            # add_bot_endpoint(
            #     job_name="discord-bots",
            #     target="localhost:8001",
            #     labels={"bot": f"{bot_config['name']}"}
            # )
            # reload_prometheus()

            # await self.add_cog(PrometheusCog(self, port=8001))

        except Exception as e:
            logger.error(f"認証に失敗しました。Cogのロードをスキップします。: {e}")
            return
        
        self.loop.create_task(self.after_ready())

    async def after_ready(self) -> None:
        logger.info("setup_hook is called")
        logger.info(startup_message())
        await update_status(self, "Bot Startup...")
        await self.tree.sync()
        logger.info(yokobou())
        await update_status(self, "現在の処理: tree sync")
        if not self.initialized:
            self.initialized = True
            await asyncio.sleep(10)
            asyncio.create_task(presence.update_presence(self))

    async def on_ready(self) -> None:
        logger.info(yokobou())
        logger.info("on_ready is called")
        log_data: dict = {
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

    async def load_cogs(self, folder_name: str) -> None:
        cur: pathlib.Path = pathlib.Path('.')
        for p in cur.glob(f"{folder_name}/**/*.py"):
            if 'Dev' in p.parts:
                continue

            if p.stem == "__init__":
                continue
            try:
                cog_path: str = p.relative_to(cur).with_suffix('').as_posix().replace('/', '.')
                await self.load_extension(cog_path)
                logger.info(f"Loaded extension: {cog_path}")
            except commands.ExtensionFailed as e:
                traceback.print_exc()
                logger.error(f"Failed to load extension: {cog_path} | {e}")

    async def auth(self):
        auth_data = load_auth()
        response = await verify_auth(auth_data)
        if not response:
            raise Exception("認証に失敗しました。")

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        if hasattr(ctx, 'handled') and ctx.handled:
            return

        error_context = {
            "command": {
                "name": ctx.command.name if ctx.command else "unknown",
                "content": ctx.message.content
            },
            "user": {
                "id": ctx.author.id,
                "name": str(ctx.author)
            }
        }
        
        if ctx.guild:
            error_context["guild"] = {
                "id": ctx.guild.id,
                "name": ctx.guild.name
            }

        # log_error_to_sentry(error, error_context)
        handled: bool = await handle_command_error(ctx, error, self.ERROR_LOG_CHANNEL_ID)
        if handled:
            ctx.handled = True

    @commands.Cog.listener()
    async def on_application_command_error(self, interaction: discord.Interaction, error: commands.CommandError) -> None:
        if hasattr(interaction, 'handled') and interaction.handled:
            return

        error_context = {
            "command": {
                "name": interaction.command.name if interaction.command else "unknown",
                "type": str(interaction.type)
            },
            "user": {
                "id": interaction.user.id,
                "name": str(interaction.user)
            }
        }
        
        if interaction.guild:
            error_context["guild"] = {
                "id": interaction.guild.id,
                "name": interaction.guild.name
            }

        # log_error_to_sentry(error, error_context)
        await handle_application_command_error(interaction, error)


intent: discord.Intents = discord.Intents.all()
bot: MyBot = MyBot(command_prefix=command_prefix, intents=intent, help_command=None)

try:
    bot.run(TOKEN)
except Exception as e:
    # log_error_to_sentry(e, {"event": "bot_crash"})
    logger.critical(f"Bot crashed: {e}", exc_info=True)
