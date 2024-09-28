import discord
from discord.ext import commands
import json
import os

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
        return {}

target_channel_id = 1212206562056085585

async def tubuyakirule_announce(message, client):
    if message.channel.id != target_channel_id:
        return

    data = load_data()
    channel_data = data.get(str(target_channel_id), {"message_count": 0, "last_message_id": None})
    message_count = channel_data['message_count'] + 1
    last_message_id = channel_data['last_message_id']

    if message_count % 5 == 0:
        if last_message_id:
            try:
                msg_to_delete = await message.channel.fetch_message(last_message_id)
                await msg_to_delete.delete()
            except Exception as e:
                print(f"Error deleting last message: {e}")

        embed = discord.Embed(
            title="https://discord.com/channels/1043759677831393291/1212206562056085585/1212207706417532958 のルール",
            description="つぶやきチャンネルでは、他の人のメッセージに対してリアクションをつける行為、メッセージに対して反応を示す行為を禁止しています。\n\n自分の言いたいことを言うだけのチャンネルです。ルールに従いご利用ください。",
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
        
        await tubuyakirule_announce(message, self.bot)

async def setup(bot):
    await bot.add_cog(TubuyakiMessageCog(bot))