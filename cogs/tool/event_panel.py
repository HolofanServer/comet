"""メンバー向けイベントパネルと、予約VCの名前の一時変更。"""

import asyncio
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks

from utils.database import execute_query
from utils.logging import logger

JST = timezone(timedelta(hours=9))
VC_NAME = re.compile(r"VC(?:10|[1-9])", re.IGNORECASE)
PANEL_CHANNEL_NAME = "イベント作成"
MAX_RESERVATIONS = 3


def parse_start(value: str, now: datetime) -> datetime:
    """日本時間の日時、今日/明日 HH:MM、HH:MMを受け付ける。"""
    value = value.strip().replace("/", "-")
    local_now = now.astimezone(JST)
    try:
        if re.fullmatch(r"\d{4}-\d{1,2}-\d{1,2}\s+\d{1,2}:\d{2}", value):
            result = datetime.strptime(value, "%Y-%m-%d %H:%M").replace(tzinfo=JST)
        else:
            match = re.fullmatch(r"(?:(今日|明日)\s*)?(\d{1,2}:\d{2})", value)
            if not match:
                raise ValueError
            clock = datetime.strptime(match[2], "%H:%M")
            result = local_now.replace(
                hour=clock.hour, minute=clock.minute, second=0, microsecond=0
            )
            if match[1] == "明日":
                result += timedelta(days=1)
    except ValueError as exc:
        raise ValueError(
            "開始日時は「明日 21:00」「21:00」「2026/10/10 21:00」などで入力してください（日本時間）。"
        ) from exc
    if result <= now:
        raise ValueError("開始日時は未来の時刻を指定してください（日本時間）。")
    return result


def overlaps(event, channel_id, start, end):
    return (
        event.channel_id == channel_id
        and event.status in (discord.EventStatus.scheduled, discord.EventStatus.active)
        and event.start_time < end
        and (event.end_time is None or start < event.end_time)
    )


async def report_error(interaction, error):
    if isinstance(error, ValueError):
        message = str(error)
    elif isinstance(error, discord.Forbidden):
        message = "Botの権限が足りません。管理者にイベント作成・チャンネル管理・VC閲覧/接続権限の確認を依頼してください。"
    else:
        logger.error("イベントパネルの操作に失敗", exc_info=error)
        message = "処理に失敗しました。時間をおいてもう一度お試しください。"
    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)


class EventStore:
    """日時とイベント名はDiscordを正とし、主催者と復元情報だけ保存する。"""

    async def setup(self):
        await execute_query(
            """CREATE TABLE IF NOT EXISTS member_vc_events (
                event_id BIGINT PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                channel_id BIGINT NOT NULL,
                owner_id BIGINT NOT NULL,
                original_name TEXT NOT NULL,
                renamed_to TEXT
            )""",
            fetch_type="status",
        )
        await execute_query(
            """CREATE TABLE IF NOT EXISTS member_event_panels (
                guild_id BIGINT PRIMARY KEY,
                channel_id BIGINT NOT NULL,
                message_id BIGINT NOT NULL
            )""",
            fetch_type="status",
        )

    async def rows(self, guild_id=None):
        if guild_id is None:
            return await execute_query("SELECT * FROM member_vc_events")
        return await execute_query(
            "SELECT * FROM member_vc_events WHERE guild_id = $1", guild_id
        )

    async def add(self, event, owner_id, original_name):
        await execute_query(
            """INSERT INTO member_vc_events
               (event_id, guild_id, channel_id, owner_id, original_name)
               VALUES ($1, $2, $3, $4, $5)""",
            event.id,
            event.guild_id,
            event.channel_id,
            owner_id,
            original_name,
            fetch_type="status",
        )

    async def rename_intent(self, event_id, name):
        await execute_query(
            "UPDATE member_vc_events SET renamed_to = $2 WHERE event_id = $1",
            event_id,
            name,
            fetch_type="status",
        )

    async def remove(self, event_id):
        await execute_query(
            "DELETE FROM member_vc_events WHERE event_id = $1",
            event_id,
            fetch_type="status",
        )

    async def panel(self, guild_id):
        return await execute_query(
            "SELECT * FROM member_event_panels WHERE guild_id = $1",
            guild_id,
            fetch_type="row",
        )

    async def save_panel(self, guild_id, message):
        await execute_query(
            """INSERT INTO member_event_panels (guild_id, channel_id, message_id)
               VALUES ($1, $2, $3) ON CONFLICT (guild_id) DO UPDATE
               SET channel_id = EXCLUDED.channel_id, message_id = EXCLUDED.message_id""",
            guild_id,
            message.channel.id,
            message.id,
            fetch_type="status",
        )


class PanelView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    async def on_error(self, interaction, error, item):
        await report_error(interaction, error)

    @discord.ui.button(
        label="イベント作成",
        style=discord.ButtonStyle.primary,
        emoji="📅",
        custom_id="member_events:create:v1",
    )
    async def create(self, interaction, button):
        await interaction.response.defer(ephemeral=True, thinking=True)
        channels = await self.cog.available_channels(interaction)
        if not channels:
            raise ValueError(
                "利用できるVC1〜VC10がありません。管理者に確認してください。"
            )
        await interaction.followup.send(
            "開催するVCを選んでください。",
            view=ChannelView(self.cog, interaction.user.id, channels),
            ephemeral=True,
        )

    @discord.ui.button(
        label="自分のイベントを終了・取消",
        style=discord.ButtonStyle.secondary,
        custom_id="member_events:manage:v1",
    )
    async def manage(self, interaction, button):
        await interaction.response.defer(ephemeral=True, thinking=True)
        events = await self.cog.owned_events(interaction)
        if not events:
            raise ValueError("開催予定・開催中の自分のイベントはありません。")
        await interaction.followup.send(
            "終了・取り消しするイベントを選んでください。次の画面で確認できます。",
            view=ManageView(self.cog, interaction.user.id, events),
            ephemeral=True,
        )


class PrivateView(discord.ui.View):
    def __init__(self, cog, owner_id):
        super().__init__(timeout=300)
        self.cog = cog
        self.owner_id = owner_id

    async def interaction_check(self, interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "この操作はパネルを開いた本人だけが使えます。", ephemeral=True
            )
            return False
        return True

    async def on_error(self, interaction, error, item):
        await report_error(interaction, error)


class ChannelView(PrivateView):
    def __init__(self, cog, owner_id, channels):
        super().__init__(cog, owner_id)
        select = discord.ui.Select(
            placeholder="VC1〜VC10から選択",
            options=[
                discord.SelectOption(
                    label=name,
                    value=str(channel.id),
                    description=f"{channel.category.name if channel.category else 'カテゴリーなし'} / {channel.name}"[
                        :100
                    ],
                )
                for channel, name in channels[:25]
            ],
        )

        async def callback(interaction):
            await interaction.response.send_modal(
                EventModal(cog, owner_id, int(select.values[0]))
            )
            self.stop()

        select.callback = callback
        self.add_item(select)


class EventModal(discord.ui.Modal, title="イベントを作成"):
    event_name = discord.ui.TextInput(label="イベント名", min_length=1, max_length=100)
    start = discord.ui.TextInput(
        label="開始日時（日本時間）", placeholder="明日 21:00 / 2026/10/10 21:00"
    )
    duration = discord.ui.TextInput(
        label="開催時間（分・5〜720）", default="60", max_length=3
    )
    description = discord.ui.TextInput(
        label="説明（任意）",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=1000,
    )

    def __init__(self, cog, owner_id, channel_id):
        super().__init__(timeout=600)
        self.cog = cog
        self.owner_id = owner_id
        self.channel_id = channel_id

    async def on_submit(self, interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        if interaction.user.id != self.owner_id:
            raise ValueError("このフォームは開いた本人だけが送信できます。")
        event = await self.cog.create_event(
            interaction,
            self.channel_id,
            str(self.event_name),
            str(self.start),
            str(self.duration),
            str(self.description),
        )
        await interaction.followup.send(
            f"イベントを作成しました！\n{event.url}\n"
            f"開始: {discord.utils.format_dt(event.start_time, 'F')}\n"
            "開始時にVC名をイベント名へ変更し、終了後に元へ戻します。",
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    async def on_error(self, interaction, error):
        await report_error(interaction, error)


class ManageView(PrivateView):
    def __init__(self, cog, owner_id, events):
        super().__init__(cog, owner_id)
        select = discord.ui.Select(
            placeholder="終了・取り消しするイベント",
            options=[
                discord.SelectOption(
                    label=event.name,
                    value=str(event.id),
                    description=event.start_time.astimezone(JST).strftime(
                        "%Y/%m/%d %H:%M（日本時間）"
                    ),
                )
                for event in events[:25]
            ],
        )

        async def callback(interaction):
            event_id = int(select.values[0])
            name = next(event.name for event in events if event.id == event_id)
            await interaction.response.edit_message(
                content=f"「{discord.utils.escape_markdown(name)}」を終了・取り消ししますか？",
                view=ConfirmEndView(cog, owner_id, event_id),
                allowed_mentions=discord.AllowedMentions.none(),
            )
            self.stop()

        select.callback = callback
        self.add_item(select)


class ConfirmEndView(PrivateView):
    def __init__(self, cog, owner_id, event_id):
        super().__init__(cog, owner_id)
        self.event_id = event_id

    @discord.ui.button(label="終了・取り消しを確定", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction, button):
        await interaction.response.defer(ephemeral=True)
        await self.cog.finish_event(interaction, self.event_id)
        await interaction.edit_original_response(
            content="イベントを終了・取り消ししました。", view=None
        )
        self.stop()


class EventPanel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.store = EventStore()
        # AutoShardedBotは単一プロセス。同一サーバーの予約と復元を直列化する。
        self.locks = defaultdict(asyncio.Lock)
        self.panel_views = []

    def new_panel_view(self):
        view = PanelView(self)
        self.panel_views.append(view)
        return view

    async def cog_load(self):
        await self.store.setup()
        self.bot.add_view(self.new_panel_view())
        self.check_events.start()

    async def cog_unload(self):
        self.check_events.cancel()
        for view in self.panel_views:
            view.stop()

    async def available_channels(self, interaction):
        guild = interaction.guild
        if guild is None or not isinstance(interaction.user, discord.Member):
            raise ValueError("サーバー内で操作してください。")
        originals = {
            row["channel_id"]: row["original_name"]
            for row in await self.store.rows(guild.id)
        }
        result = []
        # 名前変更中もIDと保存済みの元の名前でVCを特定する。
        for channel in await guild.fetch_channels():
            if not isinstance(channel, discord.VoiceChannel):
                continue
            name = originals.get(channel.id, channel.name)
            perms = channel.permissions_for(interaction.user)
            if VC_NAME.fullmatch(name) and perms.view_channel and perms.connect:
                result.append((channel, name))
        return sorted(result, key=lambda pair: (int(pair[1][2:]), pair[0].id))

    async def create_event(self, interaction, channel_id, name, start, duration, desc):
        name = name.strip()
        if not 1 <= len(name) <= 100:
            raise ValueError("イベント名を1〜100文字で入力してください。")
        try:
            minutes = int(duration)
        except ValueError as exc:
            raise ValueError("開催時間は5〜720分の整数で入力してください。") from exc
        if not 5 <= minutes <= 720:
            raise ValueError("開催時間は5〜720分の整数で入力してください。")
        start_at = parse_start(start, discord.utils.utcnow())
        end_at = start_at + timedelta(minutes=minutes)
        guild = interaction.guild
        if guild is None:
            raise ValueError("サーバー内で操作してください。")
        async with self.locks[guild.id]:
            channels = {
                channel.id: (channel, original)
                for channel, original in await self.available_channels(interaction)
            }
            if channel_id not in channels:
                raise ValueError(
                    "選択したVCを利用できません。パネルから選び直してください。"
                )
            channel, original = channels[channel_id]
            perms = channel.permissions_for(guild.me)
            if not (
                perms.view_channel
                and perms.connect
                and perms.manage_channels
                and perms.create_events
            ):
                raise ValueError(
                    "Botに、選択したVCの閲覧・接続・チャンネル管理・イベント作成権限が必要です。"
                )
            rows = await self.store.rows(guild.id)
            if (
                sum(row["owner_id"] == interaction.user.id for row in rows)
                >= MAX_RESERVATIONS
            ):
                raise ValueError(
                    "同時に予約できるイベントは3件までです。不要な予約を取り消してください。"
                )
            events = await guild.fetch_scheduled_events()
            if any(overlaps(event, channel_id, start_at, end_at) for event in events):
                raise ValueError(
                    "その時間帯のVCは予約済みです。別のVCか時間を選んでください。"
                )
            event = await guild.create_scheduled_event(
                name=name,
                start_time=start_at,
                end_time=end_at,
                channel=channel,
                entity_type=discord.EntityType.voice,
                privacy_level=discord.PrivacyLevel.guild_only,
                description=desc.strip() or None,
                reason=f"メンバーイベント作成: {interaction.user.id}",
            )
            try:
                await self.store.add(event, interaction.user.id, original)
            except Exception:
                # DB保存に失敗したイベントは自動管理できないため取り消す。
                try:
                    await event.delete(reason="イベント管理情報の保存失敗")
                except discord.HTTPException:
                    logger.exception("未保存イベントの削除に失敗: %s", event.id)
                    raise ValueError(
                        f"管理情報を保存できず、イベントの削除にも失敗しました。管理者に削除を依頼してください: {event.url}"
                    ) from None
                raise
            return event

    async def owned_events(self, interaction):
        if interaction.guild is None:
            raise ValueError("サーバー内で操作してください。")
        ids = {
            row["event_id"]
            for row in await self.store.rows(interaction.guild.id)
            if row["owner_id"] == interaction.user.id
        }
        return [
            event
            for event in await interaction.guild.fetch_scheduled_events()
            if event.id in ids
            and event.status
            in (discord.EventStatus.scheduled, discord.EventStatus.active)
        ]

    async def finish_event(self, interaction, event_id):
        guild = interaction.guild
        if guild is None:
            raise ValueError("サーバー内で操作してください。")
        async with self.locks[guild.id]:
            row = next(
                (
                    r
                    for r in await self.store.rows(guild.id)
                    if r["event_id"] == event_id
                ),
                None,
            )
            if row is None:
                raise ValueError("このイベントは既に終了・取り消し済みです。")
            if row["owner_id"] != interaction.user.id:
                raise ValueError("自分が作成したイベントだけ終了・取り消しできます。")
            try:
                event = await guild.fetch_scheduled_event(event_id)
            except discord.NotFound:
                event = None
            if event and event.status == discord.EventStatus.scheduled:
                await event.cancel(reason=f"主催者による取消: {interaction.user.id}")
            elif event and event.status == discord.EventStatus.active:
                await event.end(reason=f"主催者による終了: {interaction.user.id}")
            await self.restore(guild, row)

    async def restore(self, guild, row):
        if row["renamed_to"]:
            try:
                channel = await guild.fetch_channel(row["channel_id"])
            except discord.NotFound:
                channel = None
            if channel and channel.name == row["renamed_to"]:
                await channel.edit(
                    name=row["original_name"], reason="イベント終了によるVC名の復元"
                )
        # 手動変更された名前は上書きしない。HTTP失敗時は行を残し次回再試行。
        await self.store.remove(row["event_id"])

    async def sync_guild(self, guild):
        async with self.locks[guild.id]:
            rows = await self.store.rows(guild.id)
            if not rows:
                return
            events = {event.id: event for event in await guild.fetch_scheduled_events()}
            now = discord.utils.utcnow()
            # 復元を先に済ませ、連続する予約が前のイベント名を引き継がないようにする。
            for row in rows:
                event = events.get(row["event_id"])
                try:
                    if event and event.channel_id == row["channel_id"]:
                        if event.status in (
                            discord.EventStatus.scheduled,
                            discord.EventStatus.active,
                        ):
                            if event.end_time is None or event.end_time > now:
                                continue
                            if event.status == discord.EventStatus.active:
                                await event.end(reason="イベントの予定終了時刻")
                            else:
                                await event.cancel(
                                    reason="終了時刻を過ぎた未開始イベント"
                                )
                            events.pop(event.id, None)
                    await self.restore(guild, row)
                except Exception:
                    logger.exception("イベント復元に失敗: %s", row["event_id"])

            rows = await self.store.rows(guild.id)
            for row in rows:
                event = events.get(row["event_id"])
                if (
                    event is None
                    or event.channel_id != row["channel_id"]
                    or event.status
                    not in (discord.EventStatus.scheduled, discord.EventStatus.active)
                    or (event.end_time is not None and event.end_time <= now)
                ):
                    continue
                try:
                    if (
                        event.status == discord.EventStatus.scheduled
                        and event.start_time > now
                    ):
                        continue
                    # 手動開始/日時変更による競合も、他イベントのVC名を上書きさせない。
                    if any(
                        other["event_id"] != event.id
                        and other["channel_id"] == row["channel_id"]
                        and other["renamed_to"]
                        for other in rows
                    ) or any(
                        other.id != event.id
                        and other.channel_id == row["channel_id"]
                        and other.status == discord.EventStatus.active
                        for other in events.values()
                    ):
                        continue
                    if event.status == discord.EventStatus.scheduled:
                        event = await event.start(reason="イベントの予定開始時刻")
                        events[event.id] = event
                    channel = await guild.fetch_channel(row["channel_id"])
                    target = row["renamed_to"] or event.name
                    if channel.name == row["original_name"] and channel.name != target:
                        # API更新前に復元情報を永続化。途中再起動・通信失敗でも復元可能。
                        await self.store.rename_intent(event.id, target)
                        await channel.edit(
                            name=target, reason="イベント開始によるVC名の変更"
                        )
                except Exception:
                    logger.exception(
                        "イベント開始・VC名変更に失敗: %s", row["event_id"]
                    )

    @tasks.loop(seconds=30)
    async def check_events(self):
        try:
            guild_ids = {row["guild_id"] for row in await self.store.rows()}
            for guild_id in guild_ids:
                guild = self.bot.get_guild(guild_id)
                if guild is None or guild.unavailable:
                    continue
                try:
                    await self.sync_guild(guild)
                except Exception:
                    logger.exception("イベント同期に失敗: guild=%s", guild_id)
        except Exception:
            logger.exception("イベント管理情報の取得に失敗")

    @check_events.before_loop
    async def before_check_events(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_scheduled_event_update(self, before, after):
        await self.refresh_event(after)

    @commands.Cog.listener()
    async def on_scheduled_event_delete(self, event):
        await self.refresh_event(event)

    async def refresh_event(self, event):
        guild = self.bot.get_guild(event.guild_id)
        if guild is None:
            return
        try:
            if any(r["event_id"] == event.id for r in await self.store.rows(guild.id)):
                await self.sync_guild(guild)
        except Exception:
            logger.exception("イベント変更の反映に失敗: %s", event.id)

    @app_commands.command(
        name="イベントパネル", description="イベント作成パネルを設置します（管理者用）"
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        channel="設置先。省略すると専用の「イベント作成」チャンネルを作成します"
    )
    async def install_panel(
        self,
        interaction: discord.Interaction,
        channel: Optional[discord.TextChannel] = None,
    ):
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            async with self.locks[interaction.guild_id]:
                message = await self.place_panel(interaction.guild, channel)
            await interaction.followup.send(
                f"イベントパネルを設置しました: {message.jump_url}", ephemeral=True
            )
        except Exception as exc:
            await report_error(interaction, exc)

    async def place_panel(self, guild, channel=None):
        previous = await self.store.panel(guild.id)
        if channel is None and previous:
            try:
                channel = await guild.fetch_channel(previous["channel_id"])
            except discord.NotFound:
                pass
        if channel is None:
            channel = await guild.create_text_channel(
                PANEL_CHANNEL_NAME,
                topic="ボタンからイベントを作成できます。日時は日本時間で入力してください。",
                overwrites={
                    guild.default_role: discord.PermissionOverwrite(
                        view_channel=True,
                        send_messages=False,
                        read_message_history=True,
                    ),
                    guild.me: discord.PermissionOverwrite(
                        view_channel=True,
                        send_messages=True,
                        embed_links=True,
                        read_message_history=True,
                    ),
                },
                reason="メンバー向けイベント作成パネルの設置",
            )
        if not isinstance(channel, discord.TextChannel) or channel.guild.id != guild.id:
            raise ValueError("同じサーバーのテキストチャンネルを指定してください。")
        embed = discord.Embed(
            title="みんなのイベント",
            description=(
                "ゲーム、雑談、同時視聴など、気軽に企画してみよう！\n\n"
                "**作り方**\n"
                "1. 「イベント作成」を押す\n"
                "2. VC1〜VC10から会場を選ぶ\n"
                "3. イベント名・開始日時・開催時間を入力\n\n"
                "日時は**日本時間**です。説明は省略できます。\n"
                "開始時にVC名がイベント名になり、終了後に元へ戻ります。\n"
                "早めに終了・予約を取り消すときは、下の管理ボタンを使ってください。"
            ),
            color=discord.Color.blurple(),
        )
        if previous and previous["channel_id"] == channel.id:
            try:
                message = await channel.fetch_message(previous["message_id"])
                return await message.edit(embed=embed, view=self.new_panel_view())
            except discord.NotFound:
                pass
        message = await channel.send(embed=embed, view=self.new_panel_view())
        await self.store.save_panel(guild.id, message)
        return message


async def setup(bot):
    await bot.add_cog(EventPanel(bot))
