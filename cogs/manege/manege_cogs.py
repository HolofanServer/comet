from discord.ext import commands
import discord
from discord import app_commands

import pathlib

class ManagementCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
                
    def _get_available_cogs(self):
        folder_name = 'cogs'
        cur = pathlib.Path('.')
        
        available_cogs = []
        for p in cur.glob(f"{folder_name}/**/*.py"):
            if p.stem == "__init__":
                continue
            module_path = p.relative_to(cur).with_suffix('').as_posix().replace('/', '.')
            if module_path.startswith('cogs.'):
                available_cogs.append(module_path)
        print(available_cogs)
        return available_cogs

    async def cog_autocomplete(
        self, 
        interaction: discord.Interaction, 
        current: str
    ) -> list[app_commands.Choice[str]]:
        available_cogs = self._get_available_cogs()
        filtered_cogs = [cog for cog in available_cogs if current.lower() in cog.lower()]
        return [
            app_commands.Choice(name=cog, value=cog) for cog in filtered_cogs[:25]
        ]

    async def is_owner_interaction_check(interaction: discord.Interaction):
        return await interaction.client.is_owner(interaction.user)

    def is_owner_check():
        async def predicate(interaction: discord.Interaction):
            return await ManagementCog.is_owner_interaction_check(interaction)
        return app_commands.check(predicate)

    @app_commands.command(name="reload", description="指定したcogを再読み込みします")
    @app_commands.describe(cog="再読み込みするcogの名前")
    @app_commands.autocomplete(cog=cog_autocomplete)
    @is_owner_check()
    async def reload_cog(self, interaction: discord.Interaction, cog: str):
        available_cogs = self._get_available_cogs()
        
        if cog not in available_cogs:
            await interaction.response.send_message(f"'{cog}' は利用可能なcogのリストに含まれていません。")
            return

        try:
            await self.bot.reload_extension(cog)
            await self.bot.tree.sync()
            await interaction.response.send_message(f"{cog}を再読み込みしました。")
        except commands.ExtensionNotLoaded:
            await interaction.response.send_message(f"'{cog}' は読み込まれていません。")
        except commands.ExtensionFailed as e:
            await interaction.response.send_message(f"'{cog}' の再読み込み中にエラーが発生しました。\n{type(e).__name__}: {e}")

    @commands.hybrid_command(name='list_cogs', with_app_command=True)
    @commands.is_owner()
    async def list_cogs(self, ctx):
        """現在ロードされているCogsをリスト表示します"""
        embed = discord.Embed(title="ロードされているCogs", color=discord.Color.blue())
        cog_names = [cog for cog in self.bot.cogs.keys()]
        if cog_names:
            embed.add_field(name="Cogs", value='\n'.join(cog_names), inline=False)
        else:
            embed.add_field(name="Cogs", value="ロードされているCogはありません。", inline=False)

        if hasattr(self.bot, 'failed_cogs') and self.bot.failed_cogs:
            failed_cogs_list = [f'{cog}: {error}' for cog, error in self.bot.failed_cogs.items()]
            e_failed_cogs = discord.Embed(title="正常に読み込めなかったCogファイル一覧", color=discord.Color.red())
            e_failed_cogs.add_field(name="Failed Cogs", value='\n'.join(failed_cogs_list), inline=False)
        else:
            e_failed_cogs = discord.Embed(title="正常に読み込めなかったCogファイル一覧", color=discord.Color.green())
            e_failed_cogs.add_field(name="Failed Cogs", value="なし", inline=False)

        await ctx.send(embed=embed)
        await ctx.send(embed=e_failed_cogs)

async def setup(bot):
    await bot.add_cog(ManagementCog(bot))