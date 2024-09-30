import discord
from discord.ext import commands

from openai import OpenAI
from dotenv import load_dotenv
import os
import aiohttp
import asyncio
load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=api_key)

class DalleImageGenerator(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="generate_image")
    async def generate_image(self, ctx, *, prompt: str):
        """DALL·E APIを使って画像を生成します"""
        if not any(role.name == "Server Booster" for role in ctx.author.roles):
            mes = await ctx.channel.send("このコマンドは現在利用できません。")
            await asyncio.sleep(3)
            await mes.delete()
            await ctx.message.delete()
            return
        
        try:
            await ctx.defer()
            first_message = await ctx.send(f"生成中: '{prompt}' に基づいた画像を作成しています。お待ちください...")

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

            await first_message.edit(content="生成された画像はこちらです", embed=discord.Embed().set_image(url=image_url))

        except Exception as e:
            await first_message.edit(content=f"エラーが発生しました: {str(e)}")

async def setup(bot):
    await bot.add_cog(DalleImageGenerator(bot))