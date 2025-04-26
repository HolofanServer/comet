import discord
from discord.ext import commands

import dateparser
import re
import asyncio
import json

from datetime import datetime, timedelta, timezone
from openai import OpenAI
from collections import deque
from pytz import timezone as pytz_timezone

from utils.logging import setup_logging
from config.setting import get_settings

logger = setup_logging("D")
settings = get_settings()

api_key = settings.etc_api_openai_api_key
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
                {"role": "system", "content": "You are a helpful assistant that parses time expressions into ISO8601 format."},
                {"role": "system", "content": "When handling relative time (e.g., '5分後', '1時間後'), calculate from the CURRENT time."},
                {"role": "system", "content": f"Current time is: {datetime.now(pytz_timezone('Asia/Tokyo')).isoformat()}"},
                {"role": "system", "content": "When no timezone is specified, ALWAYS use JST (Asia/Tokyo, +09:00)."},
                {"role": "system", "content": "When year is not specified in the date, use the CURRENT year unless the date has already passed this year."},
                {"role": "user", "content": f"次の入力から時間、メッセージ、リピート情報を抽出してください: {input_string}"},
                {"role": "user", "content": "タイムゾーンが含まれている場合はそれも抽出してください。タイムゾーンが指定されていない場合は指定なしと返してください。また台北時間やロンドン時間などの都市名はタイムゾーンとして変換してください 例: Asia/Tokyo, Asia/Taipei, Europe/London。JST, UTC, GMTはロケーションタイプのタイムゾーンとして変換してください"},
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
            timezone_str = parsed_data.get('timezone', 'Asia/Tokyo')

            if timezone_str == "指定なし" or not timezone_str:
                timezone_str = "Asia/Tokyo"
            timezone_obj = pytz_timezone(timezone_str)

            if '+' not in time_str and '-' not in time_str:
                time_str = time_str.rstrip('Z') + '+09:00'

            remind_time = dateparser.parse(
                time_str,
                settings={
                    'PREFER_DATES_FROM': 'future',
                    'TIMEZONE': timezone_str,
                    'RETURN_AS_TIMEZONE_AWARE': True,
                    'RELATIVE_BASE': datetime.now(timezone_obj),
                    'PREFER_DATES_FROM': 'current_period',
                },
                languages=['ja']
            )

            if remind_time is None:
                logger.error(f"Failed to parse remind_time from {time_str}")
                return None, None, None

            now = datetime.now(timezone_obj)
            
            if remind_time.year != now.year:
                remind_time = remind_time.replace(year=now.year)
                if remind_time < now:
                    remind_time = remind_time.replace(year=now.year + 1)

            if remind_time < now and repeat_type is None:
                return None, None, None
            else:
                logger.debug(f"parse_time_and_message: remind_time={remind_time}, message={message}, repeat_type={repeat_type}, timezone={timezone_str}")
            return remind_time, message, repeat_type
        except (json.JSONDecodeError, KeyError, AttributeError, ValueError) as e:
            logger.error(f"Failed to parse OpenAI response: {e}")
            return None, None, None


    async def process_reminders(self):
        """リマインダープロセスをキューから処理"""
        while self.reminder_queue:
            context, remind_time, remind_message, repeat_type = self.reminder_queue.popleft()
            await self.set_reminder(context, remind_time, remind_message, repeat_type)

    async def set_reminder(self, context, remind_time, remind_message, repeat_type):
        """指定した時間後にメッセージを送信"""
        logger.debug(f"set_reminder: context={context}, remind_time={remind_time}, remind_message={remind_message}, repeat_type={repeat_type}")
        while True:
            now = datetime.now(timezone.utc)
            if not remind_time.tzinfo:
                remind_time = remind_time.replace(tzinfo=timezone.utc)
            
            delta = (remind_time - now).total_seconds()
            logger.debug(f"set_reminder: delta={delta}")

            if delta > 0:
                await asyncio.sleep(delta)

                if isinstance(context, commands.Context):
                    author = context.author
                    channel = context.channel
                else:
                    author = context.author
                    channel = context.channel

                await channel.send(f"{author.mention}\n{remind_message}")

                if repeat_type is None:
                    self.delete_data(author.id, remind_time, remind_message, repeat_type)
                    break
            else:
                logger.error("指定された時間は既に過ぎています。未来の時間を指定してください。")
                break

            if repeat_type == 'daily':
                remind_time = remind_time + timedelta(days=1)
            elif repeat_type == 'weekly':
                remind_time = remind_time + timedelta(weeks=1)
            elif repeat_type == 'monthly':
                next_month = remind_time.replace(day=1) + timedelta(days=32)
                remind_time = next_month.replace(day=min(remind_time.day, (next_month.replace(day=1) - timedelta(days=1)).day))
            elif repeat_type == 'hourly':
                remind_time = remind_time + timedelta(hours=1)

            logger.debug(f"set_reminder: new remind_time={remind_time}")

    def delete_data(self, user_id, remind_time, remind_message, repeat_type):
        """リマインダー情報を削除する"""
        if user_id in self.reminder_data:
            self.reminder_data[user_id] = [
                reminder for reminder in self.reminder_data[user_id]
                if not (
                    reminder["remind_time"] == remind_time and
                    reminder["remind_message"] == remind_message and
                    reminder["repeat_type"] == repeat_type
                )
            ]
            logger.debug(f"delete_data: user_id={user_id}, remind_time={remind_time}, remind_message={remind_message}, repeat_type={repeat_type}")

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
        
        if re.match(r'リマインド[ 　]ヘルプ', message.content):
            await self.send_help_embed(message.channel)
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

            self.reminder_queue.append((message, remind_time, remind_message, repeat_type))
            if self.processing_task is None or self.processing_task.done():
                self.processing_task = asyncio.create_task(self.process_reminders())


    @commands.hybrid_command(name="reminder", description="自然言語でリマインダーを設定します。例: 明日の朝9時にミーティング", aileas=["remind", "reminder"])
    async def remind(self, ctx: commands.Context, *, input_text: str):
        """自然言語でリマインダーを設定するコマンド"""
        if input_text.strip() == "ヘルプ":
            await self.send_help_embed(ctx.channel)
            return

        remind_time, remind_message, repeat_type = await self.parse_time_and_message(input_text)

        if remind_time is None:
            await ctx.send("時間とメッセージを理解できませんでした。正しい形式で入力してください。")
            return

        if remind_time < datetime.now(timezone.utc) and repeat_type is None:
            await ctx.send("指定された時間は既に過ぎています。未来の時間を指定してください。")
            return

        logger.debug(f"remind command: remind_time={remind_time}, remind_message={remind_message}, repeat_type={repeat_type}")

        self.save_data(ctx.author.id, remind_time, remind_message, repeat_type)
        e = discord.Embed(
            title="🔔リマインダー設定🕐",
            description=f"{ctx.author.display_name}さんのリマインダーを設定しました",
            color=discord.Color.blue()
        )
        e.add_field(
            name="リマインド内容",
            value=f" <t:{int(remind_time.timestamp())}> に `{remind_message}`と送信します。",
            inline=False
        )
        await ctx.send(embed=e)

        self.reminder_queue.append((ctx, remind_time, remind_message, repeat_type))
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