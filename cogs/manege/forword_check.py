import discord
from discord.ext import commands

import aiohttp
from PIL import Image
import io
import json
import os
import logging
import httpx
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

async def fetch_image(session, url):
    async with session.get(url) as response:
        return await response.read()

async def resize_image_if_needed(image_bytes, max_file_size=8*1024*1024, resize_ratio=0.9):
    image = Image.open(io.BytesIO(image_bytes))

    with io.BytesIO() as output:
        image.save(output, format='JPEG', quality=85)
        size = output.tell()
        if size <= max_file_size:
            output.seek(0)
            return output.read()

    while size > max_file_size:
        image = image.resize((int(image.width * resize_ratio), int(image.height * resize_ratio)))
        with io.BytesIO() as output:
            image.save(output, format='JPEG', quality=85)
            size = output.tell()
            if size <= max_file_size:
                output.seek(0)
                return output.read()

async def merge_images_horizontally(image_urls, max_file_size=8*1024*1024):
    async with aiohttp.ClientSession() as session:
        images = []
        total_width = 0
        max_height = 0

        for url in image_urls:
            async with session.get(url) as resp:
                if resp.status != 200:
                    continue
                image_bytes = await resp.read()
                resized_image_bytes = await resize_image_if_needed(image_bytes, max_file_size)
                image = Image.open(io.BytesIO(resized_image_bytes))
                images.append(image)
                total_width += image.width
                max_height = max(max_height, image.height)

        merged_image = Image.new('RGB', (total_width, max_height))

        x_offset = 0
        for image in images:
            merged_image.paste(image, (x_offset, 0))
            x_offset += image.width

        with io.BytesIO() as output:
            merged_image.save(output, format='PNG')
            output.seek(0)
            return discord.File(output, filename="merged_images.png")

async def send_images_in_chunks(image_urls, log_channel, max_images_per_message=10, spoiler=True):
    async with aiohttp.ClientSession() as session:
        for i in range(0, len(image_urls), max_images_per_message):
            chunk_urls = image_urls[i:i+max_images_per_message]
            images = []
            for url in chunk_urls:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        continue
                    image_bytes = await resp.read()
                    resized_image_bytes = await resize_image_if_needed(image_bytes)
                    image = Image.open(io.BytesIO(resized_image_bytes))
                    images.append(image)

            if images:
                total_width = sum(image.width for image in images)
                max_height = max(image.height for image in images)
                merged_image = Image.new('RGB', (total_width, max_height))
                x_offset = 0
                for image in images:
                    merged_image.paste(image, (x_offset, 0))
                    x_offset += image.width

                with io.BytesIO() as output:
                    merged_image.save(output, format='PNG')
                    output.seek(0)
                    file = discord.File(output, filename=f"merged_images_chunk_{i}.png")
                    try:
                        await log_channel.send(content="こちらは合成された添付画像の一部です：", file=file, spoiler=spoiler)
                    except discord.HTTPException as e:
                        if e.code == 40005:
                            await log_channel.send("画像が大きすぎるため、送信できませんでした。")

logger = logging.getLogger(__name__)

class MessageForwardCheck(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot_token = os.getenv("BOT_TOKEN")
        self.config_path = 'data/manege/forward_check.json'

    async def get_message(self, channel_id, message_id):
        url = f"https://discord.com/api/v10/channels/{channel_id}/messages/{message_id}"
        headers = {
            "Authorization": f"Bot {self.bot_token}"
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)

        if response.status_code == 200:
            return response.json()
        else:
            return None
        
    def save_config(self, guild_id, channel_id):
        """ログチャンネルの設定を保存する"""
        dir_path = os.path.dirname(self.config_path)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                config = json.load(f)
        else:
            config = {}

        config[str(guild_id)] = {"forward_log_channel": channel_id}

        with open(self.config_path, 'w') as f:
            json.dump(config, f, indent=4)

    def load_config(self, guild_id):
        """ログチャンネルの設定を読み込む"""
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                config = json.load(f)
        else:
            config = {}

        return config.get(str(guild_id), {}).get("forward_log_channel", None)
        

    @commands.hybrid_group(name="forward")
    async def forward(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @forward.command(name="set_channel")
    async def set_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        self.save_config(ctx.guild.id, ctx.channel.id)
        await ctx.send(f"{ctx.channel.mention}がログチャンネルとして設定されました。")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        
        if message.channel.type == discord.ChannelType.news:  # 修正箇所
            return
        
        if message.id:
            original_message_data = await self.get_message(message.channel.id, message.id)

            if original_message_data and 'message_reference' in original_message_data:
                ref_message = original_message_data['message_reference']
                reference_message_id = ref_message.get('message_id')
                reference_channel_id = ref_message.get('channel_id')  # 追加
                reference_message = await self.get_message(reference_channel_id, reference_message_id)  # 修正
                reference_channel = self.bot.get_channel(reference_channel_id)
                
                if reference_channel:  # 追加
                    reference_guild = reference_channel.guild
                    reference_guild_id = ref_message.get('guild_id')

                    if reference_guild_id == str(message.guild.id):
                        return
                else:
                    reference_guild = None
                    reference_guild_id = None

                await message.delete()
                e = discord.Embed(
                    title="⚠️警告⚠️",
                    description="他サーバーから転送されたメッセージを削除しました。",
                    color=discord.Color.red(),
                    timestamp=datetime.now(timezone.utc)
                )
                e.add_field(name="メッセージ情報", value=f"メッセージ: {reference_message.get('content')}\nメッセージID: {reference_message.get('id')}\nチャンネル: <#{reference_channel.id if reference_channel else 'N/A'}>\nチャンネルID: {reference_channel.id if reference_channel else 'N/A'}\nギルド: {reference_guild.name if reference_guild else 'N/A'}\nギルドID: {reference_guild.id if reference_guild else 'N/A'}")
                e.add_field(name="ユーザー", value=f"<@{reference_message.get('author').get('id')}>\n{reference_message.get('author').get('id')}")
                log_channel_id = self.load_config(message.guild.id)
                log_channel = self.bot.get_channel(log_channel_id)
                if log_channel:
                    await log_channel.send(embed=e)
                    # 画像処理の追加
                    image_urls = [attachment.url for attachment in message.attachments if attachment.filename.lower().endswith(('png', 'jpg', 'jpeg', 'gif'))]
                    if image_urls:
                        embed_image = discord.Embed(title="削除されたメッセージの添付画像", description="複数の画像を合成しています...", color=discord.Color.greyple())
                        message_embed = await log_channel.send(embed=embed_image)
                        await send_images_in_chunks(image_urls, log_channel, spoiler=True)
                        await message_embed.edit(embed=embed_image)
                else:
                    logger.error(f"ログチャンネルが見つかりません: {log_channel_id}")
                return
            else:
                return

async def setup(bot):
    await bot.add_cog(MessageForwardCheck(bot))