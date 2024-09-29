import discord
from discord.ext import commands
from dotenv import load_dotenv
import os
import re
import pathlib
import uuid
from datetime import datetime
import logging
import asyncio
import pytz
from utils import presence
from utils.logging import save_log
from utils.startup import startup_send_webhook, startup_send_botinfo
import traceback

load_dotenv()

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

logger = logging.getLogger()
logger.setLevel(logging.INFO)

TOKEN = os.getenv('BOT_TOKEN')
command_prefix = ['gz/', ':', 'ギズ']
main_guild_id = int(os.getenv('DEV_GUILD_ID'))
startup_channel_id = int(os.getenv('STARTUP_CHANNEL_ID'))
main_dev_channel_id = int(os.getenv('BUG_REPORT_CHANNLE_ID'))
bug_report_channel_id = int(os.getenv('BUG_REPORT_CHANNLE_ID'))

class BugReportModal(discord.ui.Modal, title="バグ報告"):
    reason = discord.ui.TextInput(
        label="バグの詳細",
        style=discord.TextStyle.paragraph,
        placeholder="ここにバグの詳細を記載してください...",
        required=True,
        max_length=1024
    )
    image = discord.ui.TextInput(
        label="参考画像",
        style=discord.TextStyle.paragraph,
        placeholder="[必須ではありません]画像のURLを貼り付けてください...",
        required=False,
        max_length=1024
    )

    def __init__(self, bot, error_id, channel_id, server_id, command_name, server_name):
        super().__init__()
        self.bot = bot
        self.error_id = error_id
        self.channel_id = channel_id
        self.server_id = server_id
        self.command_name = command_name
        self.server_name = server_name

    async def on_submit(self, interaction: discord.Interaction):
        dev_channel = self.bot.get_channel(bug_report_channel_id)
        if dev_channel:

            user_mention = interaction.user.mention
            channel_mention = f"<#{self.channel_id}>"

            embed = discord.Embed(title="エラーログ", description=f"エラーID: {self.error_id}", color=discord.Color.red())
            embed.add_field(name="ユーザー", value=user_mention, inline=False)
            embed.add_field(name="チャンネル", value=channel_mention, inline=False)
            embed.add_field(name="サーバー", value=self.server_name, inline=False)
            embed.add_field(name="コマンド", value=f"/{self.command_name}", inline=False)
            embed.add_field(name="エラーメッセージ", value=self.reason.value, inline=False)
            if self.image.value:
                embed.set_image(url=self.image.value)
            await dev_channel.send(embed=embed)
            
            await interaction.response.send_message("バグを報告しました。ありがとうございます！", ephemeral=True)
        else:
            e = discord.Embed(title="エラー", description="> 予期せぬエラーです\n\n<@707320830387814531>にDMを送信するか、[サポートサーバー](https://hfspro.co/asb-discord)にてお問い合わせください", color=discord.Color.red())
            await interaction.response.send_message(embed=e)

class BugReportView(discord.ui.View):
    def __init__(self, bot, error_id, channel_id, server_id, command_name, server_name):
        super().__init__()
        self.bot = bot
        self.error_id = error_id
        self.channel_id = channel_id
        self.server_id = server_id
        self.command_name = command_name
        self.server_name = server_name

    async def disable_button(self, interaction):
        await asyncio.sleep(120)
        for item in self.children:
            if item.custom_id == "my_button":
                item.disabled = True
        await interaction.edit_original_response(view=self)

    @discord.ui.button(label="バグを報告する", style=discord.ButtonStyle.red, custom_id="report_bug_button", emoji="<:Bughunter:1289674918169935934>")
    async def report_bug_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = BugReportModal(self.bot, self.error_id, self.channel_id, self.server_id, self.command_name, self.server_name)
        await interaction.response.send_modal(modal)
        asyncio.create_task(self.disable_button(interaction))

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
        print("setup_hook is called")
        await self.change_presence(activity=discord.Game(name="起動中..", status=discord.Status.idle))
        await self.load_cogs('cogs')
        await self.tree.sync()
        if not self.initialized:
            print("Initializing...")
            self.initialized = True
            print('------')
            print('All cogs have been loaded and bot is ready.')
            print('------')
            asyncio.create_task(presence.update_presence(self))

    async def on_ready(self):
        print("on_ready is called")
        log_data = {
            "event": "BotReady",
            "description": f"{self.user} has successfully connected to Discord.",
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "session_id": session_id
        }
        save_log(log_data)
        if not self.initialized:
            try:
                await startup_send_webhook(self, guild_id=main_guild_id)
                await startup_send_botinfo(self)
            except Exception as e:
                print(f"Error during startup: {e}")
            self.initialized = True


    async def load_cogs(self, folder_name: str):
        cur = pathlib.Path('.')
        for p in cur.glob(f"{folder_name}/**/*.py"):
            if p.stem == "__init__" or "backup" in p.parts:
                continue
            try:
                cog_path = p.relative_to(cur).with_suffix('').as_posix().replace('/', '.')
                await self.load_extension(cog_path)
                print(f'{cog_path} loaded successfully.')
            except commands.ExtensionFailed as e:
                traceback.print_exc()
                print(f'Failed to load extension {p.stem}: {e}\nFull error: {e.__cause__}')

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if hasattr(ctx, 'handled') and ctx.handled:
            return

        if isinstance(error, commands.CommandNotFound):
            await ctx.send("そのコマンドは存在しません。")
            ctx.handled = True
            return
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("引数が不足しています。")
            ctx.handled = True
            return
        if isinstance(error, commands.BadArgument):
            await ctx.send("引数が不正です。")
            ctx.handled = True
            return
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("あなたはのコマンドを実行する権限がありません。")
            ctx.handled = True
            return
        if isinstance(error, commands.BotMissingPermissions):
            await ctx.send("BOTがこのコマンドを実行する権限がありません。")
            ctx.handled = True
            return
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"このコマンドは{error.retry_after:.2f}秒後に再実行できます。")
            ctx.handled = True
            return
        
        if not hasattr(ctx, 'handled') or not ctx.handled:
            error_id = uuid.uuid4()

            channel_id = ctx.channel.id
            server_id = ctx.guild.id if ctx.guild else 'DM'
            server_name = ctx.guild.name if ctx.guild else 'DM'
            channel_mention = f"<#{channel_id}>"
            now = datetime.now(pytz.timezone('Asia/Tokyo'))

            e = discord.Embed(
                title="エラー通知",
                description=(
                    "> <:Error:1289674741845594193>コマンド実行中にエラーが発生しました。\n"
                    f"**エラーID**: `{error_id}`\n"
                    f"**コマンド**: {ctx.command.qualified_name if ctx.command else 'N/A'}\n"
                    f"**ユーザー**: {ctx.author.mention}\n"
                    f"**エラーメッセージ**: {error}\n"
                ),
                color=discord.Color.red(),
                timestamp=now
            )
            e.set_footer(text=f"サーバー: {server_name}")
            await self.get_channel(self.ERROR_LOG_CHANNEL_ID).send(embed=e)

            view = BugReportView(self, str(error_id), str(channel_id), str(server_id), ctx.command.qualified_name if ctx.command else "N/A", server_name)
            if hasattr(ctx, 'interaction') and ctx.interaction:
                ed = discord.Embed(
                    title="エラーが発生しました",
                    description=(
                        "> <:Error:1289674741845594193>コマンド実行中にエラーが発生しました。\n"
                        f"エラーID: `{error_id}`\n"
                        f"チャンネル: {channel_mention}\n"
                        f"サーバー: `{server_name}`\n\n"
                        "__下のボタンを押してバグを報告してください。__\n参考となるスクリーンショットがある場合は**__事前に画像URL__**を準備してください。"
                    ),
                    color=discord.Color.red(),
                    timestamp=now
                )
                view = BugReportView(self, str(error_id), str(channel_id), str(server_id), ctx.interaction.command.qualified_name if ctx.interaction.command else "N/A", server_name)
                try:
                    if not ctx.interaction.response.is_done():
                        await ctx.interaction.response.send_message(embed=ed, view=view, ephemeral=True)
                    else:
                        await ctx.interaction.followup.send(embed=ed, view=view, ephemeral=True)
                except discord.InteractionResponded:
                    await ctx.interaction.followup.send(embed=ed, view=view, ephemeral=True)
            else:
                ed = discord.Embed(
                    title="エラーが発生しました",
                    description=(
                        "> <:Error:1289674741845594193>コマンド実行中にエラーが発生しました。\n"
                        f"エラーID: `{error_id}`\n"
                        f"チャンネル: {channel_mention}\n"
                        f"サーバー: `{server_name}`\n\n"
                        "__下のボタンを押してバグを報告してください。__\n参考となるスクリーンショットがある場合は**__事前に画像URL__**を準備してください。"
                    ),
                    color=discord.Color.red()
                )

                await ctx.author.send(embed=ed, view=view)

    @commands.Cog.listener()
    async def on_application_command_error(self, interaction: discord.Interaction, error):
        if hasattr(interaction, 'handled') and interaction.handled:
            return

        if isinstance(error, commands.CommandNotFound):
            await interaction.response.send_message("そのコマンドは存在しません。", ephemeral=True)
            interaction.handled = True
            logger.error(f"CommandNotFound: {error}")
            return
        
        if isinstance(error, commands.MissingRequiredArgument):
            await interaction.response.send_message("引数が不足しています。", ephemeral=True)
            interaction.handled = True
            logger.error(f"MissingRequiredArgument: {error}")
            return
        
        if isinstance(error, commands.BadArgument):
            await interaction.response.send_message("引数が不正です。", ephemeral=True)
            interaction.handled = True
            logger.error(f"BadArgument: {error}")
            return
        
        if isinstance(error, commands.MissingPermissions):
            await interaction.response.send_message("あなたはのコマンドを実行する権限がありません。", ephemeral=True)
            interaction.handled = True
            logger.error(f"MissingPermissions: {error}")
            return
        
        if isinstance(error, commands.BotMissingPermissions):
            await interaction.response.send_message("BOTがこのコマンドを実行する権限がありません。", ephemeral=True)
            interaction.handled = True
            logger.error(f"BotMissingPermissions: {error}")
            return
        
        if isinstance(error, commands.CommandOnCooldown):
            await interaction.response.send_message(f"このコマンドは{error.retry_after:.2f}秒後に再実行できます。", ephemeral=True)
            interaction.handled = True
            logger.error(f"CommandOnCooldown: {error}")
            return

        if not interaction.handled:
            error_id = uuid.uuid4()
            
            logger.error(f"UnknownError: {error}")

            channel_id = interaction.channel_id
            server_id = interaction.guild_id if interaction.guild else 'DM'
            server_name = interaction.guild.name if interaction.guild else 'DM'
            channel_mention = f"<#{channel_id}>"
            now = datetime.now(pytz.timezone('Asia/Tokyo'))

            e = discord.Embed(
                title="エラー通知",
                description=(
                    "> <:Error:1289674741845594193>コマンド実行中にエラーが発生しました。\n"
                    f"**エラーID**: `{error_id}`\n"
                    f"**コマンド**: {interaction.command.qualified_name if interaction.command else 'N/A'}\n"
                    f"**ユーザー**: {interaction.user.mention}\n"
                    f"**エラーメッセージ**: {error}\n"
                ),
                color=discord.Color.red(),
                timestamp=now
            )
            e.set_footer(text=f"サーバー: {server_name}")
            await self.get_channel(self.ERROR_LOG_CHANNEL_ID).send(embed=e)

            es = discord.Embed(
                title="エラーが発生しました",
                description=(
                    "> <:Error:1289674741845594193>コマンド実行中にエラーが発生しました。\n"
                    f"エラーID: `{error_id}`\n"
                    f"チャンネル: {channel_mention}\n"
                    f"サーバー: `{server_name}`\n\n"
                    "__下のボタンを押してバグを報告してください。__\n参考となるスクリーンショットがある場合は**__事前に画像URL__**を準備してください。"
                ),
                color=discord.Color.red(),
                timestamp=now
            )
            view = BugReportView(self, str(error_id), str(channel_id), str(server_id), interaction.command.qualified_name if interaction.command else "N/A", server_name)

            try:
                await interaction.response.send_message(embed=es, view=view, ephemeral=True)
            except discord.InteractionResponded:
                await interaction.followup.send(embed=es, view=view, ephemeral=True)

intent: discord.Intents = discord.Intents.all()
bot = MyBot(command_prefix=command_prefix, intents=intent, help_command=None)

bot.run(TOKEN)