import discord
from discord.ext import commands

import os
import aiohttp
import pytz

from dotenv import load_dotenv
from datetime import datetime

from utils.commands_help import is_guild, log_commnads
from utils.logging import setup_logging

logger = setup_logging()

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")

class DalleImageGenerator(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.image_dir = "data/image/"

    async def save_image(self, image_url, ctx):
        if not os.path.exists(self.image_dir):
            os.makedirs(self.image_dir)

        jst = pytz.timezone('Asia/Tokyo')
        now = datetime.now(jst)
        formatted_time = now.strftime("%Y%m%d%H%M%S")
        author_id = ctx.author.id
        server_id = ctx.guild.id
        image_path = os.path.join(self.image_dir, f"generated_image_{formatted_time}_{author_id}_{server_id}.png")

        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as response:
                if response.status != 200:
                    raise Exception(f"画像の取得に失敗しました: {response.status}")
                image_data = await response.read()

                with open(image_path, "wb") as f:
                    f.write(image_data)

        return image_path

    @commands.hybrid_command(name="generate_image")
    @is_guild()
    @log_commnads()
    async def generate_image(self, ctx: commands.Context, *, prompt: str):
        """DALL·E APIを使って画像を生成します"""
        await ctx.defer()
        if not hasattr(ctx.author, 'roles') or not isinstance(ctx.author.roles, list):
            await ctx.send("役割情報を取得できませんでした。", delete_after=3)
            return

        if not any(role.name == "Server Booster" for role in ctx.author.roles):
            await ctx.channel.send("このコマンドは現在利用できません。", delete_after=3)
            return
        
        
        try:
            fm = await ctx.send(f"生成中: '{prompt}' に基づいた画像を作成しています。お待ちください...")

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.openai.com/v1/images/generations",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "dall-e-3",
                        "prompt": prompt,
                        "size": "1024x1024",
                        "quality": "standard",
                        "n": 1
                    }
                ) as response:
                    if response.status != 200:
                        raise Exception(f"APIリクエストに失敗しました: {response.status}")
                    data = await response.json()
                    image_url = data['data'][0]['url']
                    image_path = await self.save_image(image_url, ctx)

            await fm.edit(content=f"生成された画像はこちらです\nこの画像は'{prompt}'を元に生成されました")
            file = discord.File(image_path)
            file.spoiler = True
            await ctx.send(file=file)

        except Exception as e:
            await fm.edit(content=f"エラーが発生しました: {str(e)}")

async def setup(bot):
    await bot.add_cog(DalleImageGenerator(bot))