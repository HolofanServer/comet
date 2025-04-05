import discord
from discord.ext import commands
from discord.ui import View, Button
from discord import app_commands

import pytz
from datetime import datetime
import random
import re

from utils.commands_help import is_moderator, is_guild, log_commands
from utils.logging import setup_logging
from utils.sudo.json_manager import JSONManager
from utils.sudo.timer_manager import TimerManager
from utils.sudo.role_manager import RoleManager

logger = setup_logging("D")


class SudoControlView(View):
    def __init__(self, cog, session_id):
        super().__init__(timeout=None)
        self.cog = cog
        self.session_id = session_id

    async def _has_permission(self, interaction: discord.Interaction):
        """ボタンを押す権限があるか確認"""
        if not interaction.guild:
            await interaction.response.send_message("このコマンドはサーバー内でのみ使用できます。", ephemeral=True)
            logger.warning(f"DMからのボタン操作が試行されました。ユーザー: {interaction.user.id}")
            return False
            
        session = self.cog.sessions.get(self.session_id)
        if not session:
            await interaction.response.send_message("このセッションは既に終了しています。", ephemeral=True)
            return False
            
        if interaction.guild.id != session["guild_id"]:
            await interaction.response.send_message("このセッションは別のサーバーのものです。", ephemeral=True)
            logger.warning(f"別のサーバーからのセッション操作が試行されました。ユーザー: {interaction.user.id}")
            return False

        user_id = interaction.user.id
        if user_id not in {session["executor"], session["affected_member"]}:
            await interaction.response.send_message("このボタンを操作する権限がありません。", ephemeral=True)
            return False

        return True

    @discord.ui.button(label="延長（5分）", style=discord.ButtonStyle.green, custom_id="extend")
    async def extend_button(self, interaction: discord.Interaction, button: Button):
        if not await self._has_permission(interaction):
            return

        session = self.cog.sessions.get(self.session_id)
        remaining_time = session["remaining_time"]
        new_time = min(remaining_time + 300, 1800)
        session["remaining_time"] = new_time
        self.cog.sessions[self.session_id] = session
        self.cog.session_manager.save(self.cog.sessions)
        
        new_time_stamp = int(datetime.now().timestamp() + new_time)

        message = await interaction.channel.fetch_message(session["message_id"])
        embed = message.embeds[0]
        
        now_utc = datetime.utcnow()
        original_end_time = int(now_utc.timestamp() + remaining_time)
        logger.debug(f"original_end_time: {original_end_time}")
        logger.debug(f"置換前の説明: {embed.description}")

        embed.description = re.sub(
            r"終了予定時間: <t:\d+> \| <t:\d+:R>",
            f"~~終了予定時間: <t:{original_end_time}> | <t:{original_end_time}:R>~~",
            embed.description
        )
        logger.debug(f"置換後の説明: {embed.description}")
        
        if "延長情報" in [field.name for field in embed.fields]:
            embed.set_field_at(index=0, name="延長情報", value=f"セッションが5分延長されました。\n新しい残り時間: \n<t:{new_time_stamp}> | <t:{new_time_stamp}:R>", inline=False)
        else:
            embed.add_field(name="延長情報", value=f"セッションが5分延長されました。\n新しい残り時間: \n<t:{new_time_stamp}> | <t:{new_time_stamp}:R>", inline=False)
        
        embed_log = embed.copy()
        logger.debug(f"延長されたセッションのログ: {embed_log}")
        await message.edit(embed=embed)

        await self.cog.timer_manager.start_timer(
            session["affected_member"], self.session_id, new_time, self.cog.remove_role_after_delay
        )
        logger.debug(f"新しい残り時間: {new_time // 60}分")
        if new_time > 1800:
            await interaction.response.send_message(
                "延長できる時間は最大30分です。", ephemeral=True
            )
            logger.info(f"セッション {self.session_id} が延長できる時間は最大30分です。")
        else:
            await interaction.response.send_message(
                f"セッションが5分延長されました。残り時間: {new_time // 60}分", ephemeral=True
            )
        logger.info(f"セッション {self.session_id} が5分延長されました。残り時間: {new_time // 60}分")

    @discord.ui.button(label="終了", style=discord.ButtonStyle.red, custom_id="end")
    async def end_button(self, interaction: discord.Interaction, button: Button):
        if not await self._has_permission(interaction):
            return

        try:
            session = self.cog.sessions.get(self.session_id)
            if not session:
                await interaction.response.send_message("このセッションは既に終了しています。", ephemeral=True)
                return
                
            guild = self.cog.bot.get_guild(session["guild_id"])
            if not guild:
                await interaction.response.send_message("サーバーが見つかりませんでした。", ephemeral=True)
                logger.error(f"セッション {self.session_id} のギルドが見つかりませんでした。")
                return
                
            member = guild.get_member(session["affected_member"])
            role = self.cog.role_manager.get_role_by_id(guild, session["role_id"])
        
            message = await interaction.channel.fetch_message(session["message_id"])
            embed = message.embeds[0]
            
            now_utc = datetime.utcnow()
            original_end_time = int(now_utc.timestamp() + session["remaining_time"])
            logger.debug(f"original_end_time: {original_end_time}")
            logger.debug(f"置換前の説明: {embed.description}")

            embed.description = re.sub(
                r"終了予定時間: <t:\d+> \| <t:\d+:R>",
                f"~~終了予定時間: <t:{original_end_time}> | <t:{original_end_time}:R>~~",
                embed.description
            )
            logger.debug(f"置換後の説明: {embed.description}")
            
            if embed.fields:
                embed.fields[0].value = embed.fields[0].value.replace(
                    f"延長されました。\n新しい終了予定時間: <t:{int(datetime.now().timestamp() + session['remaining_time'])}> | <t:{int(datetime.now().timestamp() + session['remaining_time'])}:R>",
                    f"~~延長されました。\n新しい終了予定時間: <t:{int(datetime.now().timestamp() + session['remaining_time'])}> | <t:{int(datetime.now().timestamp() + session['remaining_time'])}:R>~~"
                )
            
            now_time_stamp = int(datetime.now().timestamp())
            embed.add_field(name="終了情報", value=f"<t:{now_time_stamp}> | <t:{now_time_stamp}:R>に終了されました。", inline=False)
            embed.color = discord.Color.red()
            
            view = SudoControlView(self.cog, self.session_id)
            for child in view.children:
                child.disabled = True
            await message.edit(embed=embed, view=view)

            if member and role:
                await member.remove_roles(role)
                self.cog.sessions.pop(self.session_id)
                self.cog.session_manager.save(self.cog.sessions)

                await interaction.response.send_message("セッションが終了しました。", ephemeral=True)
                
                logger.info(f"セッション {self.session_id} が終了しました。")
            else:
                await interaction.response.send_message("ユーザーまたはロールが見つかりませんでした。", ephemeral=True)
                logger.warning(f"セッション {self.session_id} でユーザーまたはロールが見つかりませんでした。")
        except Exception as e:
            logger.error(f"セッション終了中にエラーが発生しました: {e}")
            await interaction.response.send_message("セッションの終了中にエラーが発生しました。管理者にお問い合わせください。", ephemeral=True)


class SudoCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session_manager = JSONManager("data/sudo/sessions.json", {"sessions": {}})
        self.archived_manager = JSONManager("data/sudo/sessions_archived.json", {})
        self.config_manager = JSONManager("config/sudo.json", {"roles": {}})
        self.role_manager = RoleManager(self.config_manager)
        self.timer_manager = TimerManager()

        try:
            self.sessions = self.session_manager.load()
            self._validate_sessions()
            logger.debug("SudoCog initialized with sessions: %s", self.sessions)
        except Exception as e:
            logger.error(f"セッションのロード中にエラーが発生しました: {e}")
            self.sessions = {}
            
    def _validate_sessions(self):
        """セッションの整合性をチェックし、無効なセッションを削除します"""
        invalid_sessions = []
        for session_id, session in list(self.sessions.items()):
            required_keys = ["guild_id", "affected_member", "role_id", "executor", "remaining_time"]
            if not all(key in session for key in required_keys):
                logger.warning(f"無効なセッション（必須キー不足）: {session_id}")
                invalid_sessions.append(session_id)
                continue
                
            guild = self.bot.get_guild(session["guild_id"])
            if not guild:
                logger.warning(f"無効なセッション（ギルド不在）: {session_id}")
                invalid_sessions.append(session_id)
                continue
            
        for session_id in invalid_sessions:
            self.sessions.pop(session_id, None)
            
        if invalid_sessions:
            logger.info(f"{len(invalid_sessions)}件の無効なセッションを削除しました")
            self.session_manager.save(self.sessions)

    def generate_unique_session_id(self):
        all_possible_ids = list(range(1000, 10000))
        while True:
            new_id = str(random.choice(all_possible_ids))
            if new_id not in self.sessions:
                return new_id

    async def remove_role_after_delay(self, session_id):
        logger.info(f"セッション {session_id} のロールを削除します。")
        session = self.sessions.get(session_id)
        if not session:
            logger.warning(f"セッション {session_id} が見つかりませんでした。")
            return

        guild = self.bot.get_guild(session["guild_id"])
        if not guild:
            logger.error(f"ギルド {session['guild_id']} が見つかりませんでした。")
            return

        member = guild.get_member(session["affected_member"])
        if not member:
            logger.error(f"メンバー {session['affected_member']} が見つかりませんでした。")
            return

        role = self.role_manager.get_role_by_id(guild, session["role_id"])
        if not role:
            logger.error(f"ロール {session['role_id']} が見つかりませんでした。")
            return

        await member.remove_roles(role)
        logger.info(f"ユーザー {member.mention} からロール {role.mention} を剥奪しました。")
        self.sessions.pop(session_id)
        logger.info(f"セッション {session_id} を削除しました。")
        self.session_manager.save(self.sessions)
        logger.info(f"セッション {session_id} をJSONファイルに保存しました。")

        channel = guild.get_channel(session["channel_id"])
        if not channel:
            logger.error(f"チャンネル {session['channel_id']} が見つかりませんでした。")
            return

        logger.info(f"チャンネル {channel.name} を取得しました。")
        try:
            message = await channel.fetch_message(session["message_id"])
            logger.info(f"メッセージ {message.id} を取得しました。")
            view = SudoControlView(self, session_id)
            logger.info(f"ビュー {view} を取得しました。")
            for child in view.children:
                child.disabled = True
            
            embed = message.embeds[0]
            logger.info(f"埋め込み {embed} を取得しました。")
            embed.description = f"~~{embed.description}~~"
            embed.add_field(name="終了通知", value=f"{member.mention}から{role.mention}を剥奪しました")
            embed.color = discord.Color.red()

            await message.edit(embed=embed, view=view)
            await channel.send(f"{member.mention}\nこのsudoは終了しました。", delete_after=10)
            logger.info(f"メッセージ {message.id} を編集しました。")
        except discord.errors.NotFound:
            logger.error(f"メッセージが見つかりませんでした。セッションID: {session_id}")
        except Exception as e:
            logger.error(f"メッセージの編集中にエラーが発生しました: {e}")

        logger.info(f"セッション {session_id} ロールが削除されました。")

    def save_config_to_json(self):
        """現在の設定をJSONファイルに保存します。"""
        current_data = self.config_manager.load()
        current_data['roles'] = {"default_role": self.sessions.get('role')}
        self.config_manager.save(current_data)
        data = self.config_manager.load()
        logger.info(f"設定がJSONファイルに保存されました。: {data}")

    @commands.hybrid_command(name="sudo", description="一時的な権限を付与します。")
    @is_moderator()
    @is_guild()
    @commands.guild_only()
    @log_commands()
    @app_commands.rename(time="時間")
    @app_commands.rename(user="付与するユーザー")
    @app_commands.rename(reason="目的または理由")
    @app_commands.describe(
        time="sudoの時間を指定します（秒単位）",
        user="sudoを付与するユーザー",
        reason="sudoを付与する理由",
    )
    @app_commands.choices(time=[
        app_commands.Choice(name="5分", value=300),
        app_commands.Choice(name="10分", value=600),
        app_commands.Choice(name="30分", value=1800),
        app_commands.Choice(name="1時間", value=3600),
        app_commands.Choice(name="3時間", value=10800),
    ])
    async def sudo(self, ctx: commands.Context, user: discord.Member, reason: str, time: int):
        if not ctx.guild:
            await ctx.send("このコマンドはサーバー内でのみ使用できます。", ephemeral=True)
            logger.warning(f"DMからのsudoコマンドが試行されました。ユーザー: {ctx.author.id}")
            return
            
        if user.bot:
            await ctx.send("ボットにsudoを付与することはできません。", ephemeral=True)
            logger.warning(f"ボットへのsudo付与が試行されました。実行者: {ctx.author.id}")
            return
            
        logger.debug(f"Current sessions: {self.sessions}")
        for session in self.sessions.values():
            if (isinstance(session, dict) and 
                session.get("affected_member") == user.id and 
                session.get("guild_id") == ctx.guild.id):
                await ctx.send("このユーザーはすでにsudoを実行済みです。", ephemeral=True)
                logger.warning(f"ユーザー {user} はすでにsudoを実行済みです。ギルドID: {ctx.guild.id}")
                return

        role_ids = self.role_manager.load_roles()
        role = self.role_manager.get_role_by_id(ctx.guild, role_ids.get("default_role"))

        if not role:
            await ctx.send("指定されたロールが見つかりませんでした。", ephemeral=True)
            logger.warning(f"指定されたロールが見つかりませんでした。ユーザー: {user}, 理由: {reason}")
            return

        session_id = self.generate_unique_session_id()
        now = datetime.now(pytz.timezone("Asia/Tokyo"))
        now_utc = now.astimezone(pytz.utc)
        end_time = now.timestamp() + time

        embed = discord.Embed(
            title="sudoコマンドログ",
            description=(
                f"{user.mention}に{role.mention}を付与しました。\n\n"
                f"理由: {reason}\n"
                f"終了予定: <t:{int(end_time)}> | <t:{int(end_time)}:R>"
            ),
            color=discord.Color.green(),
            timestamp=now,
        )
        embed.set_footer(text="🟢延長ボタンで最大30分延長可能です。")

        await user.add_roles(role)
        view = SudoControlView(self, session_id)
        message = await ctx.send(embed=embed, view=view)

        self.sessions[session_id] = {
            "time": now_utc.isoformat(),
            "executor": ctx.author.id,
            "affected_member": user.id,
            "role_id": role.id,
            "guild_id": ctx.guild.id,
            "channel_id": ctx.channel.id,
            "remaining_time": time,
            "message_id": message.id,
        }
        self.session_manager.save(self.sessions)

        await self.timer_manager.start_timer(user.id, session_id, time, self.remove_role_after_delay)
        logger.info(f"セッション {session_id} が作成されました。ユーザー: {user}, 理由: {reason}, 時間: {time}秒")

    @commands.hybrid_group(name="sd", description="sudoコマンドのグループです。")
    async def sd(self, ctx: commands.Context):
        if not ctx.guild:
            await ctx.send("このコマンドはサーバー内でのみ使用できます。", ephemeral=True)
            logger.warning(f"DMからのsdコマンドが試行されました。ユーザー: {ctx.author.id}")
            return
        pass

    @sd.group(name="add", description="")
    async def add(self, ctx: commands.Context):
        if not ctx.guild:
            await ctx.send("このコマンドはサーバー内でのみ使用できます。", ephemeral=True)
            logger.warning(f"DMからのsd addコマンドが試行されました。ユーザー: {ctx.author.id}")
            return
        pass

    @add.command(name="role", description="sudoで付与するロールを追加します。")
    @is_moderator()
    @is_guild()
    @app_commands.rename(role="権限レベル")
    async def role(self, ctx: commands.Context, role: discord.Role):
        self.sessions['role'] = role.id
        self.save_config_to_json()
        e = discord.Embed(
            title="sudoコマンドログ",
            description=f"ロールを追加しました。\n\n{role.mention}",
            color=discord.Color.green(),
        )
        await ctx.send(embed=e, ephemeral=True)
        logger.info(f"ロール {role.mention} が追加されました。")

async def setup(bot):
    await bot.add_cog(SudoCog(bot))
