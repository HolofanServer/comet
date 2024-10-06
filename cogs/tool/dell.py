import discord
from discord.ext import commands

import os
import aiohttp
import asyncio
import pytz

from openai import OpenAI
from dotenv import load_dotenv
from datetime import datetime

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
                    logger.error(f"画像の取得に失敗しました: {response.status}")
                    raise Exception(f"画像の取得に失敗しました: {response.status}")
                image_data = await response.read()

                with open(image_path, "wb") as f:
                    f.write(image_data)

        logger.info(f"画像を保存しました: {image_path}")
        return image_path

    @commands.hybrid_command(name="generate_image")
    async def generate_image(self, ctx: commands.Context, *, prompt: str):
        """DALL·E APIを使って画像を生成します"""
        # 役割がリストであることを確認
        if not hasattr(ctx.author, 'roles') or not isinstance(ctx.author.roles, list):
            await ctx.send("役割情報を取得できませんでした。")
            logger.warning("役割情報を取得できませんでした。")
            return

        if not any(role.name == "Server Booster" for role in ctx.author.roles):
            mes = await ctx.channel.send("このコマンドは現在利用できません。")
            await asyncio.sleep(3)
            await mes.delete()
            await ctx.message.delete()
            logger.info("役割が不足しているため、コマンドの実行が拒否されました。")
            return
        
        try:
            await ctx.defer()
            first_message = await ctx.send(f"生成中: '{prompt}' に基づいた画像を作成しています。お待ちください...")
            logger.info(f"画像生成のリクエストを受け取りました: {prompt}")

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
                        logger.error(f"APIリクエストに失敗しました: {response.status}")
                        raise Exception(f"APIリクエストに失敗しました: {response.status}")
                    data = await response.json()
                    image_url = data['data'][0]['url']
                    image_path = await self.save_image(image_url, ctx)
                    logger.info(f"生成された画像のパス: {image_path}")

            await first_message.edit(content=f"生成された画像はこちらです\nこの画像は'{prompt}'を元に生成されました", file=discord.File(image_path))
            logger.info(f"画像生成が完了しました: {prompt}")

        except Exception as e:
            await first_message.edit(content=f"エラーが発生しました: {str(e)}")
            logger.error(f"画像生成中にエラーが発生しました: {str(e)}")

async def setup(bot):
    await bot.add_cog(DalleImageGenerator(bot))