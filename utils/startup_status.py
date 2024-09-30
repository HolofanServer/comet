import discord

async def update_status(bot, message):
    await bot.change_presence(activity=discord.Game(name=f"起動中...", state=message, status=discord.Status.idle))