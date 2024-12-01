import discord
from discord.ext import commands

import httpx
import os
import pytz
from datetime import datetime
import json

from utils.logging import setup_logging
from config.setting import get_settings

logger = setup_logging("D")
settings = get_settings()

guild_id = settings.admin_main_guild_id
fastapi_url = settings.fastapi_url

class AttachmentLogCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.target_guild_id = guild_id
        self.special_extensions = {'ogg'}
        self.image_dir = "data/image/logging"

    def get_channel_id(self, guild_id):
        config_file_path = f"data/logs/{guild_id}/config/attachment.json"
        if os.path.exists(config_file_path):
            with open(config_file_path, 'r') as f:
                config = json.load(f)
                if config.get("log_attachment", False) is False:
                    return None
                channel_id = config.get("log_channel", None)
                if channel_id is None:
                    return None
                return channel_id
        logger.warning("設定ファイルが存在しません。")
        return None

    async def save_image(self, image_url, attachment):
        if not os.path.exists(self.image_dir):
            os.makedirs(self.image_dir)
            #logger.info(f"画像ディレクトリを作成しました: {self.image_dir}")

        jst = pytz.timezone('Asia/Tokyo')
        now = datetime.now(jst)
        formatted_time = now.strftime("%Y%m%d%H%M%S")
        author_id = attachment.author.id
        server_id = attachment.guild.id
        file_name = f"attachment_{formatted_time}_{author_id}_{server_id}.png"
        image_path = os.path.join(self.image_dir, file_name)

        #logger.debug(f"画像を保存中: {image_url} -> {image_path}")
        async with httpx.AsyncClient() as client:
            response = await client.get(image_url)
            if response.status_code != 200:
                logger.error(f"画像の取得に失敗しました: {response.status_code}")
                raise Exception(f"画像の取得に失敗しました: {response.status_code}")
            image_data = response.content

        with open(image_path, "wb") as f:
            f.write(image_data)

        #logger.debug(f"画像を保存しました: {image_path}")
        return image_path, file_name

    async def upload_to_fastapi(self, image_path):
        #logger.debug(f"upload_to_fastapiが呼び出されました: {image_path}")
        async with httpx.AsyncClient() as client:
            with open(image_path, 'rb') as f:
                files = {'file': (os.path.basename(image_path), f, 'image/png')}
                try:
                    response = await client.post(fastapi_url, files=files)
                    if response.status_code != 200:
                        error_text = response.text
                        logger.error(f"FastAPIへのアップロードに失敗しました: {response.status_code}, レスポンス: {error_text}")
                        raise Exception(f"FastAPIへのアップロードに失敗しました: {response.status_code}")
                    data = response.json()
                    #logger.debug(f"FastAPIにアップロードされたファイルURL: {data['file_url']}")
                    return data['file_url']
                except Exception as e:
                    logger.error(f"FastAPIへのアップロード中にエラーが発生しました: {str(e)}", exc_info=True)
                    raise

    @commands.Cog.listener()
    async def on_message(self, message):
        #logger.debug(f"メッセージを受信しました: {message.content} (送信者: {message.author})")
        if message.author == self.bot.user:
            #logger.info("自分のメッセージは無視します。")
            return

        if message.guild is None or message.guild.id != self.target_guild_id:
            #logger.warning("対象のギルドではないメッセージを受信しました。")
            return

        channel_id = self.get_channel_id(message.guild.id)
        if channel_id is None:
            #logger.warning("チャンネルIDが取得できませんでした。")
            return

        parent_channel = self.bot.get_channel(channel_id)
        if parent_channel is None:
            #logger.warning("親チャンネルが見つかりません。")
            return

        if message.attachments:
            #logger.debug(f"メッセージに添付ファイルがあります: {message.attachments}")
            for attachment in message.attachments:
                #logger.debug(f"添付ファイルの拡張子: {file_extension}")

                image_path, file_name = await self.save_image(attachment.url, message)
                #logger.debug(f"画像を保存しました: {image_path}")
                file_url = await self.upload_to_fastapi(image_path)
                #logger.debug(f"FastAPIにアップロードされたファイルURL: {file_url}")
                embed = discord.Embed(
                    description=f'{message.author.mention}\n\n{message.jump_url}\nFile: [{attachment.filename}]({file_url})',
                    color=0x00FF00,
                    timestamp=message.created_at
                )
                embed.set_image(url=file_url)
                await parent_channel.send(embed=embed, silent=True)
                #logger.debug(f"メッセージを送信しました: {file_url}")

async def setup(bot):
    await bot.add_cog(AttachmentLogCog(bot))