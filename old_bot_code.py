import sys
import discord
from discord import app_commands
from discord.ext import commands
from googlesearch import search
import datetime
import asyncio
import random
from ruamel.yaml import YAML
from time import time as current_time1
import discord.ui
import requests
import os
import matplotlib.pyplot as plt
import pandas as pd
from typing import Dict, List
from PIL import Image
import io
import requests
from enum import Enum
from datetime import datetime,timedelta, timezone
from badge_to_emojis import badge_to_emoji
from typing import Optional, Union
from dotenv import load_dotenv
import json
import traceback

load_dotenv()

TOKEN = os.getenv('BOT_TOKEN')
application_id = os.getenv('APPLICATION_ID')

intents = discord.Intents.all()
intents.messages = True
client = discord.Client(intents=intents, application_id=application_id)
tree = app_commands.CommandTree(client)
bot = commands.Bot(command_prefix="!", intents=intents)

ModeFlag = 0

def save_timer_to_json(channel_id, expire_time):
    data = {
        "channel_id": channel_id,
        "expire_time": expire_time.isoformat()
    }
    with open("bump_timers.json", "w") as f:
        json.dump(data, f)

async def load_timers_from_json():
    try:
        with open("bump_timers.json", "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        return

    channel_id = int(data["channel_id"])
    expire_time = datetime.fromisoformat(data["expire_time"])

    channel = client.get_channel(channel_id)
    if channel:
        remaining_time = (expire_time - datetime.now(pytz.utc)).total_seconds()
        if remaining_time > 0:
            await asyncio.sleep(remaining_time)
            await set_timer_and_send_message(channel)

yaml = YAML()

with open("./config.yml", "r", encoding="utf-8") as file:
    config = yaml.load(file)

# 画像のURLとチャンネルIDを指定
image_url = "https://cdn.discordapp.com/attachments/1121698369316851732/1158217294355374191/F7USg8YawAEQKsv.jpg"
channel_id = 1128731498758017035  # メッセージを送信するチャンネルのIDを指定してください

# 画像をダウンロードしてバイナリデータとして取得

# Webhookを使用してメッセージを送信する関数
async def send_webhook_message(channel_id, content):
    current_time = datetime.now().strftime('%Y/%m/%d %H:%M:%S')
    webhook_name = f"のどかbot起動通知 | {current_time}"

    # チャンネルIDからチャンネルを取得
    channel = client.get_channel(channel_id)

    # チャンネルが見つからなかった場合は処理を中断
    if channel is None:
        return

    # Webhookを作成
    webhook = await channel.create_webhook(name=webhook_name)

    # Webhookを使用してメッセージを送信
    await webhook.send(content=content)
    await webhook.delete()

# on_readyイベントでメッセージを送信する処理
@client.event
async def on_ready():
    print('------')
    print('Online! Details:')
    print(f"Bot Username: {client.user.name}")
    print(f"BotID: {client.user.id}")
    print('------')
    
    current_time = datetime.now().strftime('%Y/%m/%d %H:%M:%S')
    message_content = f"**------**\nOnline! Details:\nBot Username:  `{client.user.name}`\nBot ID:  `{client.user.id}`\nDev user:  **freewifi_vip**\n**------**"

    # メッセージを送信する関数を呼び出し
    await send_webhook_message(channel_id, message_content)
    tree.add_command(reportmsg)
    tree.add_command(reportuser)
    await tree.sync()
    await load_timers_from_json()
    await client.change_presence(activity= discord.Activity(name="起動中です…",type=discord.ActivityType.playing))
    await asyncio.sleep(60)
    while True:
     await client.change_presence(activity = discord.Activity(name="オトナブルー / 宝鐘マリン cover", type=discord.ActivityType.listening))
     await asyncio.sleep(180)
     await client.change_presence(activity = discord.Activity(name="アイドル / 天音かなた(cover)", type=discord.ActivityType.listening))
     await asyncio.sleep(190)
     await client.change_presence(activity = discord.Activity(name="フォニイ / 星街すいせい(Cover)", type=discord.ActivityType.listening))
     await asyncio.sleep(170)
     await client.change_presence(activity = discord.Activity(name="【歌ってみた】グッバイ宣言 / 百鬼あやめ cover", type=discord.ActivityType.listening))
     await asyncio.sleep(170)
     await client.change_presence(activity = discord.Activity(name="【original】#あくあ色ぱれっと【ホロライブ/湊あくあ】", type=discord.ActivityType.listening))
     await asyncio.sleep(170)
     await client.change_presence(activity = discord.Activity(name="【original anime MV】I’m Your Treasure Box ＊あなたは マリンせんちょうを たからばこからみつけた。【hololive/宝鐘マリン】", type=discord.ActivityType.listening))
     await asyncio.sleep(170)
     await client.change_presence(activity = discord.Activity(name="【おちゃめ機能】ホロライブが吹っ切れた【24人で歌ってみた】", type=discord.ActivityType.listening))
     await asyncio.sleep(170)
     await client.change_presence(activity = discord.Activity(name="ホロライブ言えるかな？ Beyond the Stage ver.【STAGE1＋2 edit】", type=discord.ActivityType.listening))
     await asyncio.sleep(180)
     await client.change_presence(activity = discord.Activity(name="W/X/Y / 常闇トワ(cover)", type=discord.ActivityType.listening))
     await asyncio.sleep(276)
     await client.change_presence(activity = discord.Activity(name="【original】Ahoy!! 我ら宝鐘海賊団☆【ホロライブ/宝鐘マリン】", type=discord.ActivityType.listening))
     await asyncio.sleep(110)
     await client.change_presence(activity = discord.Activity(name="Say!ファンファーレ!/白上フブキ【オリジナル曲】", type=discord.ActivityType.listening))
     await asyncio.sleep(255)
     await client.change_presence(activity = discord.Activity(name="サクラカゼ / さくらみこ (official)", type=discord.ActivityType.listening))
     await asyncio.sleep(230)
     await client.change_presence(activity = discord.Activity(name="アニマル / miComet(cover)", type=discord.ActivityType.listening))
     await asyncio.sleep(152)
     await client.change_presence(activity = discord.Activity(name="ディスコミュ星人/兎田ぺこら(cover)", type=discord.ActivityType.listening))
     await asyncio.sleep(209)
     await client.change_presence(activity = discord.Activity(name="ベイビーダンス / さくらみこ x DECO*27 (official)", type=discord.ActivityType.listening))
     await asyncio.sleep(187)
     await client.change_presence(activity = discord.Activity(name="ねぇねぇねぇ。／Covered by紫咲シオン＆湊あくあ【歌ってみた】", type=discord.ActivityType.listening))
     await asyncio.sleep(213)
     await client.change_presence(activity = discord.Activity(name="マーシャルマキシマイザー - 柊マグネタイト / 風真いろは(cover)", type=discord.ActivityType.listening))
     await asyncio.sleep(163)
     await client.change_presence(activity = discord.Activity(name="【オリジナル楽曲】サイキョウチックポルカ【尾丸ポルカ】", type=discord.ActivityType.listening))
     await asyncio.sleep(240)
     await client.change_presence(activity = discord.Activity(name="ロウワー / 星街すいせい(cover)", type=discord.ActivityType.listening))
     await asyncio.sleep(234)
     await client.change_presence(activity = discord.Activity(name="Doggy god's street / 戌神ころね", type=discord.ActivityType.listening))
     await asyncio.sleep(191)
     await client.change_presence(activity = discord.Activity(name="ECHO (Yunosuke Remix) / 角巻わため(Cover)", type=discord.ActivityType.listening))
     await asyncio.sleep(180)
     await client.change_presence(activity = discord.Activity(name="Mod by FreeWiFi", type=discord.ActivityType.listening))
     await asyncio.sleep(10)


onayami_users = {}

@tree.command(
    name="匿名相談",
    description="匿名でお悩み相談をすることができます。"
)
async def onayami(inter: discord.Interaction, 求める回答: str, 求める回答者: str, 相談内容: str):

    if inter.channel_id != 1121168367357800528:
        await inter.response.send_message(f"<#1121168367357800528> 以外では使用できません。", ephemeral=True)
        return

    msg_content = f"回答が来た場合は</返信:1161082899999764625>で返信をしましょう。\n\n**【求める回答】**\n{求める回答}\n**【求める回答者】**\n{求める回答者}\n**【相談内容】**\n{相談内容}"
    await inter.response.send_message("お悩みを送信しました。", ephemeral=True)
    sent_message = await inter.channel.send(msg_content)

    onayami_users[inter.user.id] = sent_message.id

@tree.command(
    name='返信',
    description='お悩みに対する回答を送ります。'
)
async def henshin(inter: discord.Interaction, 返信内容: str):
    # /onayami コマンドを実行したか確認
    if inter.user.id not in onayami_users:
        await inter.response.send_message('先に</匿名相談:1161082899999764624>コマンドを使用して、お悩みを相談してみてください。', ephemeral=True)
        return

    original_msg_id = onayami_users[inter.user.id]
    original_msg = await inter.channel.fetch_message(original_msg_id)
    
    followup_content = f"**【返信内容】**\n{返信内容}"
    await inter.response.send_message("返信を送信しました。", ephemeral=True)
    await original_msg.reply(followup_content)

from discord.ui import Select, View, select

class ReportUserReasonView(View):
    def __init__(self):
        super().__init__()
        self.value = None
        self.add_item(ReportuserReasonSelect())

role_name = "Staff"
class ReportuserReasonSelect(Select):
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
            discord.SelectOption(label="その他", value="その他")
        ]

        super().__init__(custom_id="reason", placeholder="通報理由を選択してください", options=options)

    async def callback(self, interaction: discord.Interaction):
        self.view.value = self.values[0]
        await interaction.response.send_message(f"通報理由を {self.view.value} に設定しました。", ephemeral=True)
        self.view.stop()


@app_commands.context_menu(name="ユーザーを運営に通報")
async def reportuser(inter: discord.Interaction, user: discord.User):

    mod_channel = inter.guild.get_channel(1092326527837949992)
    if mod_channel is None:
        await inter.response.send_message("モデレーションチャンネルが見つかりません", ephemeral=True)
        return
    mod_role = discord.utils.get(inter.guild.roles, name=role_name)
    if mod_role is None:
        await inter.response.send_message("モデレーターロールが見つかりません", ephemeral=True)
        return
    view = ReportUserReasonView()
    await inter.response.send_message("通報理由を選択してください：", view=view, ephemeral=True)
    await view.wait()

    if view.value is None:
        return
    jst = pytz.timezone('Asia/Tokyo')
    now = datetime.now(jst)
    e = discord.Embed(
        title="ユーザー通報",
        description=f"{inter.user.mention}が {user.mention} を **{view.value}** で通報しました。\n直ちに事実確認を行い適切な対応をしてください。",
        color=0xFF0000,
        timestamp=now
    )
    e.set_author(name=f"通報したユーザー：{inter.user.display_name} | {inter.user.id}\n通報されたユーザー：{user.display_name} | {user.id}")

    await mod_channel.send(content=f"`{mod_role.mention}`", embed=e)
    await inter.followup.send("ユーザーが運営に通報されました。", ephemeral=True)

class ReportReasonSelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="スパム", value="スパム"),
            discord.SelectOption(label="不適切な内容", value="不適切な内容"),
            discord.SelectOption(label="ハラスメント", value="ハラスメント"),
            discord.SelectOption(label="メンバーシップの情報公開", value="メンバーシップの情報公開"),
            discord.SelectOption(label="誤情報", value="誤情報"),
            discord.SelectOption(label="違法な行為", value="違法な行為"),
            discord.SelectOption(label="自傷/他傷行為", value="自傷/他傷行為"),
            discord.SelectOption(label="差別的発言", value="差別的発言"),
            discord.SelectOption(label="プライバシー侵害", value="プライバシー侵害"),
            discord.SelectOption(label="荒らし行為", value="荒らし行為"),
            discord.SelectOption(label="その他", value="その他")
        ]

        super().__init__(custom_id="reason", placeholder="通報理由を選択してください", options=options)

    async def callback(self, interaction: discord.Interaction):
        self.view.value = self.values[0]
        await interaction.response.send_message(f"通報理由を {self.view.value} に設定しました。", ephemeral=True)
        self.view.stop()

class ReportReasonView(View):
    def __init__(self):
        super().__init__()
        self.value = None  
        self.add_item(ReportReasonSelect())

mod_channel = 1092326527837949992
role_name = "Staff"

@app_commands.context_menu(name="メッセージを運営に通報")
async def reportmsg(inter: discord.Interaction, message: discord.Message):
    allowed_guild_ids = [1092138492173242430]  # 許可するギルドIDをリストに入れます
    if inter.guild.id not in allowed_guild_ids:
        await inter.response.send_message("このサーバーではこの機能は利用できません。", ephemeral=True)
        return
    jst = pytz.timezone('Asia/Tokyo')
    now = datetime.now(jst)
    channel = inter.channel
    report_channel = inter.guild.get_channel(mod_channel)
    mod_role = discord.utils.get(inter.guild.roles, name=role_name)
    if mod_role is None:
        await inter.response.send_message("モデレーターロールが見つかりません", ephemeral=True)
        return
    
    view = ReportReasonView()
    await inter.response.send_message("通報理由を選択してください：", view=view, ephemeral=True)
    await view.wait()

    if view.value is None:
        return

    e = discord.Embed(
        title="メッセージ通報",
        description=f"{inter.user.mention}が  **{view.value}**  でメッセージを通報しました！！\n通報されたメッセージは以下の通りです。",
        color=0xFF0000,
        timestamp=now,
        url=message.jump_url
    )
    e.add_field(name="通報者", value=inter.user.mention, inline=True)
    e.add_field(name="元のチャンネル", value=channel.mention, inline=True)
    e.add_field(name="通報理由", value=view.value, inline=False)
    e.add_field(name="メッセージ内容", value=f"{message.jump_url}\n\n`{message.content}`", inline=False)
    e.add_field(name="メッセージID", value=message.id, inline=True)
    e.add_field(name="送信者", value=message.author.mention, inline=True)

    if message.attachments:
        attachment_links = [f"[{attachment.filename}]({attachment.url})" for attachment in message.attachments]
        attachment_text = "\n".join(attachment_links)
        e.add_field(name="添付ファイル", value=attachment_text, inline=False)
        e.set_image(url=message.attachments[0].url)


    await report_channel.send(content=f"{mod_role.mention}", embed=e)
    await inter.followup.send("メッセージが運営に通報されました。", ephemeral=True)

@tree.command(name="ping", description="PINGを送信します")
async def ping(inter: discord.Interaction):
    start_time = current_time1()
    await inter.response.send_message("Ping計測中...", ephemeral=True)
    jst = pytz.timezone('Asia/Tokyo')
    now = datetime.now(jst)
    end_time = current_time1()
    api_ping = round((end_time - start_time) * 1000)

    gateway_ping = round(client.ws.latency * 1000)  

    embed = discord.Embed(title="全てのPing情報", color=discord.Color.blue(), description=f"{client.user.mention}のPING一覧です。", timestamp=now)
    embed.add_field(name="WebSocket Ping", value=f"{round(client.latency * 1000)}ms", inline=True)
    embed.add_field(name="HTTP API Ping", value=f"{api_ping}ms", inline=True)
    embed.add_field(name="Gateway Ping", value=f"{gateway_ping}ms", inline=True) 

    await inter.followup.send(embed=embed)
        
def convert(time):
    pos = ["s", "m", "h", "d", "w"]
    time_dict = {"s": 1, "m": 60, "h": 3600, "d": 3600 * 24, "w": 3600 * 24 * 7}
    unit = time[-1]

    if unit not in pos:
        return -1
    try:
        val = int(time[:-1])
    except:
        return -2

    return val * time_dict[unit]

def userHasRole(user: discord.User, roleID: int):
    userRoles = [role.id for role in user.roles]
    return roleID in userRoles


@tree.command(name="giveaway", description="抽選します")
async def giveaway(interaction: discord.Interaction, channel: Union[discord.TextChannel, discord.VoiceChannel, discord.Thread], duration: str, prize: str):
    if not userHasRole(interaction.user, config["giveaway_role"]):
        embed = discord.Embed(title=":tada: **Giveaway Assistent**", description=":x: このコマンドを実行する権限がありません。")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    durationTime = convert(duration)
    if durationTime == -1:
        embed = discord.Embed(title=":tada: **Giveaway Assistent**", description=":x: 時間の指定に失敗しました。数字が半角か、単位が間違っていないかを再度ご確認ください。:\n> s = 秒(Seconds)\n> m = 分(Minutes)\n> h = 時間(Hours)\n> d = 日(Days)\n> w = 週(Weeks)", color = discord.Color.red())
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    elif durationTime == -2:
        embed = discord.Embed(title=":tada: **Giveaway Assistent**", description=":x: 時間は必ず**整数かつ半角で**お願いします", color = discord.Color.red())
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    endTime = int(current_time1() + durationTime)

    await interaction.response.send_message(f"新しい抽選が開始されました: {interaction.user.mention} | Giveaway Chat: {channel.mention} | Time: {duration} | Prize: {prize}", ephemeral=True)
    print(f"New contest started by: {interaction.user.mention} | Giveaway Chat: {channel.mention} | Time: {duration} | Prize: {prize}")
    print("------")
    embed = discord.Embed(title=f":tada: ** {prize}の抽選**", description=f"{config['react_emoji']}を押して抽選に参加！!", color=0x32cd32)
    embed.add_field(name="終了時間:", value=f"<t:{endTime}>(<t:{endTime}:R>)")
    embed.add_field(name=f"作成者:", value=interaction.user.mention)
    msg = await channel.send(embed=embed)

    await msg.add_reaction(config['react_emoji'])
    await asyncio.sleep(durationTime)

    new_msg = await channel.fetch_message(msg.id)
    users = [user async for user in new_msg.reactions[0].users()]
    users.pop(users.index(client.user))

    winner = random.choice(users)
    if config['ping_winner_message'] == True:
        await channel.send(f":tada: おめでとうございます!! {winner.mention} が **{prize}**を勝ち取りました!")
        print(f"New Winner! User: {winner.mention} | Prize: {prize}")
        print("------")

    embed2 = discord.Embed(title=f":tada: ** {prize}の抽選**", description=f":trophy: **当選者！:** {winner.mention}", color=0xffd700)
    embed2.set_footer(text="抽選は終了しました")
    await msg.edit(embed=embed2)


@tree.command(name="reroll", description="再抽選します")
async def reroll(interaction: discord.Interaction, channel: discord.TextChannel, messageid: str):
    if not userHasRole(interaction.user, config["giveaway_role"]):
        embed = discord.Embed(title=":tada: **Giveaway Assistent**", description=":x: このコマンドを実行する権限がありません。")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    if not messageid.isnumeric():
        return
    messageID = int(messageid)
    try:
        new_msg = await channel.fetch_message(messageID)
    except:
        prefix = config['prefix']
        await interaction.send(f"Wrong use! Do it like this: `{prefix}reroll <Channel Name - Must be the channel where the Giveaway was> <messageID from the Giveaway message>` ", color = discord.Color.red())

    users = [user async for user in new_msg.reactions[0].users()]
    users.pop(users.index(client.user))

    winner = random.choice(users)

    await interaction.channel.send(f":tada: The new winner is: {winner.mention}!")

@tree.command(name="ghelp", description="お品書き")
async def help(interaction: discord.Interaction):
    if config['help_command'] == True:
        embed = discord.Embed(title="**御手元 | :chopsticks:**", color = interaction.user.color)
        embed.add_field(name=":tada:抽選:", value=f"``/giveaway`` *抽選の設定を開始しパネルを作成します*", inline = False)
        embed.add_field(name=":arrows_counterclockwise:再抽選:", value=f"``/reroll <channel> <messageid>`` *再抽選で新たな当選者を選びます*", inline = False)
        embed.add_field(name=":cherry_blossom:春のさくら餅:cherry_blossom:", value=f"〜Lightning端子を添えて〜", inline = False)
        embed.set_thumbnail(url=interaction.guild.icon.url)
        await interaction.response.send_message(embed=embed)
    else:
        return

@tree.command(name="google", description="Google検索ができます")
async def google_command(interaction: discord.Interaction, 検索ワード: str):
    await interaction.response.send_message(f"`{検索ワード}`を検索中")
    count = 0
# 日本語で検索した物を表示
    search_results = search(検索ワード, lang="jp")
    for i, url in enumerate(search_results):
        if i >= 5:
            break

@tree.command(name="insight", description="サーバーインサイトのリンクを送信します。")
async def insight(interaction: discord.Interaction):
    await interaction.response.send_message("[サーバーインサイトのリンクです](https://discord.com/developers/servers/1092138492173242430/analytics/)")

@tree.command(name="メンション", description="指定のユーザーに1回だけメンションとメッセージを送信します")
async def メンションします(interaction: discord.Interaction, メンションしたい人: str, メッセージ: str):
    await interaction.response.send_message("メンションします", ephemeral=True)
    count = 0
    while True:  # ループを追加
        
        await interaction.channel.send(f"{メンションしたい人} \n{メッセージ}")
        count += 1
        if count == 1:
            break  # ループ内でのみ使用するため、ここに break を配置
@tree.command(name='server_list', description='HFSの公式サーバーのリストを提示します。')
async def serverlist(interaction: discord.Interaction):
    embed = discord.Embed(title='HFS公式派生サーバー一覧', description='[HFS TEST SERVER](<https://discord.gg/eAvTqev9uE>)\n[追加予定]')
    await  interaction.response.send_message(embed=embed)

@tree.command(name="メッセージを送信", description="BOTがあなたの代わりにメッセージを送信します")
async def メッセージを送信(interaction: discord.Interaction, タイトル: str, 埋め込みの名前: str, メッセージ: str):
    embed = discord.Embed(title=タイトル)
    embed.add_field(name=埋め込みの名前, value=メッセージ)
    await interaction.channel.send(embed=embed)

@tree.command(name="嘘ban", description="BANしてもいいですか？")
async def ゆのさんban(interaction: discord.Interaction, banする人: str):
    await interaction.response.send_message(f"{banする人}はBANされました")

@tree.command(name="mclink", description="discordとMinecraftサーバーガイドを送信します")
async def mclink(interaction: discord.Interaction):
    await interaction.response.send_message("作成しています...", ephemeral=True)
    await interaction.channel.send("### <:IMG_0245:1127658415741747290> マイクラサーバーガイド\n**━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━**\n**Minecraft名**を登録しよう！\n下の__案内__をよく読んで**登録を完了**させて下さい！\n**__わからない事__**があれば<#1108992796897058947>の__**マインクラフトに関するお問い合わせ**__をご利用ください。\n**━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━**")
    embed = discord.Embed(title="ユーザー名登録", color=0x32cd32)
    embed.add_field(name="Googleフォームは下の登録をクリック！", value="`登録する`をタップ/クリックするとGoogleフォームのリンクを取得できます")
    embed.add_field(name="入力が終わったら", value="DMに送信されたチャンネルに書いてあるIPアドレスを使って参加しよう\nそれが終わったら <@877236936316690493> に認証コードを送信しよう！")
    embed.set_image(url="https://cdn.discordapp.com/attachments/1092414295251374120/1136347486391390298/IMG_0952.png")
    embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1092414295251374120/1136348393258635294/IMG_8004.png")
    button = discord.ui.Button(label="登録する", style=discord.ButtonStyle.primary,custom_id="mclink")
    view = discord.ui.View()
    view.add_item(button)
    await interaction.channel.send(embed=embed, view=view)

#全てのインタラクションを取得
@client.event
async def on_interaction(inter:discord.Interaction):
    try:
        if inter.data['component_type'] == 2:
            await on_button_click11(inter)
    except KeyError:
        pass

# Button,Selectの処理
async def on_button_click11(inter:discord.Interaction):
    user = inter.user
    guild = inter.guild

    role_id_check = 1127686431645646908
    if any(role.id == role_id_check for role in user.roles):
        await inter.response.send_message("すでに登録済みです", ephemeral=True)
        return

    embed = discord.Embed(title="登録フォーム", color=0x32cd32)
    embed.add_field(name="Googleフォーム", value="[登録はこちらをクリック](https://docs.google.com/forms/d/1wlydd5UslGdhsDp-5IXm4psmraazWIyn5hb2nz2Drag/viewform)")
    embed.add_field(name="認証機能について", value="**Googleフォームを記載していない場合**は以下のような画面が表示されます。\n**必ず記載をお願いしたします。**")
    embed.set_image(url="https://cdn.discordapp.com/attachments/1092414295251374120/1136348392847573062/image.png")
    await inter.response.send_message(embed=embed, ephemeral=True)

    user = inter.user
    guild = inter.guild
    role_id = 1127686431645646908  #数字の部分は付与したいロールIDを書いて下さい
    if user and guild:
        role = guild.get_role(role_id)
        if role:
            await user.add_roles(role) 
    role_id = 1098355721768280084  #数字の部分は付与したいロールIDを書いて下さい
    if user and guild:
        role = guild.get_role(role_id)
        if role:
            await user.add_roles(role) 



    embed_sai = discord.Embed(title="再案内", color=0x32cd32)
    embed_sai.add_field(name="既に送信済みの方は無視してください", value="ボタンを押した際に登録できなかった向けのものです")
    embed_sai.add_field(name="Googleフォーム", value="[登録はこちらから](https://docs.google.com/forms/d/1wlydd5UslGdhsDp-5IXm4psmraazWIyn5hb2nz2Drag/viewform)")
    embed_sai.set_image(url="https://cdn.discordapp.com/attachments/1098356112677404885/1127644417059201135/IMG_0949.png")
    mess = await user.send("{}さん\n以下のチャンネルにアクセスしてサーバーに参加しよう!\n<#1098353865943945237>\n<#1098657852379373619>\n<#1098657893663920208>".format(user.mention))
    await user.send(embed=embed_sai, message=mess)

@tree.command(name="mcsupport", description="mclinkのフォームリンクを送信します")
async def mcsupport(inter: discord.Interaction, member: discord.Member):
    await inter.channel.send(f"{member.mention}\nお問い合わせありがとうございます。\n\n°不便をおかけして申し訳ありません。[こちら](https://docs.google.com/forms/d/1wlydd5UslGdhsDp-5IXm4psmraazWIyn5hb2nz2Drag/viewform) から登録をお願いします。\n\n")

@tree.command(name="dev", description="devリンクを送信します")
async def dev(interaction: discord.Interaction):
    await interaction.response.send_message("https://discord.com/developers/applications")
    
@tree.command(name="user", description="指定したユーザーの情報を表示します")
async def userinfo(interaction: discord.Interaction, member: discord.Member,):
    embed = discord.Embed(title="ユーザー情報", color=0x00ff00)
    embed.set_author(name=member.display_name, icon_url=member.avatar)
    embed.set_thumbnail(url=member.guild_avatar)
    embed.add_field(name="基本情報", value=f"NAME：{member.name}\n　ID　：{member.id}", inline=True)
    badges = [badge.name for badge in member.public_flags.all()]
    badge_emojis = [badge_to_emoji.get(badge, badge) for badge in badges]
    embed.add_field(name="プロフィールバッジ", value=' '.join(badge_emojis), inline=True)
#    embed.add_field(name="devプロフィールバッジ", value=member.public_flags.all(), inline=True)
#    embed.add_field(name="認証の有無", value=member.pending, inline=True)
    member = interaction.guild.get_member(member.id)
    if member:
        embed.add_field(name="アカウント情報", value=f"**サーバー参加日：**{member.joined_at.strftime('%Y-%m-%d %H:%M:%S')}\n **Discord参加日  ：**{member.created_at.strftime('%Y-%m-%d %H:%M:%S')}", inline=True)
    else:
        embed.add_field(name="アカウント情報", value=f"**サーバーには参加していません**\n**Discord参加日：**{member.created_at.strftime('%Y-%m-%d %H:%M:%S')}", inline=True)
    
    await interaction.response.send_message(embed=embed)

@tree.command(name="server", description="サーバーの情報を表示します")
async def server(interaction: discord.Interaction):
    embed = discord.Embed(title=F"{interaction.guild.name}の情報", color=0x32cd32)
    embed.add_field(name="基本情報", value=f"サーバー名：**{interaction.guild.name}**\nサーバーid：**{interaction.guild_id}**")
    embed.add_field(name="サーバーオーナー", value="👑 | "+str(interaction.guild.owner) +"\n ID | "+str(interaction.guild.owner_id))
    embed.add_field(name="サーバー人数", value=interaction.guild.member_count)
    embed.set_thumbnail(url=interaction.guild.icon)
    embed.set_image(url=interaction.guild.banner)
    await interaction.response.send_message(embed=embed)

@tree.command(name="embed", description="embedを送信します")
async def eee(interaction: discord.Interaction):
    embed=discord.Embed(title="サーバーマップ一覧", description="**以下のリンクかボタンをクリックするとマップを見ることができます。**\n[HUB鯖マップを見てみる](http://18.jpn.gg:6598/#world:1:-12:-18:85:0:0:0:0:perspective)\n[サバイバル鯖マップを見てみる](http://18.jpn.gg:6558/#world:8430:55:7735:149:-0.48:0:0:0:perspective)\n[未来鯖マップを見てみる](http://18.jpn.gg:6529/#world:35:-43:-23:14:0:0:0:1:flat)\n[クリエ鯖マップを見てみる](http://18.jpn.gg:6542/#world:-7:0:111:1500:0:0:0:0:perspective)", color=0x32cd32)
    embed.set_image(url="https://cdn.discordapp.com/attachments/1104493356781940766/1129490961572044841/image0.jpg")
    button_hub = discord.ui.Button(label="HUB鯖マップを見てみる", style=discord.ButtonStyle.primary, url="http://18.jpn.gg:6598/#world:1:-12:-18:85:0:0:0:0:perspective")
    view_hub = discord.ui.View()
    view_hub.add_item(button_hub)
    button_sur = discord.ui.Button(label="サバイバル鯖マップを見てみる", style=discord.ButtonStyle.primary, url="http://18.jpn.gg:6558/#world:8430:55:7735:149:-0.48:0:0:0:perspective")
    view_sur = discord.ui.View()
    view_sur.add_item(button_sur)
    button_mir = discord.ui.Button(label="未来鯖マップを見てみる", style=discord.ButtonStyle.primary, url="http://18.jpn.gg:6529/#world:35:-43:-23:14:0:0:0:1:flat")
    view_mir = discord.ui.View()
    view_mir.add_item(button_mir)
    button_cur = discord.ui.Button(label="クリエ鯖マップを見てみる", style=discord.ButtonStyle.primary, url="http://18.jpn.gg:6542/#world:-7:0:111:1500:0:0:0:0:perspective")
    view_cur = discord.ui.View()
    view_cur.add_item(button_cur)


#    await interaction.channel.send(embed=embed, view=view_hub, view=view_sur, view=view_mir, view=view_cur)


@tree.command(name="server_feedback", description="サーバへの意見・質問を送信できます")
async def feedback(interaction: discord.Interaction):
    embed = discord.Embed(title="サーバへの意見・質問", color=0x32cd32)
    embed.add_field(name="質問・意見は下の**青い部分**をクリック！", value="匿名ですのでお気軽に本音を送信してください")
    embed.add_field(name="質問・意見", value="[ここをクリック！](https://forms.gle/d6nuRrX993T2P44s5)")
    embed.set_image(url="https://cdn.discordapp.com/attachments/1120156753502416896/1131296180907814952/IMG_9620.png")
    embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1120156753502416896/1131296180534509588/IMG_9590.png")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@tree.command(name="ハート", description="♡を送ります")
async def h(inter: discord.Interaction):
    hh = ["❤️", "♡", "🫶", "♡♡♡", "きゅんです！"]
    hhh = random.choice(hh)
    await inter.response.send_message(f'{inter.user.mention}さん{hhh}')

#為替レート計算機

#class JPYUSD(Enum):
#    JPY = "JPY"
#    USD = "USD"

#@tree.command(name="Exchange", description="ドル円計算をします")
#async def exchange(interaction: discord.Integration, どっち: JPYUSD):

#全てのインタラクションを取得
@client.event
async def on_interaction(inter: discord.Interaction):
    try:
        if inter.data['component_type'] == 2:
            await on_button_click11(inter)
    except KeyError:
        pass


last_message_ids = {}
pinned_message = {}
pinned_user = {}
pinned_user_icon = {}

@tree.command(name="pin", description="指定したメッセージを固定します。")
async def pin(inter: discord.Interaction, message: str, channel: discord.TextChannel):
    global last_message_ids, pinned_message, pinned_user, pinned_user_icon

    pinned_message[channel.id] = message
    pinned_user[channel.id] = inter.user.display_name
    pinned_user_icon[channel.id] = inter.user.display_icon

    embed = discord.Embed(title="📌Message ->", description=message)
    embed.set_author(name=f"{inter.user.display_name}", icon_url=inter.user.display_icon.url)

    if channel.id in last_message_ids:
        last_message_id = last_message_ids[channel.id]
        last_message = await channel.fetch_message(last_message_id)
        await last_message.delete()

    new_message = await channel.send(embed=embed)
    last_message_ids[channel.id] = new_message.id

likeEmoji = "<a:z_like_:1104182767274696824>"
yoroshikuEmoji = "<:zm_yoroshiku_:1104198886739947560>"
youkosoEmoji = "<:zm_youkoso:1093735204159492176>"
goodEmoji = "<:THUMBSUP:>"
ryoukaiEmoji = "<:zm_ryoukaidesu:1093734857693220984>"

rigushira_THREAD_ID = 1148199851943800902
oshirase_channel_id = 1092143871829495828
jyuuyou_channel_id = 1092359999604408321
self_channel_id = 1092682540986408990
import pytz
async def set_timer_and_send_message(channel):
    now = datetime.now(pytz.utc) 
    twoh = timedelta(hours=2)
    goodtime = now + twoh 

    goodtime_epoch = int(goodtime.timestamp())
    save_timer_to_json(channel.id, goodtime)
    print(goodtime)  # 現在のUNIXエポックタイムが表示される
    embed_fir = discord.Embed(title="Bumpされました", description=f"<t:{int(goodtime_epoch)}:R> に再度bumpが可能になります\n<t:{int(goodtime_epoch)}>")
    embed_fir.set_image(url="https://cdn.discordapp.com/attachments/1104493356781940766/1139546684779679856/IMG_2122.png")
    timer_message = await channel.send(embed=embed_fir, silent=True)
    
    await asyncio.sleep(7200)  # 2時間待機

    role_id = 1092614583866372207  # ロールのIDを指定
    role = discord.utils.get(channel.guild.roles, id=role_id)
    from datetime import time
    jst = pytz.timezone('Asia/Tokyo')
    current_datetime = datetime.now(jst)
    current_time = current_datetime.time()

    print(f"current_time の型: {type(current_time)}")  # デバッグ出力

    if time(0, 0) <= current_time <= time(7, 0):
        mention_message = "深夜のためメンションは行われません。"  # メンションなし
        new_embed = discord.Embed(title="Bumpが可能になりました!", description="</bump:947088344167366698>を使おう!")
        new_embed.set_image(url="https://cdn.discordapp.com/attachments/1141551959627813006/1141583028687220746/IMB_wXLdj1.gif")
        await timer_message.delete()
        await channel.send(mention_message, embed=new_embed, silent=True)
        return
    else:
        mention_message = f"{role.mention} " if role else ""
        new_embed = discord.Embed(title="Bumpが可能になりました!", description="</bump:947088344167366698>を使おう!")
        new_embed.set_image(url="https://cdn.discordapp.com/attachments/1141551959627813006/1141583028687220746/IMB_wXLdj1.gif")
        await timer_message.delete()
        await channel.send(mention_message, embed=new_embed)
        return

async def send_repeated_messages(channel_id, stop_emoji):
    channel = client.get_channel(channel_id)
    if not channel:
        print("チャンネルが見つかりません。")
        return

    def check(reaction, user):
        return user != client.user and str(reaction.emoji) == stop_emoji

    while True:
        message = await channel.send("<@395131142535249920> \nおきろ")
        print("send")
        try:
            await client.wait_for('reaction_add', timeout=1.0, check=check)
            break
        except asyncio.TimeoutError:
            await asyncio.sleep(1)
            continue
import re
@client.event
async def on_message(message):

    global ModeFlag
    if message.author == client.user:
        return
    if message.channel.type == discord.ChannelType.text:
        user_role_id = 1092510931449299065  # DISBOARDのロールID
        #user_role_id = 1207213280398024706　# HXNでテストする時のロールID
        if isinstance(message.author, discord.Member):
            user_role = discord.utils.get(message.guild.roles, id=user_role_id)

            if user_role and user_role in message.author.roles:
                print("get_user")
                for embed in message.embeds:
                    if embed.description and "表示順をアップしたよ" in embed.description:
                        print("get_embed")
                        await set_timer_and_send_message(message.channel)
                        
    if message.content.startswith('!start_repeating'):
        parts = message.content.split()
        if len(parts) < 2:
            await message.channel.send("チャンネルIDを指定してください。例：!start_repeating 123456789012345678")
            return

        try:
            channel_id = int(parts[1])
        except ValueError:
            await message.channel.send("無効なチャンネルIDです。数値を指定してください。")
            return

        await send_repeated_messages(channel_id, '🛑')
    
    global last_message_ids, pinned_message, pinned_user, pinned_user_icon

    if message.channel.id in last_message_ids:
        last_message_id = last_message_ids[message.channel.id]
        last_message = await message.channel.fetch_message(last_message_id)
        await last_message.delete()

        content = pinned_message[message.channel.id]
        user_name = pinned_user[message.channel.id]
        user_icon = pinned_user_icon[message.channel.id]

        embed = discord.Embed(title="📌Message ->", description=content)
        embed.set_author(name=user_name, icon_url=user_icon)

        new_message = await message.channel.send(embed=embed)
        last_message_ids[message.channel.id] = new_message.id
    if isinstance(message.channel, discord.Thread) and message.channel.id == rigushira_THREAD_ID:
        print("get rigu channel")
        await message.add_reaction(likeEmoji)
        return
    
    if message.channel.id == self_channel_id:
        print("get self channel")
        await message.add_reaction(yoroshikuEmoji)
        await message.add_reaction(youkosoEmoji)
        await message.add_reaction(likeEmoji)

    if message.channel.id == 1095417644674461747:
        if message.attachments:
            for attachment in message.attachments:
                if not attachment.is_spoiler():
                    await message.delete()
                    await message.channel.send(f"{message.author.mention}\n画像にスポイラータグを付けてください。")
    target_guild_id = 1092138492173242430  
    target_channel_id = 1157895182088413275  

    if message.guild is None:  
        return

    if message.guild.id != target_guild_id:  
        return
    if message.channel.id == 1092352567826190386:
        return

    target_channel = client.get_channel(target_channel_id)

    special_extensions = {'ogg'}  

    if message.attachments:
        for attachment in message.attachments:
            file_extension = attachment.filename.split('.')[-1]

            if file_extension in special_extensions:
                embed = discord.Embed(
                    description=f'{message.author.mention}\n\n{message.channel.mention}\n[{file_extension}ファイルです]({attachment.url})\n安全のためオリジナルメッセージは消去されました。',
                    color=0xFF0000,
                    timestamp=message.created_at
                )
                await message.delete()
                await target_channel.send(embed=embed, silent=True)
            else:
                embed = discord.Embed(
                    description=f'{message.author.mention}\n\n{message.jump_url}\nFile: [{attachment.filename}]({attachment.url})',
                    color=0x00FF00,
                    timestamp=message.created_at   
                )
                embed.set_image(url=attachment.url)
                await target_channel.send(embed=embed, silent=True)

    discord_link_pattern = re.compile(r'https://discord\.com/channels/(\d+)/(\d+)/(\d+)')
    found_links = discord_link_pattern.findall(message.content)

    for link in found_links:
        if len(link) != 3:
            continue

        guild_id, channel_id, message_id = map(int, link)
        try:
            guild = client.get_guild(guild_id)
            if guild is None:
                return

            channel = guild.get_channel(channel_id)
            if channel is None:
                return

            fetched_message = await channel.fetch_message(message_id)
            if fetched_message is None:
                return
            if fetched_message.attachments:
                embed = discord.Embed(
                    title=fetched_message.jump_url,
                    description=f"{fetched_message.content}\n\n### 添付されている画像",
                    color=0x76e3ec,
                    timestamp=fetched_message.created_at
                )
                embed.set_image(url=fetched_message.attachments[0].url)
            else:
                embed = discord.Embed(
                    title=fetched_message.jump_url,
                    description=f"{fetched_message.content}",
                    color=0x76e3ec,
                    timestamp=fetched_message.created_at
                )
               
            embed.set_author(name=f"{fetched_message.author.display_name} \nSender: {message.author.id}", icon_url=fetched_message.author.display_avatar)
            embed.set_footer(text=f"チャンネル: {fetched_message.channel.name}\n🗑️を追加するとこの埋め込みを消去できます")  

            embed_message = await message.channel.send(embed=embed, silent=True)
            await embed_message.add_reaction("🗑️")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
    if message.channel.type == discord.ChannelType.news:
        try:
            await message.publish()
        except discord.errors.HTTPException as e:
            print(f"メッセージのクロスポストに失敗しました: {e}")
        
        # お知らせ
        if message.channel.id == oshirase_channel_id:
            print("get oshi channel")
            await message.add_reaction(ryoukaiEmoji)
        # 重要なお知らせ
        elif message.channel.id == jyuuyou_channel_id:
            print("get jyu channel")
            await message.add_reaction(ryoukaiEmoji)
        return

@client.event
async def on_reaction_add(reaction, user):
    if user.bot:
        return

    if str(reaction.emoji) == "🗑️":
        embed = reaction.message.embeds[0] if reaction.message.embeds else None
        if embed and embed.author.name:
            author_text = embed.author.name
            sender_id_str = author_text.split('Sender: ')[-1]
            sender_id = int(sender_id_str)

            if sender_id == user.id:
                await reaction.message.delete()
            else:
                await reaction.remove(user)

@tree.command(name="avatar", description="指定したユーザーのアイコン画像を表示します。")
async def avater(inter: discord.Interaction, user: discord.User):
    jst = pytz.timezone('Asia/Tokyo')
    now = datetime.now(jst)
    e = discord.Embed(
        title=f"{user.display_name}のアイコン画像です。",
        timestamp=now
    )
    if user.avatar.url == user.display_avatar.url:
        e.description = (f"[アイコンURL]({user.avatar.url})")
        e.set_image(url=user.display_avatar)
    else:
        e.description = f"[共通のアイコンURL]({user.avatar.url})\n[サーバーのアイコンURL]({user.display_avatar.url})"
        e.set_thumbnail(url=user.avatar)
        e.set_image(url=user.display_avatar)
    
    await inter.response.send_message(embed=e)
  
#おみくじコマンド
last_omikuji = {}
@tree.command(name="omikuji", description="一日一回おみくじが引けます！")
async def omikuji(interaction: discord.Interaction):

    user_id = interaction.user.id

    # 現在の日付を日本時間で取得
    jp_time = datetime.now(pytz.timezone('Asia/Tokyo'))
    today = jp_time.date()

    # ユーザーが今日既におみくじを引いているかチェック
    if user_id in last_omikuji and last_omikuji[user_id] == today:
        await interaction.response.send_message("今日はもうおみくじを引いています！\n毎日24時にリセットされます！")
        return

    last_omikuji[user_id] = today

    steps = [
        "電脳さくら神社に来た",
        "桜が舞う中おみくじを選ぶ",
        "みこちがこちらをニコニコしながら眺めている",
        "心を落ち着かせおみくじを開く",
    ]

    fortune_choices = ["大吉", "中吉", "小吉", "吉", "末吉"]
    weights = [1, 2, 4, 5, 3] 
    fortune = random.choices(fortune_choices, weights=weights, k=1)[0]

    embed = discord.Embed(title="おみくじ結果", color=0xffdbed)
    embed.set_footer(text="おみくじを引いてくれてありがとう！また明日引いてみてね！")
    embed.set_author(name="電脳さくら神社にて...", url="https://cdn.discordapp.com/attachments/1121698369316851732/1146622798723285023/IMG_2490.png")
    embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1121698369316851732/1146623689127903242/IMG_2492.jpg",)

    # レスポンスを送信
    await interaction.response.send_message(content="おみくじを引きに行く...")

    # メッセージを送信
    message = await interaction.followup.send(content=interaction.user.mention, embed=embed)

    # 一行ずつメッセージを送信していく
    description_with_steps = ""
    for step in steps:
        await asyncio.sleep(2)  # 1秒待機
        description_with_steps += f"\n\n{step}"  # 改行と空行を追加
        embed.description = description_with_steps
        await message.edit(embed=embed)
        await asyncio.sleep(1)
        embed.description += f"\n\nおみくじには**{fortune}**と書かれていた"
    await message.edit(embed=embed)
    if fortune == "大吉":
        await asyncio.sleep(1)
        embed.description += f"\n\nおめでとう！\n今日はとても良い日になるでしょう！"
        await message.edit(embed=embed)
        await message.add_reaction("🎉")

SPECIAL_ROLE_ID = 1106343986391683152

@client.event
async def on_member_update(before, after):
    try:
        if after.guild is None or before.roles == after.roles:
            return

        special_role = after.guild.get_role(SPECIAL_ROLE_ID)
        if special_role in after.roles and special_role not in before.roles:
            print(f"{after.display_name} が参加拒否ロールを取得しました。")

            roles_to_remove = [role for role in before.roles if role.id != SPECIAL_ROLE_ID and role.name != '@everyone']
            if roles_to_remove:
                await after.remove_roles(*roles_to_remove)
                removed_roles_names = [role.name for role in roles_to_remove]
                print(f"{after.display_name} から剥奪されたロール: {', '.join(removed_roles_names)}")
                await asyncio.sleep(5)

                if removed_roles_names:
                    removed_roles_str = ', '.join(removed_roles_names)
                    channel = after.guild.get_channel(1092326527837949992)
                    embed = discord.Embed(title="参加拒否通知", color=discord.Color.red())
                    embed.add_field(name="ユーザー", value=after.display_name, inline=True)
                    embed.add_field(name="ユーザーID", value=after.id, inline=True)
                    embed.add_field(name="削除されたロール", value=removed_roles_str, inline=False)
                    embed.set_thumbnail(url=after.avatar.url)
                    
                    await channel.send(embed=embed)

    except Exception as e:
        print(f"エラーが発生しました: {type(e).__name__}, {e}")

COLORS = {
    "赤": "FF0000",
    "緑": "00FF00",
    "青": "0000FF",
    "黄": "FFFF00",
    "白": "FFFFFF",
}

@tree.command(name="create_role", description="ロールを作成します")
async def create_role(interaction: discord.Interaction, name: str, color:str):
    role_name = name

    # 色が辞書に存在する場合、該当する色コードを取得
    if color in COLORS:
        color_code = COLORS[color]
    else:
        await interaction.response.send_message(f"指定された色 `{color}` は認識できません。", ephemeral=True)
        return

    role_color = discord.Color(int(color_code, 16))
    # ロール作成
    role = await interaction.guild.create_role(name=role_name, color=role_color)
    await interaction.response.send_message(f"{role.mention}を`{role.color}`色で作成しました", ephemeral=True)


#ログ機能テスト


import math
import aiohttp

async def fetch_image(session, url):
    async with session.get(url) as response:
        return await response.read()

@client.event
async def on_message_delete(message):
    if message.author.bot:
        return
    if message.channel.name == "📮┫グローバルチャット":
        return
    guild = message.guild
    deleter = None

    async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.message_delete):
        if entry.target.id == message.author.id and entry.extra.channel.id == message.channel.id:
            deleter = entry.user
            break

    embed = discord.Embed(title="メッセージ消去ログ", color=discord.Color.red(), timestamp=message.created_at )
    embed.set_author(name=message.author.display_name, icon_url=message.author.avatar)
    embed.add_field(name="メッセージ", value=f"`{message.content}`" or "なし", inline=False)
    embed.add_field(name="チャンネル", value=message.channel.mention, inline=True)
    embed.set_footer(text="メッセージID | " + str(message.id))
    if deleter:
        embed.add_field(name="消去者", value=deleter.mention, inline=True)
    else:
        embed.add_field(name="消去者", value=message.author.mention, inline=True)

    attachment_urls = [attachment.url for attachment in message.attachments]
    if len(attachment_urls) > 0:
        async with aiohttp.ClientSession() as session:
            images = []
            image_links = []
            max_width = 0
            max_height = 0
            for i, attachment_url in enumerate(attachment_urls[:10], start=1):
                image_bytes = await fetch_image(session, attachment_url)
                image = Image.open(io.BytesIO(image_bytes))
                images.append(image)
                image_links.append(f"[画像{i}]({attachment_url})")

                # 最大の画像サイズを取得
                max_width = max(max_width, image.width)
                max_height = max(max_height, image.height)

            num_images = len(images)
            max_images_per_row = 2
            max_rows = math.ceil(num_images / max_images_per_row)

            merged_width = max_width * max_images_per_row
            merged_height = max_height * max_rows

            merged_image = Image.new("RGB", (merged_width, merged_height), (255, 255, 255))

            for i, image in enumerate(images):
                resized_image = image.resize((max_width, max_height))
                x_offset = (i % max_images_per_row) * max_width
                y_offset = (i // max_images_per_row) * max_height
                merged_image.paste(resized_image, (x_offset, y_offset))

            with io.BytesIO() as output:
                merged_image.save(output, format='PNG')
                output.seek(0)
                file = discord.File(output, filename="merged_images.png")

                channel = client.get_channel(1128694609980174467)
                thread = None

                for existing_thread in channel.threads:
                    if existing_thread.id == 1128694821935141105:
                        thread = existing_thread
                        break

                if thread is None:
                    # スレッドが見つからなかった場合の処理
                    return

                await thread.send(embed=embed)  # スレッドにメッセージを投稿
                await thread.send("`消去された画像`")
                await thread.send(file=file)  # スレッドに画像を投稿

    else:
        embed.add_field(name="添付ファイル", value="なし", inline=False)

        channel = client.get_channel(1128694609980174467)
        thread = None

        for existing_thread in channel.threads:
            if existing_thread.id == 1128694821935141105:
                thread = existing_thread
                break

        if thread is None:
            # スレッドが見つからなかった場合の処理
            return

        await thread.send(embed=embed)  # スレッドにメッセージを投稿
        return
   
def shorten_text(text, max_length=1024):
    if len(text) > max_length:
        return text[:max_length-3] + "..."
    return text

@client.event
async def on_message_edit(message_before, message_after):
    # ボットが送信したメッセージは無視する
    if message_before.author.bot:
        return

    # メッセージの内容が変更されていない場合は無視する
    if message_before.content == message_after.content:
        return

    # 現在の時刻を取得
    JST = timezone(timedelta(hours=+9))
    now = datetime.now(JST)

    # ログを埋め込みメッセージとして作成
    embed = discord.Embed(title="メッセージ編集ログ", color=discord.Color.green(), timestamp=message_before.created_at )
    embed.add_field(name="編集前", value=shorten_text(message_before.content), inline=True)
    embed.add_field(name="編集後", value=shorten_text(message_after.content), inline=True)
    embed.add_field(name="チャンネル", value="\n"+message_before.channel.mention + f"\n[メッセージに飛ぶ]({message_after.jump_url})", inline=True)
    embed.set_author(icon_url=message_before.author.avatar, name=message_before.author.display_name)
    embed.set_footer(text="メッセージID | " + str(message_before.id))

    thread_id = 1128694821935141105
    thread = await client.fetch_channel(thread_id)

    if thread is None or not isinstance(thread, discord.Thread):
        return

    try:
        await thread.send(embed=embed)
    except discord.Forbidden:
        return

@client.event
async def on_voice_state_update(member, before, after):
    thread_id = 1128694862263369849
    thread = await client.fetch_channel(thread_id)

    if thread is None or not isinstance(thread, discord.Thread):
        return

    JST = timezone(timedelta(hours=+9))
    now = datetime.now(JST)

    if before.channel is None and after.channel is not None:
        embed = discord.Embed(title="ボイスチャンネル入室ログ", color=discord.Color.green(), timestamp=now )
        embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1104493356781940766/1158216598142845018/IMG_1002_adobe_express.png")
        embed.set_author(name=member.display_name, icon_url=member.avatar)
        embed.add_field(name="ユーザー", value=member.mention, inline=True)
        embed.add_field(name="参加したチャンネル", value=f"{after.channel.name}\n{after.channel.mention}", inline=True)
        

        try:
            await thread.send(embed=embed)
        except discord.Forbidden:
            return

    elif before.channel is not None and after.channel is None:
        embed = discord.Embed(title="ボイスチャンネル退出ログ", color=discord.Color.red(), timestamp=now )
        embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1104493356781940766/1158216598553894982/IMG_1003_adobe_express.png")
        embed.set_author(name=member.display_name, icon_url=member.avatar)
        embed.add_field(name="ユーザー", value=member.mention, inline=True)
        embed.add_field(name="退出したチャンネル", value=f"{before.channel.name}\n{before.channel.mention}", inline=True)

        

        try:
            await thread.send(embed=embed)
        except discord.Forbidden:
            return

    elif before.channel != after.channel:
        embed = discord.Embed(title="ボイスチャンネル移動ログ", color=discord.Color.blue(), timestamp=now )
        embed.set_thumbnail(url="https://raw.githubusercontent.com/twitter/twemoji/master/assets/72x72/2195.png")
        embed.set_author(name=member.display_name, icon_url=member.avatar)
        embed.add_field(name="ユーザー", value=member.mention, inline=True)
        embed.add_field(name="移動前のチャンネル", value=f"{before.channel.name}\n{before.channel.mention}", inline=True)
        embed.add_field(name="移動後のチャンネル", value=f"{after.channel.name}\n{after.channel.mention}", inline=True)

        

        try:
            await thread.send(embed=embed)
        except discord.Forbidden:
            return

    return

@client.event
async def on_member_join(member):
    thread_id = 1128694782827446333
    thread = await client.fetch_channel(thread_id)
    
    JST = timezone(timedelta(hours=+9))
    now = datetime.now(JST)

    created_at = member.created_at.replace(tzinfo=timezone.utc).astimezone(JST)

    embed = discord.Embed(title="ユーザー参加ログ", color=discord.Color.green(), timestamp=now )
    embed.set_author(name=member.name, icon_url=member.avatar)
    embed.add_field(name="ユーザー名", value=member.display_name + "\n" + member.mention, inline=True)
    embed.add_field(name="ユーザーID", value=str(member.id), inline=True)

    nownow = current_time1()
    created_at_timestamp = created_at.timestamp()
    account_age = nownow - created_at_timestamp

    embed.add_field(name="アカウント年齢", value=now.strftime('%Y/%m/%d  %H:%M:%S') + f"| <t:{int(account_age)}:R>", inline=True)

    await thread.send(embed=embed)
@client.event
async def on_member_remove(member):
    thread_id = 1128694782827446333
    thread = await client.fetch_channel(thread_id)
    guild = member.guild
    JST = timezone(timedelta(hours=+9))
    now = datetime.now(JST)
    async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.kick):
        if discord.utils.utcnow() - entry.created_at < timedelta(minutes=1):
            thread_id = 1128694908832718968
            thread = await client.fetch_channel(thread_id)
            if entry.reason == None:
                reason = "なし"
            else:
                reason = entry.reason
            embed = discord.Embed(title="ユーザーキックログ", color=discord.Color.orange(), timestamp=now)
            embed.set_author(name=member.name, icon_url=member.avatar)
            embed.add_field(name="ユーザー名", value=member.mention, inline=True)
            embed.add_field(name="ユーザーID", value=member.id, inline=True)
            embed.add_field(name="実行者", value=entry.user.mention, inline=True)
            embed.add_field(name="理由", value=reason, inline=True)  
            await thread.send(embed=embed)
            break
        else:
            embed = discord.Embed(title="ユーザー退出ログ", color=discord.Color.red(), timestamp=now)
            embed.set_author(name=member.name, icon_url=member.avatar)
            embed.add_field(name="ユーザー名", value=member.display_name + "\n" + member.mention, inline=True)
            embed.add_field(name="ユーザーID", value=member.id, inline=True)
            await thread.send(embed=embed)
            return

@client.event
async def on_member_ban(guild, user):
    thread_id = 1128694908832718968
    thread = await client.fetch_channel(thread_id)
    if thread is None:
        return
    async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.ban):     
                if user == entry.target and discord.utils.utcnow() - entry.created_at < timedelta(seconds=30):
                    if entry.reason == None:
                        reason = "なし"
                    else:
                        reason = entry.reason
                        JST = timezone(timedelta(hours=+9))
                        now = datetime.now(JST)
                        embed = discord.Embed(title="ユーザーBANログ", color=discord.Color.red(), timestamp=now)
                        embed.set_author(name=user.display_name, icon_url=user.avatar)
                        embed.add_field(name="ユーザー名", value=user.mention, inline=True)
                        embed.add_field(name="ユーザーID", value=user.id, inline=True)
                        embed.add_field(name="実行者", value=entry.user.mention, inline=True)
                        embed.add_field(name="理由", value=reason, inline=True)

                        await thread.send(embed=embed)
                        return

@client.event
async def on_member_unban(guild, member):
    thread_id = 1128694908832718968
    thread = await client.fetch_channel(thread_id)
    
    async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.unban):
        print(discord.utils.utcnow())
        print(entry.created_at)
        if member == entry.target and discord.utils.utcnow() - entry.created_at < timedelta(seconds=30):

            JST = timezone(timedelta(hours=+9))
            now = datetime.now(JST)
            embed = discord.Embed(title="ユーザーUNBANログ", color=discord.Color.green(), timestamp=now)
            embed.set_author(name=member.display_name, icon_url=member.avatar)
            embed.add_field(name="ユーザー名", value=member.mention, inline=True)
            embed.add_field(name="ユーザーID", value=member.id, inline=True)
            embed.add_field(name="実行者", value=entry.user.mention, inline=False)


            await thread.send(embed=embed)
            return

#@client.event
#async def on_member_timeout(member, time_remaining, reason):
#    thread_id = 1128694908832718968  # ログを送信するスレッドのIDを指定してください
#    thread = await client.fetch_channel(thread_id)

#    if thread is None or not isinstance(thread, discord.Thread):
        # スレッドが見つからなかった場合の処理
#        return

#    now = datetime.datetime.now()
#    timeout_end = now + datetime.timedelta(seconds=time_remaining)

#    embed = discord.Embed(title="タイムアウトログ", color=discord.Color.orange())
#    embed.set_author(name=member.name, icon_url=member.avatar.url)
#    embed.add_field(name="ユーザー名", value=member.display_name, inline=True)
#    embed.add_field(name="ユーザーID", value=member.id, inline=True)
#    embed.add_field(name="タイムアウト解除までの残り時間", value=f"{time_remaining}秒", inline=False)
#    embed.add_field(name="タイムアウト解除予定時刻", value=timeout_end.strftime('%Y/%m/%d  %H:%M:%S'), inline=False)
#    embed.add_field(name="理由", value=reason, inline=False)
#    embed.set_footer(text=now.strftime('%Y/%m/%d  %H:%M:%S'))

#    try:
#        await thread.send(embed=embed)  # スレッドにメッセージを投稿
#    except discord.Forbidden:
        # メッセージの投稿権限がない場合の処理
#        return

class MyStatus(Enum):
    オンライン = "online"
    オフライン = "invisible"
    取り込み中 = "dnd"
    退席中 = "idle"

@tree.command(description="Botのステータスを変更します")
async def status(inter: discord.Interaction, chosen_status: MyStatus):
    try:
        new_status = MyStatus(chosen_status).value
    except ValueError:
        available_statuses = ", ".join([status.name for status in MyStatus])
        await inter.response.send_message(f"無効なステータス！以下の選択肢から選んでください: {available_statuses}")
        return
    
    await inter.response.send_message(f"Botのステータスを {new_status} に設定しました。")
    while True:
     await client.change_presence(status=discord.Status[new_status])

@tree.command(
    name="show_spam_user",
    description="スパム疑惑のあるユーザーをリスト化して送信します。"
)
async def spam_user(interaction: discord.Interaction):
    specific_role_ids = {1092330136617107476, 1092143589284401292, 1092354666328772618}

    if interaction.guild is not None:
        member_infos = []

        for member in interaction.guild.members:
            member_role_ids = {role.id for role in member.roles if role.name != "@everyone"}

            if member_role_ids == specific_role_ids:
                member_info = f"{member.mention} - 参加日: {member.joined_at.strftime('%Y年%m月%d日')}"
                member_infos.append(member_info)

        if member_infos:
            message_content = "指定されたロールのみを持っているユーザー:\n" + "\n".join(member_infos)
            await interaction.response.send_message(message_content)
        else:
            await interaction.response.send_message("指定されたロールのみを持っているユーザーはいません。")
    else:
        await interaction.response.send_message("ギルドの情報が取得できませんでした。")

@bot.tree.command(
    name="assign_role_to_spam_user",
    description="スパム疑惑のあるユーザーに新しいロールを付与します。"
)
async def assign_role_to_spam_user(interaction: discord.Interaction):
    specific_role_ids = {1092330136617107476, 1092143589284401292, 1092354666328772618}
    new_role_id = 123456789012345678

    if interaction.guild is not None:
        new_role = interaction.guild.get_role(new_role_id)

        if new_role is None:
            await interaction.response.send_message("新しいロールが見つかりません。")
            return

        for member in interaction.guild.members:
            member_role_ids = {role.id for role in member.roles if role.name != "@everyone"}

            if member_role_ids == specific_role_ids:
                await member.add_roles(new_role)

        await interaction.response.send_message("指定されたロールを持つユーザーに新しいロールを付与しました。")
    else:
        await interaction.response.send_message("ギルドの情報が取得できませんでした。")

@tree.command(
    name="show_hololisu_role_user",
    description="ホロリスロールのみを持っているユーザーをリスト化して送信します。"
)
async def show_single_role_user(interaction: discord.Interaction):
    single_role_id = 1092143589284401292

    if interaction.guild is not None:
        member_infos = []

        for member in interaction.guild.members:
            member_role_ids = {role.id for role in member.roles if role.name != "@everyone"}

            if member_role_ids == {single_role_id}:
                member_info = (member, member.joined_at)  # メンバーと参加日をタプルで保存
                member_infos.append(member_info)

        # 参加日が古い順にソート
        member_infos.sort(key=lambda x: x[1])

        total_members = len(member_infos)
        if member_infos:
            message_content = f"ホロリスロールのみを持っているユーザー: {total_members}人\n"
            await interaction.response.send_message(message_content)
            # メッセージを2000文字ごとに分割して送信
            for i in range(0, len(member_infos), 10):  # 10メンバーごとに分割
                message_part = "\n".join([f"{member[0].mention} - 参加日: {member[1].strftime('%Y年%m月%d日')}" for member in member_infos[i:i+10]])
                await interaction.followup.send(message_part)
        else:
            await interaction.response.send_message("条件に合うユーザーはいません。")
    else:
        await interaction.response.send_message("ギルドの情報が取得できませんでした。")

@tree.command(
    name="show_none_role_user",
    description="ロールを一つも持っていないユーザーをリスト化して送信します。"
)
async def show_none_role_user(interaction: discord.Interaction):
    if interaction.guild is not None:
        member_infos = []

        for member in interaction.guild.members:
            # メンバーが持っているロールIDのセット（@everyone ロールを除外）
            member_role_ids = {role.id for role in member.roles if role.name != "@everyone"}

            # メンバーが他のロールを一つも持っていないかチェック
            if not member_role_ids:
                member_info = f"{member.mention} - 参加日: {member.joined_at.strftime('%Y年%m月%d日')}"
                member_infos.append(member_info)

        total_members = len(member_infos)
        if member_infos:
            message_content = f"ロールを一つも持っていないユーザー: {total_members}人\n"
            await interaction.response.send_message(message_content)
            # メッセージを2000文字ごとに分割して送信
            for i in range(0, len(member_infos), 10):  # 10メンバーごとに分割
                message_part = "\n".join(member_infos[i:i+10])
                await interaction.followup.send(message_part)
        else:
            await interaction.response.send_message("条件に合うユーザーはいません。")
    else:
        await interaction.response.send_message("ギルドの情報が取得できませんでした。")

client.run(TOKEN)