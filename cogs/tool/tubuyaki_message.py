import discord
from discord.ext import commands

import json
import os

from utils.logging import setup_logging
from config.setting import get_settings

logger = setup_logging()

settings = get_settings()

filename = 'data/tubuyaki/ta_message.json'

def save_data(data, filename=filename):
    with open(filename, 'w') as f:
        if filename is None:
            os.makedirs(os.path.dirname(filename), exist_ok=True)
        json.dump(data, f, indent=4)

def load_data(filename=filename):
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        os.makedirs(os.path.dirname(filename), exist_ok=True)

target_channel_id = settings.admin_tubuyaki_channel_id
# mod_channel_id = settings.admin_mod_channel_id
dev_server_id = settings.admin_dev_guild_id
main_server_id = settings.admin_main_guild_id

async def tubuyakirule_announce(message, client):
    if message.channel.id != target_channel_id:
        return

    data = load_data()
    channel_data = data.get(str(target_channel_id), {"message_count": 0, "last_message_id": None})
    message_count = channel_data['message_count'] + 1
    last_message_id = channel_data['last_message_id']

    if message_count % 10 == 0:
        if last_message_id:
            try:
                msg_to_delete = await message.channel.fetch_message(last_message_id)
                await msg_to_delete.delete()
            except Exception as e:
                print(f"Error deleting last message: {e}")

        embed = discord.Embed(
            title="https://discord.com/channels/753903663298117694/1156414531292106752/1156416165661384775 のルール",
            description="つぶやきチャンネルでは、他の人のメッセージに対してリアクションをつける行為、メッセージに対して反応を示す行為を禁止しています。\n\n自分の言いたいことを言うだけのチャンネルです。ルールに従いご利用ください。\n詳しくは[こちら](https://discord.com/channels/753903663298117694/1156414531292106752/1156416165661384775) のメッセージをご覧ください。",
            color=0x00ff00
        )
        text_content = "【定期連絡】"
        sent_message = await message.channel.send(text_content, embed=embed, silent=True)
        channel_data['last_message_id'] = sent_message.id

    channel_data['message_count'] = message_count
    data[str(target_channel_id)] = channel_data
    save_data(data)

class TubuyakiMessageCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.bot.user:
            return
        
        # # 他のメッセージへの返信を検出
        # if message.channel.id == target_channel_id and message.reference and message.reference.message_id:
        #     original_message = await message.channel.fetch_message(message.reference.message_id)
        #     await message.delete()
        #     warning_message = await message.channel.send(f"{message.author.mention} さん、他の人のメッセージに返信することは禁止されています。", delete_after=10)
        #     logger.warning(f"{message.author} replied to {original_message.author}'s message in the restricted channel.")
        #     e = discord.Embed(
        #         description=f"{message.author.display_name} さんが呟きチャンネルで他の人のメッセージに返信しました.",
        #         color=0xff0000
        #     )
        #     e.add_field(name="メッセージ内容", value=original_message.content)
        #     e.set_author(name=original_message.author.display_name, icon_url=original_message.author.display_avatar.url)
        #     e.set_footer(text=f"メッセージID: {original_message.id} | すでに削除されました")
        #     mod_channel = self.bot.get_channel(mod_channel_id)
        #     await mod_channel.send(embed=e)

        await tubuyakirule_announce(message, self.bot)

    # @commands.Cog.listener()
    # async def on_reaction_add(self, reaction, user):
    #     # 特定のチャンネルでのみリアクションの検出
    #     if reaction.message.channel.id == target_channel_id and not user.bot:
    #         await reaction.message.remove_reaction(reaction.emoji, user)
    #         warning_message = await reaction.message.channel.send(f"{user.mention} さん、他の人のメッセージにリアクションをつけることは禁止されています。", delete_after=10)
    #         logger.warning(f"{user} reacted with {reaction.emoji} to {reaction.message.author}'s message in the restricted channel.")
    #         e = discord.Embed(
    #             description=f"{user.mention} さんが呟きチャンネルで他の人のメッセージにリアクションしました。",
    #             color=0xff0000
    #         )
    #         if reaction.emoji:
    #             if isinstance(reaction.emoji, (discord.Emoji, discord.PartialEmoji)):
    #                 # カスタム絵文字の場合
    #                 e.add_field(name="リアクション", value=str(reaction.emoji))
    #                 e.set_thumbnail(url=reaction.emoji.url)
    #             else:
    #                 # デフォルト絵文字の場合
    #                 e.add_field(name="リアクション", value=reaction.emoji)
        
    #         e.set_author(name=reaction.message.author.display_name, icon_url=reaction.message.author.display_avatar.url)
    #         e.set_footer(text=f"メッセージID: {reaction.message.id} | すでに削除されました")
    #         mod_channel = self.bot.get_channel(mod_channel_id)
    #         await mod_channel.send(embed=e)
            
async def setup(bot):
    await bot.add_cog(TubuyakiMessageCog(bot))