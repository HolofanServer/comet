import discord
import random
import os
from discord.ext import commands


class SoundboardCogs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.target_channel_ids = [768485824517505055, 889075104481423461]
        
        self.messages = [
            "ｴｯﾎｴｯﾎ　　εε＝📱🦉　　ｴｯﾎｴｯﾎ\nライトニングは最強端子だって伝えなきゃ\nｴｯﾎｴｯﾎ　　εε＝📱🦉　　ｴｯﾎｴｯﾎ",
            "ｴｯﾎｴｯﾎ　　εε＝📱🦉　　ｴｯﾎｴｯﾎ\nあみとうさんはライトニング教の教祖だって伝えなきゃ\nｴｯﾎｴｯﾎ　　εε＝📱🦉　　ｴｯﾎｴｯﾎ",
            "ｴｯﾎｴｯﾎ　　εε＝📱🦉　　ｴｯﾎｴｯﾎ\niPhoneは3Gが最強だって伝えなきゃ\nｴｯﾎｴｯﾎ　　εε＝📱🦉　　ｴｯﾎｴｯﾎ",
            "ｴｯﾎｴｯﾎ　　εε＝📱🦉　　ｴｯﾎｴｯﾎ\nUSB-Cに変えたAppleは邪教だって伝えなきゃ\nｴｯﾎｴｯﾎ　　εε＝📱🦉　　ｴｯﾎｴｯﾎ",
            "ｴｯﾎｴｯﾎ　　εε＝📱🦉　　ｴｯﾎｴｯﾎ\n30ピンコネクタの偉大さを伝えなきゃ\nｴｯﾎｴｯﾎ　　εε＝📱🦉　　ｴｯﾎｴｯﾎ",
            "ｴｯﾎｴｯﾎ　　εε＝📱🦉　　ｴｯﾎｴｯﾎ\niPhone 3Gのホームボタンは宇宙一のクリック感だって伝えなきゃ\nｴｯﾎｴｯﾎ　　εε＝📱🦉　　ｴｯﾎｴｯﾎ",
            "ｴｯﾎｴｯﾎ　　εε＝📱🦉　　ｴｯﾎｴｯﾎ\nスティーブ・ジョブズもライトニング端子を愛していたって伝えなきゃ\nｴｯﾎｴｯﾎ　　εε＝📱🦉　　ｴｯﾎｴｯﾎ",
            "ｴｯﾎｴｯﾎ　　εε＝📱🦉　　ｴｯﾎｴｯﾎ\nクマさんでもわかるライトニングの素晴らしさを伝えなきゃ\nｴｯﾎｴｯﾎ　　εε＝📱🦉　　ｴｯﾎｴｯﾎ",
            "ｴｯﾎｴｯﾎ　　εε＝📱🦉　　ｴｯﾎｴｯﾎ\niPhoneは角があって武器になるって伝えなきゃ\nｴｯﾎｴｯﾎ　　εε＝📱🦉　　ｴｯﾎｴｯﾎ"
        ]
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """「伝えなきゃ」で終わるメッセージを監視して反応します。"""
        # 自分自身のメッセージには反応しない
        if message.author.bot:
            return
            
        # 特定のチャンネルIDかどうか確認
        if message.channel.id in self.target_channel_ids:
            # メッセージが「伝えなきゃ」で終わるか確認
            if message.content.endswith('伝えなきゃ'):
                # 定型メッセージを送信
                await message.channel.send("ｴｯﾎｴｯﾎ　　εε＝📱🦉　　ｴｯﾎｴｯﾎ")
            
    @commands.hybrid_command(name="ｴｯﾎｴｯﾎ")
    async def april(self, ctx: commands.Context):
        """ランダムなｴｯﾎｴｯﾎメッセージを送信します。"""
        # メッセージリストからランダムに選択
        selected_message = random.choice(self.messages)
        await ctx.send(selected_message)

async def setup(bot):
    await bot.add_cog(SoundboardCogs(bot))
