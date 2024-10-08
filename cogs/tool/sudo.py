import discord
from discord.ext import commands

import json
import random
import asyncio

from datetime import datetime
from enum import Enum
import pytz

from utils.commands_help import is_guild, is_moderator
from utils.logging import setup_logging

logger = setup_logging()

class SudoCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.sessionafile = 'data/sessions_archived.json'
        self.sessionfile = 'data/sessions.json'
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
            return {}

    def load_archived_from_json(self):
        try:
            with open(self.sessionafile, "r") as f:
                data = json.load(f)
                return data
        except FileNotFoundError:
            return {}

    async def remove_role_after_delay(self, user, role, session_id, ctx):
        remaining_time = self.sessions.get(session_id, {}).get('remaining_time', 0)
        while remaining_time > 0:
            await asyncio.sleep(1)
            session = self.sessions.get(session_id, {})
            remaining_time = session.get('remaining_time', 0)
            remaining_time -= 1  
            session['remaining_time'] = remaining_time  
            self.save_sessions_to_json()
            if remaining_time == 0:
                await user.remove_roles(role)
                jst = pytz.timezone('Asia/Tokyo')
                now = datetime.now(jst)
                embed = discord.Embed(
                    title="sudoコマンドログ",
                    description=f"{user.mention}から{role.mention}を剥奪しました",
                    color=discord.Color.red(),
                    timestamp=now
                )
                embed.set_author(name=f"ID : {session_id}")
                try:
                    if isinstance(ctx, discord.Interaction):
                        await ctx.followup.send(embed=embed)
                    else:
                        await ctx.send(embed=embed)
                except discord.errors.NotFound:
                    # インタラクションが見つからない場合、チャンネルに直接メッセージを送信
                    channel = self.bot.get_channel(ctx.channel_id)
                    if channel:
                        await channel.send(embed=embed)
                self.archive_session(session_id)
                del self.user_timers[user.id]

    class Per(Enum):
        channeledit = "チャンネル編集権限"
        modchanneledit = "Modカテゴリー編集権限"
        admin = "管理者権限"

    def generate_unique_session_id(self):
        all_possible_ids = list(range(1000, 10000))
        while True:
            new_id = str(random.choice(all_possible_ids))
            if new_id not in self.sessions:
                return new_id

    @commands.command(name="sudo", description="特定の権限を付与します。")
    @is_moderator()
    @is_guild()
    async def sudo(self, ctx: commands.Context, user: discord.Member, reason: str, permission: Per):

        if isinstance(ctx, discord.Interaction):
            interaction = ctx
            executor = interaction.user
        else:
            interaction = None
            executor = ctx.author

        role_name = "moderator"  
        has_role = any(role.name == role_name for role in user.roles)

        if not has_role:
            if interaction:
                await interaction.response.send_message("指定したユーザーはこのコマンドを使用する権限がありません。", ephemeral=True)
            else:
                await ctx.send("指定したユーザーはこのコマンドを使用する権限がありません。")
            return

        session_id = self.generate_unique_session_id()
        if user.id in self.user_timers:
            if interaction:
                await interaction.response.send_message(f"{user.mention}さんはすでにコマンドを実行している為、現在はコマンドを使用できません。")
            else:
                await ctx.send(f"{user.mention}さんはすでにコマンドを実行している為、現在はコマンドを使用できません。")
            return

        role_id = {
            self.Per.channeledit: 1274033302935699527,
            self.Per.modchanneledit: 1158230233938399273,
            self.Per.admin: 1147273889186058391
        }.get(permission)

        role = discord.utils.get(ctx.guild.roles, id=role_id)
        
        if role is None:
            if interaction:
                await interaction.response.send_message(content="指定されたロールが見つかりませんでした")
            else:
                await ctx.send("指定されたロールが見つかりませんでした")
            return

        await user.add_roles(role)
        remaining_time = 600
        jst = pytz.timezone('Asia/Tokyo')
        now = datetime.now(jst)
        formatted_time = now.strftime('%Y-%m-%d %H:%M:%S')
        
        self.sessions[session_id] = {
            'time': formatted_time,
            'executor': executor.display_name,
            'executor_id': executor.id,
            'affected_member': user.id,
            'role': role.name,
            'role_id': role.id,
            'reason': reason,
            'remaining_time': remaining_time  
        }
        self.save_sessions_to_json()
        
        timer_task = asyncio.create_task(self.remove_role_after_delay(user, role, session_id, ctx))
        
        old_timer = self.user_timers.get(user.id)
        if old_timer:
            old_timer.cancel()
        
        self.user_timers[user.id] = {
            'task': timer_task,
            'session_id': session_id  
        }

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
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
                            await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(SudoCog(bot))