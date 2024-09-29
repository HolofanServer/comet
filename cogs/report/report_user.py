import discord
from discord.ext import commands
from discord import app_commands
import pytz
from datetime import datetime

class ReportUserReasonView(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.value = None
        self.add_item(ReportUserReasonSelect())

class ReportUserReasonSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="スパム", value="スパム"),
            discord.SelectOption(label="荒らし行為", value="荒らし行為"),
            discord.SelectOption(label="不適切な内容", value="不適切な内容"),
            discord.SelectOption(label="ハラスメント", value="ハラスメント"),
            discord.SelectOption(label="メンバーシップの情報公開", value="メンバーシップの情報公開"),
            discord.SelectOption(label="誤情報", value="誤情報"),
            discord.SelectOption(label="違法な行為", value="違法な行為"),
            discord.SelectOption(label="自傷/他傷行為", value="自傷/他傷行為"),
            discord.SelectOption(label="差別的発言", value="差別的発言"),
            discord.SelectOption(label="プライバシー侵害", value="プライバシー侵害"),
            discord.SelectOption(label="不適切なユーザー名・プロフィール画像", value="不適切なユーザー名・プロフィール画像"),
            discord.SelectOption(label="複数アカウントの不正利用", value="複数アカウントの不正利用"),
            discord.SelectOption(label="嫌がらせ", value="嫌がらせ"),
            discord.SelectOption(label="不適切なリンクの共有", value="不適切なリンクの共有"),
            discord.SelectOption(label="コミュニティルール違反", value="コミュニティルール違反"),
            discord.SelectOption(label="スポイラーの無断投稿", value="スポイラーの無断投稿"),
            discord.SelectOption(label="誹謗中傷", value="誹謗中傷"),
            discord.SelectOption(label="広告・宣伝行為", value="広告・宣伝行為"),
            discord.SelectOption(label="ゲームの不正行為", value="ゲームの不正行為"),
            discord.SelectOption(label="暴力的または威脅的な行為", value="暴力的または威脅的な行為"),
            discord.SelectOption(label="その他", value="その他"),
        ]
        super().__init__(custom_id="reason", placeholder="通報理由を選択してください", options=options)

    async def callback(self, interaction: discord.Interaction):
        self.view.value = self.values[0]
        await interaction.response.send_message(f"通報理由を {self.view.value} に設定しました。", ephemeral=True)
        self.view.stop()

class ReportUserCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

async def setup(bot):
    cog = ReportUserCog(bot)
    await bot.add_cog(cog)

    async def report_user(interaction: discord.Interaction, user: discord.User):
        role_name = "Staff"
        mod_channel = interaction.guild.get_channel(1220578233875959918)
        if mod_channel is None:
            await interaction.response.send_message("モデレーションチャンネルが見つかりません", ephemeral=True)
            return
        mod_role = discord.utils.get(interaction.guild.roles, name=role_name)
        if mod_role is None:
            await interaction.response.send_message("モデレーターロールが見つかりません", ephemeral=True)
            return

        view = ReportUserReasonView()
        await interaction.response.send_message("通報理由を選択してください：", view=view, ephemeral=True)
        await view.wait()

        if view.value is None:
            return

        jst = pytz.timezone('Asia/Tokyo')
        now = datetime.now(jst)
        e = discord.Embed(
            title="ユーザー通報",
            description=f"{interaction.user.mention}が {user.mention} を **{view.value}** で通報しました。\n直ちに事実確認を行い適切な対応をしてください。",
            color=0xFF0000,
            timestamp=now
        )
        e.set_author(name=f"通報したユーザー：{interaction.user.display_name} | {interaction.user.id}\n通報されたユーザー：{user.display_name} | {user.id}")

        await mod_channel.send(content=f"{mod_role.mention}", embed=e)
        await interaction.followup.send("ユーザーが運営に通報されました。", ephemeral=True)

    command = app_commands.ContextMenu(
        name="ユーザーを運営に通報",
        callback=report_user,
        type=discord.AppCommandType.user
    )

    bot.tree.add_command(command)
