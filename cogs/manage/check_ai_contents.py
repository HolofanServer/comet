import discord
from discord.ext import commands
from discord import ui
import aiohttp
from typing import Optional, Dict, Any, List, Tuple, Callable
import asyncio
import json
from pathlib import Path

from utils.logging import setup_logging
from utils.error import handle_command_error
from utils.commands_help import is_guild, is_moderator, log_commands
from config.setting import get_settings

logger = setup_logging("D")
settings = get_settings()

class DeleteConfirmModal(ui.Modal, title="メッセージ削除の確認"):
    """メッセージ削除の確認モーダル"""
    
    reason = ui.TextInput(
        label="削除理由",
        placeholder="メッセージを削除する理由を入力してください",
        style=discord.TextStyle.paragraph,
        required=True,
        min_length=10
    )

    def __init__(self, callback: Callable):
        super().__init__()
        self.callback = callback

    async def on_submit(self, interaction: discord.Interaction):
        await self.callback(interaction, str(self.reason))

class DiscussionConfirmModal(ui.Modal, title="対応スレッド作成の確認"):
    """対応スレッド作成の確認モーダル"""
    
    reason = ui.TextInput(
        label="対応理由",
        placeholder="対応が必要な理由を入力してください",
        style=discord.TextStyle.paragraph,
        required=True,
        min_length=10
    )

    def __init__(self, callback: Callable):
        super().__init__()
        self.callback = callback

    async def on_submit(self, interaction: discord.Interaction):
        await self.callback(interaction, str(self.reason))

class ActionButtons(ui.View):
    """アラートメッセージのアクションボタン"""
    def __init__(self, original_message: discord.Message, alert_message: discord.Message, mod_channel_id: int):
        super().__init__(timeout=None)
        self.original_message = original_message
        self.alert_message = alert_message
        self.mod_channel_id = mod_channel_id
        
        self.add_item(discord.ui.Button(
            style=discord.ButtonStyle.link,
            label="メッセージを確認",
            emoji="🔍",
            url=self.original_message.jump_url
        ))

    async def delete_message_callback(self, interaction: discord.Interaction, reason: str):
        """メッセージ削除のコールバック"""
        try:
            await self.original_message.delete()

            embed = self.alert_message.embeds[0]
            embed.color = discord.Color.red()
            embed.title = f"🗑️ {embed.title} (削除済み)"
            embed.add_field(
                name="削除情報",
                value=f"削除実行者: {interaction.user.mention}\n"
                      f"削除理由: {reason}",
                inline=False
            )
            await self.alert_message.edit(embed=embed)
            
            await interaction.response.send_message(
                "メッセージを削除しました。",
                ephemeral=True
            )
        except discord.NotFound:
            await interaction.response.send_message(
                "メッセージはすでに削除されています。",
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "メッセージを削除する権限がありません。",
                ephemeral=True
            )

    @ui.button(label="メッセージを削除", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def delete_message(self, interaction: discord.Interaction, button: ui.Button):
        """メッセージを削除する（確認付き）"""
        modal = DeleteConfirmModal(self.delete_message_callback)
        await interaction.response.send_modal(modal)

    async def start_discussion_callback(self, interaction: discord.Interaction, reason: str):
        """対応スレッド作成のコールバック"""
        mod_channel = interaction.guild.get_channel(self.mod_channel_id)
        if not mod_channel:
            await interaction.response.send_message(
                "モデレーターチャンネルが見つかりません。",
                ephemeral=True
            )
            return

        preview = self.original_message.content[:10]
        if len(self.original_message.content) > 10:
            preview += "..."
        thread_name = f"🚨{self.original_message.author.display_name}の投稿: {preview}"

        thread = await mod_channel.create_thread(
            name=thread_name,
            type=discord.ChannelType.private_thread
        )
        
        mod_role = discord.utils.get(interaction.guild.roles, name="moderator")
        editor_role = discord.utils.get(interaction.guild.roles, name="編集部")
        
        if mod_role:
            for member in mod_role.members:
                if editor_role and editor_role in member.roles:
                    logger.debug(f"Skipping editor {member.display_name}")
                    continue
                
                try:
                    await thread.add_user(member)
                except discord.HTTPException:
                    logger.warning(f"Could not add {member.display_name} to thread")
                    continue
        
        embed = discord.Embed(
            title="メッセージ対応スレッド",
            description=f"このスレッドは検出されたメッセージの対応のために作成されました。\n\n"
                       f"**対応理由**\n{reason}",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="対象メッセージ",
            value=f"[メッセージを確認]({self.original_message.jump_url})",
            inline=False
        )
        embed.add_field(
            name="ユーザー",
            value=f"{self.original_message.author.mention} (`{self.original_message.author.display_name}`)",
            inline=False
        )
        embed.add_field(
            name="対応開始者",
            value=interaction.user.mention,
            inline=False
        )
        
        await thread.send(embed=embed)
        await interaction.response.send_message(
            f"対応スレッドを作成しました: {thread.jump_url}",
            ephemeral=True
        )

    @ui.button(label="対応を開始", style=discord.ButtonStyle.success, emoji="💬")
    async def start_discussion(self, interaction: discord.Interaction, button: ui.Button):
        """モデレーターチャンネルでの対応を開始（確認付き）"""
        modal = DiscussionConfirmModal(self.start_discussion_callback)
        await interaction.response.send_modal(modal)

class AIContentChecker(commands.Cog):
    """AIコンテンツと長文を検出するためのCog"""

    def __init__(self, bot):
        self.bot = bot
        self.api_key = settings.etc_api_undetectable_ai_key
        self.session = aiohttp.ClientSession()
        self.threshold = 50
        self.log_channel_id = None
        self.long_text_threshold = 400
        self.data_dir = Path("data/aicheck")
        self.mod_channel_id = None
        self.load_data()

    def cog_unload(self):
        """Cogのアンロード時にセッションを閉じる"""
        if self.session:
            self.bot.loop.create_task(self.session.close())

    def save_data(self):
        """設定をJSONファイルに保存します"""
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            
            data = {
                "threshold": self.threshold,
                "log_channel_id": self.log_channel_id,
                "long_text_threshold": self.long_text_threshold,
                "mod_channel_id": self.mod_channel_id
            }
            
            with open(self.data_dir / "settings.json", "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            logger.info("Settings saved successfully")
        except Exception as e:
            logger.error(f"Error saving settings: {e}")
    
    def load_data(self):
        """JSONファイルから設定を読み込みます"""
        try:
            settings_file = self.data_dir / "settings.json"
            if not settings_file.exists():
                logger.info("Settings file not found, using default values")
                return
            
            with open(settings_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            self.threshold = data.get("threshold", self.threshold)
            self.log_channel_id = data.get("log_channel_id", self.log_channel_id)
            self.long_text_threshold = data.get("long_text_threshold", self.long_text_threshold)
            self.mod_channel_id = data.get("mod_channel_id", self.mod_channel_id)
            logger.info("Settings loaded successfully")
        except Exception as e:
            logger.error(f"Error loading settings: {e}")

    @commands.hybrid_group(name="aicheck")
    @is_guild()
    @is_moderator()
    @log_commands()
    async def aicheck(self, ctx):
        """AIチェック関連のコマンドグループ"""
        if ctx.invoked_subcommand is None:
            await ctx.send("サブコマンドを指定してください。")

    @aicheck.command(name="set_log_channel")
    @is_guild()
    @is_moderator()
    @log_commands()
    async def set_log_channel(self, ctx, channel: discord.TextChannel):
        try:
            self.log_channel_id = channel.id
            await ctx.send(f"AI検出時のログを {channel.mention} に設定しました。")
            logger.info(f"Log channel set to {channel.name} by {ctx.author} in {ctx.guild.name}")
            self.save_data()
        except Exception as e:
            logger.error(f"Error setting log channel: {e}")
            await handle_command_error(ctx, e, settings.admin_error_log_channel_id)

    @aicheck.command(name="set_mod_channel")
    @is_guild()
    @is_moderator()
    @log_commands()
    async def set_mod_channel(self, ctx, channel: discord.TextChannel):
        """モデレーターチャンネルを設定します"""
        try:
            self.mod_channel_id = channel.id
            await ctx.send(f"モデレーターチャンネルを {channel.mention} に設定しました。")
            logger.info(f"Moderator channel set to {channel.name} by {ctx.author} in {ctx.guild.name}")
            self.save_data()
        except Exception as e:
            logger.error(f"Error setting moderator channel: {e}")
            await handle_command_error(ctx, e, settings.admin_error_log_channel_id)

    @aicheck.command(name="set_long_text_threshold")
    @is_guild()
    @is_moderator()
    @log_commands()
    async def set_long_text_threshold(self, ctx, threshold: int):
        """長文判定の文字数しきい値を設定します"""
        try:
            if threshold < 100:
                await ctx.send("しきい値は100文字以上に設定してください。")
                return
            self.long_text_threshold = threshold
            await ctx.send(f"長文判定のしきい値を{threshold}文字に設定しました。")
            logger.info(f"Long text threshold set to {threshold} by {ctx.author} in {ctx.guild.name}")
            self.save_data()
        except Exception as e:
            logger.error(f"Error setting long text threshold: {e}")
            await handle_command_error(ctx, e, settings.admin_error_log_channel_id)

    async def detect_ai_content(self, text: str) -> Optional[Dict[str, Any]]:
        """UndetectableAI APIを使用してテキストがAIによって生成されたかどうかを判定します"""
        logger.debug(f"AI detection for text of length: {len(text)}")
        if not self.api_key:
            logger.warning("UndetectableAI API key is not set")
            return None

        detect_url = "https://ai-detect.undetectable.ai/detect"
        detect_payload = {
            "text": text,
            "key": self.api_key,
            "model": "detector_v2"
        }

        try:
            async with self.session.post(detect_url, json=detect_payload) as response:
                if response.status != 200:
                    logger.error(f"Detection API error: {response.status}")
                    return None
                detect_data = await response.json()
                logger.debug(f"Detection API response: {detect_data}")

            query_url = "https://ai-detect.undetectable.ai/query"
            query_payload = {"id": detect_data["id"]}

            max_retries = 10
            for retry in range(max_retries):
                async with self.session.post(query_url, json=query_payload) as response:
                    if response.status != 200:
                        logger.error(f"Query API error: {response.status}")
                        return None
                    
                    result = await response.json()
                    logger.debug(f"Query API response (retry {retry}): {result}")
                    
                    if result.get("status") == "done":
                        return result
                    elif result.get("status") == "error":
                        logger.error(f"API returned error status: {result}")
                        return None

                    await asyncio.sleep(0.5)
            
            logger.warning(f"Max retries ({max_retries}) reached, giving up")
            return None

        except Exception as e:
            logger.error(f"Error in AI detection: {e}")
            return None

    async def send_alert(self, message: discord.Message, alerts: List[Tuple[str, str]]):
        """アラートをログチャンネルに送信します"""
        if not self.log_channel_id:
            return

        try:
            log_channel = self.bot.get_channel(self.log_channel_id)
            if not log_channel:
                logger.error(f"Could not find log channel with ID {self.log_channel_id}")
                return

            alert_types = [alert[0] for alert in alerts]
            embed = discord.Embed(
                title=f"⚠️ {' & '.join(alert_types)}を検出",
                color=discord.Color.yellow(),
                timestamp=message.created_at
            )

            content_preview = message.content[:1000]
            if len(message.content) > 1000:
                content_preview += "..."
            embed.description = f"**メッセージ内容**\n```\n{content_preview}\n```"

            details = "\n".join([f"・{alert[0]}: {alert[1]}" for alert in alerts])
            embed.add_field(
                name="🚨 検出内容",
                value=details,
                inline=False
            )

            basic_info = (
                f"📝 {message.channel.mention} | "
                f"🆔 {message.id}"
            )
            embed.add_field(
                name="基本情報",
                value=basic_info,
                inline=False
            )

            user_info = (
                f"👤 {message.author.mention} (`{message.author.display_name}`)\n"
                f"🆔 {message.author.id}"
            )
            embed.add_field(
                name="ユーザー",
                value=user_info,
                inline=True
            )

            stats = (
                f"📊 {len(message.content):,}文字 | "
                f"📝 {len(message.content.splitlines()):,}行\n"
                f"📎 {len(message.attachments)}個の添付 | "
                f"🔖 {len(message.embeds)}個の埋め込み"
            )
            embed.add_field(
                name="統計",
                value=stats,
                inline=True
            )

            if message.attachments:
                files = "\n".join([
                    f"・`{attach.filename}` ({attach.content_type}, {attach.size:,} bytes)"
                    for attach in message.attachments
                ])
                embed.add_field(
                    name="📎 添付ファイル",
                    value=f"```\n{files}\n```",
                    inline=False
                )

            embed.set_thumbnail(url=message.author.display_avatar.url)

            view = ActionButtons(message, None, self.mod_channel_id)
            alert_message = await log_channel.send(embed=embed, view=view)

            view.alert_message = alert_message

            logger.info(
                f"Alert sent: {' & '.join(alert_types)} | "
                f"User: {message.author.display_name} ({message.author.id}) | "
                f"Channel: #{message.channel.name}"
            )
        except Exception as e:
            logger.error(f"Error sending alert: {e}")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """メッセージを受信したときにAI判定と長文判定を行います"""
        if message.author.bot or not self.log_channel_id:
            return

        try:
            alerts = []

            is_long_text = len(message.content) >= self.long_text_threshold
            if is_long_text:
                alerts.append(("長文メッセージ", f"メッセージ長: {len(message.content)}文字"))

            is_ai_content = False
            human_score = None
            if self.api_key:
                logger.info(f"Checking message {message.id} from {message.author} in {message.guild.name}")
                result = await self.detect_ai_content(message.content)
                
                if result and result.get("status") == "done":
                    human_score = result.get("result_details", {}).get("human", 0)
                    logger.info(f"Message {message.id} - Human score: {human_score}%")
                    is_ai_content = human_score < self.threshold
                    if is_ai_content:
                        alerts.append(("AI生成コンテンツ", f"人間らしさスコア: {human_score}%"))

            if len(alerts) > 0:
                await self.send_alert(message, alerts)

        except Exception as e:
            logger.error(f"Error processing message {message.id}: {e}")

async def setup(bot):
    await bot.add_cog(AIContentChecker(bot))