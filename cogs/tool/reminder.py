"""
リマインダーシステム

ユーザーが指定した時間にリマインダーを送信する機能を提供します。
"""

import re
from datetime import datetime, timedelta
from typing import Optional

import discord
import pytz
from discord import app_commands
from discord.ext import commands, tasks

from utils.database import execute_query
from utils.logging import setup_logging

logger = setup_logging()

# 日本時間のタイムゾーン
JST = pytz.timezone('Asia/Tokyo')


def parse_time_string(time_str: str) -> Optional[timedelta]:
    """
    時間文字列をtimedeltaに変換します。

    対応形式:
    - 30s, 30秒 -> 30秒
    - 5m, 5分 -> 5分
    - 2h, 2時間 -> 2時間
    - 1d, 1日 -> 1日
    - 1w, 1週間 -> 1週間
    - 複合: 1d2h30m -> 1日2時間30分

    Args:
        time_str: 時間を表す文字列

    Returns:
        timedelta または None（パース失敗時）
    """
    time_str = time_str.lower().strip()

    # 複合パターン: 1d2h30m のような形式
    pattern = r'(?:(\d+)(?:d|日))?(?:(\d+)(?:h|時間?))?(?:(\d+)(?:m|分))?(?:(\d+)(?:s|秒))?(?:(\d+)(?:w|週間?))?'
    match = re.fullmatch(pattern, time_str)

    if match and any(match.groups()):
        days = int(match.group(1) or 0)
        hours = int(match.group(2) or 0)
        minutes = int(match.group(3) or 0)
        seconds = int(match.group(4) or 0)
        weeks = int(match.group(5) or 0)
        return timedelta(weeks=weeks, days=days, hours=hours, minutes=minutes, seconds=seconds)

    # 単純パターン: 30m, 2h など
    simple_patterns = [
        (r'^(\d+)(?:s|秒)$', lambda m: timedelta(seconds=int(m.group(1)))),
        (r'^(\d+)(?:m|分)$', lambda m: timedelta(minutes=int(m.group(1)))),
        (r'^(\d+)(?:h|時間?)$', lambda m: timedelta(hours=int(m.group(1)))),
        (r'^(\d+)(?:d|日)$', lambda m: timedelta(days=int(m.group(1)))),
        (r'^(\d+)(?:w|週間?)$', lambda m: timedelta(weeks=int(m.group(1)))),
    ]

    for pattern, converter in simple_patterns:
        match = re.match(pattern, time_str)
        if match:
            return converter(match)

    return None


def format_timedelta(td: timedelta) -> str:
    """timedeltaを日本語の読みやすい形式に変換します。"""
    total_seconds = int(td.total_seconds())

    if total_seconds < 0:
        return "期限切れ"

    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)

    parts = []
    if days > 0:
        parts.append(f"{days}日")
    if hours > 0:
        parts.append(f"{hours}時間")
    if minutes > 0:
        parts.append(f"{minutes}分")
    if seconds > 0 and not parts:
        parts.append(f"{seconds}秒")

    return "".join(parts) if parts else "まもなく"


class ReminderView(discord.ui.View):
    """リマインダー削除用のView"""

    def __init__(self, reminder_id: int, user_id: int):
        super().__init__(timeout=None)
        self.reminder_id = reminder_id
        self.user_id = user_id

    @discord.ui.button(label="削除", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def delete_reminder(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "このリマインダーを削除する権限がありません。",
                ephemeral=True
            )
            return

        await execute_query(
            "DELETE FROM reminders WHERE id = $1",
            self.reminder_id,
            fetch_type='status'
        )

        await interaction.response.send_message(
            "✅ リマインダーを削除しました。",
            ephemeral=True
        )

        # 元のメッセージのボタンを無効化
        for item in self.children:
            item.disabled = True
        await interaction.message.edit(view=self)


class Reminder(commands.Cog):
    """リマインダー機能を提供するCog"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.check_reminders.start()

    async def cog_load(self):
        """Cogロード時にテーブルを作成"""
        await self._setup_table()

    async def cog_unload(self):
        """Cogアンロード時にタスクを停止"""
        self.check_reminders.cancel()

    async def _setup_table(self):
        """リマインダーテーブルを作成"""
        await execute_query(
            '''
            CREATE TABLE IF NOT EXISTS reminders (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                guild_id BIGINT,
                channel_id BIGINT NOT NULL,
                message_id BIGINT,
                content TEXT NOT NULL,
                remind_at TIMESTAMP WITH TIME ZONE NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                is_dm BOOLEAN DEFAULT FALSE
            )
            ''',
            fetch_type='status'
        )
        # インデックス作成
        await execute_query(
            'CREATE INDEX IF NOT EXISTS idx_reminders_remind_at ON reminders (remind_at)',
            fetch_type='status'
        )
        logger.info("リマインダーテーブルを確認・作成しました")

    @tasks.loop(seconds=30)
    async def check_reminders(self):
        """期限が来たリマインダーをチェックして送信"""
        try:
            now = datetime.now(JST)
            reminders = await execute_query(
                '''
                SELECT id, user_id, guild_id, channel_id, message_id, content, remind_at, is_dm
                FROM reminders
                WHERE remind_at <= $1
                ORDER BY remind_at ASC
                LIMIT 50
                ''',
                now,
                fetch_type='all'
            )

            for reminder in reminders:
                await self._send_reminder(reminder)
                await execute_query(
                    "DELETE FROM reminders WHERE id = $1",
                    reminder['id'],
                    fetch_type='status'
                )

        except Exception as e:
            logger.error(f"リマインダーチェック中にエラー: {e}")

    @check_reminders.before_loop
    async def before_check_reminders(self):
        """BOT準備完了まで待機"""
        await self.bot.wait_until_ready()

    async def _send_reminder(self, reminder: dict):
        """リマインダーを送信"""
        try:
            user = self.bot.get_user(reminder['user_id'])
            if not user:
                user = await self.bot.fetch_user(reminder['user_id'])

            embed = discord.Embed(
                title="⏰ リマインダー",
                description=reminder['content'],
                color=discord.Color.blue(),
                timestamp=datetime.now(JST)
            )
            embed.set_footer(text="設定したリマインダーの時間になりました")

            if reminder['is_dm']:
                # DMで送信
                try:
                    await user.send(embed=embed)
                except discord.Forbidden:
                    logger.warning(f"ユーザー {reminder['user_id']} へのDM送信に失敗")
            else:
                # チャンネルで送信
                channel = self.bot.get_channel(reminder['channel_id'])
                if channel:
                    await channel.send(
                        content=f"<@{reminder['user_id']}>",
                        embed=embed
                    )
                else:
                    # チャンネルが見つからない場合はDMにフォールバック
                    try:
                        await user.send(embed=embed)
                    except discord.Forbidden:
                        pass

        except Exception as e:
            logger.error(f"リマインダー送信エラー: {e}")

    @commands.hybrid_command(name="remind", description="指定した時間後にリマインダーを送信します")
    @app_commands.describe(
        time="時間（例: 30m, 2h, 1d, 1d2h30m）",
        message="リマインダーの内容",
        dm="DMで通知するか（デフォルト: チャンネル）"
    )
    async def remind(
        self,
        ctx: commands.Context,
        time: str,
        *,
        message: str,
        dm: bool = False
    ):
        """リマインダーを設定します"""
        # 時間をパース
        td = parse_time_string(time)
        if not td:
            await ctx.send(
                "❌ 時間の形式が正しくありません。\n"
                "例: `30s`（30秒）, `5m`（5分）, `2h`（2時間）, `1d`（1日）, `1w`（1週間）\n"
                "複合: `1d2h30m`（1日2時間30分）",
                ephemeral=True
            )
            return

        # 最小時間チェック（10秒未満は不可）
        if td.total_seconds() < 10:
            await ctx.send(
                "❌ リマインダーは10秒以上先に設定してください。",
                ephemeral=True
            )
            return

        # 最大時間チェック（1年以上は不可）
        if td.total_seconds() > 365 * 24 * 60 * 60:
            await ctx.send(
                "❌ リマインダーは1年以内に設定してください。",
                ephemeral=True
            )
            return

        remind_at = datetime.now(JST) + td

        # データベースに保存
        result = await execute_query(
            '''
            INSERT INTO reminders (user_id, guild_id, channel_id, content, remind_at, is_dm)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id
            ''',
            ctx.author.id,
            ctx.guild.id if ctx.guild else None,
            ctx.channel.id,
            message,
            remind_at,
            dm,
            fetch_type='row'
        )

        reminder_id = result['id']

        embed = discord.Embed(
            title="✅ リマインダーを設定しました",
            color=discord.Color.green()
        )
        embed.add_field(
            name="内容",
            value=message[:1024],
            inline=False
        )
        embed.add_field(
            name="通知時間",
            value=f"<t:{int(remind_at.timestamp())}:F>（{format_timedelta(td)}後）",
            inline=False
        )
        embed.add_field(
            name="通知方法",
            value="📩 DM" if dm else "📢 このチャンネル",
            inline=False
        )
        embed.set_footer(text=f"リマインダーID: {reminder_id}")

        view = ReminderView(reminder_id, ctx.author.id)
        await ctx.send(embed=embed, view=view)

    @commands.hybrid_command(name="remind_list", description="設定中のリマインダー一覧を表示します")
    async def remind_list(self, ctx: commands.Context):
        """リマインダー一覧を表示"""
        reminders = await execute_query(
            '''
            SELECT id, content, remind_at, is_dm, channel_id
            FROM reminders
            WHERE user_id = $1
            ORDER BY remind_at ASC
            LIMIT 25
            ''',
            ctx.author.id,
            fetch_type='all'
        )

        if not reminders:
            await ctx.send(
                "📭 設定中のリマインダーはありません。",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="📋 リマインダー一覧",
            color=discord.Color.blue()
        )

        for reminder in reminders:
            remind_at = reminder['remind_at']
            if remind_at.tzinfo is None:
                remind_at = JST.localize(remind_at)

            content = reminder['content']
            if len(content) > 50:
                content = content[:47] + "..."

            location = "📩 DM" if reminder['is_dm'] else f"<#{reminder['channel_id']}>"

            embed.add_field(
                name=f"#{reminder['id']} - {content}",
                value=f"⏰ <t:{int(remind_at.timestamp())}:R>\n{location}",
                inline=False
            )

        embed.set_footer(text=f"合計 {len(reminders)} 件のリマインダー")
        await ctx.send(embed=embed, ephemeral=True)

    @commands.hybrid_command(name="remind_cancel", description="リマインダーをキャンセルします")
    @app_commands.describe(reminder_id="キャンセルするリマインダーのID")
    async def remind_cancel(self, ctx: commands.Context, reminder_id: int):
        """リマインダーをキャンセル"""
        # 存在確認と所有者チェック
        reminder = await execute_query(
            "SELECT id, user_id FROM reminders WHERE id = $1",
            reminder_id,
            fetch_type='row'
        )

        if not reminder:
            await ctx.send(
                "❌ 指定されたリマインダーが見つかりません。",
                ephemeral=True
            )
            return

        if reminder['user_id'] != ctx.author.id:
            await ctx.send(
                "❌ このリマインダーをキャンセルする権限がありません。",
                ephemeral=True
            )
            return

        await execute_query(
            "DELETE FROM reminders WHERE id = $1",
            reminder_id,
            fetch_type='status'
        )

        await ctx.send(
            f"✅ リマインダー #{reminder_id} をキャンセルしました。",
            ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Reminder(bot))
