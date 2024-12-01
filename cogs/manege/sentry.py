import discord
from discord.ext import commands, tasks

import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration
import psutil
import datetime
import platform
import socket

from utils.logging import setup_logging
from config.setting import get_settings

logger = setup_logging("D")
settings = get_settings()

dsn = settings.sentry_dsn

# Sentry初期化
sentry_sdk.init(
    dsn=dsn,
    integrations=[LoggingIntegration()],
    traces_sample_rate=1.0,
    debug=True
)

class DetailedMonitoringCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.uptime_start = datetime.datetime.utcnow()  # Botの起動時間
        self.host_status_monitor.start()  # ホストステータス監視
        self.ping_monitor.start()  # Ping監視

    @commands.Cog.listener()
    async def on_ready(self):
        with sentry_sdk.start_transaction(op="bot_event", name="on_ready"):
            sentry_sdk.capture_message("Bot is ready", level="info")
            logger.info("Sentry: Bot is ready")

    @commands.Cog.listener()
    async def on_command(self, ctx):
        with sentry_sdk.start_transaction(op="command", name=f"Command: {ctx.command}"):
            with sentry_sdk.start_span(name="Command Execution"):
                sentry_sdk.set_tag("user_id", ctx.author.id)
                sentry_sdk.set_tag("guild_id", ctx.guild.id)
                sentry_sdk.set_tag("channel_id", ctx.channel.id)
                sentry_sdk.capture_message(f"Command executed: {ctx.command}")
                logger.info(
                    f"Sentry: Command executed: {ctx.command}\n"
                    f"User: {ctx.author} (ID: {ctx.author.id})\n"
                    f"Channel: {ctx.channel} (ID: {ctx.channel.id})\n"
                    f"Guild: {ctx.guild} (ID: {ctx.guild.id})"
                )

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        with sentry_sdk.start_transaction(op="error", name="Command Error"):
            sentry_sdk.capture_exception(error)
            sentry_sdk.set_context("Error Context", {
                "command": str(ctx.command),
                "user": f"{ctx.author} (ID: {ctx.author.id})",
                "channel": f"{ctx.channel} (ID: {ctx.channel.id})",
                "guild": f"{ctx.guild} (ID: {ctx.guild.id})",
            })
            logger.error(
                f"Sentry: Error in command: {ctx.command}\n"
                f"User: {ctx.author} (ID: {ctx.author.id})\n"
                f"Channel: {ctx.channel} (ID: {ctx.channel.id})\n"
                f"Guild: {ctx.guild} (ID: {ctx.guild.id})"
            )

    @commands.Cog.listener()
    async def on_application_command_error(self, interaction, error):
        with sentry_sdk.start_transaction(op="error", name="Application Command Error"):
            sentry_sdk.capture_exception(error)
            sentry_sdk.set_context("Error Context", {
                "command": str(interaction.command),
                "user": f"{interaction.user} (ID: {interaction.user.id})",
                "channel": f"{interaction.channel} (ID: {interaction.channel.id})",
                "guild": f"{interaction.guild} (ID: {interaction.guild.id})",
            })
            logger.error(
                f"Sentry: Error in command: {interaction.command}\n"
                f"User: {interaction.user} (ID: {interaction.user.id})\n"
                f"Channel: {interaction.channel} (ID: {interaction.channel.id})\n"
                f"Guild: {interaction.guild} (ID: {interaction.guild.id})"
            )

    @tasks.loop(minutes=5)
    async def host_status_monitor(self):
        with sentry_sdk.start_transaction(op="monitoring", name="Host Status"):
            try:
                with sentry_sdk.start_span(name="System Metrics"):
                    cpu = psutil.cpu_percent()
                    memory = psutil.virtual_memory().percent
                    disk = psutil.disk_usage("/").percent
                    network = psutil.net_io_counters()
                    process_count = len(psutil.pids())

                    sentry_sdk.set_context("Host Status", {
                        "CPU Usage (%)": cpu,
                        "Memory Usage (%)": memory,
                        "Disk Usage (%)": disk,
                        "Bytes Sent": network.bytes_sent,
                        "Bytes Received": network.bytes_recv,
                        "Active Processes": process_count,
                        "Hostname": socket.gethostname(),
                        "OS": platform.platform(),
                    })
                    sentry_sdk.capture_message("Host status updated", level="info")
                    logger.info("Sentry: Host status updated")
            except Exception as e:
                sentry_sdk.capture_exception(e)
                logger.error(f"Sentry: Error in host status monitor: {e}")

    @tasks.loop(minutes=1)
    async def ping_monitor(self):
        with sentry_sdk.start_transaction(op="monitoring", name="Ping Check"):
            try:
                latency = round(self.bot.latency * 1000)
                sentry_sdk.set_tag("latency_ms", latency)
                sentry_sdk.capture_message(f"Bot Ping - Latency: {latency}ms", level="info")
                logger.info(f"Sentry: Bot Ping - Latency: {latency}ms")
            except Exception as e:
                sentry_sdk.capture_exception(e)
                logger.error(f"Sentry: Error in ping monitor: {e}")

    @commands.hybrid_command(name="uptime")
    async def uptime(self, ctx):
        """Botの稼働時間を確認するコマンド"""
        with sentry_sdk.start_transaction(op="command", name="/uptime"):
            now = datetime.datetime.utcnow()
            uptime_duration = now - self.uptime_start
            await ctx.send(f"Bot has been running for: {uptime_duration}")
            sentry_sdk.capture_message(f"Uptime checked: {uptime_duration}", level="info")
            logger.info(f"Sentry: Uptime checked: {uptime_duration}")

    @commands.hybrid_command(name="hostinfo")
    async def hostinfo(self, ctx):
        """ホストの詳細情報を確認するコマンド"""
        with sentry_sdk.start_transaction(op="command", name="/hostinfo"):
            try:
                cpu = psutil.cpu_percent()
                memory = psutil.virtual_memory().percent
                disk = psutil.disk_usage("/").percent
                network = psutil.net_io_counters()
                process_count = len(psutil.pids())

                embed = discord.Embed(
                    title="ホスト情報",
                    color=discord.Color.green()
                )
                embed.add_field(name="CPU Usage", value=f"{cpu}%", inline=True)
                embed.add_field(name="Memory Usage", value=f"{memory}%", inline=True)
                embed.add_field(name="Disk Usage", value=f"{disk}%", inline=True)
                embed.add_field(name="Bytes Sent", value=network.bytes_sent, inline=True)
                embed.add_field(name="Bytes Received", value=network.bytes_recv, inline=True)
                embed.add_field(name="Active Processes", value=process_count, inline=True)
                embed.add_field(name="Hostname", value=socket.gethostname(), inline=True)
                embed.add_field(name="OS", value=platform.platform(), inline=True)
                await ctx.send(embed=embed)
                message = (
                    f"**Host Information:**\n"
                    f"- CPU Usage: {cpu}%\n"
                    f"- Memory Usage: {memory}%\n"
                    f"- Disk Usage: {disk}%\n"
                    f"- Bytes Sent: {network.bytes_sent}\n"
                    f"- Bytes Received: {network.bytes_recv}\n"
                    f"- Active Processes: {process_count}\n"
                    f"- Hostname: {socket.gethostname()}\n"
                    f"- OS: {platform.platform()}"
                )
                await ctx.send(embed=embed)
                sentry_sdk.capture_message("Host info command executed", level="info")
                logger.info("Sentry: Host info command executed")
            except Exception as e:
                await ctx.send("Error retrieving host information.")
                sentry_sdk.capture_exception(e)
                logger.error(f"Sentry: Error in host info command: {e}")

    @commands.hybrid_command(name="issues")
    async def issues(self, ctx):
        """Sentryの問題一覧を表示するコマンド"""
        with sentry_sdk.start_transaction(op="command", name="/issues"):
            try:
                # Get issues from Sentry
                issues = sentry_sdk.Hub.current.client.transport.get_issues()
                
                if not issues:
                    embed = discord.Embed(
                        title="Sentry Issues",
                        description="現在、報告された問題はありません。",
                        color=discord.Color.green()
                    )
                else:
                    embed = discord.Embed(
                        title="Sentry Issues",
                        description=f"最近報告された問題: {len(issues)}件",
                        color=discord.Color.orange()
                    )
                    
                    for issue in issues[:10]:  # Display up to 10 most recent issues
                        error_title = issue.get('title', 'Unknown Error')
                        last_seen = issue.get('lastSeen', 'Unknown')
                        count = issue.get('count', 0)
                        level = issue.get('level', 'error')
                        
                        embed.add_field(
                            name=error_title,
                            value=f"最終発生: {last_seen}\n発生回数: {count}\nレベル: {level}",
                            inline=False
                        )
                
                await ctx.send(embed=embed)
                sentry_sdk.capture_message("Issues command executed", level="info")
                logger.info("Sentry: Issues command executed")
            except Exception as e:
                await ctx.send("Error retrieving Sentry issues.")
                sentry_sdk.capture_exception(e)
                logger.error(f"Sentry: Error in issues command: {e}")

    def cog_unload(self):
        """Cogがアンロードされたときにタスクを停止"""
        self.host_status_monitor.cancel()
        self.ping_monitor.cancel()
        logger.debug("Cog unloaded")

async def setup(bot):
    await bot.add_cog(DetailedMonitoringCog(bot))
