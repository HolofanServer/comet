from discord.ext import commands

class GitHubCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.github_repo = "https://github.com/GIZMODO-WOODS/study-programming"

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        if "?github" == message.content or "?g" == message.content:
            await message.channel.send(self.github_repo)
        else:
            return

async def setup(bot):
    await bot.add_cog(GitHubCog(bot))