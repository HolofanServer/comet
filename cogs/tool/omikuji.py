import discord
from discord.ext import commands
import json
from datetime import datetime, timedelta
import asyncio
import random
import os

class OmikujiCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.omikujifile = 'data/omikuji/last_omikuji.json'
        self.streakfile = 'data/omikuji/streak_omikuji.json'
        self.last_omikuji = self.load_last_omikuji()
        self.streak_data = self.load_streak_data()
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
        with open(self.omikujifile, "w") as f:
            if not os.path.exists(os.path.dirname(self.omikujifile)):
                os.makedirs(os.path.dirname(self.omikujifile), exist_ok=True)
            json.dump(data, f)

    def load_streak_data(self):
        try:
            with open(self.streakfile, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            if not os.path.exists(os.path.dirname(self.streakfile)):
                os.makedirs(os.path.dirname(self.streakfile), exist_ok=True)
            return {}

    def save_streak_data(self, data):
        with open(self.streakfile, "w") as f:
            if not os.path.exists(os.path.dirname(self.streakfile)):
                os.makedirs(os.path.dirname(self.streakfile), exist_ok=True)
            json.dump(data, f)

    def load_ids(self):
        try:
            with open(self.idfile, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            if not os.path.exists(os.path.dirname(self.idfile)):
                os.makedirs(os.path.dirname(self.idfile), exist_ok=True)
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

    @commands.hybrid_command(name="omikuji", aliases=["おみくじ"])
    async def omikuji(self, ctx):
        """1日1回だけおみくじを引くことができます。"""
        user_id = str(ctx.author.id)

        now_utc = datetime.utcnow()
        now_jst = now_utc + timedelta(hours=9)
        today_jst = now_jst.date()

        if user_id in self.last_omikuji and self.last_omikuji[user_id] == today_jst.isoformat():
            await ctx.send("今日はもうおみくじを引いています！\n日本時間24時にリセットされます。")
            return

        if user_id in self.streak_data:
            last_date = datetime.fromisoformat(self.streak_data[user_id]['last_date']).date()
            if last_date == today_jst - timedelta(days=1):
                self.streak_data[user_id]['streak'] += 1
            else:
                self.streak_data[user_id]['streak'] = 1
        else:
            self.streak_data[user_id] = {'streak': 1}

        self.streak_data[user_id]['last_date'] = today_jst.isoformat()
        self.save_streak_data(self.streak_data)

        self.last_omikuji[user_id] = today_jst.isoformat()
        self.save_last_omikuji(self.last_omikuji)

        steps = [
            "iPhoneだけだよ神社に来た",
            "Lightningケーブルがぶら下がってる中おみくじを選ぶ",
            "**Lightningおじさん**がこちらをニコニコしながら眺めている",
            "心を落ち着かせおみくじを開く",
        ]

        fortune = random.choice(list(self.ids.keys()))

        embed = discord.Embed(title="おみくじ結果", color=0x34343c)
        embed.set_author(name="iPhoneだけだよ神社にて...")
        embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1121700273254055936/1147277206381416599/c7b0850d740fa8bb9272b4d3289ef37c.png")

        fm = await ctx.send(content=f"{ctx.author.mention}\nおみくじを引きに行く...", embed=None)

        description_with_steps = ""
        for step in steps:
            await asyncio.sleep(2)
            description_with_steps += f"\n\n{step}"
            embed.description = description_with_steps
            await fm.edit(embed=embed)

        await asyncio.sleep(1)
        embed.description += f"\n\nおみくじには**{fortune}**と書かれていた"
        embed.set_footer(text=f"おみくじを引いてくれてありがとう！また明日引いてみてね！\n連続ログイン: {self.streak_data[user_id]['streak']}日目")
        await fm.edit(embed=embed)
        if fortune == "iPhoneだけだよ！":
            await asyncio.sleep(1)
            embed.description += "\n\niPhoneだけじゃなかったのかよ..."
            await fm.edit(embed=embed)
            iphonedakedayo_emoji1 = "<a:gizGif_dakedayo:1052474489037914172>"
            iphonedakedayo_emoji2 = "<:1giz_amitodakedayoFace:760497129671884900>"
            iphonedakedayo_emoji3 = "<:1giz_amitomugon:760497186478882866>"
            iphonedakedayo_emoji4 = "<:terminal_LightningC:760770112311001139>"
            iphonedakedayo_emoji5 = "<:terminal_LightningW:760770240337936416>"
            iphonedakedayo_emoji6 = "<:moji_p_iPhone_dake_dayo:1096852346992087050>"

            emoji_list = [iphonedakedayo_emoji1, iphonedakedayo_emoji2, iphonedakedayo_emoji3, iphonedakedayo_emoji4, iphonedakedayo_emoji5, iphonedakedayo_emoji6]
            for emoji in emoji_list:
                await fm.add_reaction(emoji)

    @commands.hybrid_group(name="omkj")
    async def omikuji_group(self, ctx):
        """おみくじを引くコマンドです。"""
        if ctx.invoked_subcommand is None:
            await ctx.send("おみくじを引くコマンドです。")

    @omikuji_group.command(name="add_fortune")
    async def add_fortune(self, ctx, fortune: str):
        """おみくじに追加するコマンドです。"""
        await ctx.defer()
        if fortune in self.ids:
            await ctx.send(f"{fortune}はすでにおみくじに存在します。")
            return
        self.ids[fortune] = fortune
        with open(self.idfile, "w", encoding="utf-8") as f:
            json.dump(self.ids, f, indent=4, ensure_ascii=False)
        await ctx.send(f"{fortune}をおみくじに追加しました。")

    @omikuji_group.command(name="remove_fortune")
    async def remove_fortune(self, ctx, fortune: str):
        """おみくじから削除するコマンドです。"""
        await ctx.defer()
        if fortune in self.ids:
            del self.ids[fortune]
            with open(self.idfile, "w", encoding="utf-8") as f:
                json.dump(self.ids, f, indent=4, ensure_ascii=False)
            await ctx.send(f"{fortune}をおみくじから削除しました。")
        else:
            await ctx.send(f"{fortune}はおみくじに存在しません。")

async def setup(bot):
    await bot.add_cog(OmikujiCog(bot))