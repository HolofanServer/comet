import discord

async def update_status(bot, message):
    activity = discord.Activity(type=discord.ActivityType.playing, name="起動中...", state=message, status=discord.Status.idle)
    await bot.change_presence(activity=activity)