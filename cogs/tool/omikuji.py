import discord
from discord.ext import commands

import json
import asyncio
import random
import os

from datetime import datetime, timedelta

from utils.logging import setup_logging
from utils.commands_help import is_guild, is_owner, is_booster, log_commands

from config.setting import get_settings

settings = get_settings()

logger = setup_logging("D")

class OmikujiCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.omikujifile = 'data/omikuji/last_omikuji.json'
        self.streakfile = 'data/omikuji/streak_omikuji.json'
        self.today_stats_file = 'data/omikuji/today_stats.json'
        self.last_omikuji = self.load_last_omikuji()
        self.streak_data = self.load_streak_data()
        self.today_stats = self.load_today_stats()
        self.fortunefile = 'data/omikuji/last_fortune.json'
        self.last_fortune = self.load_last_fortune()
        self.idfile = 'data/ids.json'
        self.ids = self.load_ids()

    def load_last_omikuji(self):
        try:
            with open(self.omikujifile, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            if not os.path.exists(os.path.dirname(self.omikujifile)):
                os.makedirs(os.path.dirname(self.omikujifile), exist_ok=True)
            return {}

    def save_last_omikuji(self, data):
        if not os.path.exists(os.path.dirname(self.omikujifile)):
            os.makedirs(os.path.dirname(self.omikujifile), exist_ok=True)
        with open(self.omikujifile, "w") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    def load_streak_data(self):
        try:
            with open(self.streakfile, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            if not os.path.exists(os.path.dirname(self.streakfile)):
                os.makedirs(os.path.dirname(self.streakfile), exist_ok=True)
            return {}

    def save_streak_data(self, data):
        if not os.path.exists(os.path.dirname(self.streakfile)):
            os.makedirs(os.path.dirname(self.streakfile), exist_ok=True)
        with open(self.streakfile, "w") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    def load_today_stats(self):
        try:
            with open(self.today_stats_file, "r") as f:
                data = json.load(f)
                if 'count' not in data:
                    data['count'] = 0
                return data
        except FileNotFoundError:
            if not os.path.exists(os.path.dirname(self.today_stats_file)):
                os.makedirs(os.path.dirname(self.today_stats_file), exist_ok=True)
            return {'count': 0}

    def save_today_stats(self, data):
        if not os.path.exists(os.path.dirname(self.today_stats_file)):
            os.makedirs(os.path.dirname(self.today_stats_file), exist_ok=True)
        with open(self.today_stats_file, "w") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    def load_last_fortune(self):
        try:
            with open(self.fortunefile, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            if not os.path.exists(os.path.dirname(self.fortunefile)):
                os.makedirs(os.path.dirname(self.fortunefile), exist_ok=True)
            return {}

    def save_last_fortune(self, data):
        if not os.path.exists(os.path.dirname(self.fortunefile)):
            os.makedirs(os.path.dirname(self.fortunefile), exist_ok=True)
        with open(self.fortunefile, "w") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    def load_ids(self):
        try:
            with open(self.idfile, "r") as f:
                content = f.read().strip()
                if not content:
                    return {}
                return json.loads(content)
        except FileNotFoundError:
            if not os.path.exists(os.path.dirname(self.idfile)):
                os.makedirs(os.path.dirname(self.idfile), exist_ok=True)
            return {}
        except json.JSONDecodeError:
            logger.error(f"JSONDecodeError: {self.idfile}の内容が無効です。")
            return {}

    async def reset_at_midnight(self):
        while True:
            now_utc = datetime.utcnow()
            now_jst = now_utc + timedelta(hours=9)
            next_midnight_jst = datetime(now_jst.year, now_jst.month, now_jst.day) + timedelta(days=1)
            sleep_seconds = (next_midnight_jst - now_jst).total_seconds()

            await asyncio.sleep(sleep_seconds)

            self.last_omikuji.clear()
            self.save_last_omikuji(self.last_omikuji)
            self.today_stats["count"] = 0
            self.save_today_stats(self.today_stats)

    @commands.hybrid_command(name="omikuji", aliases=["おみくじ"])
    @is_guild()
    @log_commands()
    async def omikuji(self, ctx):
        """1日1回だけおみくじを引くことができます。"""
        logger.debug("Starting omikuji command")
        
        self.streak_data = self.load_streak_data()
        
        user_id = str(ctx.author.id)
        special_user_id = str(settings.bot_owner_id)

        now_utc = datetime.utcnow()
        now_jst = now_utc + timedelta(hours=9)
        today_jst = now_jst.date()

        logger.debug(f"User ID: {user_id}, Today JST: {today_jst}")

        if user_id in self.last_omikuji and self.last_omikuji[user_id] == today_jst.isoformat():
            if user_id != special_user_id:
                logger.debug(special_user_id)
                await ctx.send("今日はもうおみくじを引いています！\n日本時間24時にリセットされます。")
                logger.debug(f"User {user_id} has already drawn the omikuji today.")
                return

        logger.debug("Checking streak data")
        if user_id in self.streak_data:
            last_date = datetime.fromisoformat(self.streak_data[user_id]['last_date']).date()
            logger.debug(f"Last date: {last_date}")
            if user_id == special_user_id:
                if last_date < today_jst - timedelta(days=1):
                    self.streak_data[user_id]['streak'] = self.streak_data[user_id].get('streak', 1)
                    logger.debug(f"Streak: {self.streak_data[user_id]['streak']}")
            elif last_date == today_jst - timedelta(days=1):
                self.streak_data[user_id]['streak'] += 1
                logger.debug(f"Streak: {self.streak_data[user_id]['streak']}")
            else:
                self.streak_data[user_id]['streak'] = 1
                logger.debug(f"Streak: {self.streak_data[user_id]['streak']}")
        else:
            self.streak_data[user_id] = {'streak': 1}
            logger.debug(f"Streak: {self.streak_data[user_id]['streak']}")
            
        self.streak_data[user_id]['last_date'] = today_jst.isoformat()
        self.save_streak_data(self.streak_data)

        logger.debug("Updating last omikuji and today stats")
        self.last_omikuji[user_id] = today_jst.isoformat()
        self.save_last_omikuji(self.last_omikuji)

        logger.debug(f"Current today_stats: {self.today_stats}")
        self.today_stats["count"] += 1
        self.save_today_stats(self.today_stats)

        steps = [
            "iPhoneだけだよ神社に来た",
            "Lightningケーブルがぶら下がってる中おみくじを選ぶ",
            "**Lightningおじさん**がこちらをニコニコしながら眺めている",
            "心を落ち着かせおみくじを開く",
        ]

        normal_icon = "https://images.frwi.net/data/images/e5081f55-07a0-4996-9487-3b63d2fbe292.jpeg"
        special_icon = "https://images.frwi.net/data/images/3ff4aef3-e0a1-47e7-9969-cc0b0b192032.png"
        chance_icon = "https://images.frwi.net/data/images/b5972c13-9a4e-4c50-bd29-fbbe8e0f4fab.jpeg"

        streak = self.streak_data[user_id]['streak']
        base_fortunes = list(self.ids.keys())
        weights = [1] * len(base_fortunes)

        iphone_fortune_index = base_fortunes.index("iPhoneだけだよ!!")
        weights[iphone_fortune_index] += streak // 2

        is_super_rare = random.randint(1, 100) <= 5

        is_chance = random.randint(1, 100) <= 20
        is_rich_animation = random.randint(1, 100) <= 10

        normal_fortune = random.choices(base_fortunes, weights=weights, k=1)[0]
        fortune = "✨✨超大当たり✨✨" if is_super_rare else normal_fortune

        embed = discord.Embed(
            title="おみくじ結果",
            color=0xffd700 if is_super_rare else 0x34343c
        )
        embed.set_author(name=f"大当たりが当たる確率が{streak}%アップ中だよ！\niPhoneだけだよ神社にて...", url=normal_icon)
        embed.set_thumbnail(url="https://images.frwi.net/data/images/7b54adae-c988-47f1-a090-625a7838f1c1.png")

        fm = await ctx.send(content=f"{ctx.author.mention}\nおみくじを引きに行く...", embed=None)

        description_with_steps = ""

        for i, step in enumerate(steps):
            await asyncio.sleep(2 if not is_rich_animation else 3)

            if is_chance and i == len(steps) - 2:
                embed.set_thumbnail(url=chance_icon)
                description_with_steps += "\n\n✨✨**チャンス到来！**✨✨"

            if is_super_rare and i == len(steps) - 1:
                description_with_steps += "\n\n🌟🌟**リーチ！**🌟🌟"

            description_with_steps += f"\n\n{step}"
            embed.description = description_with_steps
            await fm.edit(embed=embed)

        await asyncio.sleep(2 if not is_super_rare else 5)

        embed.description += f"\n\nおみくじには**{fortune}**と書かれていた"
        await fm.edit(embed=embed)

        iphonedakedayo_emoji1 = "<:omkj_iphone_dakedayo_1:1290367507575869582>"
        iphonedakedayo_emoji2 = "<:omkj_iphone_dakedayo_2:1290367485937451038>"
        iphonedakedayo_emoji3 = "<:omkj_iphone_dakedayo_3:1290367469998833727>"
        iphonedakedayo_emoji4 = "<a:omkj_iphone_dakedayo_4:1290367451061686363>"
        iphonedakedayo_emoji5 = "<:giz_server_icon:1264027561856471062>"

        emoji_list = [iphonedakedayo_emoji1, iphonedakedayo_emoji2, iphonedakedayo_emoji3, iphonedakedayo_emoji4, iphonedakedayo_emoji5]
        if is_super_rare:
            embed.set_author(name=f"大当たりが当たる確率が{streak}%アップ中だよ！\niPhoneだけだよ神社にて...", url=special_icon)
            await asyncio.sleep(2)
            embed.description += "\n\n✨✨「神々しい光があなたを包み込んだ！」✨✨"
            embed.set_image(url="https://images.frwi.net/data/images/a0cdbfa7-047e-43c5-93f3-f1c6478a6c64.jpeg")
            embed.color = 0xffd700
            await fm.edit(embed=embed)

            super_reactions = ["🎉", "✨", "💎", "🌟", "🔥"]

            for emoji in super_reactions:
                try:
                    await fm.add_reaction(emoji)
                except discord.HTTPException:
                    continue

            for emoji in emoji_list:
                try:
                    await fm.add_reaction(emoji)
                except discord.HTTPException:
                    continue

        elif fortune == "iPhoneだけだよ!!":
            await asyncio.sleep(1)
            embed.description += "\n\niPhoneだけじゃなかったのかよ..."
            await fm.edit(embed=embed)
            
            for emoji in emoji_list:
                try:
                    await fm.add_reaction(emoji)
                except discord.HTTPException:
                    continue

        embed.set_footer(text=
                         "おみくじを引いてくれてありがとう！また明日引いてみてね！\n"
                         f"連続ログイン: {self.streak_data[user_id]['streak']}日目"
                         )
        await fm.edit(embed=embed)


    @commands.hybrid_command(name="fortune", aliases=["運勢"])
    @is_guild()
    @log_commands()
    async def fortune(self, ctx):
        """1日1回だけ今日の運勢を占えます。"""
        logger.debug("Starting fortune command")
        
        user_id = str(ctx.author.id)
        special_user_id = str(settings.bot_owner_id)

        now_utc = datetime.utcnow()
        now_jst = now_utc + timedelta(hours=9)
        today_jst = now_jst.date()

        logger.debug(f"User ID: {user_id}, Today JST: {today_jst}")

        if user_id in self.last_fortune and self.last_fortune[user_id] == today_jst.isoformat():
            if user_id != special_user_id:
                logger.debug(special_user_id)
                await ctx.send("今日はもう運勢を占っています！\n日本時間24時にリセットされます。")
                logger.debug(f"User {user_id} has already checked their fortune today.")
                return

        logger.debug("Updating last fortune and today stats")
        self.last_fortune[user_id] = today_jst.isoformat()
        self.save_last_fortune(self.last_fortune)

        logger.debug(f"Current today_stats: {self.today_stats}")
        self.today_stats["count"] += 1
        self.save_today_stats(self.today_stats)

        steps = [
            "占い師のLightningおじさんの元へ向かう",
            "水晶玉の中でLightningケーブルが光り輝いている",
            "**Lightningおじさん**が目を閉じて集中している",
            "あなたの運勢を占っています...",
        ]

        fortunes = ["大吉", "中吉", "小吉", "吉", "末吉", "凶"]
        weights = [10, 15, 20, 25, 20, 10]
        
        lucky_colors_with_hex = {
            "スペースブラック": 0x1C1C1E,
            "シルバー": 0xE3E3E3,
            "ゴールド": 0xFFD700,
            "ディープパープル": 0x800080,
            "ナチュラルチタニウム": 0xC0C0C0,
            "ミッドナイト": 0x191970,
            "スターライト": 0xFAF0E6,
            "プロダクトレッド": 0xFF0000,
            "パシフィックブルー": 0x1E90FF,
            "アルパイングリーン": 0x228B22
        }
        
        lucky_colors = list(lucky_colors_with_hex.keys())
        
        lucky_items = [
            "Lightning充電器",
            "iPhoneケース",
            "AirPods",
            "MagSafe充電器",
            "Apple Watch",
            "iPadスタンド",
            "AirTag",
            "MacBookスリーブ",
            "ApplePencil",
            "MagSafeウォレット",
            "MacBook Air",
            "MacBook Pro",
            "Mac Pro",
        ]
        
        lucky_apps = [
            "メモ",
            "カメラ",
            "マップ",
            "Safari",
            "メッセージ",
            "電話",
            "ミュージック",
            "天気",
            "リマインダー",
            "FaceTime",
            "Twitter(現X)",
            "Instagram",
            "discord",
            "LINE",
            "Gmail",
            "Zoom",
            "Slack",
            "TikTok",
            "Youtube",
            "Netflix",
            "Spotify",
            "Apple Music",
        ]

        fortune = random.choices(fortunes, weights=weights, k=1)[0]
        lucky_color = random.choice(lucky_colors)
        lucky_item = random.choice(lucky_items)
        lucky_app = random.choice(lucky_apps)

        embed = discord.Embed(title="今日の運勢", color=0x34343c)
        embed.set_author(name="Lightningおじさんの占い館にて...")
        embed.set_thumbnail(url="https://images.frwi.net/data/images/5d0b70e1-e16d-4e12-b399-e5dde756e6a3.png")

        fm = await ctx.send(content=f"{ctx.author.mention}\n占い師のもとへ向かっています...", embed=None)

        description_with_steps = ""
        for step in steps:
            await asyncio.sleep(2)
            description_with_steps += f"\n\n{step}"
            embed.description = description_with_steps
            await fm.edit(embed=embed)

        await asyncio.sleep(1)
        
        embed.color = lucky_colors_with_hex[lucky_color]
        await fm.edit(embed=embed)
        
        await asyncio.sleep(1)
        
        fortune_messages = {
            "大吉": "素晴らしい1日になりそうです！新しいiPhoneに出会えるかも...？",
            "中吉": "良い1日になりそうです。iPhoneの調子も最高！",
            "小吉": "まずまずの1日。iPhoneのバッテリーは満タンに！",
            "吉": "普通の1日。iPhoneを大切に使いましょう。",
            "末吉": "気を付けて。iPhoneのバックアップはちゃんととってね。",
            "凶": "今日はiPhoneを落とさないように特に注意..."
        }

        embed.description += f"\n\n**{fortune}** - {fortune_messages[fortune]}"
        embed.add_field(name="🎨 ラッキーカラー", value=lucky_color, inline=True)
        embed.add_field(name="🎁 ラッキーアイテム", value=lucky_item, inline=True)
        embed.add_field(name="📱 ラッキーアプリ", value=lucky_app, inline=True)
        
        embed.set_footer(text="Lightningおじさんの占いをご利用いただき、ありがとうございます。\nまた明日も占いにいらしてください。")
        await fm.edit(embed=embed)

    @commands.hybrid_command(name="ranking", aliases=["ランキング"])
    @is_guild()
    async def ranking(self, ctx):
        """おみくじのランキングを表示するコマンドです。"""
        await ctx.defer()
        self.streak_data = self.load_streak_data()
        e = discord.Embed(title="おみくじ連続ログインランキング", color=0x34343c)

        top_users = sorted(self.streak_data.items(), key=lambda x: x[1]['streak'], reverse=True)[:5]

        for rank, (user_id, data) in enumerate(top_users, start=1):
            member = ctx.guild.get_member(int(user_id))
            if member:
                e.add_field(
                    name=f"{rank}位: {member.display_name}",
                    value=f"{data['streak']}日連続",
                    inline=False
                )

        await ctx.send(embed=e)

    @commands.hybrid_group(name="omkj")
    @is_guild()
    async def omikuji_group(self, ctx):
        """おみくじを引くコマンドです。"""
        if ctx.invoked_subcommand is None:
            await ctx.send("おみくじを引くコマンドです。")

    @omikuji_group.command(name="debug")
    @is_owner()
    @is_guild()
    async def debug(self, ctx):
        """デバッグコマンドです。"""
        steps = [
            "iPhoneだけだよ神社に来た",
            "Lightningケーブルがぶら下がってる中おみくじを選ぶ",
            "**Lightningおじさん**がこちらをニコニコしながら眺めている",
            "心を落ち着かせおみくじを開く",
        ]

        fortune = "iPhoneだけだよ!!"

        embed = discord.Embed(title="おみくじ結果", color=0x34343c)
        embed.set_author(name="大当たりが当たる確率がN/A%アップ中だよ！\niPhoneだけだよ神社にて...")
        embed.set_thumbnail(url="https://images.frwi.net/data/images/7b54adae-c988-47f1-a090-625a7838f1c1.png")

        fm = await ctx.send(content=f"{ctx.author.mention}\nおみくじを引きに行く...", embed=None)

        description_with_steps = ""
        for step in steps:
            await asyncio.sleep(2)
            description_with_steps += f"\n\n{step}"
            embed.description = description_with_steps
            await fm.edit(embed=embed)

        await asyncio.sleep(1)
        embed.description += f"\n\nおみくじには**{fortune}**と書かれていた"
        embed.set_footer(text="おみくじを引いてくれてありがとう！また明日引いてみてね！\n連続ログイン: N/A | 今日N/A回目のおみくじを引いたよ！")
        await fm.edit(embed=embed)
        if fortune == "iPhoneだけだよ!!":
            await asyncio.sleep(1)
            embed.description += "\n\niPhoneだけじゃなかったのかよ..."
            await fm.edit(embed=embed)
            iphonedakedayo_emoji1 = "<:omkj_iphone_dakedayo_1:1290367507575869582>"
            iphonedakedayo_emoji2 = "<:omkj_iphone_dakedayo_2:1290367485937451038>"
            iphonedakedayo_emoji3 = "<:omkj_iphone_dakedayo_3:1290367469998833727>"
            iphonedakedayo_emoji4 = "<a:omkj_iphone_dakedayo_4:1290367451061686363>"
            iphonedakedayo_emoji5 = "<:giz_server_icon:1264027561856471062>"

            emoji_list = [iphonedakedayo_emoji1, iphonedakedayo_emoji2, iphonedakedayo_emoji3, iphonedakedayo_emoji4, iphonedakedayo_emoji5]
            for emoji in emoji_list:
                try:
                    await fm.add_reaction(emoji)
                except discord.HTTPException:
                    continue

    @omikuji_group.command(name="add_fortune")
    @is_guild()
    @is_booster()
    async def add_fortune(self, ctx, fortune: str):
        """おみくじに追加するコマンドです。"""
        await ctx.defer()
        self.ids = self.load_ids()
        if fortune in self.ids:
            await ctx.send(f"{fortune}はすでにおみくじに存在します。")
            return
        self.ids[fortune] = fortune
        with open(self.idfile, "w", encoding="utf-8") as f:
            json.dump(self.ids, f, indent=4, ensure_ascii=False)
        await ctx.send(f"{fortune}をおみくじに追加しました。")

    @omikuji_group.command(name="remove_fortune")
    @is_guild()
    @is_booster()
    async def remove_fortune(self, ctx, fortune: str):
        """おみくじから削除するコマンドです。"""
        await ctx.defer()
        self.ids = self.load_ids()
        if fortune in self.ids:
            del self.ids[fortune]
            with open(self.idfile, "w", encoding="utf-8") as f:
                json.dump(self.ids, f, indent=4, ensure_ascii=False)
            await ctx.send(f"{fortune}をおみくじから削除しました。")
        else:
            await ctx.send(f"{fortune}はおみくじに存在しません。")

    @omikuji_group.command(name="list_fortune")
    @is_guild()
    @is_booster()
    async def list_fortune(self, ctx):
        """おみくじのリストを表示するコマンドです。"""
        await ctx.defer()
        self.ids = self.load_ids()
        logger.info(f"おみくじのリスト: {self.ids}")
        if self.ids:
            e = discord.Embed(
                title="おみくじのリスト",
                description="",
                color=discord.Color.blurple()
            )
            for fortune in self.ids:
                e.description += f"{fortune}\n"
            await ctx.send(embed=e)
        else:
            await ctx.send("おみくじのリストは空です。")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot == self.bot.user:
            return
        if message.content == "ギズみくじ":
            if message.guild is None:
                await message.channel.send("このコマンドはサーバーでのみ利用できます。")
                return
            if message.channel.id in [889075104481423461, 1096027971900428388]:
                ctx = await self.bot.get_context(message)
                await self.omikuji(ctx)

        if message.content == "運勢":
            if message.guild is None:
                await message.channel.send("このコマンドはサーバーでのみ利用できます。")
                return
            if message.channel.id in [889075104481423461, 1096027971900428388]:
                ctx = await self.bot.get_context(message)
                await self.fortune(ctx)

async def setup(bot):
    await bot.add_cog(OmikujiCog(bot))
