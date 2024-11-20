import discord
from discord.ext import commands

import time
import subprocess
import datetime
import platform

from utils.startup_create import create_usage_bar
from utils.stats import get_stats
from utils.commands_help import log_commnads, is_moderator
from utils.logging import setup_logging

logger = setup_logging("D")

class ProcessInfoCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.start_time = time.monotonic()
        
    @commands.hybrid_group(name="bot")
    async def bot(self, ctx):
        """botの管理コマンド"""
        pass

    @bot.command(name="info")
    @is_moderator()
    @log_commnads()
    async def info(self, ctx):
        """BOTのプロセス情報を取得します。"""
        logger.info("BOTのプロセス情報取得コマンドが実行されました。")
        try:
            if platform.system() == "Darwin":
                python_path = "/Users/freewifi/iphone3g/iphone3g/bin/python"
            elif platform.system() == "Linux":
                python_path = "/home/freewifi110/iphone3g/iphone3g/bin/python"
            else:
                python_path = None
                logger.warning("サポートされていないOSです。")
                await ctx.send("サポートされていないOSです。")
                return

            if python_path:
                result = subprocess.run(
                    ["pgrep", "-af", python_path],
                    stdout=subprocess.PIPE,
                    text=True
                )
            else:
                await ctx.send("サポートされていないOSです。")
                logger.warning("サポートされていないOSです。")
                return

            lines = result.stdout.strip().split("\n")
            if not lines:
                await ctx.send("指定されたコマンドを実行しているプロセスが見つかりませんでした。")
                logger.warning("指定されたコマンドを実行しているプロセスが見つかりませんでした。")
                return
            
            process_info = []
            for line in lines:
                parts = line.split(None, 1)
                pid = parts[0]

                result = subprocess.run(
                    ["ps", "-p", pid, "-o", "%cpu,%mem,rss"],
                    stdout=subprocess.PIPE,
                    text=True
                )
                process_data = result.stdout.strip().split("\n")[1].split(None, 3)
                cpu, mem, rss = process_data

                memory_usage_gb = round(int(rss) / (1024 ** 2), 2)

                cpu_bar = create_usage_bar(float(cpu))
                mem_bar = create_usage_bar(float(mem))

                process_info.append((cpu_bar, mem_bar, memory_usage_gb))

            embed1 = discord.Embed(title="BOTのプロセス情報", color=discord.Color.blue())
            embed1.add_field(name="CPU使用率", value=f"{cpu_bar}", inline=True)
            embed1.add_field(name="メモリ使用率", value=f"{mem_bar} / {memory_usage_gb}GB", inline=True)

            embed2 = discord.Embed(title="BOTの情報", color=discord.Color.blue())
            elapsed_time = time.monotonic() - self.start_time
            uptime_delta = datetime.timedelta(seconds=int(elapsed_time))
            total_seconds = uptime_delta.total_seconds()

            weeks, remainder = divmod(total_seconds, 604800)
            days, remainder = divmod(remainder, 86400)
            hours, remainder = divmod(remainder, 3600)
            minutes, seconds = divmod(remainder, 60)

            if weeks > 0:
                uptime_text = f"{int(weeks)}週間{int(days)}日{int(hours)}時間{int(minutes)}分{int(seconds)}秒"
            elif days > 0:
                uptime_text = f"{int(days)}日{int(hours)}時間{int(minutes)}分{int(seconds)}秒"
            elif hours > 0:
                uptime_text = f"{int(hours)}時間{int(minutes)}分{int(seconds)}秒"
            elif minutes > 0:
                uptime_text = f"{int(minutes)}分{int(seconds)}秒"
            else:
                uptime_text = f"{int(seconds)}秒"

            embed2.add_field(name="UPTIME", value=uptime_text, inline=False)

            stats = await get_stats()
            embed2.add_field(name="トータルコマンド回数", value=f"{stats.get('commands', {}).get('total', 0)}回", inline=True)
            embed2.add_field(name="トータルエラー回数", value=f"{stats.get('errors', {}).get('total', 0)}回", inline=True)
            embed2.add_field(name="Bot Ping", value="計測中...", inline=True)

            sent_message = await ctx.send(embeds=[embed1, embed2])
            logger.info("BOTのプロセス情報を送信しました。")
            end_time = time.monotonic()
            logger.info("BOTのPingを計測します。")

            bot_ping = round((end_time - self.start_time) * 1000)
            logger.info(f"BOTのPingを計測しました。{bot_ping}ms")
            
            embed2.set_field_at(3, name="Bot Ping", value=f"{bot_ping}ms", inline=True)
            
            await sent_message.edit(embeds=[embed1, embed2])
            logger.info("BOTのPingを送信しました。")
        except Exception as e:
            logger.error(f"エラーが発生しました: {e}")
            await ctx.send(f"エラーが発生しました: {e}")

async def setup(bot):
    await bot.add_cog(ProcessInfoCog(bot))