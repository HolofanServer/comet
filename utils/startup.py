import discord
from discord.ext import commands
from datetime import datetime
import pytz
import platform
import psutil
import os
from utils.startup_create import create_usage_bar
from pathlib import Path
import subprocess
from dotenv import load_dotenv
import json

load_dotenv()

bot_owner_id = int(os.getenv('BOT_OWNER_ID'))
startup_channel_id = int(os.getenv('STARTUP_CHANNEL_ID'))
startup_guild_id = int(os.getenv('MAIN_GUILD_ID'))
print(f"{startup_channel_id}, {startup_guild_id}")

async def load_cogs(bot, directory='./cogs'):
    failed_cogs = {}
    for path in Path(directory).rglob('*.py'):
        relative_path = path.relative_to('.')
        cog_path = str(relative_path).replace('/', '.').replace('\\', '.')[:-3]

        try:
            await bot.load_extension(cog_path)
        except commands.ExtensionAlreadyLoaded:
            continue
        except (commands.ExtensionFailed, commands.NoEntryPointError, commands.ExtensionNotFound) as e:
            failed_cogs[cog_path] = str(e)

    bot.failed_cogs = failed_cogs
    return failed_cogs

def get_cpu_model_name():
    """CPUモデル名を取得する"""
    try:
        result = subprocess.run(["lscpu"], capture_output=True, text=True, check=True)
        if result.stdout:
            for line in result.stdout.split('\n'):
                if "Model name" in line:
                    return line.split(':')[1].strip()
    except subprocess.CalledProcessError:
        return "取得に失敗しました"

def get_service_uptime(service_name: str):
    try:
        result = subprocess.run(["sudo", "systemctl", "show", "-p", "ActiveEnterTimestamp", service_name], capture_output=True, text=True, check=True)
        output = result.stdout.strip()

        utc_zone = datetime.timezone.utc
        jst_zone = datetime.timezone(datetime.timedelta(hours=9))

        start_time_str = output.split("=")[-1].strip()
        start_time_utc = datetime.datetime.strptime(start_time_str, "%a %Y-%m-%d %H:%M:%S %Z")

        start_time_jst = start_time_utc.replace(tzinfo=utc_zone).astimezone(jst_zone)
        now_jst = datetime.datetime.now(jst_zone)
        uptime = now_jst - start_time_jst

        return str(uptime).split('.')[0]
    except Exception:
        return "取得に失敗しました"

async def startup_send_webhook(bot, guild_id):
    guild = bot.get_guild(guild_id)
    if guild is None:
        print("ギルドが見つかりません。")
        return

    channel = guild.get_channel(startup_channel_id)
    if channel is None:
        print("指定されたチャンネルが見つかりません。")
        return

    jst_time = datetime.now(pytz.timezone('Asia/Tokyo')).strftime('%Y-%m-%d_%H-%M-%S')
    webhook_name = f"{bot.user.name} | {jst_time}"

    def find_latest_log_file(base_dir='data/logging'):
        """最新のログファイルのパスを返す関数"""
        latest_date_dir = max([os.path.join(base_dir, d) for d in os.listdir(base_dir)], key=os.path.getmtime)
        latest_time_dir = max([os.path.join(latest_date_dir, d) for d in os.listdir(latest_date_dir)], key=os.path.getmtime)
        log_files = [os.path.join(latest_time_dir, f) for f in os.listdir(latest_time_dir) if f.endswith('.json')]
        if log_files:
            return max(log_files, key=os.path.getmtime)
        return None

    def find_session_id_from_json(log_file_path):
        """JSON形式のログファイルからセッションIDを検索し、見つかった場合は返す関数"""
        try:
            with open(log_file_path, 'r') as log_file:
                log_data = json.load(log_file)
                return log_data.get('session_id')
        except FileNotFoundError:
            print(f"ログファイルが見つかりません: {log_file_path}")
        except json.JSONDecodeError:
            print(f"ログファイルの形式が正しくありません: {log_file_path}")
        return None

    latest_log_file = find_latest_log_file()
    session_id = None
    if latest_log_file:
        session_id = find_session_id_from_json(latest_log_file)
        if session_id:
            print(f"Found Session ID: {session_id}")
        else:
            print("Session ID not found.")
    else:
        print("ログファイルが見つかりませんでした。")

    failed_cogs = await load_cogs(bot)

    embed = discord.Embed(title="起動通知", description="Botが起動しました。", color=discord.Color.green() if not failed_cogs else discord.Color.red())
    embed.add_field(name="Bot名", value=bot.user.name, inline=True)
    embed.add_field(name="Bot ID", value=bot.user.id, inline=True)
    embed.add_field(name="CogsList", value=", ".join(bot.cogs.keys()), inline=False)
    embed.set_footer(text="Botは正常に起動しました。" if not failed_cogs else "Botは正常に起動していません。")
    embed.set_author(name=session_id)

    if failed_cogs:
        failed_embed = discord.Embed(title="正常に読み込めなかったCogファイル一覧", color=discord.Color.red())
        for cog, error in failed_cogs.items():
            failed_embed.add_field(name=cog, value=error, inline=False)
        webhook = await channel.create_webhook(name=webhook_name)
        await webhook.send(embeds=[embed, failed_embed])
        await webhook.delete()
    else:
        webhook = await channel.create_webhook(name=webhook_name)
        await webhook.send(embed=embed)
        await webhook.delete() 

async def startup_send_botinfo(bot):
    guild = bot.get_guild(startup_guild_id)
    bo = bot.get_user(bot_owner_id)
    if guild is None:
        print("ギルドが見つかりません。")
        return

    channel = guild.get_channel(startup_channel_id)
    if channel is None:
        print("指定されたチャンネルが見つかりません。")
        return
    discord_py_version = discord.__version__
    os_info = f"{platform.system()} {platform.release()} ({platform.version()})"
    cpu_info = get_cpu_model_name()
    cpu_cores = f"論理コア: {psutil.cpu_count(logical=True)}, 物理コア: {psutil.cpu_count(logical=False)}"

    cpu_usage = psutil.cpu_percent()
    memory = psutil.virtual_memory()
    memory_usage = memory.percent

    total_memory_gb = round(memory.total / (1024 ** 3), 2)
    
    cpu_bar = create_usage_bar(cpu_usage)
    memory_bar = create_usage_bar(memory_usage)

    embed = discord.Embed(title="BOT情報", color=0x00ff00)
    embed.add_field(name="BOT", value=f"開発者: <@{bo.id}>", inline=False)
    embed.add_field(name="開発言語", value=f"discord.py {discord_py_version}", inline=False)
    embed.add_field(name="OS", value=os_info, inline=False)
    embed.add_field(name="CPU", value=cpu_info, inline=False)
    embed.add_field(name="CPU コア", value=cpu_cores, inline=False)
    embed.add_field(name="稼働時間", value=get_service_uptime("nijiiro_yume.service"), inline=False)
    embed.add_field(name="CPU 使用率", value=cpu_bar, inline=False)
    embed.add_field(name="メモリ使用率", value=f"{memory_bar} / {total_memory_gb}GB", inline=False)

    webhook = await channel.create_webhook(name="BOT情報")
    await webhook.send(embed=embed)

    await webhook.delete()