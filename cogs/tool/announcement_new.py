import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import io
import time
from collections import defaultdict
from typing import Dict, List, Set, Optional

from utils.commands_help import is_owner, log_commands
from utils.logging import setup_logging

logger = setup_logging("D")

class ThreadActionView(discord.ui.View):
    def __init__(self, thread: discord.Thread, original_message: discord.Message) -> None:
        super().__init__(timeout=None)
        self.thread = thread
        self.original_message = original_message
        self.delete_votes: Dict[str, Set[discord.Member]] = defaultdict(set)
        self.close_votes: Dict[str, Set[discord.Member]] = defaultdict(set)
        self.required_votes: int = 3

    @discord.ui.button(label="メッセージ消去", style=discord.ButtonStyle.danger)
    async def delete_message(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        
        for votes in self.delete_votes.values():
            if interaction.user in votes and str(interaction.user.id) != user_id:
                await interaction.response.send_message("既に投票しています。", ephemeral=True)
                return

        if user_id in self.delete_votes and interaction.user in self.delete_votes[user_id]:
            self.delete_votes[user_id].remove(interaction.user)
            await interaction.response.send_message("投票を取り消しました。", ephemeral=True)
        else:
            self.delete_votes[user_id].add(interaction.user)
            total_votes = len(set().union(*self.delete_votes.values()))
            await interaction.response.send_message(
                f"投票を受け付けました。(現在: {total_votes}/{self.required_votes})",
                ephemeral=True
            )

            if total_votes >= self.required_votes:
                await self.original_message.delete()
                await interaction.followup.send("メッセージを消去しました。", ephemeral=True)

    @discord.ui.button(label="対応終了", style=discord.ButtonStyle.secondary)
    async def close_thread(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        
        for votes in self.close_votes.values():
            if interaction.user in votes and str(interaction.user.id) != user_id:
                await interaction.response.send_message("既に投票しています。", ephemeral=True)
                return

        if user_id in self.close_votes and interaction.user in self.close_votes[user_id]:
            self.close_votes[user_id].remove(interaction.user)
            await interaction.response.send_message("投票を取り消しました。", ephemeral=True)
        else:
            self.close_votes[user_id].add(interaction.user)
            total_votes = len(set().union(*self.close_votes.values()))
            await interaction.response.send_message(
                f"投票を受け付けました。(現在: {total_votes}/{self.required_votes})",
                ephemeral=True
            )

            if total_votes >= self.required_votes:
                await self.thread.edit(archived=True, locked=True)
                await interaction.followup.send("スレッドをロックし、アーカイブしました。", ephemeral=True)

class Announcement(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._announcement_views = {}
        self._thread_views: Dict[int, ThreadActionView] = {}

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        thread = message.channel
        view = self._thread_views.get(thread.id) if isinstance(thread, discord.Thread) else None

        if not view:
            if message.content.startswith("gz/"):
                await message.delete()
            return

        if message.content.startswith("gz/delete"):
            reason = message.content[10:].strip()
            if not reason:
                await message.delete()
                await message.channel.send("消去理由を指定してください。", delete_after=5)
                return

            embed = discord.Embed(
                title="メッセージ消去の投票",
                color=discord.Color.red(),
                timestamp=message.created_at
            )
            embed.add_field(name="消去理由", value=reason, inline=False)
            embed.add_field(name="実行者", value=f"{message.author.mention} (`{message.author.display_name}`)", inline=False)

            votes_info = ""
            for user_id, voters in view.delete_votes.items():
                if voters:
                    voters_text = ", ".join([f"`{voter.display_name}`" for voter in voters])
                    votes_info += f"\n• {voters_text}"
            
            if votes_info:
                embed.add_field(name="現在の投票状況", value=votes_info, inline=False)
            else:
                embed.add_field(name="現在の投票状況", value="まだ投票がありません", inline=False)

            await message.delete()
            await message.channel.send(embed=embed)

        elif message.content.startswith("gz/close"):
            embed = discord.Embed(
                title="スレッドロックの投票",
                color=discord.Color.blue(),
                timestamp=message.created_at
            )
            embed.add_field(name="実行者", value=f"{message.author.mention} (`{message.author.display_name}`)", inline=False)

            votes_info = ""
            for user_id, voters in view.close_votes.items():
                if voters:
                    voters_text = ", ".join([f"`{voter.display_name}`" for voter in voters])
                    votes_info += f"\n• {voters_text}"
            
            if votes_info:
                embed.add_field(name="現在の投票状況", value=votes_info, inline=False)
            else:
                embed.add_field(name="現在の投票状況", value="まだ投票がありません", inline=False)

            await message.delete()
            await message.channel.send(embed=embed)

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
        view_id = f"announcement_{interaction.user.id}_{int(time.time())}"
        view = SimpleAnnouncementView(self.bot, channel, view_id)
        await interaction.response.send_message(content="編集するとここにそのメッセージが表示されます", view=view)
        self._announcement_views[view_id] = view
        logger.info(f"Simple announcement prepared for channel: {channel.name} with view_id: {view_id}")

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
    def __init__(self, bot: commands.Bot, channel: discord.TextChannel, view_id: str) -> None:
        super().__init__(timeout=None)
        self.bot = bot
        self.channel = channel
        self.message: str = ""
        self.original_message: Optional[discord.Message] = None
        self.files: List[discord.File] = []
        self.view_id: str = view_id

    async def on_timeout(self):
        if self.original_message:
            await self.original_message.edit(view=None)

    async def convert_mentions(self, message: str) -> str:
        """@の後のテキストをメンションに変換"""
        lines = message.split('\n')
        converted_lines = []

        for line in lines:
            words = line.split()
            converted_words = []

            for word in words:
                if word.startswith('@'):
                    mention_name = word[1:]
                    role = discord.utils.get(self.channel.guild.roles, name=mention_name)
                    if role:
                        converted_words.append(role.mention)
                        continue
                    
                    member = discord.utils.get(self.channel.guild.members, display_name=mention_name)
                    if member:
                        converted_words.append(member.mention)
                        continue
                    
                    converted_words.append(word)
                else:
                    converted_words.append(word)
            
            converted_lines.append(' '.join(converted_words))
        
        return '\n'.join(converted_lines)

    @discord.ui.button(label="送信", style=discord.ButtonStyle.green)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # メッセージ内容を取得し、メンションを変換
        message_content = self.message.split("\n\n添付ファイル:")[0]
        converted_content = await self.convert_mentions(message_content)
        
        # シンプルにメッセージと添付ファイルを送信
        await self.channel.send(content=converted_content, files=self.files)
        
        # ボタンを無効化
        for item in self.children:
            item.disabled = True
        await interaction.message.edit(view=self)
        await interaction.response.send_message("メッセージを送信しました！", ephemeral=True)
        logger.info(f"Simple announcement sent to channel: {self.channel.name}")
        
        # ビューをクリーンアップ
        if hasattr(self.bot.cogs['Announcement'], '_announcement_views'):
            if self.view_id in self.bot.cogs['Announcement']._announcement_views:
                del self.bot.cogs['Announcement']._announcement_views[self.view_id]
        self.stop()

    @discord.ui.button(label="編集", style=discord.ButtonStyle.blurple)
    async def edit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.original_message = interaction.message
        await interaction.response.send_modal(SimpleEditModal(self.bot, self.message, self.channel, self.original_message, self.view_id))

    MAX_FILES = 10
    MAX_FILE_SIZE = 25 * 1024 * 1024

    @discord.ui.button(label="ファイル添付", style=discord.ButtonStyle.grey)
    async def attach_file_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if len(self.files) >= self.MAX_FILES:
            await interaction.response.send_message(f"添付ファイルは{self.MAX_FILES}個までです。", ephemeral=True)
            return

        if not self.original_message:
            self.original_message = interaction.message

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
            
            if len(self.files) >= self.MAX_FILES:
                for item in self.children:
                    if item.label == "ファイル添付":
                        item.disabled = True
            
            await self.original_message.edit(content=self.message, view=self)
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
    def __init__(self, bot: commands.Bot, message: str, channel: discord.TextChannel, original_message: discord.Message, view_id: str):
        super().__init__(title="メッセージ編集")
        self.bot = bot
        self.message = message
        self.channel = channel
        self.original_message = original_message
        self.view_id = view_id
        self.add_item(discord.ui.TextInput(
            label="メッセージ",
            default=message if message else "",
            style=discord.TextStyle.long,
            placeholder="ここにメッセージを入力してください"
        ))

    async def on_submit(self, interaction: discord.Interaction):
        new_message = self.children[0].value
        view = SimpleAnnouncementView(self.bot, self.channel, self.view_id)
        view.message = new_message
        view.original_message = self.original_message
        view.files = []
        await self.original_message.edit(content=new_message, view=view)
        await interaction.response.send_message("編集しました。", ephemeral=True)
        logger.info("Simple announcement message edited")

async def setup(bot):
    await bot.add_cog(Announcement(bot))