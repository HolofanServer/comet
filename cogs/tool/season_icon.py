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
            logger.info(f"アイコンデータを読み込みました: {self.icon_data}")
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"アイコンデータの読み込みに失敗しました: {e}")
            self.icon_data = {}

    async def save_data(self) -> None:
        try:
            async with aiofiles.open(DATA_PATH, mode='w', encoding='utf-8') as f:
                await f.write(json.dumps(self.icon_data, indent=4, ensure_ascii=False))
            logger.info(f"アイコンデータを保存しました: {self.icon_data}")
        except Exception as e:
            logger.error(f"アイコンデータの保存に失敗しました: {e}")

    def get_season_icon(self, custom_date=None) -> tuple[str, str] | tuple[None, None]:
        if custom_date:
            now = custom_date
        else:
            now = datetime.datetime.now(JST)
        
        month, day = now.month, now.day
        logger.info(f"現在の日付: {month}月{day}日")

        special_days = {
            (12, 24): "クリスマス", (12, 25): "クリスマス",
            (12, 31): "HNY", (1, 1): "HNY", (1, 2): "HNY", (1, 3): "HNY",
            (7, 7): "七夕", (9, 9): "月見", (10, 31): "ハロウィン"
        }

        if (month, day) in special_days:
            season_name = special_days[(month, day)]
            icon_url = self.icon_data.get("icons", {}).get(season_name, None)
            logger.info(f"特別な日({season_name})のアイコン: {icon_url}")
            return icon_url, season_name

        if (month == 12 and day >= 26) or (month == 1 and day <= 3):
            icon_url = self.icon_data.get("icons", {}).get("冬", None)
            logger.info(f"冬期間のアイコン: {icon_url}")
            return icon_url, "冬"

        season_periods = {
            (3, 5): "春",
            (6, 6): "梅雨",
            (7, 8): "夏",
            (9, 11): "秋",
            (12, 2): "冬"
        }
        
        for (start_month, end_month), season in season_periods.items():
            if start_month <= end_month:
                if start_month <= month <= end_month:
                    icon_url = self.icon_data.get("icons", {}).get(season, None)
                    logger.info(f"{season}の期間 ({start_month}月〜{end_month}月) のアイコン: {icon_url}")
                    return icon_url, season
            else:
                if month >= start_month or month <= end_month:
                    icon_url = self.icon_data.get("icons", {}).get(season, None)
                    logger.info(f"{season}の期間 ({start_month}月〜{end_month}月) のアイコン: {icon_url}")
                    return icon_url, season

        logger.warning("該当する季節アイコンが見つかりませんでした")
        return None, None

    async def change_icon(self, force=False) -> None:
        await self.load_data()
        icon_url, season_name = self.get_season_icon()

        if not icon_url:
            logger.warning("変更するアイコンURLが見つかりませんでした")
            return

        try:
            guild_id = self.icon_data.get("guild_id")
            if guild_id is None:
                logger.warning("guild_id が設定されていません。")
                return
                
            logger.info(f"ギルドID: {guild_id}を検索中")
            guild = self.bot.get_guild(guild_id)
            
            if not guild:
                logger.error(f"ギルドID: {guild_id} が見つかりませんでした。ボットがこのサーバーに参加していることを確認してください。")
                return
                
            logger.info(f"ギルド '{guild.name}' が見つかりました。アイコンの変更を試みます。")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(icon_url) as resp:
                    if resp.status == 200:
                        avatar = await resp.read()
                        await guild.edit(icon=avatar)
                        logger.info(f"ギルド '{guild.name}' のアイコンを {season_name} ({icon_url}) に変更しました")
                        
                        notify_channel_id = self.icon_data.get("notify_channel")
                        if notify_channel_id:
                            channel = self.bot.get_channel(notify_channel_id)
                            if channel:
                                await channel.send(f"サーバーアイコンを {season_name} ({icon_url}) に変更しました！")
                            else:
                                logger.warning(f"通知チャンネル(ID: {notify_channel_id})が見つかりませんでした")
                    else:
                        logger.error(f"アイコン画像の取得に失敗しました: HTTP {resp.status}")
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
        """ 対象のギルドIDを設定（他の設定を保持） """
        await self.load_data()
        if not isinstance(self.icon_data, dict):
            self.icon_data = {}
        self.icon_data["guild_id"] = ctx.guild.id
        await self.save_data()
        await ctx.send(f"ギルドIDを `{ctx.guild.id}` に設定しました！")
        
    @seasonicon.command(name="update")
    @log_commands()
    @is_owner()
    @is_guild()
    async def update_icon(self, ctx: commands.Context):
        """ 現在のシーズンに合わせて今すぐアイコンを更新 """
        await ctx.send("アイコンの更新を試みています...")
        await self.change_icon(force=True)
        await ctx.send("アイコン更新処理を完了しました。ログを確認してください。")
        
    @seasonicon.command(name="status")
    @log_commands()
    @is_owner()
    @is_guild()
    async def check_status(self, ctx: commands.Context):
        """ 現在の設定状況とシーズン情報を確認 """
        await self.load_data()
        
        icon_url, season = self.get_season_icon()
        guild_id = self.icon_data.get("guild_id")
        notify_channel = self.icon_data.get("notify_channel")
        
        embed = discord.Embed(title="シーズンアイコン設定状況", color=0x00ff00)
        embed.add_field(name="現在のシーズン", value=season if season else "設定なし", inline=False)
        embed.add_field(name="アイコンURL", value=icon_url if icon_url else "設定なし", inline=False)
        embed.add_field(name="ギルドID", value=str(guild_id) if guild_id else "設定なし", inline=True)
        embed.add_field(name="通知チャンネル", value=f"<#{notify_channel}>" if notify_channel else "設定なし", inline=True)
        
        # 設定されているすべてのシーズンアイコン
        icons = self.icon_data.get("icons", {})
        icon_list = "\n".join([f"**{k}**: {v}" for k, v in icons.items()])
        embed.add_field(name="登録済みアイコン", value=icon_list if icon_list else "なし", inline=False)
        
        await ctx.send(embed=embed)
    
    @seasonicon.command(name="test")
    @log_commands()
    @is_owner()
    @is_guild()
    async def test_date(self, ctx: commands.Context, month: int, day: int):
        """ 特定の日付でアイコンをテスト """
        if not (1 <= month <= 12 and 1 <= day <= 31):
            await ctx.send("無効な日付です。月は1-12、日は1-31の範囲で指定してください。")
            return
            
        test_date = datetime.datetime(2025, month, day, tzinfo=JST)
        icon_url, season = self.get_season_icon(custom_date=test_date)
        
        if icon_url and season:
            await ctx.send(f"{month}月{day}日は「{season}」のアイコン({icon_url})が適用されます。")
        else:
            await ctx.send(f"{month}月{day}日には適用されるアイコンがありません。")
            
    @seasonicon.command(name="force")
    @log_commands()
    @is_owner()
    @is_guild()
    async def force_icon(self, ctx: commands.Context, season: str):
        """ 特定のシーズンアイコンを強制的に設定 """
        await self.load_data()
        
        icons = self.icon_data.get("icons", {})
        if season not in icons:
            seasons_list = "、".join(list(icons.keys()))
            await ctx.send(f"指定されたシーズン「{season}」は登録されていません。\n登録済み: {seasons_list}")
            return
            
        icon_url = icons[season]
        
        try:
            guild_id = self.icon_data.get("guild_id")
            if not guild_id:
                await ctx.send("ギルドIDが設定されていません。先に `/seasonicon set_guild_id` を実行してください。")
                return
                
            guild = self.bot.get_guild(guild_id)
            if not guild:
                await ctx.send(f"ギルドID: {guild_id} が見つかりませんでした。ボットがこのサーバーに参加していることを確認してください。")
                return
                
            async with aiohttp.ClientSession() as session:
                async with session.get(icon_url) as resp:
                    if resp.status == 200:
                        avatar = await resp.read()
                        await guild.edit(icon=avatar)
                        await ctx.send(f"サーバーアイコンを {season} ({icon_url}) に強制変更しました！")
                    else:
                        await ctx.send(f"アイコン画像の取得に失敗しました: HTTP {resp.status}")
        except Exception as e:
            await ctx.send(f"エラーが発生しました: {e}")
            logger.error(f"強制アイコン変更失敗: {e}")

async def setup(bot: commands.Bot):
    cog = SeasonIcon(bot)
    await cog.load_data()
    await bot.add_cog(cog)
    # 起動時にアイコン更新をチェック
    await cog.change_icon()
    # スケジュールタスクを開始
    asyncio.create_task(cog.schedule_icon_change())
    logger.info("SeasonIcon Cogが正常に読み込まれました。スケジュール更新が設定されました。")