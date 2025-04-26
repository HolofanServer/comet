import discord
from discord.ext import commands
from discord import app_commands

import io
import re
import json
import matplotlib as mpl
import matplotlib.pyplot as plt
import os
import platform

from utils.logging import setup_logging
from config.setting import get_settings

logger = setup_logging("D")
settings = get_settings()

with open('config/bot.json', 'r') as f:
    bot_config: dict[str, str] = json.load(f)
    
if platform.system() == 'Darwin':
    os.environ['PATH'] = '/Library/TeX/texbin:' + os.environ.get('PATH', '')
else:
    os.environ['PATH'] = '/bin:' + os.environ.get('PATH', '')

plt.rcParams['text.usetex'] = True
plt.rcParams['text.latex.preamble'] = r'\usepackage{amsmath}'
plt.rcParams['font.family'] = 'serif'
mpl.rcParams['mathtext.fontset'] = 'cm'

class LatexCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.hybrid_command(name="latex", aliases=["tex", "数式"])
    @app_commands.describe(latex_code_or_expression="LaTeX形式の数式または表現式")
    async def render_latex(self, ctx, *, latex_code_or_expression: str):
        """LaTeX形式の数式を画像化するコマンド"""
        try:
            logger.info(f"LaTeX command invoked by {ctx.author} (ID: {ctx.author.id}) in {ctx.guild.name if ctx.guild else 'DM'}")
            logger.info(f"Input expression: {latex_code_or_expression}")
            latex_code = f"${latex_code_or_expression}$"

            buf = io.BytesIO()

            fig, ax = plt.subplots(figsize=(5, 2))
            ax.text(0.5, 0.5, latex_code, fontsize=24, va='center', ha='center', color='black')
            ax.axis('off')
            plt.savefig(buf, format='png', bbox_inches='tight', pad_inches=0.1, dpi=300)
            buf.seek(0)
            plt.close()
            
            file = discord.File(buf, filename="latex_image.png")
            await ctx.send(file=file)
            logger.info(f"Successfully rendered and sent LaTeX image for {ctx.author}")
            
            buf.close()

        except Exception as e:
            error_msg = f"Error processing LaTeX for {ctx.author}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            await ctx.send(f"数式の処理中にエラーが発生しました。構文を確認してください: {str(e)}")
            
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        
        if message.content.startswith(bot_config["prefix"]):
            return
        
        latex_pattern = r'(\$\$[^$]+\$\$|\$[^$]+\$)'
        matches = re.finditer(latex_pattern, message.content)
        
        match_count = 0
        for match in matches:
            match_count += 1
            latex_code = match.group(1)
            logger.info(f"LaTeX expression detected in message {message.id}: {latex_code}")

            ctx = await self.bot.get_context(message)
            await self.render_latex(ctx, latex_code_or_expression=latex_code.strip('$'))
        
        if match_count > 0:
            logger.info(f"Processed {match_count} LaTeX expression(s) in message {message.id}")


async def setup(bot):
    await bot.add_cog(LatexCog(bot))