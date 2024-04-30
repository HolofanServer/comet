import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import Button, View, Select, Modal
from discord import SelectOption
import pytz
from datetime import datetime
import os
from dotenv import load_dotenv

dotenv_path = '/Users/freewifi/yo-chan_bot/.env'
load_dotenv(dotenv_path)

help_channel_id_env = os.getenv("HELP_CHANNEL_ID", "0")
help_command_id_env = os.getenv("HELP_COMMAND_ID", "0")
print("HELP_COMMAND_ID:", help_command_id_env)

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
        self.help_channel_id = help_channel_id_env
        try:
            self.help_channel_id = int(help_channel_id_env)
        except ValueError:
            self.help_channel_id = 1233304435967529031

        super().__init__(title="質問を入力してください.")
        self.add_item(discord.ui.TextInput(label="コマンド名", placeholder="募集コマンド", style=discord.TextStyle.short))
        self.add_item(discord.ui.TextInput(label="質問内容", placeholder="〇〇がわからない。", style=discord.TextStyle.long))

    async def on_submit(self, interaction: discord.Interaction):
        command_name = self.children[0].value
        question_content = self.children[1].value

        await interaction.response.send_message("質問を送信しました！", ephemeral=True)
        channel = interaction.client.get_channel(self.help_channel_id)
        if channel is None:
            return
        e = discord.Embed(title="質問", description=f"{command_name}\n{question_content}", color=discord.Color.blurple())
        e.set_footer(text=f"{interaction.user}", icon_url=interaction.user.avatar.url)
        help_embed = await channel.send(embed=e)
        await help_embed.edit(view=HelpReplyView(interaction.user, help_embed))

class HelpReplyModal(Modal):
    def __init__(self, user: discord.User, help_embed: discord.Message):
        self.help_channel_id = help_channel_id_env
        self.help_embed = help_embed
        try:
            self.help_channel_id = int(help_channel_id_env)
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
        e.set_footer(text=f"{interaction.user}", icon_url=interaction.user.avatar.url)
        reply_msg = await user.send(embed=e)
        await self.help_embed.delete()

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
        e.set_footer(text=f"{interaction.user}", icon_url=interaction.user.avatar.url)
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
            self.help_command_id = 1232610580628635719

        options = [
            SelectOption(label="home", value="home", emoji="🏠"),
            SelectOption(label="メンションを使った募集方法", value="mention", emoji="🔔"),
            SelectOption(label="時間を指定した募集方法", value="time", emoji="⏰")
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

        if selected_value == "mention":
            e = discord.Embed(title='メンションを使った募集方法', colour=color, timestamp=now)
            e.add_field(name='メンションを使用する場合', value='/募集 <募集のタイトル> <募集の怖しい説明> <使用予定のVC> <募集する人数> <ここでメンションしたいロールを選択> <最大三つまで同時に可能です> <ここには3個目>\n - コマンドを入力した際に[オプション]として表示されます。詳しくは画像をご覧ください。', inline=False)
            e.set_footer(text="メンションを使った募集方法の説明")
            e.set_thumbnail(url=interaction.client.user.avatar.url)
            e.set_author(name=f"{interaction.client.user.name}のヘルプ", icon_url=interaction.client.user.avatar.url)
            e.set_image(url="https://cdn.discordapp.com/attachments/1232610580628635719/1232610580628635719/unknown.png")

        elif selected_value == "time":
            e = discord.Embed(title='募集方法', colour=color, timestamp=now)
            e.add_field(name='時間を指定した募集', value='/募集 <募集のタイトル> <募集の怖しい説明> <使用予定のVC> <募集する人数> <募集メッセージを送信する時刻>\n - 時間は[12:00]または[30分後]の形式で指定してください', inline=False)
            e.set_footer(text="時間を指定した募集方法の説明")
            e.set_thumbnail(url=interaction.client.user.avatar.url)
            e.set_author(name=f"{interaction.client.user.name}のヘルプ", icon_url=interaction.client.user.avatar.url)
            e.set_image(url="https://cdn.discordapp.com/attachments/1232610580628635719/1232610580628635719/unknown.png")

        elif selected_value == "home":
            if interaction.guild:
                member = interaction.guild.get_member(interaction.user.id)
                if member:
                    color = member.color
                else:
                    color = discord.Color.blurple()
            else:
                color = discord.Color.blurple()
            e = discord.Embed(title='ヘルプ', colour=color, timestamp=now)
            e.add_field(name='募集コマンドの使い方', value='/募集 <募集のタイトル> <募集の怖しい説明> <使用予定のVC> <募集する人数>', inline=False)
            e.add_field(name='メンションを使用する場合', value='/募集 <募集のタイトル> <募集の怖しい説明> <使用予定のVC> <募集する人数> <ここでメンションしたいロールを選択> <最大三つまで同時に可能です> <ここには3個目>\n - コマンドを入力した際に[オプション]として表示されます。詳しくは画像をご覧ください。', inline=False)
            e.add_field(name='時間を指定した募集', value='/募集 <募集のタイトル> <募集の怖しい説明> <使用予定のVC> <募集する人数> <募集メッセージを送信する時刻>\n - 時間は[12:00]または[30分後]の形式で指定してください', inline=False)
            e.set_thumbnail(url=interaction.client.user.avatar.url)
            e.set_author(name=f"{interaction.client.user.name}のヘルプ", icon_url=interaction.client.user.avatar.url)
            e.set_image(url="https://cdn.discordapp.com/attachments/1232610580628635719/1232610580628635719/unknown.png")

        else:
            e = discord.Embed(title="エラー", description="不明なカテゴリが選択されました。", color=discord.Color.red())

        await interaction.response.edit_message(embed=e, view=HelpView())

class HelpButton(Button):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.primary, label="直接質問", emoji="❓")

    async def callback(self, interaction: discord.Interaction):
        modal = HelpModal()  # HelpModal インスタンスを作成
        await interaction.response.send_modal(modal)  # 修正: send_modal を正しく呼び出す

class HelpCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        help_command_id_env = os.getenv("HELP_COMMAND_ID", "0")
        try:
            self.help_command_id = int(help_command_id_env)
        except ValueError:
            self.help_command_id = 1232610580628635719

    @app_commands.command(name="help", description="ヘルプを表示します")
    @app_commands.describe(option="ヘルプを表示するカテゴリ名")
    @app_commands.choices(option=[
        app_commands.Choice(name="メンションを使った募集", value="mention"),
        app_commands.Choice(name="時間を指定した募集", value="time")
    ])
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
            e.add_field(name='募集コマンドの使い方', value='/募集 <募集のタイトル> <募集の怖しい説明> <使用予定のVC> <募集する人数>', inline=False)
            e.add_field(name='メンションを使用する場合', value='/募集 <募集のタイトル> <募集の怖しい説明> <使用予定のVC> <募集する人数> <ここでメンションしたいロールを選択> <最大三つまで同時に可能です> <ここには3個目>\n - コマンドを入力した際に[オプション]として表示されます。詳しくは画像をご覧ください。', inline=False)
            e.add_field(name='時間を指定した募集', value='/募集 <募集のタイトル> <募集の怖しい説明> <使用予定のVC> <募集する人数> <募集メッセージを送信する時刻>\n - 時間は[12:00]または[30分後]の形式で指定してください', inline=False)
            e.set_footer(text="募集方法")
            e.set_thumbnail(url=interaction.client.user.avatar.url)
            e.set_author(name=f"{interaction.client.user.name}のヘルプ", icon_url=interaction.client.user.avatar.url)
            e.set_image(url="https://cdn.discordapp.com/attachments/1232610580628635719/1232610580628635719/unknown.png")

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
            if selected_value == "mention":
                e = discord.Embed(title='メンションを使った募集方法', colour=color, timestamp=now)
                e.add_field(name='メンションを使用する場合', value='/募集 <募集のタイトル> <募集の怖しい説明> <使用予定のVC> <募集する人数> <ここでメンションしたいロールを選択> <最大三つまで同時に可能です> <ここには3個目>\n - コマンドを入力した際に[オプション]として表示されます。詳しくは画像をご覧ください。', inline=False)
                e.set_footer(text="メンションを使った募集方法の説明")
                e.set_thumbnail(url=interaction.client.user.avatar.url)
                e.set_author(name=f"{interaction.client.user.name}のヘルプ", icon_url=interaction.client.user.avatar.url)
                e.set_image(url="https://cdn.discordapp.com/attachments/1232610580628635719/1232610580628635719/unknown.png")

            elif selected_value == "time":
                e = discord.Embed(title='募集方法', colour=color, timestamp=now)
                e.add_field(name='時間を指定した募集', value='/募集 <募集のタイトル> <募集の怖しい説明> <使用予定のVC> <募集する人数> <募集メッセージを送信する時刻>\n - 時間は[12:00]または[30分後]の形式で指定してください', inline=False)
                e.set_footer(text="時間を指定した募集方法の説明")
                e.set_thumbnail(url=interaction.client.user.avatar.url)
                e.set_author(name=f"{interaction.client.user.name}のヘルプ", icon_url=interaction.client.user.avatar.url)
                e.set_image(url="https://cdn.discordapp.com/attachments/1232610580628635719/1232610580628635719/unknown.png")

            await interaction.response.send_message(embed=e, view=HelpView(), ephemeral=True)

async def setup(bot):
    await bot.add_cog(HelpCog(bot))