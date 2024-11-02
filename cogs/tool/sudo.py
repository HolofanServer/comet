import discord
from discord.ext import commands
from discord import app_commands

import json
import random
import asyncio
import os
import pytz

from datetime import datetime

from utils.logging import setup_logging
from utils.commands_help import is_guild, is_moderator

logger = setup_logging()

class SudoCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.sessionafile = 'data/sudo/sessions_archived.json'
        self.sessionfile = 'data/sudo/sessions.json'
        self.sessions = self.load_sessions_from_json()
        self.archived_sessions = self.load_archived_from_json()
        self.user_timers = {}

    def save_archived_to_json(self):
        with open(self.sessionafile, "w", encoding='utf-8') as f:
            json.dump(self.archived_sessions, f, ensure_ascii=False, indent=4)

    def archive_session(self, session_id):
        self.archived_sessions[session_id] = self.sessions.pop(session_id)
        self.save_archived_to_json()

    def save_sessions_to_json(self):
        with open(self.sessionfile, "w", encoding='utf-8') as f:
            json.dump(self.sessions, f, ensure_ascii=False, indent=4)

    def load_sessions_from_json(self):
        try:
            with open(self.sessionfile, "r") as f:
                data = json.load(f)
                return data.get("sessions", {})
        except FileNotFoundError:
            os.makedirs(os.path.dirname(self.sessionfile), exist_ok=True)
            with open(self.sessionfile, "w") as f:
                json.dump({"sessions": {}}, f, ensure_ascii=False, indent=4)
            return {}

    def load_archived_from_json(self):
        try:
            with open(self.sessionafile, "r") as f:
                data = json.load(f)
                return data
        except FileNotFoundError:
            os.makedirs(os.path.dirname(self.sessionafile), exist_ok=True)
            with open(self.sessionafile, "w") as f:
                json.dump({"sessions": {}}, f, ensure_ascii=False, indent=4)
            return {}

    def save_config_to_json(self):
        with open('config/sudo.json', "w", encoding='utf-8') as f:
            if not os.path.exists('config/sudo.json'):
                os.makedirs(os.path.dirname('config/sudo.json'), exist_ok=True)
                json.dump(self.sessions, f, ensure_ascii=False, indent=4)
            else:
                data = self.load_config_from_json()
                data['roles'] = self.sessions
                json.dump(data, f, ensure_ascii=False, indent=4)

    def load_config_from_json(self):
        try:
            with open('config/sudo.json', "r", encoding='utf-8') as f:
                data = json.load(f)
                return data
        except (FileNotFoundError, json.JSONDecodeError):
            os.makedirs(os.path.dirname('config/sudo.json'), exist_ok=True)
            with open('config/sudo.json', "w", encoding='utf-8') as f:
                json.dump({"roles": {}}, f, ensure_ascii=False, indent=4)
            return {"roles": {}}

    async def remove_role_after_delay(self, user, role, session_id, ctx):
        if ctx.bot.user.id != self.bot.user.id:
            return
        try:
            session = self.sessions.get(session_id, {})
            message_id = session.get('message_id')
            message = await ctx.fetch_message(message_id)

            if message.embeds:
                first_embed = message.embeds[0]
            else:
                return

            remaining_time = session.get('remaining_time', 0)
            while remaining_time > 0:
                await asyncio.sleep(1)
                session = self.sessions.get(session_id, {})
                remaining_time = session.get('remaining_time', 0)
                remaining_time -= 1
                session['remaining_time'] = remaining_time
                self.sessions[session_id] = session
                self.save_sessions_to_json()
                if remaining_time == 0:
                    await user.remove_roles(role)

                    first_embed.description = f"~~{first_embed.description}~~"
                    first_embed.add_field(name="終了通知", value=f"{user.mention}から{role.mention}を剥奪しました")
                    first_embed.color = discord.Color.red()
                    first_embed.set_author(name=f"ID : {session_id}")
                    try:
                        await message.edit(embed=first_embed)
                        await ctx.send(f"{user.mention}\nこのsudoは終了しました。", delete_after=10)
                    except discord.errors.NotFound:
                        channel = self.bot.get_channel(ctx.channel_id)
                        if channel:
                            await channel.send(embed=first_embed)
                            await channel.send(f"{user.mention}\nこのsudoは終了しました。", delete_after=10)

                    self.archive_session(session_id)
                    del self.user_timers[user.id]
        except Exception as e:
            logger.error(f"Error in remove_role_after_delay: {e}")
            pass

    def generate_unique_session_id(self):
        all_possible_ids = list(range(1000, 10000))
        while True:
            new_id = str(random.choice(all_possible_ids))
            if new_id not in self.sessions:
                return new_id

    def load_sudo_roles(self):
        data = self.load_config_from_json()
        roles = data.get('roles', {})
        role1_id = roles.get('role1', None)
        role2_id = roles.get('role2', None)
        role3_id = roles.get('role3', None)
        return role1_id, role2_id, role3_id

    @commands.hybrid_command(name="sudo", description="特定の権限を付与します。")
    @is_moderator()
    @is_guild()
    @app_commands.choices(permission=[
        app_commands.Choice(name="権限レベル1", value="権限レベル1"),
        app_commands.Choice(name="権限レベル2", value="権限レベル2"),
        app_commands.Choice(name="権限レベル3", value="権限レベル3")
    ])
    async def sudo(self, ctx: commands.Context, user: discord.Member, reason: str, permission: app_commands.Choice[str]):
        executor = ctx.author

        role_ids = self.load_sudo_roles()
        role_id_map = {
            "権限レベル1": role_ids[0],
            "権限レベル2": role_ids[1],
            "権限レベル3": role_ids[2]
        }
        role_id = role_id_map.get(permission.name)

        if role_id is None:
            await ctx.send("指定された権限レベルに対応するロールが設定されていません。", ephemeral=True)
            return

        role = discord.utils.get(ctx.guild.roles, id=role_id)

        if role is None:
            await ctx.send("指定されたロールが見つかりませんでした", ephemeral=True)
            return

        session_id = self.generate_unique_session_id()

        jst = pytz.timezone('Asia/Tokyo')
        now = datetime.now(jst)
        goodtime = now.timestamp() + 600

        e = discord.Embed(
            title="sudoコマンドログ",
            description=f"{user.mention}に{role.mention}を付与しました。\n\n理由：{reason}\n終了予定時間: <t:{int(goodtime)}> | <t:{int(goodtime)}:R>",
            color=discord.Color.green(),
            timestamp=now
        )
        e.set_footer(text="🟢延長ボタンを押すことで最大30分まで時間を延長できません。")
        e.set_author(name=f"ID：{session_id}")

        await ctx.author.add_roles(role)
        message = await ctx.send(embed=e)

        self.sessions[session_id] = {
            'time': now.strftime('%Y-%m-%d %H:%M:%S'),
            'executor': executor.display_name,
            'executor_id': executor.id,
            'affected_member': user.id,
            'role': role.name,
            'role_id': role.id,
            'reason': reason,
            'remaining_time': 600,
            'message_id': message.id
        }
        self.save_sessions_to_json()
        try:
            timer_task = asyncio.create_task(self.remove_role_after_delay(user, role, session_id, ctx))
        except Exception as e:
            logger.error(f"Error in remove_role_after_delay: {e}")
            pass
        old_timer = self.user_timers.get(user.id)
        if old_timer:
            old_timer.cancel()

        self.user_timers[user.id] = {
            'task': timer_task,
            'session_id': session_id
        }

    @commands.hybrid_group(name="sd", description="sudoコマンドのグループです。")
    async def sd(self, ctx: commands.Context):
        pass

    @sd.group(name="add", description="")
    async def add(self, ctx: commands.Context):
        pass

    @add.command(name="role", description="sudoで付与するロールを追加します。")
    @is_moderator()
    @is_guild()
    @app_commands.rename(role1="権限レベル1", role2="権限レベル2", role3="権限レベル3")
    async def role(self, ctx: commands.Context, role1: discord.Role, role2: discord.Role, role3: discord.Role):
        self.sessions['role1'] = role1.id
        self.sessions['role2'] = role2.id
        self.sessions['role3'] = role3.id
        self.save_config_to_json()
        e = discord.Embed(
            title="sudoコマンドログ",
            description=f"ロールを追加しました。\n\n{role1.mention}\n{role2.mention}\n{role3.mention}",
            color=discord.Color.green(),
        )
        await ctx.send(embed=e, ephemeral=True)

    @commands.hybrid_command(name="beta_sudo", description="sudo機能β版です。")
    @is_moderator()
    @is_guild()
    @app_commands.rename(time="時間")
    @app_commands.rename(user="付与するユーザー")
    @app_commands.rename(reason="目的-or-理由")
    @app_commands.describe(time="sudoの時間を指定します。")
    @app_commands.describe(user="sudoを付与するユーザーを指定します。")
    @app_commands.describe(reason="sudoを付与する目的-or-理由を指定します。")
    @app_commands.choices(time=[
        app_commands.Choice(name="5分", value=300),
        app_commands.Choice(name="10分", value=600),
        app_commands.Choice(name="30分", value=1800),
        app_commands.Choice(name="1時間", value=3600),
        app_commands.Choice(name="3時間", value=10800),
    ])
    async def beta_sudo(self, ctx: commands.Context, user: discord.Member, reason: str, time: int):
        executor = ctx.author
        
        role_ids = self.load_sudo_roles()

        role = discord.utils.get(ctx.guild.roles, id=role_ids[2])

        if role is None:
            await ctx.send("指定されたロールが見つかりませんでした", ephemeral=True)
            return

        session_id = self.generate_unique_session_id()

        jst = pytz.timezone('Asia/Tokyo')
        now = datetime.now(jst)
        goodtime = now.timestamp() + time

        e = discord.Embed(
            title="sudoコマンドログ",
            description=f"{user.mention}に{role.mention}を付与しました。\n\n理由：{reason}\n終了予定時間: <t:{int(goodtime)}> | <t:{int(goodtime)}:R>",
            color=discord.Color.green(),
            timestamp=now
        )
        e.set_footer(text="🟢延長ボタンを押すことで最大30分まで時間を延長できません。")
        e.set_author(name=f"ID：{session_id}")

        await ctx.author.add_roles(role)
        message = await ctx.send(embed=e)

        self.sessions[session_id] = {
            'time': now.strftime('%Y-%m-%d %H:%M:%S'),
            'executor': executor.display_name,
            'executor_id': executor.id,
            'affected_member': user.id,
            'role': role.name,
            'role_id': role.id,
            'reason': reason,
            'remaining_time': time,
            'message_id': message.id
        }
        self.save_sessions_to_json()
        try:
            timer_task = asyncio.create_task(self.remove_role_after_delay(user, role, session_id, ctx))
        except Exception as e:
            logger.error(f"Error in remove_role_after_delay: {e}")
            pass
        old_timer = self.user_timers.get(user.id)
        if old_timer:
            old_timer.cancel()

        self.user_timers[user.id] = {
            'task': timer_task,
            'session_id': session_id
        }

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.user.id != self.bot.user.id:
            return
        if interaction.type == discord.InteractionType.component:
            user_timer = self.user_timers.get(interaction.user.id, {})
            session_id = user_timer.get('session_id', None)

            if not session_id:
                return

            current_session = self.sessions.get(session_id, {})
            if current_session:
                if (interaction.user.id == current_session['executor_id'] or interaction.user.id == current_session['affected_member']):
                    if interaction.data.get('custom_id') == "eee":
                        if current_session.get('remaining_time', 0) == 0:
                            embed = discord.Embed(
                                title="sudoコマンドログ",
                                description="このsudoは終了しています。\nその為延長することはできません。",
                                color=discord.Color.yellow(),
                            )
                            await interaction.response.send_message(embed=embed, ephemeral=True)
                        else:
                            new_remaining_time = min(current_session.get('remaining_time', 0) + 300, 1800)
                            current_session['remaining_time'] = new_remaining_time

                            self.sessions[session_id] = current_session
                            self.save_sessions_to_json()

                            embed = discord.Embed(
                                title="sudoコマンドログ",
                                description="時間を5分延長しました（最大30分まで）",
                                color=discord.Color.yellow(),
                            )
                            await interaction.response.send_message(embed=embed, ephemeral=True)
                    else:
                        pass
                else:
                    pass
            else:
                pass
        else:
            pass

async def setup(bot):
    await bot.add_cog(SudoCog(bot))
