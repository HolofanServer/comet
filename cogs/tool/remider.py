import discord
from discord.ext import commands

import dateparser
import re
import asyncio
import os
import json
import logging
from datetime import datetime, timedelta
from openai import OpenAI
from collections import deque

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

api_key = os.getenv("OPENAI_API_KEY")

client_ai = OpenAI(api_key=api_key)

class ReminderCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.reminder_queue = deque()
        self.processing_task = None

    async def parse_time_and_message(self, input_string):
        """入力から時間、メッセージ、リピート情報を抽出する"""
        logger.debug(f"parse_time_and_message: input_string={input_string}")

        response = client_ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": f"次の入力から時間、メッセージ、リピート情報を抽出してください: {input_string}"},
                {"role": "system", "content": "以下の形式でリマインダーを設定できます。特定の日時にリマインド: `リマインド 2024年10月1日午前9時にミーティング開始と送信して`"},
                {"role": "system", "content": "結果を以下のJSON形式で返してください: {\"time\": \"時間\", \"message\": \"メッセージ\", \"repeat_type\": \"リピート情報\"}"}
            ]
        )
        result = response.choices[0].message.content.strip()
        logger.debug(f"OpenAI response: {result}")

        try:
            result_json = re.search(r'{.*}', result)
            if result_json:
                parsed_data = json.loads(result_json.group(0))
                time_str = parsed_data['time']
                message = parsed_data['message']
                repeat_type = parsed_data.get('repeat_type')

                remind_time = dateparser.parse(time_str, settings={'PREFER_DATES_FROM': 'future', 'RELATIVE_BASE': datetime.now()})

                logger.debug(f"parse_time_and_message: remind_time={remind_time}, message={message}, repeat_type={repeat_type}")
                return remind_time, message, repeat_type
            else:
                raise ValueError("Response does not contain valid JSON")
        except (json.JSONDecodeError, KeyError, AttributeError, ValueError) as e:
            logger.error(f"Failed to parse OpenAI response: {e}")
            return None, None, None

    def get_next_weekday_time(self, day_of_week, time_string):
        """次の指定された曜日と時間のdatetimeを返す"""
        logger.debug(f"get_next_weekday_time: day_of_week={day_of_week}, time_string={time_string}")
        day_of_week_map = {
            '日曜日': 6,
            '月曜日': 0,
            '火曜日': 1,
            '水曜日': 2,
            '木曜日': 3,
            '金曜日': 4,
            '土曜日': 5
        }
        today = datetime.now()
        target_day = day_of_week_map.get(day_of_week)
        if target_day is None:
            logger.debug("get_next_weekday_time: invalid day_of_week")
            return None

        days_ahead = target_day - today.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        next_weekday = today + timedelta(days=days_ahead)
        next_time = dateparser.parse(time_string)
        result = next_weekday.replace(hour=next_time.hour, minute=next_time.minute, second=next_time.second, microsecond=0)
        logger.debug(f"get_next_weekday_time: result={result}")
        return result

    def get_next_monthday_time(self, day_of_month, time_string):
        """次の指定された月日と時間のdatetimeを返す"""
        logger.debug(f"get_next_monthday_time: day_of_month={day_of_month}, time_string={time_string}")
        today = datetime.now()
        year = today.year
        month = today.month

        if today.day >= day_of_month:
            month += 1
            if month > 12:
                month = 1
                year += 1

        next_monthday = datetime(year, month, day_of_month)
        next_time = dateparser.parse(time_string)
        result = next_monthday.replace(hour=next_time.hour, minute=next_time.minute, second=next_time.second, microsecond=0)
        logger.debug(f"get_next_monthday_time: result={result}")
        return result

    def get_next_time(self, repeat_type, time_string):
        """次の指定された時間を返す（毎日、毎時など）"""
        logger.debug(f"get_next_time: repeat_type={repeat_type}, time_string={time_string}")
        now = datetime.now()

        if repeat_type == 'daily':
            next_time = dateparser.parse(time_string)
            if now.hour > next_time.hour or (now.hour == next_time.hour and now.minute >= next_time.minute):
                result = now + timedelta(days=1)
            else:
                result = now.replace(hour=next_time.hour, minute=next_time.minute, second=next_time.second, microsecond=0)
            logger.debug(f"get_next_time: result={result}")
            return result

        elif repeat_type == 'hourly':
            match = re.match(r'毎時(\d+)分', time_string)
            if match:
                minute = int(match.group(1))
                if now.minute >= minute:
                    result = now + timedelta(hours=1)
                else:
                    result = now
                result = result.replace(minute=minute, second=0, microsecond=0)
                logger.debug(f"get_next_time: result={result}")
                return result

        logger.error(f"Unsupported repeat type: {repeat_type}")
        return None

    def save_data(self, user_id, remind_time, message, repeat_type):
        """リマインダーをファイルに保存する"""
        logger.debug(f"save_data: user_id={user_id}, remind_time={remind_time}, message={message}, repeat_type={repeat_type}")
        user_dir = f'data/reminder/{user_id}'
        if not os.path.exists(user_dir):
            os.makedirs(user_dir)

        data_path = os.path.join(user_dir, 'reminder.json')
        data = self.load_data(user_id)

        data.append({
            "time": remind_time.timestamp(),
            "message": message,
            "repeat": repeat_type
        })

        with open(data_path, 'w') as f:
            json.dump(data, f, indent=4)

        logger.info(f"リマインダーを保存しました: ユーザーID={user_id}, 時間={remind_time}, メッセージ={message}, リピートタイプ={repeat_type}")

    def load_data(self, user_id):
        """リマインダーデータをファイルから読み込む"""
        logger.debug(f"load_data: user_id={user_id}")
        user_dir = f'data/reminder/{user_id}'
        data_path = os.path.join(user_dir, 'reminder.json')

        if os.path.exists(data_path):
            with open(data_path, 'r') as f:
                data = json.load(f)
                logger.debug(f"load_data: data={data}")
                return data

        logger.debug("load_data: no data found")
        return []

    async def process_reminders(self):
        while self.reminder_queue:
            message, remind_time, remind_message, repeat_type = self.reminder_queue.popleft()
            await self.set_reminder(message, remind_time, remind_message, repeat_type)

    async def set_reminder(self, message, remind_time, remind_message, repeat_type):
        """リマインダーを設定し、指定時間後にメッセージを送信する"""
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

            if repeat_type == 'daily':
                remind_time += timedelta(days=1)
            elif repeat_type == 'weekly':
                remind_time += timedelta(weeks=1)
            elif repeat_type == 'monthly':
                remind_time = self.get_next_monthday_time(remind_time.day, remind_time.strftime("%H:%M"))
            elif repeat_type == 'hourly':
                remind_time += timedelta(hours=1)

            logger.debug(f"set_reminder: new remind_time={remind_time}")

    def delete_data(self, user_id, remind_time, message, repeat_type):
        """リマインダーデータをファイルから削除する"""
        logger.debug(f"delete_data: user_id={user_id}, remind_time={remind_time}, message={message}, repeat_type={repeat_type}")
        user_dir = f'data/reminder/{user_id}'
        data_path = os.path.join(user_dir, 'reminder.json')
        data = self.load_data(user_id)

        data = [entry for entry in data if not (
            entry["time"] == remind_time.timestamp() and
            entry["message"] == message and
            entry["repeat"] == repeat_type
        )]

        with open(data_path, 'w') as f:
            json.dump(data, f, indent=4)

        logger.info(f"リマインダーを削除しました: ユーザーID={user_id}, 時間={remind_time}, メッセージ={message}, リピートタイプ={repeat_type}")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        if not re.search(r'リマインド', message.content):
            return
        
        if not any(role.name == "moderator" for role in message.author.roles):
            mes = await message.channel.send("このコマンドは現在利用できません。")
            await asyncio.sleep(3)
            await mes.delete()
            await message.delete()
            return
        
        if re.search(r'^リマインド$', message.content.strip()):
            e = discord.Embed(
                title="リマインド",
                description="リマインドを設定するには、以下の形式でメッセージを送信してください。\n\n`リマインド 5分後にミーティング開始と送信して`",
                color=discord.Color.blue()
            )
            await message.channel.send(embed=e)
            return

        if re.search(r'リマインド ヘルプ', message.content):
            await self.send_help_embed(message.channel)
            return

        if re.search(r'リマインド[ 　]', message.content):
            remind_time, remind_message, repeat_type = await self.parse_time_and_message(message.content)
            logger.debug(f"on_message: remind_time={remind_time}, remind_message={remind_message}, repeat_type={repeat_type}")

            if remind_time is None:
                await message.channel.send("時間とメッセージを理解できませんでした。正しい形式で入力してください。")
                return

            if remind_time < datetime.now() and repeat_type is None:
                await message.channel.send("指定された時間は既に過ぎています。未来の時間を指定してください。")
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
            name="特定の曜日と時間のリマインド",
            value="`リマインド 毎週水曜日の午後7時にジムに行くと送信して`",
            inline=False
        )

        await channel.send(embed=embed)

async def setup(bot):
    await bot.add_cog(ReminderCog(bot))