import discord
from discord.ext import commands

from utils.spam_blocker import SpamBlocker

class ModerationCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.spam_blocker = SpamBlocker(bot)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None:
            return

        ctx = await self.bot.get_context(message)
        
        if await self.spam_blocker.check_blacklist(ctx):
            return

        is_spam = await self.spam_blocker.process_spam(ctx, message)
        
        if not is_spam:
            await self.bot.process_commands(message)
        else:
            return

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        ctx = await self.bot.get_context(interaction)

        # スパムチェック
        is_spam = await self.spam_blocker.process_spam(ctx, interaction)

        if is_spam:
            # スパムの場合は警告メッセージを返す
            await interaction.response.send_message("コマンドを頻繁に送信しすぎています。", ephemeral=True)
            return

        # スパムでない場合、スラッシュコマンドは自動的に処理されるので、特に何もする必要がありません

    @commands.group(name="moderation", aliases=["mod"])
    @commands.is_owner()
    async def moderation(self, ctx: commands.Context):
        """スパム管理コマンド"""
        pass

    @moderation.command(name="blacklist", aliases=["bl"])
    @commands.is_owner()
    async def blacklist(self, ctx: commands.Context, user: discord.User):
        """特定のユーザーをブラックリストに追加するコマンド"""
        await self.spam_blocker.add_to_blacklist(user.id)
        await ctx.send(f"{user.name} がブラックリストに追加されました。")

    @moderation.command(name="whitelist", aliases=["wl"])
    @commands.is_owner()
    async def whitelist(self, ctx: commands.Context, user: discord.User):
        """ブラックリストからユーザーを削除するコマンド"""
        await self.spam_blocker.remove_from_blacklist(user.id)
        await ctx.send(f"{user.name} がブラックリストから削除されました。")

    @moderation.command(name="list_blacklist", aliases=["lb"])
    @commands.is_owner()
    async def list_blacklist(self, ctx: commands.Context):
        """ブラックリストを表示"""
        blacklist = await self.spam_blocker.list_blacklist()
        e = discord.Embed(title="ブラックリスト", description="ブラックリストに登録されているユーザーを表示します。")
        for user_id in blacklist:
            user = await self.bot.fetch_user(user_id)
            e.add_field(name=user.name, value=user.id, inline=False)
        await ctx.send(embed=e)

    @moderation.command(name="search_member", aliases=["sm"])
    async def search_member(self, ctx: commands.Context, *, name: str):
        """名前でメンバーを検索するコマンド"""
        member = discord.utils.get(ctx.guild.members, name=name)
        if member:
            await ctx.send(f"メンバーが見つかりました: {member.name}")
        else:
            await ctx.send(f"名前が {name} のメンバーが見つかりませんでした")

async def setup(bot: commands.Bot):
    await bot.add_cog(ModerationCog(bot))