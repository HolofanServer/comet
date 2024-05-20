import discord
from discord.ext import commands

class ServerInfoCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_group(name='info', invoke_without_command=True)
    async def info_group(self, ctx):
        """情報コマンドのグループ"""
        await ctx.send("情報コマンドのサブコマンドを使ってください")

    @info_group.command(name='server')
    async def server_info(self, ctx):
        """サーバーの情報を表示します"""
        guild = ctx.guild

        number_of_text_channels = len(guild.text_channels)
        number_of_voice_channels = len(guild.voice_channels)
        number_of_stage_channels = len(guild.stage_channels)
        number_of_categories = len(guild.categories)
        
        nsfw_level = str(guild.nsfw_level).replace('_', ' ').title()
        nsfw_level = str(guild.nsfw_level).replace('Nsfwlevel.', ' ').title()

        description = (
            f'**オーナー/ID:** {guild.owner} ({guild.owner_id})\n'
            f'**作成日:** {guild.created_at.strftime("%Y-%m-%d %H:%M:%S")}\n'
            f'**言語:** {guild.preferred_locale}\n'
            f'**メンバー数:** {guild.member_count}/{guild.max_members}\n'
            f'**BOT数:** {sum(1 for member in guild.members if member.bot)}\n'
            f'**ロール数:** {len(guild.roles)}\n'
            f'**絵文字の数:** {len(guild.emojis)}/{guild.emoji_limit}\n'
            f'**スタンプの数:** {len(guild.stickers)}/{guild.sticker_limit}\n'
            f'**認証レベルl:** {str(guild.verification_level)}\n'
            f'**NSFW レベル:** {nsfw_level}\n'
            f'**チャンネル:** \n📁 カテゴリー数: {number_of_categories}\n'
            f'💬 テキスト: {number_of_text_channels}\n'
            f'🔊 ボイス: {number_of_voice_channels}\n'
            f'🎤 ステージ: {number_of_stage_channels}\n'
            f'**AFK チャンネル/タイムアウト時間:** {guild.afk_channel}\n{guild.afk_timeout // 60} 分\n'
            f'**ブーストレベル:** {guild.premium_tier} (ブースター数: {guild.premium_subscription_count})\n'
        )

        embed = discord.Embed(title=f'{guild.name} サーバー情報', description=description, color=discord.Color.blue())
        embed.set_thumbnail(url=str(guild.icon.url))

        await ctx.send(embed=embed)

    @info_group.command(name='user')
    async def user_info(self, ctx, *, user: discord.Member = None):
        """ユーザーの情報を表示します"""
        user = user or ctx.author
        if user.premium_since is not None:
            boosting_since = user.premium_since.strftime('%Y-%m-%d %H:%M:%S')
        else:
            boosting_since = 'ブーストはしていません'
        roles_description = ", ".join(role.mention for role in user.roles[1:])

        description = f"**ID:** {user.id}\n**作成日:** {user.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n**参加日:** {user.joined_at.strftime('%Y-%m-%d %H:%M:%S')}\n**ロール:** \n{roles_description}\n**一番上のロール:** {user.top_role.mention}\n**ブースト:** {boosting_since}\n"

        embed = discord.Embed(title=f'{user} ユーザー情報', description=description, color=discord.Color.blue())
        embed.set_thumbnail(url=str(user.avatar.url))

        await ctx.send(embed=embed)

    @info_group.command(name='channel')
    async def channel_info(self, ctx, *, channel: discord.abc.GuildChannel = None):
        """チャンネルの情報を表示します"""
        channel = channel or ctx.channel

        description = (
            f'**ID:** {channel.id}\n'
            f'**作成日:** {channel.created_at.strftime("%Y-%m-%d %H:%M:%S")}\n'
            f'**種類:** {channel.type}\n'
        )

        embed = discord.Embed(title=f'{channel.name} チャンネル情報', description=description, color=discord.Color.blue())

        await ctx.send(embed=embed)
    
    @info_group.command(name='emoji')
    async def emoji_info(self, ctx, *, emoji: discord.Emoji):
        """絵文字の情報を表示するします"""
        description = (
            f'**ID:** {emoji.id}\n'
            f'**作成日:** {emoji.created_at.strftime("%Y-%m-%d %H:%M:%S")}\n'
            f'**URL:** [Link]({emoji.url})\n'
        )

        embed = discord.Embed(title=f'{emoji.name} 絵文字情報', description=description, color=discord.Color.blue())
        embed.set_thumbnail(url=str(emoji.url))

        await ctx.send(embed=embed)
    
    @info_group.command(name='emoji_list')
    async def emoji_list(self, ctx):
        """絵文字のリストを表示するにぇ"""
        emojis_str = "\n".join(str(emoji) for emoji in ctx.guild.emojis)
        chars_per_embed = 2000

        emojis_chunks = [emojis_str[i:i+chars_per_embed] for i in range(0, len(emojis_str), chars_per_embed)]

        for chunk in emojis_chunks:
            embed = discord.Embed(title="絵文字リスト", description=chunk, color=discord.Color.blue())
            await ctx.send(embed=embed)

    @info_group.command(name='role')
    async def role_info(self, ctx, *, role: discord.Role):
        """役職の情報を表示します"""
        description = (
            f'**ID:** {role.id}\n'
            f'**作成日:** {role.created_at.strftime("%Y-%m-%d %H:%M:%S")}\n'
            f'**色:** {role.color}\n'
            f'**権限:** {role.permissions}\n'
            f'**位置:** {role.position}\n'
        )

        embed = discord.Embed(title=f'{role.name} ロール情報', description=description, color=role.color)
        embed.set_thumbnail(url=str(ctx.guild.icon.url))

        await ctx.send(embed=embed)
    

async def setup(bot):
    await bot.add_cog(ServerInfoCog(bot))