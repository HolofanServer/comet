import discord
from discord.ext import commands, tasks

import json
import asyncio
import traceback
import os
import socket
import datetime
import subprocess

from utils.logging import setup_logging
from config.setting import get_settings

logger = setup_logging("D")
settings = get_settings()

main_guild_id = int(settings.admin_main_guild_id)


class GizmcStatusCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.server_ports = {}
        self.server_states = {}
        self.offline_messages = {}
        
        # ファイルパスの設定
        guild_dir = f'data/status/gizmc/{main_guild_id}'
        if not os.path.exists(guild_dir):
            os.makedirs(guild_dir, exist_ok=True)
            logger.info(f"Created directory: {guild_dir}")
            
        self.mod_ch_file = f'{guild_dir}/mod_ch.json'
        self.status_ch_file = f'{guild_dir}/status_ch.json'
        self.server_ip_file = f'{guild_dir}/server_ip.json'
        
        # データの読み込み
        try:
            mod_ch_data = self.load_mod_ch()
            status_ch_data = self.load_status_ch()
            if isinstance(mod_ch_data, dict):
                self.mod_ch = mod_ch_data.get('channel_id')
            else:
                self.mod_ch = mod_ch_data
            if isinstance(status_ch_data, dict):
                self.status_ch = status_ch_data.get('channel_id')
            else:
                self.status_ch = status_ch_data
            logger.info(f"Loaded channels - mod_ch: {self.mod_ch}, status_ch: {self.status_ch}")
        except Exception as e:
            logger.error(f"Error loading channels: {e}")
            self.mod_ch = None
            self.status_ch = None
            
        # Start the background task after initialization
        self.check_servers.start()
        
    def get_guild_id(self, guild_id):
        logger.debug(f"Checking guild ID: {guild_id}")
        if guild_id == main_guild_id:
            logger.info(f"Valid guild ID found: {guild_id}")
            return guild_id
        error_msg = f"Invalid guild ID: {guild_id}"
        logger.error(error_msg)
        raise ValueError(error_msg)

    def load_mod_ch(self):
        try:
            with open(self.mod_ch_file, "r") as f:
                try:
                    data = json.load(f)
                    logger.info(f"Loaded mod channel data: {data}")
                    return data
                except json.JSONDecodeError:
                    f.seek(0)
                    data = int(f.read().strip())
                    logger.info(f"Loaded mod channel data (legacy format): {data}")
                    return data
        except FileNotFoundError:
            logger.warning("Mod channel file not found")
            return None

    def save_mod_ch(self, data):
        with open(self.mod_ch_file, "w") as f:
            json_data = {'channel_id': data, 'updated_at': datetime.datetime.now().isoformat()}
            json.dump(json_data, f, indent=4, ensure_ascii=False)
            logger.info(f"Saved mod channel data: {json_data}")

    def load_status_ch(self):
        try:
            with open(self.status_ch_file, "r") as f:
                try:
                    data = json.load(f)
                    logger.info(f"Loaded status channel data: {data}")
                    return data
                except json.JSONDecodeError:
                    f.seek(0)
                    data = int(f.read().strip())
                    logger.info(f"Loaded status channel data (legacy format): {data}")
                    return data
        except FileNotFoundError:
            logger.warning("Status channel file not found")
            return None

    def save_status_ch(self, data):
        with open(self.status_ch_file, "w") as f:
            json_data = {'channel_id': data, 'updated_at': datetime.datetime.now().isoformat()}
            json.dump(json_data, f, indent=4, ensure_ascii=False)
            logger.info(f"Saved status channel data: {json_data}")

    def load_server_ip(self):
        try:
            with open(self.server_ip_file, "r") as f:
                data = json.load(f)
                if data and isinstance(next(iter(data.values())), str):
                    logger.info("Converting old format server IP data to new format")
                    converted = {}
                    for label, ip in data.items():
                        converted[label] = {"ip": ip, "port": 25565}
                        self.server_ports[label] = 25565
                    logger.info(f"Converted server IP data: {converted}")
                    return converted
                for label, info in data.items():
                    self.server_ports[label] = info["port"]
                logger.info(f"Loaded server IP data: {data}")
                return data
        except FileNotFoundError:
            logger.warning("Server IP file not found")
            return {}

    def save_server_ip(self, data):
        with open(self.server_ip_file, "w") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
            logger.info(f"Saved server IP data: {data}")

    @commands.hybrid_group(name="gizmc")
    async def gizmc(self, ctx):
        logger.debug(f"Gizmc command invoked by {ctx.author} in {ctx.guild}")
        if ctx.invoked_subcommand is None:
            logger.warning(f"No subcommand specified by {ctx.author}")
            await ctx.send("サブコマンドを指定してください。")

    @gizmc.command(name="setup")
    async def setup(self, ctx, mod_ch: discord.TextChannel, status_ch: discord.TextChannel):
        logger.debug(f"Setup command invoked by {ctx.author} in {ctx.guild}")
        try:
            guild_id = self.get_guild_id(ctx.guild.id)
            self.save_mod_ch(mod_ch.id)
            self.save_status_ch(status_ch.id)
            logger.info(f"Setup completed for guild {guild_id} with mod_ch: {mod_ch.id}, status_ch: {status_ch.id}")
            await ctx.send(f'mod_ch: {mod_ch.mention}\nstatus_ch: {status_ch.mention}')
        except ValueError as e:
            logger.error(f"Setup failed for guild {ctx.guild.id}: {str(e)}")
            await ctx.send(f"Error: {e}")

    @gizmc.command(name="ip")
    async def ip(self, ctx, ip: str, port: int, label: str):
        logger.debug(f"IP command invoked by {ctx.author} in {ctx.guild}")
        try:
            guild_id = self.get_guild_id(ctx.guild.id)
            server_ips = self.load_server_ip()
            server_ips[label] = {"ip": ip, "port": port}
            self.server_ports[label] = port
            self.save_server_ip(server_ips)
            logger.info(f"IP set for guild {guild_id}, label: {label}, ip: {ip}, port: {port}")
            await ctx.send(f'サーバー「{label}」を {ip}:{port} として保存しました')
        except ValueError as e:
            logger.error(f"IP command failed for guild {ctx.guild.id}: {str(e)}")
            await ctx.send(f"Error: {e}")

    def check_tcp_connection(self, host: str, port: int) -> bool:
        logger.debug(f"Checking TCP connection for {host}:{port}")
        try:
            with socket.create_connection((host, port), timeout=3):
                logger.info(f"TCP connection successful to {host}:{port}")
                return True
        except (socket.timeout, ConnectionRefusedError, OSError) as e:
            logger.warning(f"TCP connection failed to {host}:{port}: {str(e)}")
            return False

    def create_status_embed(self, label: str, ip: str, port: int, is_up: bool, duration: str = None) -> discord.Embed:
        logger.debug(f"Creating status embed for {label}, is_up: {is_up}")
        branch = self.get_gh_branch()
        
        if is_up:
            if branch == "dev":
                status = "<:ONLINE:1311908128169791578> Operational"  
            else:
                status = "<:ONLINE:1311908265604677733> Operational"  
            color = discord.Color.green()
            description = f"サーバー {label} は正常に動作しています。"
        else:
            if branch == "dev":
                status = "<:OFFLINE:1311908112437084300> Service Disruption"  
            else:
                status = "<:OFFLINE:1311908249745887332> Service Disruption"  
            color = discord.Color.red()
            description = f"サーバー {label} との接続が切断されました。開発チームが状況を確認しています。"
            if duration:
                description += f"\n\n停止時間: {duration}"
        
        embed = discord.Embed(
            title=f"サーバーステータス: {label}",
            timestamp=datetime.datetime.now()
        )
        
        embed.color = color
        embed.description = description
        
        embed.add_field(
            name="Status", 
            value=status, 
            inline=False
        )
        embed.add_field(
            name="Server Information", 
            value=f"```\nHost: {label}\n```", 
            inline=False
        )
        
        embed.set_footer(text="最終更新")
        
        logger.debug(f"Created status embed for {label}")
        return embed

    @tasks.loop(minutes=1)
    async def check_servers(self):
        logger.debug("Checking servers")
        if not self.status_ch or not self.mod_ch:
            logger.warning("No status channel or mod channel set")
            return
        
        status_channel = self.bot.get_channel(self.status_ch)
        mod_channel = self.bot.get_channel(self.mod_ch)
        if not status_channel or not mod_channel:
            logger.warning("No status channel or mod channel found")
            return

        server_ips = self.load_server_ip()
        current_time = datetime.datetime.now()
        
        for label, server_info in server_ips.items():
            ip = server_info["ip"]
            port = server_info["port"]
            
            is_up = self.check_tcp_connection(ip, port)
            prev_state = self.server_states.get(label, True)
            
            if not is_up and prev_state:
                self.server_states[label] = False
                self.server_states[f"{label}_down_time"] = current_time
                
                status_embed = self.create_status_embed(label, ip, port, False)
                status_msg = await status_channel.send(
                    f"⚠️ **Service Disruption** - {label}\n" \
                    f"開発チームが接続の問題について調査中です。この間、サービスの一部が利用できない可能性があります。\n" \
                    f"ご不便をおかけして申し訳ありません。",
                    embed=status_embed
                )
                self.offline_messages[label] = status_msg.id
                
                await mod_channel.send(
                    f"🚨 **Service Alert** - {label}\n" \
                    f"<@698739561563422812> <@707320830387814531>\n接続の問題が検出されました。至急確認をお願いします。",
                    embed=status_embed
                )
                
            elif is_up and not prev_state:
                self.server_states[label] = True
                down_time = self.server_states.get(f"{label}_down_time")
                
                if down_time:
                    duration = self.format_duration((current_time - down_time).seconds)
                    status_embed = self.create_status_embed(label, ip, port, True, duration)
                    
                    if label in self.offline_messages:
                        branch = self.get_gh_branch()
                        try:
                            msg = await status_channel.fetch_message(self.offline_messages[label])
                            msg_mod = await mod_channel.fetch_message(self.offline_messages[label])
                            if branch == "main":
                                await msg.edit(
                                    content = f"<:Checkmark:1311910220909510666> **Service Restored** - {label}\n" \
                                            f"サービスは正常に復旧し、通常通り動作しています。\n" \
                                            f"ご利用ありがとうございます。\n\n" \
                                            f"停止時間: {duration}",
                                    embed=status_embed
                                )
                                await msg_mod.edit(
                                    content = f"<:Checkmark:1311910220909510666> **Service Restored** - {label}\n" \
                                            f"復旧しました。\n" \
                                            f"停止時間: {duration}",
                                    embed=status_embed
                                )
                            else:
                                await msg.edit(
                                    content = f"<:Checkmark:1311910501453660210> **Service Restored** - {label}\n" \
                                            f"サービスは正常に復旧し、通常通り動作しています。\n" \
                                            f"ご利用ご返礼です。\n\n" \
                                            f"停止時間: {duration}",
                                    embed=status_embed
                                )
                                await msg_mod.edit(
                                    content = f"<:Checkmark:1311910501453660210> **Service Restored** - {label}\n" \
                                            f"復旧しました。\n" \
                                            f"停止時間: {duration}",
                                    embed=status_embed
                                )
                        except discord.NotFound:
                            pass
                        
                        del self.offline_messages[label]
                        del self.server_states[f"{label}_down_time"]

    def format_duration(self, seconds: int) -> str:
        logger.debug(f"Formatting duration: {seconds} seconds")
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        days, hours = divmod(hours, 24)
        
        parts = []
        if days > 0:
            parts.append(f"{days}日")
        if hours > 0:
            parts.append(f"{hours}時間")
        if minutes > 0:
            parts.append(f"{minutes}分")
        if seconds > 0:
            parts.append(f"{seconds}秒")
            
        logger.debug(f"Formatted duration: {(''.join(parts))}")
        return "".join(parts) if parts else "0秒"

    @check_servers.before_loop
    async def before_check_servers(self):
        logger.debug("Waiting for bot to be ready")
        await self.bot.wait_until_ready()

    def cog_unload(self):
        logger.debug("Unloading cog")
        self.check_servers.cancel()

    def get_gh_branch(self):
        logger.debug("Getting git branch")
        try:
            branch = subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], 
                                          cwd=os.path.dirname(os.path.abspath(__file__))).decode('utf-8').strip()
            logger.info(f"Current git branch: {branch}")
            return branch
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to get git branch: {str(e)}")
            return "取得に失敗しました"

async def setup(bot):
    logger.debug("Setting up cog")
    await bot.add_cog(GizmcStatusCog(bot))