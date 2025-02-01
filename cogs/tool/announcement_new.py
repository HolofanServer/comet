import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import io

from utils.commands_help import is_owner, log_commands
from utils.logging import setup_logging

logger = setup_logging("D")

class Announcement(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._announcement_views = {}

    template_choices = [
        app_commands.Choice(name="新機能リリース", value="new_feature"),
        app_commands.Choice(name="機能アップデート", value="update_notice"),
        app_commands.Choice(name="新機能紹介", value="feature_intro"),
        app_commands.Choice(name="基本お知らせ", value="announcement"),
        app_commands.Choice(name="サーバーブースター専用機能お知らせ", value="announcement_server_booster"),
    ]
    description_new_feature = "> 新機能の説明を入力してください。\n{feature}\n\n> コマンド一覧"
    description_update_notice = "> アップデート内容を入力してください。\n{feature}\n\n> コマンド一覧"
    description_feature_intro = "> 新機能の説明を入力してください。\n{feature}\n\n> コマンド一覧"
    description_announcement = "> お知らせ内容を入力してください。"
    description_announcement_server_booster = "> サーバーブースター専用機能のお知らせ内容を入力してください。\n{feature}\n\n> コマンド一覧"

    def create_embed(self, template, feature):
        if template.value == "new_feature":
            embed = discord.Embed(
                title="🌟 新機能リリースのお知らせ",
                description=self.description_new_feature.format(feature=feature),
                color=discord.Color.green()
            ).set_footer(text="今すぐチェックしてください！")
        elif template.value == "update_notice":
            embed = discord.Embed(
                title="✨ アップデートのお知らせ",
                description=self.description_update_notice.format(feature=feature),
                color=discord.Color.blue()
            ).set_footer(text="最新情報をお見逃しなく！")
        elif template.value == "feature_intro":
            embed = discord.Embed(
                title="🚀 新機能のご紹介",
                description=self.description_feature_intro.format(feature=feature),
                color=discord.Color.purple()
            ).set_footer(text="フィードバックをお待ちしています！")
        elif template.value == "announcement":
            embed = discord.Embed(
                title="📢 お知らせ",
                description=self.description_announcement,
                color=discord.Color.orange()
            ).set_footer(text="お知らせをお見逃しなく！")
        elif template.value == "announcement_server_booster":
            embed = discord.Embed(
                title="💰 サーバーブースター専用機能のお知らせ",
                description=self.description_announcement_server_booster.format(feature=feature),
                color=discord.Color.gold()
            ).set_footer(text="お知らせをお見逃しなく！")
        logger.info(f"Embed created with template: {template.value}")
        return embed

    @app_commands.command(name="prepare_announcement", description="管理者用お知らせ作成コマンド")
    @app_commands.choices(template=template_choices)
    @app_commands.describe(channel="通知を送信するチャンネル", template="テンプレートを選択", feature="新機能の説明")
    @is_owner()
    @log_commands()
    async def prepare_announcement(self, interaction: discord.Interaction, channel: discord.TextChannel, template: app_commands.Choice[str], feature: str):
        embed = self.create_embed(template, feature)
        view = AnnouncementView(channel, embed)
        await interaction.response.send_message(embed=embed, view=view)
        logger.info(f"Announcement prepared for channel: {channel.name} with template: {template.value}")
        
    @app_commands.command(name="send_announcement", description="BOT経由のお知らせを送信するコマンド")
    @app_commands.describe(channel="通知を送信するチャンネル")
    @is_owner()
    @log_commands()
    async def send_announcement(self, interaction: discord.Interaction, channel: discord.TextChannel):
        view = SimpleAnnouncementView(self.bot, channel)
        message = await interaction.response.send_message(content="編集するとここにそのメッセージが表示されます", view=view)
        self._announcement_views[interaction.user.id] = view
        logger.info(f"Simple announcement prepared for channel: {channel.name}")

class AnnouncementView(discord.ui.View):
    def __init__(self, channel, embed):
        super().__init__(timeout=60)
        self.channel = channel
        self.embed = embed
        self.message = None

    async def on_timeout(self):
        if self.message:
            await self.message.edit(view=None)

    @discord.ui.button(label="送信", style=discord.ButtonStyle.green)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.channel.send(embed=self.embed)
        for item in self.children:
            item.disabled = True
        await interaction.message.edit(view=self)
        await interaction.response.send_message("通知を送信しました！", ephemeral=True)
        logger.info(f"Announcement sent to channel: {self.channel.name}")
        self.stop()

    @discord.ui.button(label="編集", style=discord.ButtonStyle.blurple)
    async def edit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.message = interaction.message
        await interaction.response.send_modal(EditModal(self.embed, self.channel, self.message))

    @discord.ui.button(label="キャンセル", style=discord.ButtonStyle.red)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            item.disabled = True
        await interaction.message.edit(view=self)
        await interaction.response.send_message("操作をキャンセルしました。", ephemeral=True)
        logger.info("Announcement preparation canceled.")
        self.stop()

class EditModal(discord.ui.Modal):
    def __init__(self, embed, channel, message):
        super().__init__(title="Embed編集")
        self.embed = embed
        self.channel = channel
        self.message = message
        self.add_item(discord.ui.TextInput(label="タイトル", default=embed.title, style=discord.TextStyle.short, max_length=256))
        self.add_item(discord.ui.TextInput(label="説明", default=embed.description, style=discord.TextStyle.long))

    async def on_submit(self, interaction: discord.Interaction):
        self.embed.title = self.children[0].value
        self.embed.description = self.children[1].value
        view = AnnouncementView(self.channel, self.embed)
        view.message = self.message
        await self.message.edit(embed=self.embed, view=view)
        await interaction.response.send_message("編集しました。", ephemeral=True)
        logger.info(f"Embed edited: {self.embed.title}")

class SimpleAnnouncementView(discord.ui.View):
    def __init__(self, bot: commands.Bot, channel: discord.TextChannel):
        super().__init__(timeout=60)
        self.bot = bot
        self.channel = channel
        self.message = ""
        self.original_message = None
        self.files = []

    async def on_timeout(self):
        if self.original_message:
            await self.original_message.edit(view=None)

    @discord.ui.button(label="送信", style=discord.ButtonStyle.green)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        message_content = self.message.split("\n\n添付ファイル:")[0]
        await self.channel.send(content=message_content, files=self.files)
        for item in self.children:
            item.disabled = True
        await interaction.message.edit(view=self)
        await interaction.response.send_message("通知を送信しました！", ephemeral=True)
        logger.info(f"Simple announcement sent to channel: {self.channel.name}")
        self.stop()

    @discord.ui.button(label="編集", style=discord.ButtonStyle.blurple)
    async def edit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.original_message = interaction.message
        await interaction.response.send_modal(SimpleEditModal(self.bot, self.message, self.channel, self.original_message))

    MAX_FILES = 10
    MAX_FILE_SIZE = 25 * 1024 * 1024

    @discord.ui.button(label="ファイル添付", style=discord.ButtonStyle.grey)
    async def attach_file_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if len(self.files) >= self.MAX_FILES:
            await interaction.response.send_message(f"添付ファイルは{self.MAX_FILES}個までです。", ephemeral=True)
            return

        await interaction.response.send_message("ファイルをアップロードしてください", ephemeral=True)
        try:
            message = await self.bot.wait_for(
                'message',
                timeout=60.0,
                check=lambda m: m.author == interaction.user and m.channel == interaction.channel and m.attachments
            )
            
            for attachment in message.attachments:
                if attachment.size > self.MAX_FILE_SIZE:
                    await interaction.followup.send(f"ファイルサイズは25MB以下にしてください。\n{attachment.filename}: {attachment.size / 1024 / 1024:.1f}MB", ephemeral=True)
                    await message.delete()
                    return

            file_names = []
            for attachment in message.attachments:
                file_data = await attachment.read()
                self.files.append(discord.File(io.BytesIO(file_data), filename=attachment.filename))
                file_names.append(f"`{attachment.filename}`")
            
            files_info = "\n\n添付ファイル:\n" + "\n".join(file_names)
            if not self.message.endswith(files_info):
                self.message = self.message.split("\n\n添付ファイル:")[0] + files_info
            
            await message.delete()
            await self.original_message.edit(content=self.message)
            await interaction.followup.send(f"ファイルが添付されました。(現在: {len(self.files)}/{self.MAX_FILES}個)", ephemeral=True)
            
        except asyncio.TimeoutError:
            await interaction.followup.send("タイムアウトしました。もう一度お試しください。", ephemeral=True)

    @discord.ui.button(label="キャンセル", style=discord.ButtonStyle.red)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            item.disabled = True
        await interaction.message.edit(view=self)
        await interaction.response.send_message("操作をキャンセルしました。", ephemeral=True)
        logger.info("Simple announcement preparation canceled.")
        self.stop()

class SimpleEditModal(discord.ui.Modal):
    def __init__(self, bot: commands.Bot, message: str, channel: discord.TextChannel, original_message: discord.Message):
        super().__init__(title="メッセージ編集")
        self.bot = bot
        self.message = message
        self.channel = channel
        self.original_message = original_message
        self.add_item(discord.ui.TextInput(
            label="メッセージ",
            default=message if message else "",
            style=discord.TextStyle.long,
            placeholder="ここにメッセージを入力してください"
        ))

    async def on_submit(self, interaction: discord.Interaction):
        new_message = self.children[0].value
        view = SimpleAnnouncementView(self.bot, self.channel)
        view.message = new_message
        view.original_message = self.original_message
        view.files = []
        await self.original_message.edit(content=new_message, view=view)
        await interaction.response.send_message("編集しました。", ephemeral=True)
        logger.info("Simple announcement message edited")

async def setup(bot):
    await bot.add_cog(Announcement(bot))