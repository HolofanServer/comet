import discord
from discord.ext import commands
import json
from datetime import datetime, timedelta
import asyncio
import random

class OmikujiCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.omikujifile = 'data/last_omikuji.json'
        self.last_omikuji = self.load_last_omikuji()

    def load_last_omikuji(self):
        try:
            with open(self.omikujifile, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            return {}

    def save_last_omikuji(self, data):
        with open(self.omikujifile, "w") as f:
            json.dump(data, f)

    async def reset_at_midnight(self):
        while True:
            now_utc = datetime.utcnow()
            now_jst = now_utc + timedelta(hours=9)
            next_midnight_jst = datetime(now_jst.year, now_jst.month, now_jst.day) + timedelta(days=1)
            sleep_seconds = (next_midnight_jst - now_jst).total_seconds()

            await asyncio.sleep(sleep_seconds)

            self.last_omikuji.clear()
            self.save_last_omikuji(self.last_omikuji)

    @commands.hybrid_command(name="omikuji")
    async def omikuji(self, ctx):
        """1日1回だけおみくじを引くことができます。"""
        user_id = str(ctx.author.id)

        now_utc = datetime.utcnow()
        now_jst = now_utc + timedelta(hours=9)
        today_jst = now_jst.date()

        if user_id in self.last_omikuji and self.last_omikuji[user_id] == today_jst.isoformat():
            await ctx.send("今日はもうおみくじを引いています！\n日本時間24時にリセットされます。")
            return

        self.last_omikuji[user_id] = today_jst.isoformat()
        self.save_last_omikuji(self.last_omikuji)

        steps = [
            "iPhoneだけだよ神社に来た",
            "Lightningケーブルがぶら下がってる中おみくじを選ぶ",
            "**Lightningおじさん**がこちらをニコニコしながら眺めている",
            "心を落ち着かせおみくじを開く",
        ]

        fortune_choices = ["Lightningケーブル", "Type-Cケーブル", "Micro-Bケーブル", "HDMIケーブル", "iPhoneだけだよ！", "VGA Connector", "Type-Aケーブル", "DPケーブル", "Type-Bケーブル", "Mini-Bケーブル"]
        fortune = random.choice(fortune_choices)

        embed = discord.Embed(title="おみくじ結果", color=0x34343c)
        embed.set_author(name="iPhoneだけだよ神社にて...")
        embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1121700273254055936/1147277206381416599/c7b0850d740fa8bb9272b4d3289ef37c.png")

        await ctx.send(content="おみくじを引に行く...")

        message = await ctx.send(content=ctx.author.mention, embed=embed)

        description_with_steps = ""
        for step in steps:
            await asyncio.sleep(2)
            description_with_steps += f"\n\n{step}"
            embed.description = description_with_steps
            await message.edit(embed=embed)

        await asyncio.sleep(1)
        embed.description += f"\n\nおみくじには**{fortune}**と書かれていた"
        embed.set_footer(text="おみくじを引いてくれてありがとう！また明日引いてみてね！")
        await message.edit(embed=embed)
        if fortune == "iPhoneだけだよ！":
            await asyncio.sleep(1)
            embed.description += f"\n\niPhoneだけじゃなかったのかよ..."
            await message.edit(embed=embed)
            iphonedakedayo_emoji1 = "<a:gizGif_dakedayo:1052474489037914172>"
            iphonedakedayo_emoji2 = "<:1giz_amitodakedayoFace:760497129671884900>"
            iphonedakedayo_emoji3 = "<:1giz_amitomugon:760497186478882866>"
            iphonedakedayo_emoji4 = "<:terminal_LightningC:760770112311001139>"
            iphonedakedayo_emoji5 = "<:terminal_LightningW:760770240337936416>"
            iphonedakedayo_emoji6 = "<:moji_p_iPhone_dake_dayo:1096852346992087050>"

            emoji_list = [iphonedakedayo_emoji1, iphonedakedayo_emoji2, iphonedakedayo_emoji3, iphonedakedayo_emoji4, iphonedakedayo_emoji5, iphonedakedayo_emoji6]
            for emoji in emoji_list:
                await message.add_reaction(emoji)

async def setup(bot):
    await bot.add_cog(OmikujiCog(bot))