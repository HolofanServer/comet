import discord
from discord.ext import commands

import os
import aiohttp
import pytz

from datetime import datetime

from config.setting import get_settings

from utils.commands_help import is_guild, is_booster, log_commnads
from utils.logging import setup_logging

logger = setup_logging("D")
settings = get_settings()

api_key = settings.etc_api_openai_api_key
fastapi_url = settings.fastapi_url

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
        file_name = f"generated_image_{formatted_time}_{author_id}_{server_id}.png"
        image_path = os.path.join(self.image_dir, file_name)

        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as response:
                if response.status != 200:
                    raise Exception(f"画像の取得に失敗しました: {response.status_code}")
                image_data = await response.content.read()

            with open(image_path, "wb") as f:
                f.write(image_data)

        logger.debug(f"画像を保存しました: {image_path}")
        return image_path, file_name

    async def upload_to_fastapi(self, image_path):
        logger.debug(f"upload_to_fastapiが呼び出されました: {image_path}")
        async with aiohttp.ClientSession() as session:
            with open(image_path, 'rb') as f:
                form = aiohttp.FormData()
                form.add_field('file', f, filename=os.path.basename(image_path), content_type='image/png')
                headers = {}

                try:
                    async with session.post(fastapi_url, data=form, headers=headers) as response:
                        if response.status != 200:
                            error_text = await response.text()
                            logger.error(f"FastAPIへのアップロードに失敗しました: {response.status}, レスポンス: {error_text}")
                            raise Exception(f"FastAPIへのアップロードに失敗しました: {response.status}")
                        data = await response.json()
                        logger.debug(f"FastAPIにアップロードされたファイルURL: {data['file_url']}")
                        return data['file_url']
                except Exception as e:
                    logger.error(f"FastAPIへのアップロード中にエラーが発生しました: {str(e)}", exc_info=True)
                    raise

    @commands.hybrid_command(name="generate_image")
    @is_guild()
    @is_booster()
    @log_commnads()
    async def generate_image(self, ctx: commands.Context, *, prompt: str):
        """DALL·E APIを使って画像を生成します"""
        logger.debug(f"generate_imageコマンドが呼び出されました: {prompt}")
        await ctx.defer()
        try:
            fm = await ctx.send(f"生成中: '{prompt}' に基づいた画像を作成しています。お待ちください...")
            logger.debug(f"画像生成プロンプト: {prompt}")

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
                        logger.error(f"APIリクエストに失敗しました: {response.status}, レスポンス: {response.text}")
                        raise Exception(f"APIリクエストに失敗しました: {response.status}")
                    data = await response.json()
                    image_url = data['data'][0]['url']
                    logger.debug(f"生成された画像URL: {image_url}")
                    image_path, file_name = await self.save_image(image_url, ctx)

            file_url = await self.upload_to_fastapi(image_path)
            jst = pytz.timezone('Asia/Tokyo')
            now = datetime.now(jst)

            await fm.edit(content=f"生成された画像はこちらです。\nこの画像は`{prompt}`を元に生成されました")
            e = discord.Embed(
                title="",
                description="",
                color=discord.Color.blue(),
                timestamp=now
            )
            e.set_image(url=file_url)
            logger.debug(f"送信された画像パス: {image_path}")
            logger.debug(f"送信されたファイル名: {file_name}")
            await ctx.send(embed=e)

        except Exception as e:
            logger.error(f"エラーが発生しました: {str(e)}")
            await fm.edit(content=f"エラーが発生しました: {str(e)}")

async def setup(bot):
    await bot.add_cog(DalleImageGenerator(bot))
