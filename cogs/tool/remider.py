import discord
from discord.ext import commands

import dateparser
import re
import asyncio
import os
import json
import logging
from datetime import datetime, timedelta, timezone
from openai import OpenAI
from collections import deque
from pytz import timezone as pytz_timezone

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

api_key = os.getenv("OPENAI_API_KEY")
client_ai = OpenAI(api_key=api_key)

class ReminderCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.reminder_queue = deque()
        self.processing_task = None
        self.reminder_data = {}

    async def parse_time_and_message(self, input_string):
        """入力から時間、メッセージ、リピート情報を抽出する"""
        logger.debug(f"parse_time_and_message: input_string={input_string}")

        response = client_ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": f"次の入力から時間、メッセージ、リピート情報を抽出してください: {input_string}"},
                {"role": "user", "content": "タイムゾーンが含まれている場合はそれも抽出してください。タイムゾーンが指定されていない場合は指定なしと返してください。また台北時間やロンドン時間などの都市名はタイムゾーンとして変換してください 例: JST, UTC, GMT"},
                {"role": "system", "content": "以下の形式でリマインダーを設定できます。特定の日時にリマインド: `リマインド 2024年10月1日午前9時にミーティング開始と送信して`"},
                {"role": "system", "content": "結果を以下のJSON形式で返してください: {\"time\": \"ISO8601形式の時間\", \"message\": \"メッセージ\", \"repeat_type\": \"リピート情報\", \"timezone\": \"タイムゾーン\"}"}
            ]
        )
        result = response.choices[0].message.content.strip()
        logger.debug(f"OpenAI response: {result}")

        try:
            result = result.strip('```json').strip('```')
            parsed_data = json.loads(result)
            
            time_str = parsed_data['time']
            message = parsed_data['message']
            repeat_type = parsed_data.get('repeat_type')
            timezone = parsed_data.get('timezone')

            if timezone is None or timezone == "指定なし":
                timezone = "Asia/Tokyo"
            timezone_obj = pytz_timezone(timezone)

            remind_time = dateparser.parse(
                time_str,
                settings={
                    'PREFER_DATES_FROM': 'future',
                    'TIMEZONE': timezone,
                    'RETURN_AS_TIMEZONE_AWARE': True,
                },
                languages=['ja']
            )

            if remind_time is None:
                logger.error(f"Failed to parse remind_time from {time_str}")

            now_str = datetime.now(timezone_obj)
            
            if time_str < now_str and repeat_type is None:
                await message.channel.send("指定された時間は既に過ぎています。未来の時間を指定してください。")
                return
            else:
                logger.debug(f"parse_time_and_message: remind_time={remind_time}, message={message}, repeat_type={repeat_type}, timezone={timezone}")
            return remind_time, message, repeat_type
        except (json.JSONDecodeError, KeyError, AttributeError, ValueError) as e:
            logger.error(f"Failed to parse OpenAI response: {e}")
            return None, None, None


    async def process_reminders(self):
        """リマインダープロセスをキューから処理"""
        while self.reminder_queue:
            message, remind_time, remind_message, repeat_type = self.reminder_queue.popleft()
            await self.set_reminder(message, remind_time, remind_message, repeat_type)

    async def set_reminder(self, message, remind_time, remind_message, repeat_type):
        """指定した時間後にメッセージを送信"""
        logger.debug(f"set_reminder: message={message}, remind_time={remind_time}, remind_message={remind_message}, repeat_type={repeat_type}")
        while True:
            delta = (remind_time - datetime.now()).total_seconds()
            logger.debug(f"set_reminder: delta={delta}")

            if delta > 0:
                await asyncio.sleep(delta)
                mention_author = message.author.mention
                e = discord.Embed(
                    title=f"🔔{message.author.display_name}さんのリマインダー🕐",
                    description=f"設定されたリマインダーです！\n\n{remind_message}",
                    color=discord.Color.blue()
                )
                await message.channel.send(content=mention_author, embed=e)

                if repeat_type is None:
                    self.delete_data(message.author.id, remind_time, remind_message, repeat_type)
                    break
            else:
                logger.error("指定された時間は既に過ぎています。未来の時間を指定してください。")
                break

            # 繰り返しリマインダーの処理
            if repeat_type == 'daily':
                remind_time += timedelta(days=1)
            elif repeat_type == 'weekly':
                remind_time += timedelta(weeks=1)
            elif repeat_type == 'monthly':
                remind_time = self.get_next_monthday_time(remind_time.day, remind_time.strftime("%H:%M"))
            elif repeat_type == 'hourly':
                remind_time += timedelta(hours=1)

            logger.debug(f"set_reminder: new remind_time={remind_time}")

    def save_data(self, user_id, remind_time, remind_message, repeat_type):
        """リマインダー情報を保存する"""
        if user_id not in self.reminder_data:
            self.reminder_data[user_id] = []
        
        self.reminder_data[user_id].append({
            "remind_time": remind_time,
            "remind_message": remind_message,
            "repeat_type": repeat_type
        })
        logger.debug(f"save_data: user_id={user_id}, remind_time={remind_time}, remind_message={remind_message}, repeat_type={repeat_type}")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        if not re.search(r'リマインド', message.content):
            return
        
        if re.search(r'リマインド[ 　]', message.content):
            remind_time, remind_message, repeat_type = await self.parse_time_and_message(message.content)

            if remind_time is None:
                await message.channel.send("時間とメッセージを理解できませんでした。正しい形式で入力してください。")
                return

            if remind_time < datetime.now(timezone.utc) and repeat_type is None:
                await message.channel.send("指定された時間は既に過ぎています。未来の時間を指定してください。")
                return

            logger.debug(f"on_message: remind_time={remind_time}, remind_message={remind_message}, repeat_type={repeat_type}")

            if remind_time is None:
                await message.channel.send("時間とメッセージを理解できませんでした。正しい形式で入力してください。")
                return

            self.save_data(message.author.id, remind_time, remind_message, repeat_type)
            e = discord.Embed(
                title="🔔リマインダー設定🕐",
                description=f"{message.author.display_name}さんのリマインダーを設定しました",
                color=discord.Color.blue()
            )
            e.add_field(
                name="リマインド内容",
                value=f" <t:{int(remind_time.timestamp())}> に `{remind_message}`と送信します。",
                inline=False
            )
            await message.channel.send(embed=e)

            # リマインダーをキューに追加
            self.reminder_queue.append((message, remind_time, remind_message, repeat_type))
            if self.processing_task is None or self.processing_task.done():
                self.processing_task = asyncio.create_task(self.process_reminders())


    async def send_help_embed(self, channel):
        """リマインドの使用例を含むヘルプEmbedを送信する"""
        logger.debug("send_help_embed")
        embed = discord.Embed(
            title="リマインダー機能の使い方",
            description="以下の形式でリマインダーを設定できます。",
            color=discord.Color.blue()
        )

        embed.add_field(
            name="特定の日時にリマインド",
            value="`リマインド 2024年10月1日午前9時にミーティング開始と送信して`",
            inline=False
        )

        embed.add_field(
            name="明日の指定でリマインド",
            value="`リマインド 明日朝8時に出社と送信して`",
            inline=False
        )

        embed.add_field(
            name="今から何分後にリマインド",
            value="`リマインド 30分後に休憩と送信して`",
            inline=False
        )

        embed.add_field(
            name="毎日のリマインド",
            value="`リマインド 毎日の午後3時に水分補給と送信して`",
            inline=False
        )

        embed.add_field(
            name="毎週のリマインド",
            value="`リマインド 毎週月曜日の朝9時に週次ミーティング開始と送信して`",
            inline=False
        )

        embed.add_field(
            name="毎月のリマインド",
            value="`リマインド 毎月15日の午後1時に報告書提出と送信して`",
            inline=False
        )

        embed.add_field(
            name="毎時のリマインド",
            value="`リマインド 毎時30分に休憩と送信して`",
            inline=False
        )

        embed.add_field(
            name="特定の曜日と時間のリマンド",
            value="`マインド 毎週水曜日の午後7時にジムに行くと送信して`",
            inline=False
        )

        await channel.send(embed=embed)

async def setup(bot):
    await bot.add_cog(ReminderCog(bot))