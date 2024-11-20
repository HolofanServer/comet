import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import Button, View, Select, Modal
from discord import SelectOption

import pytz
from datetime import datetime

from utils.logging import setup_logging
from utils.commands_help import log_commands

from config.setting import get_settings

logger = setup_logging()
settings = get_settings()

help_command_id_env = settings.bot_help_command_id

jst = pytz.timezone('Asia/Tokyo')
now = datetime.now(jst)

class HelpView(View):
    def __init__(self):
        super().__init__()
        self.add_item(HelpSelect())
        self.add_item(HelpButton())

class HelpReplyView(View):
    def __init__(self, user: discord.User, help_embed: discord.Message):
        super().__init__()
        self.add_item(HelpReplyButton(user, help_embed))

class HelpReplyEditView(View):
    def __init__(self, user: discord.User, help_embed: discord.Message, reply_msg: discord.Message):
        super().__init__()
        self.add_item(HelpReplyEditButton(user, help_embed, reply_msg))

class HelpModal(Modal):
    def __init__(self):
        self.help_channel_id = settings.help_channel_id
        try:
            self.help_channel_id = int(settings.help_channel_id)
        except ValueError:
            self.help_channel_id = 1289693851560316942

        super().__init__(title="質問を入力してください.")
        self.add_item(discord.ui.TextInput(label="コマンド名", placeholder="おみくじコマンド", style=discord.TextStyle.short))
        self.add_item(discord.ui.TextInput(label="質問内容", placeholder="〇〇がわからない。", style=discord.TextStyle.long))

    async def on_submit(self, interaction: discord.Interaction):
        command_name = self.children[0].value
        question_content = self.children[1].value

        await interaction.response.send_message("質問を送信しました！", ephemeral=True)
        channel = interaction.client.get_channel(self.help_channel_id)
        if channel is None:
            return
        e = discord.Embed(title="質問", description=f"{command_name}\n{question_content}", color=discord.Color.blurple())
        if interaction.client.user.avatar:
            icon_url = interaction.client.user.avatar.url
        else:
            icon_url = ""
        e.set_footer(text=f"{interaction.user}", icon_url=icon_url)
        help_embed = await channel.send(embed=e)
        await help_embed.edit(view=HelpReplyView(interaction.user, help_embed))

class HelpReplyModal(Modal):
    def __init__(self, user: discord.User, help_embed: discord.Message):
        self.help_channel_id = settings.help_channel_id
        try:
            self.help_channel_id = int(settings.help_channel_id)
        except ValueError:
            self.help_channel_id = 1233304435967529031

        super().__init__(title="質問に返信してください。")
        self.add_item(discord.ui.TextInput(label="返信内容", placeholder="〇〇です。", style=discord.TextStyle.long))
        self.user = user

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message("質問に返信しました！", ephemeral=True)
        user = self.user
        if user is None:
            return
        e = discord.Embed(title="質問に対しての回答", description="", color=discord.Color.blurple())
        e.add_field(name="質問内容", value=f"{interaction.message.embeds[0].description}", inline=False)
        e.add_field(name="返信内容", value=f"{self.children[0].value}", inline=False)
        if interaction.user.avatar:
            icon_url = interaction.user.avatar.url
        else:
            icon_url = ""
        e.set_footer(text=f"{interaction.user}", icon_url=icon_url)
        reply_msg = await user.send(embed=e)

        button = discord.ui.Button(label="返信を編集", style=discord.ButtonStyle.primary)
        async def button_callback(interaction: discord.Interaction):
            modal = HelpReplyEditModal(self.user, self.help_embed, reply_msg)
            await interaction.response.send_modal(modal)
        button.callback = button_callback
        view = discord.ui.View()
        view.add_item(button)
        await interaction.response.send_message("質問に返信しました！返信を編集するには以下のボタンをクリックしてください。", view=view)

class HelpReplyEditModal(Modal):
    def __init__(self, user: discord.User, help_embed: discord.Message, reply_msg: discord.Message):
        super().__init__(title="質問に返信してください。")
        self.user = user
        self.help_embed = help_embed
        self.reply_msg = reply_msg
        self.add_item(discord.ui.TextInput(label="返信内容", placeholder="〇〇です。", style=discord.TextStyle.long))

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message("質問に返信しました！", ephemeral=True)
        e = discord.Embed(title="質問に対しての回答", description="", color=discord.Color.blurple())
        e.add_field(name="質問内容", value=f"{interaction.message.embeds[0].description}", inline=False)
        e.add_field(name="返信内容", value=f"{self.children[0].value}", inline=False)
        if interaction.user.avatar:
            icon_url = interaction.user.avatar.url
        else:
            icon_url = ""  # ここにデフォルトのアバターURLを設定
        e.set_footer(text=f"{interaction.user}", icon_url=icon_url)
        reply_msg = await interaction.user.send(embed=e)
        await self.help_embed.edit(embed=self.help_embed.embeds[0].add_field(name="返信内容", value=f"{self.children[0].value}", inline=False), view=None)

        button = discord.ui.Button(label="返信を編集", style=discord.ButtonStyle.primary)
        async def button_callback(interaction: discord.Interaction):
            modal = HelpReplyEditModal(self.user, self.help_embed, reply_msg)
            await interaction.response.send_modal(modal)
        button.callback = button_callback
        view = discord.ui.View()
        view.add_item(button)
        await interaction.followup.send("返信を編集するには以下のボタンをクリックしてください。", view=view, ephemeral=True)

class HelpReplyButton(Button):
    def __init__(self, user: discord.User, help_embed: discord.Message):
        super().__init__(style=discord.ButtonStyle.primary, label="返信", emoji="📩")
        self.user = user
        self.help_embed = help_embed

    async def callback(self, interaction: discord.Interaction):
        modal = HelpReplyModal(self.user, self.help_embed)
        await interaction.response.send_modal(modal)

class HelpReplyEditButton(Button):
    def __init__(self, user: discord.User, help_embed: discord.Message, reply_msg: discord.Message):
        super().__init__(style=discord.ButtonStyle.primary, label="返信を編集", emoji="📩")
        self.user = user
        self.help_embed = help_embed
        self.reply_msg = reply_msg

    async def callback(self, interaction: discord.Interaction):
        modal = HelpReplyEditModal(self.user, self.help_embed, self.reply_msg)
        await interaction.response.send_modal(modal)

class HelpSelect(Select):
    def __init__(self):
        self.help_command_id = help_command_id_env
        try:
            self.help_command_id = int(help_command_id_env)
        except ValueError:
            self.help_command_id = 1289693851560316942

        options = [
            SelectOption(label="home", value="home", emoji="🏠"),
            SelectOption(label="おみくじ", value="omikuji", emoji="🍀"),
            SelectOption(label="bug_report", value="bug_report", emoji="🐛"),
        ]
        super().__init__(placeholder="カテゴリを選択してください。", options=options)

    async def callback(self, interaction: discord.Interaction):
        selected_value = self.values[0]
        if interaction.guild:
            member = interaction.guild.get_member(interaction.user.id)
            if member:
                color = member.color
            else:
                color = discord.Color.blurple()
        else:
            color = discord.Color.blurple()

        if selected_value == "home":
            e = discord.Embed(title='ヘルプ', colour=color, timestamp=now)
            if interaction.client.user.avatar:
                icon_url = interaction.client.user.avatar.url
            else:
                icon_url = ""
            e.add_field(name='コマンド一覧', value='/help <カテゴリ名> : </help:1289693851560316942>\n/help omikuji : </omikuji:1289693851560316947>\n/help bug_report : </bug_report:1289693851560316946>', inline=False)
            e.set_footer(text="ヘルプ")
            e.set_author(name=f"{interaction.client.user.name}のヘルプ", icon_url=icon_url)

        elif selected_value == "omikuji":
            e = discord.Embed(title='おみくじコマンド', colour=color, timestamp=now)
            e.add_field(name='おみくじコマンドの使い方', value='/omikuji : </omikuji:1289693851560316947>', inline=False)
            e.add_field(name='おみくじ結果の追加コマンド\n(サーバーブースター専用)', value='/omkj add_fortune <結果> : </omkj add_fortune:1289693851790999703>', inline=False)
            e.add_field(name='おみくじ結果の削除コマンド\n(サーバーブースター専用)', value='/omkj remove_fortune <結果> : </omkj remove_fortune:1289693851790999703>', inline=False)
            e.set_footer(text="おみくじコマンドの説明")
            if interaction.client.user.avatar:
                icon_url = interaction.client.user.avatar.url
            else:
                icon_url = ""
            e.set_author(name=f"{interaction.client.user.name}のヘルプ", icon_url=icon_url)

        elif selected_value == "bug_report":
            e = discord.Embed(title='バグ報告コマンド', colour=color, timestamp=now)
            e.add_field(name='バグ報告コマンドの使い方', value='/bug_report <内容> <画像> : </bug_report:1289693851560316946>', inline=False)
            e.set_footer(text="バグ報告コマンドの説明")
            if interaction.client.user.avatar:
                icon_url = interaction.client.user.avatar.url
            else:
                icon_url = ""
            e.set_author(name=f"{interaction.client.user.name}のヘルプ", icon_url=icon_url)

        else:
            e = discord.Embed(title="エラー", description="不明なカテゴリが選択されました。", color=discord.Color.red())

        await interaction.response.edit_message(embed=e, view=HelpView())

class HelpButton(Button):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.primary, label="直接質問", emoji="❓")

    async def callback(self, interaction: discord.Interaction):
        modal = HelpModal()
        await interaction.response.send_modal(modal)

class HelpCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        help_command_id_env = settings.bot_help_command_id
        try:
            self.help_command_id = int(help_command_id_env)
        except ValueError:
            self.help_command_id = 1289693851560316942

    @app_commands.command(name="help", description="ヘルプを表示します")
    @app_commands.describe(option="ヘルプを表示するカテゴリ名")
    @app_commands.choices(option=[
        app_commands.Choice(name="おみくじコマンド", value="omikuji"),
        app_commands.Choice(name="バグ報告コマンド", value="bug_report"),
    ])
    @log_commands()
    async def help(self, interaction: discord.Interaction, option: app_commands.Choice[str] = None):
        if option is None:
            if interaction.guild:
                member = interaction.guild.get_member(interaction.user.id)
                if member:
                    color = member.color
                else:
                    color = discord.Color.blurple()
            else:
                color = discord.Color.blurple()
            e = discord.Embed(title='ヘルプ', colour=color, timestamp=now)
            if interaction.client.user.avatar:
                icon_url = interaction.client.user.avatar.url
            else:
                icon_url = ""

            e.add_field(name='コマンド一覧', value='/help <カテゴリ名> : </help:1289693851560316942>\n/help omikuji : </omikuji:1289693851560316947>\n/help bug_report : </bug_report:1289693851560316946>', inline=False)
            e.set_footer(text="ヘルプ")
            e.set_author(name=f"{interaction.client.user.name}のヘルプ", icon_url=icon_url)

            await interaction.response.send_message(embed=e, view=HelpView(), ephemeral=True)

        else:
            selected_value = option.value
            if interaction.guild:
                member = interaction.guild.get_member(interaction.user.id)
                if member:
                    color = member.color
                else:
                    color = discord.Color.blurple()
            else:
                color = discord.Color.blurple()
            if selected_value == "omikuji":
                e = discord.Embed(
                    title='おみくじコマンド',
                    description='一日一回おみくじを引けるコマンドです。',
                    colour=color,
                    timestamp=now
                )
                e.add_field(name='おみくじコマンドの使い方', value='/omikuji : </omikuji:1289693851560316947>', inline=False)
                e.add_field(name='おみくじ結果の追加コマンド\n(サーバーブースター専用)', value='/omkj add_fortune <結果> : </omkj add_fortune:1289693851790999703>', inline=False)
                e.add_field(name='おみくじ結果の削除コマンド\n(サーバーブースター専用)', value='/omkj remove_fortune <結果> : </omkj remove_fortune:1289693851790999703>', inline=False)
                e.set_footer(text="おみくじコマンドの説明")
                if interaction.client.user.avatar:
                    icon_url = interaction.client.user.avatar.url
                else:
                    icon_url = ""
                e.set_author(name=f"{interaction.client.user.name}のヘルプ", icon_url=icon_url)

            elif selected_value == "bug_report":
                e = discord.Embed(
                    title='バグ報告コマンド',
                    description='BOTで発生したバグを開発者に報告するコマンドです。',
                    colour=color,
                    timestamp=now
                )
                e.add_field(name='バグ報告コマンドの使い方',
                            value='/bug_report <内容> <画像> : </bug_report:1289693851560316946>',
                            inline=False)
                e.set_footer(text="バグ報告コマンドの説明")
                if interaction.client.user.avatar:
                    icon_url = interaction.client.user.avatar.url
                else:
                    icon_url = ""
                e.set_author(name=f"{interaction.client.user.name}のヘルプ", icon_url=icon_url)

            else:
                e = discord.Embed(title="エラー", description="不明なカテゴリが選択されました。", color=discord.Color.red())

            await interaction.response.send_message(embed=e, view=HelpView(), ephemeral=True)

async def setup(bot):
    await bot.add_cog(HelpCog(bot))