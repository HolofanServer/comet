"""
スケジュール投稿システム

指定した日時にメッセージを自動投稿する機能を提供します。
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


def parse_datetime_string(dt_str: str) -> Optional[datetime]:
    """
    日時文字列をdatetimeに変換します。

    対応形式:
    - 2024-12-25 09:00
    - 2024/12/25 09:00
    - 12/25 09:00 (今年)
    - 09:00 (今日)
    - 明日 09:00
    - +30m (30分後)
    - +2h (2時間後)
    - +1d (1日後)

    Args:
        dt_str: 日時を表す文字列

    Returns:
        datetime (JST) または None（パース失敗時）
    """
    dt_str = dt_str.strip()
    now = datetime.now(JST)

    # 相対時間パターン: +30m, +2h, +1d
    relative_pattern = r'^\+(\d+)([smhd])$'
    match = re.match(relative_pattern, dt_str.lower())
    if match:
        value = int(match.group(1))
        unit = match.group(2)
        if unit == 's':
            return now + timedelta(seconds=value)
        elif unit == 'm':
            return now + timedelta(minutes=value)
        elif unit == 'h':
            return now + timedelta(hours=value)
        elif unit == 'd':
            return now + timedelta(days=value)

    # 明日パターン: 明日 09:00
    tomorrow_pattern = r'^明日\s*(\d{1,2}):(\d{2})$'
    match = re.match(tomorrow_pattern, dt_str)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2))
        tomorrow = now + timedelta(days=1)
        return tomorrow.replace(hour=hour, minute=minute, second=0, microsecond=0)

    # 今日の時刻パターン: 09:00
    time_only_pattern = r'^(\d{1,2}):(\d{2})$'
    match = re.match(time_only_pattern, dt_str)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2))
        result = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        # 過去の時刻なら明日に設定
        if result <= now:
            result += timedelta(days=1)
        return result

    # 月/日 時:分 パターン: 12/25 09:00
    md_pattern = r'^(\d{1,2})[/\-](\d{1,2})\s+(\d{1,2}):(\d{2})$'
    match = re.match(md_pattern, dt_str)
    if match:
        month = int(match.group(1))
        day = int(match.group(2))
        hour = int(match.group(3))
        minute = int(match.group(4))
        try:
            result = now.replace(month=month, day=day, hour=hour, minute=minute, second=0, microsecond=0)
            # 過去なら来年に設定
            if result <= now:
                result = result.replace(year=result.year + 1)
            return result
        except ValueError:
            return None

    # 年/月/日 時:分 パターン: 2024-12-25 09:00 または 2024/12/25 09:00
    full_pattern = r'^(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})\s+(\d{1,2}):(\d{2})$'
    match = re.match(full_pattern, dt_str)
    if match:
        year = int(match.group(1))
        month = int(match.group(2))
        day = int(match.group(3))
        hour = int(match.group(4))
        minute = int(match.group(5))
        try:
            return JST.localize(datetime(year, month, day, hour, minute, 0))
        except ValueError:
            return None

    return None


class ScheduledPostView(discord.ui.View):
    """スケジュール投稿管理用のView"""

    def __init__(self, post_id: int, author_id: int):
        super().__init__(timeout=None)
        self.post_id = post_id
        self.author_id = author_id

    @discord.ui.button(label="キャンセル", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def cancel_post(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 権限チェック（作成者または管理者）
        if interaction.user.id != self.author_id:
            if not interaction.user.guild_permissions.manage_messages:
                await interaction.response.send_message(
                    "このスケジュール投稿をキャンセルする権限がありません。",
                    ephemeral=True
                )
                return

        await execute_query(
            "DELETE FROM scheduled_posts WHERE id = $1",
            self.post_id,
            fetch_type='status'
        )

        await interaction.response.send_message(
            "✅ スケジュール投稿をキャンセルしました。",
            ephemeral=True
        )

        # 元のメッセージを更新
        for item in self.children:
            item.disabled = True
        try:
            await interaction.message.edit(
                content="~~スケジュール投稿~~ **キャンセル済み**",
                view=self
            )
        except discord.NotFound:
            pass


class ScheduledPost(commands.Cog):
    """スケジュール投稿機能を提供するCog"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.check_scheduled_posts.start()

    async def cog_load(self):
        """Cogロード時にテーブルを作成"""
        await self._setup_table()

    async def cog_unload(self):
        """Cogアンロード時にタスクを停止"""
        self.check_scheduled_posts.cancel()

    async def _setup_table(self):
        """スケジュール投稿テーブルを作成"""
        await execute_query(
            '''
            CREATE TABLE IF NOT EXISTS scheduled_posts (
                id SERIAL PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                channel_id BIGINT NOT NULL,
                author_id BIGINT NOT NULL,
                content TEXT,
                embed_json JSONB,
                post_at TIMESTAMP WITH TIME ZONE NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                repeat_interval TEXT,
                is_active BOOLEAN DEFAULT TRUE
            )
            ''',
            fetch_type='status'
        )
        # インデックス作成
        await execute_query(
            'CREATE INDEX IF NOT EXISTS idx_scheduled_posts_post_at ON scheduled_posts (post_at) WHERE is_active = TRUE',
            fetch_type='status'
        )
        logger.info("スケジュール投稿テーブルを確認・作成しました")

    @tasks.loop(seconds=30)
    async def check_scheduled_posts(self):
        """期限が来たスケジュール投稿を実行"""
        try:
            now = datetime.now(JST)
            posts = await execute_query(
                '''
                SELECT id, guild_id, channel_id, author_id, content, embed_json, post_at, repeat_interval
                FROM scheduled_posts
                WHERE post_at <= $1 AND is_active = TRUE
                ORDER BY post_at ASC
                LIMIT 20
                ''',
                now,
                fetch_type='all'
            )

            for post in posts:
                await self._execute_post(post)

                if post['repeat_interval']:
                    # リピート設定がある場合は次回の投稿時間を計算
                    next_time = self._calculate_next_time(post['post_at'], post['repeat_interval'])
                    if next_time:
                        await execute_query(
                            "UPDATE scheduled_posts SET post_at = $1 WHERE id = $2",
                            next_time,
                            post['id'],
                            fetch_type='status'
                        )
                    else:
                        await execute_query(
                            "UPDATE scheduled_posts SET is_active = FALSE WHERE id = $1",
                            post['id'],
                            fetch_type='status'
                        )
                else:
                    # 一回限りの投稿は削除
                    await execute_query(
                        "DELETE FROM scheduled_posts WHERE id = $1",
                        post['id'],
                        fetch_type='status'
                    )

        except Exception as e:
            logger.error(f"スケジュール投稿チェック中にエラー: {e}")

    @check_scheduled_posts.before_loop
    async def before_check_scheduled_posts(self):
        """BOT準備完了まで待機"""
        await self.bot.wait_until_ready()

    def _calculate_next_time(self, current_time: datetime, interval: str) -> Optional[datetime]:
        """次回の投稿時間を計算"""
        if current_time.tzinfo is None:
            current_time = JST.localize(current_time)

        if interval == 'daily':
            return current_time + timedelta(days=1)
        elif interval == 'weekly':
            return current_time + timedelta(weeks=1)
        elif interval == 'monthly':
            # 翌月の同日（存在しない場合は月末）
            try:
                if current_time.month == 12:
                    return current_time.replace(year=current_time.year + 1, month=1)
                else:
                    return current_time.replace(month=current_time.month + 1)
            except ValueError:
                # 日が存在しない場合（例: 1/31 → 2/28）
                next_month = current_time.replace(day=1) + timedelta(days=32)
                return next_month.replace(day=1) - timedelta(days=1)
        return None

    async def _execute_post(self, post: dict):
        """スケジュール投稿を実行"""
        try:
            channel = self.bot.get_channel(post['channel_id'])
            if not channel:
                logger.warning(f"チャンネル {post['channel_id']} が見つかりません")
                return

            # Embed作成
            embed = None
            if post['embed_json']:
                try:
                    embed = discord.Embed.from_dict(post['embed_json'])
                except Exception as e:
                    logger.error(f"Embed作成エラー: {e}")

            # メッセージ送信
            if post['content'] or embed:
                await channel.send(
                    content=post['content'],
                    embed=embed
                )
                logger.info(f"スケジュール投稿を実行: #{post['id']} -> {channel.name}")
            else:
                logger.warning(f"スケジュール投稿 #{post['id']} に内容がありません")

        except discord.Forbidden:
            logger.error(f"チャンネル {post['channel_id']} への送信権限がありません")
        except Exception as e:
            logger.error(f"スケジュール投稿実行エラー: {e}")

    @app_commands.command(name="schedule", description="指定した日時にメッセージを投稿します")
    @app_commands.describe(
        datetime_str="投稿日時（例: 2024-12-25 09:00, 12/25 09:00, 明日 09:00, +30m）",
        message="投稿するメッセージ内容",
        channel="投稿先チャンネル（省略時: このチャンネル）",
        repeat="繰り返し設定"
    )
    @app_commands.choices(repeat=[
        app_commands.Choice(name="なし", value="none"),
        app_commands.Choice(name="毎日", value="daily"),
        app_commands.Choice(name="毎週", value="weekly"),
        app_commands.Choice(name="毎月", value="monthly"),
    ])
    @app_commands.default_permissions(manage_messages=True)
    async def schedule(
        self,
        interaction: discord.Interaction,
        datetime_str: str,
        message: str,
        channel: Optional[discord.TextChannel] = None,
        repeat: str = "none"
    ):
        """スケジュール投稿を設定"""
        target_channel = channel or interaction.channel

        # 日時をパース
        post_at = parse_datetime_string(datetime_str)
        if not post_at:
            await interaction.response.send_message(
                "❌ 日時の形式が正しくありません。\n\n"
                "**対応形式:**\n"
                "• `2024-12-25 09:00` - 年月日 時分\n"
                "• `12/25 09:00` - 月日 時分（今年）\n"
                "• `09:00` - 時分（今日または明日）\n"
                "• `明日 09:00` - 明日の指定時刻\n"
                "• `+30m` - 30分後\n"
                "• `+2h` - 2時間後\n"
                "• `+1d` - 1日後",
                ephemeral=True
            )
            return

        # 過去の日時チェック
        now = datetime.now(JST)
        if post_at <= now:
            await interaction.response.send_message(
                "❌ 過去の日時は指定できません。",
                ephemeral=True
            )
            return

        # 権限チェック
        if not target_channel.permissions_for(interaction.guild.me).send_messages:
            await interaction.response.send_message(
                f"❌ {target_channel.mention} への送信権限がありません。",
                ephemeral=True
            )
            return

        # データベースに保存
        repeat_interval = None if repeat == "none" else repeat
        result = await execute_query(
            '''
            INSERT INTO scheduled_posts (guild_id, channel_id, author_id, content, post_at, repeat_interval)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id
            ''',
            interaction.guild.id,
            target_channel.id,
            interaction.user.id,
            message,
            post_at,
            repeat_interval,
            fetch_type='row'
        )

        post_id = result['id']

        # 確認メッセージ
        embed = discord.Embed(
            title="📅 スケジュール投稿を設定しました",
            color=discord.Color.green()
        )
        embed.add_field(
            name="投稿先",
            value=target_channel.mention,
            inline=True
        )
        embed.add_field(
            name="投稿日時",
            value=f"<t:{int(post_at.timestamp())}:F>",
            inline=True
        )
        if repeat_interval:
            repeat_text = {"daily": "毎日", "weekly": "毎週", "monthly": "毎月"}.get(repeat_interval, "なし")
            embed.add_field(
                name="繰り返し",
                value=repeat_text,
                inline=True
            )
        embed.add_field(
            name="内容プレビュー",
            value=message[:500] + ("..." if len(message) > 500 else ""),
            inline=False
        )
        embed.set_footer(text=f"スケジュールID: {post_id}")

        view = ScheduledPostView(post_id, interaction.user.id)
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="schedule_list", description="スケジュール投稿一覧を表示します")
    @app_commands.default_permissions(manage_messages=True)
    async def schedule_list(self, interaction: discord.Interaction):
        """スケジュール投稿一覧を表示"""
        posts = await execute_query(
            '''
            SELECT id, channel_id, content, post_at, repeat_interval
            FROM scheduled_posts
            WHERE guild_id = $1 AND is_active = TRUE
            ORDER BY post_at ASC
            LIMIT 25
            ''',
            interaction.guild.id,
            fetch_type='all'
        )

        if not posts:
            await interaction.response.send_message(
                "📭 スケジュール投稿はありません。",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="📋 スケジュール投稿一覧",
            color=discord.Color.blue()
        )

        for post in posts:
            post_at = post['post_at']
            if post_at.tzinfo is None:
                post_at = JST.localize(post_at)

            content = post['content'] or "(内容なし)"
            if len(content) > 50:
                content = content[:47] + "..."

            repeat_text = ""
            if post['repeat_interval']:
                repeat_map = {'daily': '毎日', 'weekly': '毎週', 'monthly': '毎月'}
                repeat_text = f" 🔁 {repeat_map.get(post['repeat_interval'], '')}"

            embed.add_field(
                name=f"#{post['id']} - {content}",
                value=f"📍 <#{post['channel_id']}>\n⏰ <t:{int(post_at.timestamp())}:R>{repeat_text}",
                inline=False
            )

        embed.set_footer(text=f"合計 {len(posts)} 件")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="schedule_cancel", description="スケジュール投稿をキャンセルします")
    @app_commands.describe(post_id="キャンセルするスケジュール投稿のID")
    @app_commands.default_permissions(manage_messages=True)
    async def schedule_cancel(self, interaction: discord.Interaction, post_id: int):
        """スケジュール投稿をキャンセル"""
        # 存在確認
        post = await execute_query(
            "SELECT id, guild_id FROM scheduled_posts WHERE id = $1 AND is_active = TRUE",
            post_id,
            fetch_type='row'
        )

        if not post:
            await interaction.response.send_message(
                "❌ 指定されたスケジュール投稿が見つかりません。",
                ephemeral=True
            )
            return

        if post['guild_id'] != interaction.guild.id:
            await interaction.response.send_message(
                "❌ このサーバーのスケジュール投稿ではありません。",
                ephemeral=True
            )
            return

        await execute_query(
            "DELETE FROM scheduled_posts WHERE id = $1",
            post_id,
            fetch_type='status'
        )

        await interaction.response.send_message(
            f"✅ スケジュール投稿 #{post_id} をキャンセルしました。",
            ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(ScheduledPost(bot))
