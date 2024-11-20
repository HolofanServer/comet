from discord.ext import commands
import discord
from discord import app_commands

import pathlib

from utils.commands_help import is_owner_app, is_owner, log_commands
from utils.logging import setup_logging

logger = setup_logging()

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

    def _get_available_dev_cogs(self):
        folder_name = 'cogs_dev'
        cur = pathlib.Path('.')
        
        available_dev_cogs = []
        for p in cur.glob(f"{folder_name}/**/*.py"):
            if p.stem == "__init__":
                continue
            module_path = p.relative_to(cur).with_suffix('').as_posix().replace('/', '.')
            if module_path.startswith('cogs_dev.'):
                available_dev_cogs.append(module_path)
        return available_dev_cogs

    async def dev_cog_autocomplete(
        self, 
        interaction: discord.Interaction, 
        current: str
    ) -> list[app_commands.Choice[str]]:
        available_cogs = self._get_available_dev_cogs()
        filtered_cogs = [cog for cog in available_cogs if current.lower() in cog.lower()]
        return [
            app_commands.Choice(name=cog, value=cog) for cog in filtered_cogs[:25]
        ]
    
    @app_commands.command(name="load", description="指定したcogを読み込みます")
    @app_commands.describe(cog="読み込むcogの名前")
    @app_commands.autocomplete(cog=dev_cog_autocomplete)
    @is_owner_app()
    @log_commands()
    async def load_dev_cog(self, interaction: discord.Interaction, cog: str):
        available_dev_cogs = self._get_available_dev_cogs()

        await interaction.response.defer()
        logger.info(f"読み込むcog: {cog}")
        
        if cog not in available_dev_cogs:
            logger.debug("Cog not in available cogs list")
            await interaction.followup.send(f"'{cog}' は利用可能なcogのリストに含まれていません。")
            logger.warning(f"'{cog}' は利用可能なcogのリストに含まれていません。")
            return

        try:
            await self.bot.load_extension(cog)
            logger.debug("Cog loaded successfully")
            await interaction.followup.send(f"{cog}を読み込みました。")
            logger.info(f"{cog}を読み込みました。")
        except commands.ExtensionFailed as e:
            logger.debug(f"Extension failed: {e}")
            await interaction.followup.send(f"'{cog}' の読み込み中にエラーが発生しました。\n{type(e).__name__}: {e}")
            logger.error(f"'{cog}' の読み込み中にエラーが発生しました。\n{type(e).__name__}: {e}")

    @app_commands.command(name="unload", description="指定したcogをアンロードします")
    @app_commands.describe(cog="アンロードするcogの名前")
    @app_commands.autocomplete(cog=cog_autocomplete)
    @is_owner_app()
    @log_commands()
    async def unload_cog(self, interaction: discord.Interaction, cog: str):
        available_dev_cogs = self._get_available_dev_cogs()

        await interaction.response.defer()
        logger.info(f"アンロードするcog: {cog}")
        
        if cog not in available_dev_cogs:
            logger.debug("Cog not in available cogs list")
            await interaction.followup.send(f"'{cog}' は利用可能なcogのリストに含まれていません。")
            logger.warning(f"'{cog}' は利用可能なcogのリストに含まれていません。")
            return

        try:
            await self.bot.unload_extension(cog)
            logger.debug("Cog unloaded successfully")
            await interaction.followup.send(f"{cog}をアンロードしました。")
            logger.info(f"{cog}をアンロードしました。")
        except commands.ExtensionNotLoaded:
            logger.debug("Extension not loaded")
            await interaction.followup.send(f"'{cog}' は読み込まれていません。")
            logger.warning(f"'{cog}' は読み込まれていません。")
        except commands.ExtensionFailed as e:
            logger.debug(f"Extension failed: {e}")
            await interaction.followup.send(f"'{cog}' のアンロード中にエラーが発生しました。\n{type(e).__name__}: {e}")
            logger.error(f"'{cog}' のアンロード中にエラーが発生しました。\n{type(e).__name__}: {e}")
            
    @app_commands.command(name="reload", description="指定したcogを再読み込みします")
    @app_commands.describe(cog="再読み込みするcogの名前")
    @app_commands.autocomplete(cog=cog_autocomplete)
    @is_owner_app()
    @log_commands()
    async def reload_cog(self, interaction: discord.Interaction, cog: str):
        available_cogs = self._get_available_cogs()

        await interaction.response.defer()
        logger.info(f"再読み込みするcog: {cog}")
        
        if cog not in available_cogs:
            logger.debug("Cog not in available cogs list")
            await interaction.followup.send(f"'{cog}' は利用可能なcogのリストに含まれていません。")
            logger.warning(f"'{cog}' は利用可能なcogのリストに含まれていません。")
            return

        try:
            await self.bot.reload_extension(cog)
            await self.bot.tree.sync()
            logger.debug("Cog reloaded successfully")
            await interaction.followup.send(f"{cog}を再読み込みしました。")
            logger.info(f"{cog}を再読み込みしました。")
        except commands.ExtensionNotLoaded:
            logger.debug("Extension not loaded")
            await interaction.followup.send(f"'{cog}' は読み込まれていません。")
            logger.warning(f"'{cog}' は読み込まれていません。")
        except commands.ExtensionFailed as e:
            logger.debug(f"Extension failed: {e}")
            await interaction.followup.send(f"'{cog}' の再読み込み中にエラーが発生しました。\n{type(e).__name__}: {e}")
            logger.error(f"'{cog}' の再読み込み中にエラーが発生しました。\n{type(e).__name__}: {e}")
            
    @commands.hybrid_command(name='list_cogs', with_app_command=True)
    @is_owner()
    @log_commands()
    async def list_cogs(self, ctx):
        """現在ロードされているCogsをディレクトリごとにリスト表示します"""
        embed = discord.Embed(title="ロードされているCogs", color=discord.Color.blue())
        
        cogs_by_directory = {}
        for cog in self.bot.extensions.keys():
            parts = cog.split('.')
            if len(parts) > 2:
                directory = parts[1]
            elif len(parts) > 1:
                directory = parts[0]
            else:
                directory = 'その他'

            if directory not in cogs_by_directory:
                cogs_by_directory[directory] = []
            cogs_by_directory[directory].append(cog)
        
        for directory, cogs in cogs_by_directory.items():
            embed.add_field(name=directory.capitalize(), value='\n'.join(cogs), inline=False)

        if not cogs_by_directory:
            embed.add_field(name="Cogs", value="ロードされているCogはありません。", inline=False)

        if hasattr(self.bot, 'failed_cogs') and self.bot.failed_cogs:
            failed_cogs_list = [f'{cog}: {error}' for cog, error in self.bot.failed_cogs.items()]
            e_failed_cogs = discord.Embed(title="正常に読み込めなかったCogファイル一覧", color=discord.Color.red())
            e_failed_cogs.add_field(name="Failed Cogs", value='\n'.join(failed_cogs_list), inline=False)
        else:
            e_failed_cogs = discord.Embed(title="正常に読み込めなかったCogファイル一覧", color=discord.Color.green())
            e_failed_cogs.add_field(name="Failed Cogs", value="なし", inline=False)

        await ctx.send(embeds=[embed, e_failed_cogs])

async def setup(bot):
    await bot.add_cog(ManagementCog(bot))