import discord
import asyncio
import json
import datetime
import pytz
import aiofiles
import aiohttp
from discord.ext import commands

from utils.logging import setup_logging
from config.setting import get_settings
from utils.commands_help import is_owner, log_commands, is_guild

logger = setup_logging("D")
settings = get_settings()

DATA_PATH = "data/si/data.json"
JST = pytz.timezone("Asia/Tokyo")

class SeasonIcon(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.icon_data = {}

    async def load_data(self) -> None:
        try:
            async with aiofiles.open(DATA_PATH, mode='r', encoding='utf-8') as f:
                data = await f.read()
                self.icon_data = json.loads(data)
        except (FileNotFoundError, json.JSONDecodeError):
            self.icon_data = {}

    async def save_data(self) -> None:
        async with aiofiles.open(DATA_PATH, mode='w', encoding='utf-8') as f:
            await f.write(json.dumps(self.icon_data, indent=4, ensure_ascii=False))

    def get_season_icon(self) -> str | None:
        now = datetime.datetime.now(JST)
        month, day = now.month, now.day

        special_days = {
            (12, 24): "クリスマス", (12, 25): "クリスマス",
            (12, 31): "HNY", (1, 1): "HNY", (1, 2): "HNY", (1, 3): "HNY"
        }

        season_map = {
            (3, 6): "春", (6, 6): "梅雨", (7, 9): "夏", (7, 7): "七夕", (9, 9): "月見",
            (10, 11): "秋", (10, 31): "ハロウィン", (12, 2): "冬"
        }

        if (month, day) in special_days:
            return self.icon_data.get("icons", {}).get(special_days[(month, day)], None)

        if (month == 12 and day >= 26) or (month == 1 and day >= 4):
            return self.icon_data.get("icons", {}).get("冬", None)

        for (m, d), season in season_map.items():
            if month == m and (d == 9 or day == d):
                return self.icon_data.get("icons", {}).get(season, None)

        return None

    async def change_icon(self) -> None:
        await self.load_data()
        icon_url = self.get_season_icon()

        if not icon_url:
            return

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(icon_url) as resp:
                    if resp.status == 200:
                        avatar = await resp.read()
                        guild_id = self.icon_data.get("guild_id")
                        if guild_id is None:
                            logger.warning("guild_id が設定されていません。")
                            return
                        guild = self.bot.get_guild(guild_id)
                        if guild:
                            await guild.edit(icon=avatar)
                            channel = self.bot.get_channel(self.icon_data.get("notify_channel"))
                            if channel:
                                await channel.send(f"サーバーアイコンを {icon_url} に変更しました！")
        except Exception as e:
            logger.error(f"サーバーアイコン変更失敗: {e}")

    async def schedule_icon_change(self) -> None:
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            now = datetime.datetime.now(JST)
            next_run = now.replace(hour=0, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)
            wait_time = (next_run - now).total_seconds()
            await asyncio.sleep(wait_time)
            await self.change_icon()

    @commands.hybrid_group()
    @log_commands()
    @is_owner()
    @is_guild()
    async def seasonicon(self, ctx: commands.Context):
        """ アイコンの設定を行います """
        pass

    @seasonicon.command()
    @log_commands()
    @is_owner()
    @is_guild()
    async def set_icon(self, ctx: commands.Context, season: str, url: str):
        """ アイコンを設定するコマンド """
        if "icons" not in self.icon_data:
            self.icon_data["icons"] = {}
        self.icon_data["icons"][season] = url
        await self.save_data()
        await ctx.send(f"{season} のアイコンを設定しました！")

    @seasonicon.command()
    @log_commands()
    @is_owner()
    @is_guild()
    async def set_notify_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        """ 通知チャンネルを設定 """
        self.icon_data["notify_channel"] = channel.id
        await self.save_data()
        await ctx.send(f"通知チャンネルを {channel.mention} に設定しました！")

    @seasonicon.command()
    @log_commands()
    @is_owner()
    @is_guild()
    async def set_guild_id(self, ctx: commands.Context):
        """ 対象のギルドIDを設定 """
        self.icon_data["guild_id"] = ctx.guild.id
        await self.save_data()
        await ctx.send(f"ギルドIDを `{ctx.guild.id}` に設定しました！")

async def setup(bot: commands.Bot):
    cog = SeasonIcon(bot)
    await bot.add_cog(cog)
    asyncio.create_task(cog.schedule_icon_change())