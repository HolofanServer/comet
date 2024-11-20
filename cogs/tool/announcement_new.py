import discord
from discord.ext import commands
from discord import app_commands

from utils.commands_help import is_owner, log_commnads
from utils.logging import setup_logging

logger = setup_logging("D")

class Announcement(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

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
    @log_commnads()
    async def prepare_announcement(self, interaction: discord.Interaction, channel: discord.TextChannel, template: app_commands.Choice[str], feature: str):
        embed = self.create_embed(template, feature)
        view = AnnouncementView(channel, embed)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        logger.info(f"Announcement prepared for channel: {channel.name} with template: {template.value}")

class AnnouncementView(discord.ui.View):
    def __init__(self, channel, embed):
        super().__init__(timeout=60)
        self.channel = channel
        self.embed = embed

    @discord.ui.button(label="送信", style=discord.ButtonStyle.green)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.channel.send(embed=self.embed)
        await interaction.response.send_message("通知を送信しました！", ephemeral=True)
        logger.info(f"Announcement sent to channel: {self.channel.name}")
        self.stop()

    @discord.ui.button(label="編集", style=discord.ButtonStyle.blurple)
    async def edit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(EditModal(self.embed, self.channel))

    @discord.ui.button(label="キャンセル", style=discord.ButtonStyle.red)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("操作をキャンセルしました。", ephemeral=True)
        logger.info("Announcement preparation canceled.")
        self.stop()

class EditModal(discord.ui.Modal):
    def __init__(self, embed, channel):
        super().__init__(title="Embed編集")
        self.embed = embed
        self.channel = channel
        self.add_item(discord.ui.TextInput(label="タイトル", default=embed.title, style=discord.TextStyle.short, max_length=256))
        self.add_item(discord.ui.TextInput(label="説明", default=embed.description, style=discord.TextStyle.long))

    async def on_submit(self, interaction: discord.Interaction):
        self.embed.title = self.children[0].value
        self.embed.description = self.children[1].value
        view = AnnouncementView(self.channel, self.embed)
        await interaction.response.send_message(embed=self.embed, view=view, ephemeral=True)
        logger.info(f"Embed edited: {self.embed.title}")

async def setup(bot):
    await bot.add_cog(Announcement(bot))