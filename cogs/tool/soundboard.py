import discord
from discord.ext import commands


class SoundboardCogs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.terget_sound = "iPhoneだけだよ!"

    @commands.Cog.listener()
    async def on_message(self, message):
        """特定のメッセージが送信されたらサウンドボードを再生"""
        if message.author.bot:
            return
        
        if message.content in ["iPhoneだけだよ！", "iPhoneだけだよ!"]:
            if message.guild and message.author.voice:
                voice_channel = message.author.voice.channel
                if not message.guild.voice_client:
                    await voice_channel.connect()

                sound = message.guild.get_soundboard_sound(self.terget_sound)
                if sound:
                    await message.guild.voice_client.channel.send_sound(sound)
                else:
                    return
            else:
                return

    @commands.command()
    async def join(ctx):
        """ボイスチャンネルに参加"""
        if ctx.author.voice:
            channel = ctx.author.voice.channel
            await channel.connect()
            await ctx.send("VCに接続したよ！")
        else:
            await ctx.send("VCに入ってから使ってね！")

    @commands.command()
    async def leave(ctx):
        """ボイスチャンネルから退出"""
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
            await ctx.send("VCから切断したよ！")
            
    @commands.hybrid_command(name="ｴｯﾎｴｯﾎ　　εε＝🦉　　ｴｯﾎｴｯﾎ")
    async def april(self, ctx: commands.Context):
        await ctx.send("ｴｯﾎｴｯﾎ　　εε＝📱🦉　　ｴｯﾎｴｯﾎ")

async def setup(bot):
    await bot.add_cog(SoundboardCogs(bot))
