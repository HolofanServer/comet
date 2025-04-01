import discord
from discord.ext import commands


class SoundboardCogs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
            
    @commands.hybrid_command(name="ｴｯﾎｴｯﾎ")
    async def april(self, ctx: commands.Context):
        await ctx.send("ｴｯﾎｴｯﾎ　　εε＝📱🦉　　ｴｯﾎｴｯﾎ")

async def setup(bot):
    await bot.add_cog(SoundboardCogs(bot))
