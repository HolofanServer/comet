from datetime import datetime

import discord
import pytz
from discord import app_commands
from discord.ext import commands
from discord.ui import Modal, TextInput

from utils.logging import setup_logging

logger = setup_logging()

class OtherReasonModal(Modal):
    def __init__(self, message: discord.Message, mod_channel: discord.TextChannel, **kwargs):
        super().__init__(title="通報理由の詳細", **kwargs)
        self.message = message
        self.mod_channel = mod_channel
        self.reason = TextInput(label="詳細な通報理由", style=discord.TextStyle.long, placeholder="ここに詳細な通報理由を記入してください...", required=True)
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message("通報理由が送信されました。", ephemeral=True)
        self.guild = interaction.guild
        mod_role = discord.utils.get(self.guild.roles, name="moderator")
        embed = discord.Embed(
            title="メッセージ通報",
            description=f"{interaction.user.mention} が {self.message.jump_url} ({self.message.author.mention}) を **その他の理由** で通報しました。\n直ちに事実確認を行い適切な対応をしてください。",
            color=0xFF0000,
            timestamp=datetime.now().astimezone(pytz.timezone('Asia/Tokyo'))
        )
        embed.add_field(name="通報理由", value=self.reason.value, inline=False)
        embed.add_field(name="通報されたメッセージ", value=f"{self.message.content}\n\n`{self.message.content}`", inline=False)
        embed.set_author(name=f"通報者：{interaction.user.display_name} | {interaction.user.id}\n通報されたユーザー：{self.message.author.display_name} | {self.message.author.id}")
        await self.mod_channel.send(embed=embed, content=f"{mod_role.mention}")
        await interaction.followup.send("メッセージが運営に通報されました。", ephemeral=True)
        self.stop()

class ReportReasonView(discord.ui.View):
    def __init__(self, message: discord.Message, mod_channel: discord.TextChannel):
        super().__init__()
        self.add_item(ReportReasonSelect(message=message, mod_channel=mod_channel))

class ReportReasonSelect(discord.ui.Select):
    def __init__(self, message: discord.Message, mod_channel: discord.TextChannel, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.message = message
        self.mod_channel = mod_channel
        self.placeholder = '通報理由を選択してください'
        self.options = [
            discord.SelectOption(label="スパム", value="スパム"),
            discord.SelectOption(label="不適切な内容", value="不適切な内容"),
            discord.SelectOption(label="ハラスメント", value="ハラスメント"),
            discord.SelectOption(label="メンバーシップの情報公開", value="メンバーシップの情報公開"),
            discord.SelectOption(label="誤情報", value="誤情報"),
            discord.SelectOption(label="違法な行為", value="違法な行為"),
            discord.SelectOption(label="自傷/他傷行為", value="自傷/他傷行為"),
            discord.SelectOption(label="生成AIコンテンツ", value="生成AIコンテンツ"),
            discord.SelectOption(label="差別的発言", value="差別的発言"),
            discord.SelectOption(label="プライバシー侵害", value="プライバシー侵害"),
            discord.SelectOption(label="荒らし行為", value="荒らし行為"),
            discord.SelectOption(label="その他", value="その他"),
        ]

    async def callback(self, interaction: discord.Interaction):
        self.view.value = self.values[0]
        if self.view.value == "その他":
            modal = OtherReasonModal(message=self.message, mod_channel=self.mod_channel)
            await interaction.response.send_modal(modal)
        else:
            await interaction.response.send_message(f"通報理由を {self.view.value} に設定しました。", ephemeral=True)
            self.view.stop()

class ReportMessageCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

async def setup(bot):
    cog = ReportMessageCog(bot)
    await bot.add_cog(cog)

    async def report_message(interaction: discord.Interaction, message: discord.Message):
        from .settings import ReportSettingsCog
        mod_channel_id = await ReportSettingsCog.load_config(interaction.guild.id)
        mod_role_id = await ReportSettingsCog.load_mod_role(interaction.guild.id)

        if mod_channel_id is None:
            await interaction.response.send_message("通報チャンネルが設定されていません。", ephemeral=True)
            return

        mod_channel = interaction.guild.get_channel(mod_channel_id)
        if mod_channel is None:
            await interaction.response.send_message("モデレーションチャンネルが見つかりません", ephemeral=True)
            return

        if mod_role_id is None:
            await interaction.response.send_message("モデレーターロールが設定されていません。", ephemeral=True)
            return

        mod_role = interaction.guild.get_role(mod_role_id)
        if mod_role is None:
            await interaction.response.send_message("モデレーターロールが見つかりません", ephemeral=True)
            return

        view = ReportReasonView(message=message, mod_channel=mod_channel)
        await interaction.response.send_message("通報理由を選択してください：", view=view, ephemeral=True)
        await view.wait()

        if view.value is None:
            await interaction.followup.send("通報がキャンセルされました。", ephemeral=True)
            return

        if view.value == "その他":
            return

        jst = pytz.timezone('Asia/Tokyo')
        now = datetime.now(jst)
        embed = discord.Embed(
        title="メッセージ通報",
        description=f"{interaction.user.mention}が {message.jump_url} ({message.author.mention}) を **{view.value if view.value != 'その他' else 'その他の理由'}** で通報しました。\n直ちに事実確認を行い適切な対応をしてください。",
        color=0xFF0000,
        timestamp=now
    )
        embed.set_author(name=f"通報者：{interaction.user.display_name} | {interaction.user.id}\n通報されたユーザー : {message.author.display_name} | {message.author.id}")

        embed.add_field(name="通報理由", value=view.value, inline=False)

        embed.add_field(name="通報されたメッセージ", value=f"{message.content}\n\n`{message.content}`", inline=False)
        if message.attachments:
            embed.add_field(name="添付ファイル", value="\n".join([attachment.url for attachment in message.attachments]), inline=False)
            if message.attachments[0].content_type.startswith("image"):
                embed.set_image(url=message.attachments[0].url)
            else:
                embed.add_field(name="ファイル名", value="プレビュー不可", inline=False)

        await mod_channel.send(content=f"{mod_role.mention}", embed=embed)
        await interaction.followup.send("メッセージが運営に通報されました。", ephemeral=True)

    command = app_commands.ContextMenu(
        name="メッセージを運営に通報",
        callback=report_message,
        type=discord.AppCommandType.message
    )

    bot.tree.add_command(command)
