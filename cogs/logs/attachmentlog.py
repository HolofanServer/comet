import discord
from discord.ext import commands
import aiohttp
from dotenv import load_dotenv
import os

load_dotenv()

guild_id = int(os.getenv("MAIN_GUILD_ID"))
channel_id = int(os.getenv("ATTACHMENT_CHANNEL_ID"))

class AttachmentLogCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.target_guild_id = guild_id
        self.target_channel_id = channel_id
        self.special_extensions = {'ogg'}

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.bot.user:
            return

        if message.guild is None or message.guild.id != self.target_guild_id:
            return

        target_channel = self.bot.get_channel(self.target_channel_id)

        if message.attachments:
            for attachment in message.attachments:
                file_extension = attachment.filename.split('.')[-1]

                if file_extension in self.special_extensions:
                    if message.author.guild_permissions.administrator:
                        embed = discord.Embed(
                            description=f'{message.author.mention}\n\n{message.channel.mention}\n[{file_extension}ファイルです]({attachment.url})\n安全のためオリジナルメッセージは消去されました。',
                            color=0xFF0000,
                            timestamp=message.created_at
                        )
                        await message.delete()
                        await target_channel.send(embed=embed)
                        await message.author.send(f'事故防止のため{message.author.mention}さんが送信した[{attachment.filename}]({attachment.url})は消去されました。')
                    else:
                        async with aiohttp.ClientSession() as session:
                            async with session.get(attachment.url) as resp:
                                if resp.status == 200:
                                    with open(f'tmp/{attachment.filename}', 'wb') as f:
                                        while True:
                                            chunk = await resp.content.read(1024)
                                            if not chunk:
                                                break
                                            f.write(chunk)
                        file = discord.File(f'tmp/{attachment.filename}', filename=attachment.filename)
                        embed = discord.Embed(
                            description=f'{message.author.mention}\n\n{message.jump_url}\nFile: [{attachment.filename}]({attachment.url})',
                            color=0x00FF00,
                            timestamp=message.created_at
                        )
                        embed.set_image(url=attachment.url)
                        await target_channel.send(embed=embed, silent=True)

                else:
                    embed = discord.Embed(
                        description=f'{message.author.mention}\n\n{message.jump_url}\nFile: [{attachment.filename}]({attachment.url})',
                        color=0x00FF00,
                        timestamp=message.created_at
                    )
                    embed.set_image(url=attachment.url)
                    await target_channel.send(embed=embed, silent=True)

async def setup(bot):
    await bot.add_cog(AttachmentLogCog(bot))