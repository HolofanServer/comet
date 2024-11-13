import discord
from discord.ext import commands

import uuid
import pytz
import asyncio

from datetime import datetime

from config.setting import get_settings

from utils.logging import setup_logging
from utils.github_issue import create_github_issue

logger = setup_logging("E")
settings = get_settings()

ERROR_LOG_CHANNEL_ID = settings.admin_error_log_channel_id
BUG_REPORT_CHANNEL_ID = settings.admin_bug_report_channel_id

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
        dev_channel = self.bot.get_channel(BUG_REPORT_CHANNEL_ID)
        if dev_channel:
            logger.info(f"バグ報告が送信されました。エラーID: {self.error_id}")

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
            logger.error("バグ報告チャンネルが見つかりませんでした。")
            e = discord.Embed(title="エラー", description="> 予期せぬエラーです\n\n<@707320830387814531>にDMにてお問い合わせください", color=discord.Color.red())
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

async def handle_command_error(ctx, error, error_log_channel_id):

    error_id = uuid.uuid4()
    error_message = str(error)
    issue_title = f"エラー発生: {ctx.command.qualified_name if ctx.command else 'N/A'}"
    issue_body = (
        f"**サーバー**: {ctx.guild.name if ctx.guild else 'DM'}\n"
        f"**BOT**: {ctx.bot.user.display_name}\n"
        f"**チャンネル**: <#{ctx.channel.name}>\n"
        f"**コマンド**: /{ctx.command.qualified_name if ctx.command else 'N/A'}\n"
        f"**エラーID**: `{error_id}`\n"
        f"**ユーザー**: {ctx.author.display_name}\n"
        f"**エラーメッセージ**: {error_message}\n"
    )
    await create_github_issue(issue_title, issue_body)
    
    if error_message == "You must own this bot to use Jishaku.":
        logger.warning(f"someone try to use jishaku commands: {ctx.author.name}")
        await ctx.send("このコマンドはBOTオーナーのみ使用可能です。", ephemeral=True)
        return True
        
    if isinstance(error, commands.CommandNotFound):
        logger.warning(f"コマンドが見つかりません: {ctx.command}")
        await ctx.send("そのコマンドは存在しません。")
        return True
        
    if isinstance(error, commands.MissingRequiredArgument):
        logger.warning(f"引数が不足しています: {ctx.command}")
        await ctx.send("引数が不足しています。")
        return True
        
    if isinstance(error, commands.BadArgument):
        logger.warning(f"引数が不正です: {ctx.command}")
        await ctx.send("引数が不正です。")
        return True
        
    if isinstance(error, commands.MissingPermissions):
        logger.warning(f"権限が不足しています: {ctx.command}")
        await ctx.send("あなたはのコマンドを実行する権限がありません。")
        return True
        
    if isinstance(error, commands.BotMissingPermissions):
        logger.warning(f"BOTの権限が不足しています: {ctx.command}")
        await ctx.send("BOTがこのコマンドを実行する権限がありません。")
        return True
        
    if isinstance(error, commands.CommandOnCooldown):
        logger.warning(f"コマンドがクールダウン中です: {ctx.command}")
        await ctx.send(f"このコマンドは{error.retry_after:.2f}秒後に再実行できます。")
        return True

    logger.error(f"UnknownError: {error}")

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
    await ctx.bot.get_channel(error_log_channel_id).send(embed=e)

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
    view = BugReportView(ctx.bot, str(error_id), str(channel_id), str(server_id), ctx.command.qualified_name if ctx.command else "N/A", server_name)

    try:
        await ctx.send(embed=es, view=view, ephemeral=True)
    except discord.InteractionResponded:
        await ctx.followup.send(embed=es, view=view, ephemeral=True)
    return False

async def handle_application_command_error(interaction, error):
    if hasattr(interaction, 'handled') and interaction.handled:
        return

    if isinstance(error, commands.CommandNotFound):
        logger.warning(f"コマンドが見つかりません: {interaction.command}")
        await interaction.response.send_message("そのコマンドは存在しません。", ephemeral=True)
        interaction.handled = True
        logger.error(f"CommandNotFound: {error}")
        return
        
    if isinstance(error, commands.MissingRequiredArgument):
        logger.warning(f"引数が不足しています: {interaction.command}")
        await interaction.response.send_message("引数が不足しています。", ephemeral=True)
        interaction.handled = True
        logger.error(f"MissingRequiredArgument: {error}")
        return
        
    if isinstance(error, commands.BadArgument):
        logger.warning(f"引数が不正です: {interaction.command}")
        await interaction.response.send_message("引数が不正です。", ephemeral=True)
        interaction.handled = True
        logger.error(f"BadArgument: {error}")
        return
        
    if isinstance(error, commands.MissingPermissions):
        logger.warning(f"権限が不足しています: {interaction.command}")
        await interaction.response.send_message("あなたはのコマンドを実行する権限がありません。", ephemeral=True)
        interaction.handled = True
        logger.error(f"MissingPermissions: {error}")
        return
        
    if isinstance(error, commands.BotMissingPermissions):
        logger.warning(f"BOTの権限が不足しています: {interaction.command}")
        await interaction.response.send_message("BOTがこのコマンドを実行する権限がありません。", ephemeral=True)
        interaction.handled = True
        logger.error(f"BotMissingPermissions: {error}")
        return
        
    if isinstance(error, commands.CommandOnCooldown):
        logger.warning(f"コマンドがクールダウン中です: {interaction.command}")
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
        await interaction.bot.get_channel(ERROR_LOG_CHANNEL_ID).send(embed=e)

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
        view = BugReportView(interaction.bot, str(error_id), str(channel_id), str(server_id), interaction.command.qualified_name if interaction.command else "N/A", server_name)

        try:
            await interaction.response.send_message(embed=es, view=view, ephemeral=True)
        except discord.InteractionResponded:
            await interaction.followup.send(embed=es, view=view, ephemeral=True)
