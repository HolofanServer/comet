import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
import pytz
from datetime import datetime
import asyncio
import time
from dotenv import load_dotenv
import os
import json

load_dotenv()

main_guild_id = os.getenv("MAIN_GUILD_ID")

async def load_games():
    file_path = 'data/game/games.json'
    if not os.path.exists(file_path):
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as file:
            json.dump({}, file)
        return {}
    with open(file_path, 'r', encoding='utf-8') as file:
        try:
            games = json.load(file)
            if not isinstance(games, dict):
                raise ValueError("games.json should be a dictionary.")
            return games
        except json.JSONDecodeError:
            print(f"ファイルが壊れています: {file_path}")
            return {}

async def save_games(games):
    with open('data/game/games.json', 'w', encoding='utf-8') as file:
        json.dump(games, file, ensure_ascii=False, indent=4)

async def save_thread(thread, message_id):
    data_path = 'data/game/active'
    if not os.path.exists(data_path):
        os.makedirs(data_path)
    thread_data = {'thread_id': thread.id, 'message_id': message_id}
    file_name = f"{message_id}.json"
    with open(os.path.join(data_path, file_name), 'w') as file:
        json.dump(thread_data, file)

async def load_thread_data(message_id):
    file_path = f'data/game/active/{message_id}.json'
    if not os.path.exists(file_path):
        print(f"ファイルが見つかりません: {file_path}")
        return None
    with open(file_path, 'r') as file:
        thread_data = json.load(file)
    return thread_data

class GameRecruitmentCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.main_guild = self.bot.get_guild(int(main_guild_id))
        self.choices = None

    async def game_roles_autocomplete(self, interaction: discord.Interaction, current: str):
        games = await load_games()
        choices = []
        for name in games:
            if current.lower() in name.lower():
                value = games[name]
                if isinstance(value, int) or isinstance(value, float) or isinstance(value, str):
                    choices.append(app_commands.Choice(name=name, value=str(value)))
                    print(f"Debug: Added choice {name}")
                else:
                    print(f"Debug: Incorrect data type {type(value)} for {name}")
        print(f"Debug: Returning {len(choices)} choices")
        print(choices)
        return choices

    @commands.hybrid_command(name='募集', description='簡単に募集を作成します')
    @commands.guild_only()
    @app_commands.describe(募集タイトル='募集タイトル', 説明='募集説明', vc='VC', 募集人数='募集人数', 開始時間='開始時間', メンションするロール1='1', メンションするロール2='2', メンションするロール3='3')
    @app_commands.autocomplete(メンションするロール1=game_roles_autocomplete, メンションするロール2=game_roles_autocomplete, メンションするロール3=game_roles_autocomplete)
    async def gagame(self, ctx: commands.Context, 募集タイトル: str, 説明: str, vc: discord.VoiceChannel, 募集人数: int, 開始時間: int = None, メンションするロール1: Optional[str] = None, メンションするロール2: Optional[str] = None, メンションするロール3: Optional[str] = None):
        if ctx.channel.id != 920523526694391858 and ctx.channel.id != 920523140860379186 and ctx.channel.id != 920945679566798868:
            await ctx.send("このコマンドは <#920523526694391858> <#920523140860379186> でのみ使用可能です", ephemeral=True)
            return
        
        jst = pytz.timezone('Asia/Tokyo')
        now = datetime.now(jst)
        start_time = now
        if 募集人数 == 1:
            募集人数 = 2
        embed = discord.Embed(title=f'**{募集タイトル}**の募集です', color=0x00F7F3)
        embed.add_field(name=f'{ctx.author.display_name} の募集内容', value=f'- {説明}')
        embed.add_field(name='使用VC', value=vc.mention)
        embed.add_field(name='募集人数', value=f'{募集人数}人', inline=False)
        embed.add_field(name="参加人数", value="1人")
        embed.add_field(name="参加者", value=f"{ctx.author.display_name}")

        button_sa = discord.ui.Button(style=discord.ButtonStyle.green, label="参加する", custom_id="sanka")
        button_ta = discord.ui.Button(style=discord.ButtonStyle.red, label="参加をやめる", custom_id="ta")
        button_ya = discord.ui.Button(style=discord.ButtonStyle.grey, label="募集をやめる", custom_id="ya") 

        view = discord.ui.View()
        view.add_item(button_sa)
        view.add_item(button_ta)
        view.add_item(button_ya)
        now = time.time()
        twoh = 10800
        goodtime = now + twoh
        
        messg = ""
        if メンションするロール1 is not None:
            messg = f"<@&{メンションするロール1}>"
            if メンションするロール2 is not None:
                messg += f" <@&{メンションするロール2}>"
                if メンションするロール3 is not None:
                    messg += f" <@&{メンションするロール3}>"
        messg += f"\n{ctx.author.display_name}によって__**{募集タイトル}**__の募集が開始されました。"
        messg += f"\n### 募集終了予定時刻: <t:{int(goodtime)}>(<t:{int(goodtime)}:R>)"

        await ctx.send("募集を作成しました！", ephemeral=True)

        try:
            response = await ctx.channel.send(content=messg, embed=embed, view=view)
            print(response.guild)
            thread_response = await response.create_thread(name=f"{募集タイトル}の募集")
            await thread_response.add_user(ctx.author)
            await thread_response.send(f"{ctx.author.mention} さん、ようこそ! こちらが{募集タイトル}の募集スレッドです。")
            await save_thread(thread_response, response.id)
        except Exception as e:
            print(f"スレッド作成中にエラーが発生しました: {e}")
        message_id = response.id
        print(message_id)

        if not hasattr(self.bot, 'gagame_sessions'):
            self.bot.gagame_sessions = {}

        target_participants = 募集人数
        self.bot.gagame_sessions[message_id] = {
            'participants': 1,
            'target_participants': target_participants,
            'participant_users': [ctx.author],
            'command_user': ctx.author,
            'joined_users': {ctx.author.id},
            'view': view,
            'start_time': start_time,
            'message': response
        }  
        await self.end_recruitment_timer(message_id, start_time)

        session = self.bot.gagame_sessions.get(message_id)

    async def end_recruitment_timer(self, message_id, start_time):
        print("timer start")
        await asyncio.sleep(3 * 60 * 60)
        current_time = datetime.utcnow()
        if (current_time - start_time).total_seconds() >= 3 * 60 * 60:
            session = self.bot.gagame_sessions.get(message_id)
            if session:
                print("End recruitment button pressed")
                embed = session['message'].embeds[0]
                embed.title = embed.title.replace("の募集です", "")
                embed.title += "の募集は終了しました"
                embed.color = discord.Color.red()

                await session['message'].edit(embed=embed, view=None)
                del self.bot.gagame_sessions[message_id]

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        print("Interaction received")
        if interaction.type == discord.InteractionType.component:
            print("Component interaction detected")
            session = self.bot.gagame_sessions.get(interaction.message.id)
            print(f"Session for message ID {interaction.message.id}: {session}")
            custom_id = interaction.data.get('custom_id')
            print(f"Received custom_id: {custom_id}")
            if session is not None:

                user_id = interaction.user.id
                if 'joined_users' not in session:
                    session['joined_users'] = set()

                if custom_id == 'sanka':
                    print("Join button pressed")
                    if user_id not in session['joined_users']:
                        session['participants'] += 1 
                        session['participant_users'].append(interaction.user)
                        print(f"Current participants: {session['participants']}, Target: {session['target_participants']}")
                        session['joined_users'].add(user_id)
                        session['view'].children[1].label = f"参加をやめる ({session['participants']}人)"
                        await interaction.response.send_message(f"参加しました！", ephemeral=True)
                        thread_id = interaction.message.channel.id
                        thread_data = await load_thread_data(interaction.message.id)
                        if thread_data:
                            thread = await self.bot.fetch_channel(thread_data['thread_id'])
                            print(f"Adding user {interaction.user} to thread {thread}")
                            await thread.add_user(interaction.user)
                            await thread.send(f"{interaction.user.mention} さん、ようこそ! こちらが{interaction.message.embeds[0].title}の募集スレッドです。")
                        else:
                            print("Thread data not found.")
                    elif user_id == session['command_user'].id:
                        await interaction.response.send_message(f"コマンドの実行者はすでに参加しています！", ephemeral=True)
                        return
                    else:
                        await interaction.response.send_message(f"すでに参加しています！", ephemeral=True)
                        return

                    embed = interaction.message.embeds[0]
                    embed.set_field_at(3, name="参加人数", value=f"{session['participants']}人", inline=False)
                    participant_names = session['command_user'].display_name + "\n"
                    participant_names += "\n".join([user.display_name for user in session['participant_users'] if user.id != session['command_user'].id])
            
                    embed.set_field_at(4, name="参加者", value=participant_names, inline=True)
                    await interaction.message.edit(embed=embed)

                    if session['participants'] == session['target_participants']:
                        vc_mention = interaction.message.embeds[0].fields[1].value
                        mentions = ' '.join([participant.mention for participant in session['participant_users']])
                        thread_id = interaction.message.channel.id
                        thread_data = await load_thread_data(interaction.message.id)
                        if thread_data:
                            thread = await self.bot.fetch_channel(thread_data['thread_id'])
                            await thread.send(f"人数が揃いました! \n VC: {vc_mention}  \n参加者: {mentions}")
                        else:
                            print("Thread data not found.")
            
                        embed.color = discord.Color.red()
                        embed.title = embed.title.replace("の募集です", "")
                        embed.title += "の募集は終了しました"
                        await interaction.message.edit(embed=embed, view=None)
                        del self.bot.gagame_sessions[interaction.message.id]

                elif custom_id == 'ta':
                    print("Leave button pressed")
                    if user_id in session['joined_users']:
                        session['participants'] -= 1
                        for user in session['participant_users']:
                            if user.id == user_id:
                                session['participant_users'].remove(user)
                                break

                        session['joined_users'].remove(user_id)
                        session['view'].children[1].label = f"参加をやめる ({session['participants']}人)"
                        await interaction.response.send_message(f"参加をやめました", ephemeral=True)
                        thread_id = interaction.message.channel.id
                        thread_data = await load_thread_data(interaction.message.id)
                        if thread_data:
                            thread = await self.bot.fetch_channel(thread_data['thread_id'])
                            print(f"Removing user {interaction.user} from thread {thread}")
                            await thread.remove_user(interaction.user)
                        else:
                            print("Thread data not found.")
                    else:
                        await interaction.response.send_message(f"あなたはまだ参加していません!", ephemeral=True)

                    embed = interaction.message.embeds[0]
                    embed.set_field_at(3, name="参加人数", value=f"{session['participants']}人", inline=False)
        
                    participant_names = "\n".join([user.display_name for user in session['participant_users']])
                    if not participant_names:
                        participant_names = "まだ参加者はいません"
                    embed.set_field_at(4, name="参加者", value=participant_names, inline=False)

                    await interaction.message.edit(embed=embed)
            custom_id = interaction.data.get('custom_id')
            print(f"Received custom_id: {custom_id}")   
            if session is not None:

                user_id = interaction.user.id
                command_user_id = session['command_user'].id

                if custom_id == 'ya':
                    if user_id == command_user_id:
                        print("End recruitment button pressed")
                        embed = interaction.message.embeds[0]
                        embed.title = embed.title.replace("の募集です", "")
                        embed.title += "の募集は終了しました"
                        embed.color = discord.Color.red()

                        await interaction.response.send_message(content="募集をやめました", ephemeral=True)
                        await interaction.message.edit(embed=embed, view=None)
                        del self.bot.gagame_sessions[interaction.message.id]
                        thread_id = interaction.message.channel.id
                        thread_data = await load_thread_data(interaction.message.id)
                        if thread_data:
                            thread = await self.bot.fetch_channel(thread_data['thread_id'])
                            print(f"Deleting thread {thread}")
                            await thread.delete()
                        else:
                            print("Thread data not found.")
                    else:
                        await interaction.response.send_message(content="申し訳ありませんが、この操作は募集を作成したユーザーにのみ許可されています.", ephemeral=True)

    @commands.hybrid_command(name='add_mention_role', description='ゲームのロールを追加します')
    @app_commands.describe(role='ロールを選択')
    async def add_mention_role(self, ctx, role: discord.Role):
        if ctx.author.roles[-1] < ctx.guild.get_role(745756840582840411):
            await ctx.send("あなたにはこのコマンドを実行する権限がありません。", ephemeral=True)
            return
        games = await load_games()
        games[role.name] = role.id
        await save_games(games)
        await ctx.send(f'『{role.name}』のロールが追加されました。', ephemeral=True)

async def setup(bot):
    await bot.add_cog(GameRecruitmentCog(bot))