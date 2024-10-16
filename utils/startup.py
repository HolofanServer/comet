import discord
from discord.ext import commands

import pytz
import platform
import psutil
import os
import subprocess
import json
import pyfiglet
import pkg_resources

from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

from utils.startup_create import create_usage_bar
from utils.logging import setup_logging

logger = setup_logging()
load_dotenv()

bot_owner_id = int(os.getenv('BOT_OWNER_ID'))
startup_channel_id = int(os.getenv('STARTUP_CHANNEL_ID'))
startup_guild_id = int(os.getenv('DEV_GUILD_ID'))

with open('config/bot.json', 'r') as f:
    bot_config = json.load(f)
with open('config/version.json', 'r') as f:
    version_config = json.load(f)

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
        if platform.system() == "Darwin":
            result = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True, check=True)
            return result.stdout.strip()
        if platform.system() == "Windows":
            result = subprocess.run(["wmic", "cpu", "get", "name"], capture_output=True, text=True, check=True)
            return result.stdout.strip().split('\n')[1]
        else:
            result = subprocess.run(["lscpu"], capture_output=True, text=True, check=True)
            if result.stdout:
                for line in result.stdout.split('\n'):
                    if "Model name" in line:
                        return line.split(':')[1].strip()
    except subprocess.CalledProcessError:
        return "取得に失敗しました"
    except FileNotFoundError:
        return "コマンドが見つかりません"

def get_detailed_discord_version():
    """詳細なdiscord.pyのバージョンを取得する"""
    try:
        version = pkg_resources.get_distribution("discord.py").version
        return version
    except pkg_resources.DistributionNotFound:
        return "バージョン情報が見つかりません"

async def startup_send_webhook(bot, guild_id):
    guild = bot.get_guild(guild_id)
    if guild is None:
        logger.warning("ギルドが見つかりません。")
        return

    channel = guild.get_channel(startup_channel_id)
    if channel is None:
        logger.warning("指定されたチャンネルが見つかりません。")
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
            logger.warning(f"ログファイルが見つかりません: {log_file_path}")
        except json.JSONDecodeError:
            logger.warning(f"ログファイルの形式が正しくありません: {log_file_path}")
        return None

    latest_log_file = find_latest_log_file()
    session_id = None
    if latest_log_file:
        session_id = find_session_id_from_json(latest_log_file)
        if session_id:
            logger.info(f"Found Session ID: {session_id}")
        else:
            logger.warning("Session ID not found.")
    else:
        logger.warning("ログファイルが見つかりませんでした。")

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
        logger.warning("ギルドが見つかりません。")
        return

    channel = guild.get_channel(startup_channel_id)
    if channel is None:
        logger.warning("指定されたチャンネルが見つかりません。")
        return
    
    discord_py_hash = get_detailed_discord_version().split(discord.__version__)[1]
    os_info = f"{platform.system()} {platform.release()} ({platform.version()})"
    cpu_info = get_cpu_model_name()
    cpu_cores = f"{psutil.cpu_count(logical=True)} / {psutil.cpu_count(logical=False)}"
    if psutil.cpu_count(logical=True) == psutil.cpu_count(logical=False):
        cpu_cores = f"{psutil.cpu_count(logical=True)}"

    cpu_usage = psutil.cpu_percent()
    memory = psutil.virtual_memory()
    memory_usage = memory.percent

    total_memory_gb = round(memory.total / (1024 ** 3), 2)
    
    cpu_bar = create_usage_bar(cpu_usage)
    memory_bar = create_usage_bar(memory_usage)

    embed = discord.Embed(title="BOT情報", color=0x00ff00)
    embed.add_field(name="BOT", value=f"開発者: <@{bo.id}>", inline=False)
    if discord_py_hash != "":
        embed.add_field(name="開発言語", value=f"discord.py {discord.__version__}[{discord_py_hash}](https://github.com/Rapptz/discord.py/commit/master)", inline=False)
    else:
        embed.add_field(name="開発言語", value=f"discord.py {discord.__version__}", inline=False)
    embed.add_field(name="OS", value=os_info, inline=False)
    embed.add_field(name="CPU", value=cpu_info, inline=False)
    embed.add_field(name="CPU コア", value=cpu_cores, inline=False)
    embed.add_field(name="CPU 使用率", value=cpu_bar, inline=False)
    embed.add_field(name="メモリ使用率", value=f"{memory_bar} / {total_memory_gb}GB", inline=False)

    webhook = await channel.create_webhook(name="BOT情報")
    await webhook.send(embed=embed)

    await webhook.delete()

def startup_message():
    b_v = rainbow_text(pyfiglet.figlet_format("Bot Version: " + version_config['version']))
    b_n = rainbow_text(pyfiglet.figlet_format("Bot Name: " + bot_config['name']))
    yokobou = rainbow_text("----------------------------------------")

    startup_message = "\n" + yokobou + "\n" + b_v + "\n" + b_n + "\n" + yokobou + "\n"
    return startup_message

def yokobou():
    return rainbow_text("----------------------------------------")

def rainbow_text(text):
    """文字列を虹色にする"""
    colors = [
        "\033[1;31m",
        "\033[1;33m",
        "\033[1;32m",
        "\033[1;36m",
        "\033[1;34m",
        "\033[1;35m",
    ]
    reset = "\033[0m"
    colored_text = ""
    for i, char in enumerate(text):
        colored_text += colors[i % len(colors)] + char
    return colored_text + reset
