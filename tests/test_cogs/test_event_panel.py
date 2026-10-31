"""実際のDiscord UI/Cogを使い、通信とDBだけを置き換えたイベント管理テスト。"""

import asyncio
import importlib
import sys
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

NOW = datetime(2030, 10, 10, 10, tzinfo=timezone.utc)


@pytest.fixture
def module():
    # 共通conftestのDiscord全体mockをfixture内だけ解除し、実UIと登録を検証。
    with patch.dict(sys.modules):
        for name in list(sys.modules):
            if name == "discord" or name.startswith("discord."):
                del sys.modules[name]
        sys.modules.pop("cogs.tool.event_panel", None)
        loaded = importlib.import_module("cogs.tool.event_panel")
        with patch.object(loaded.discord.utils, "utcnow", return_value=NOW):
            yield loaded


class MemoryStore:
    def __init__(self):
        self.records = {}
        self.panels = {}

    async def rows(self, guild_id=None):
        return [
            dict(row)
            for row in self.records.values()
            if guild_id is None or row["guild_id"] == guild_id
        ]

    async def add(self, event, owner_id, original_name):
        self.records[event.id] = {
            "event_id": event.id,
            "guild_id": event.guild_id,
            "channel_id": event.channel_id,
            "owner_id": owner_id,
            "original_name": original_name,
            "renamed_to": None,
        }

    async def rename_intent(self, event_id, name):
        self.records[event_id]["renamed_to"] = name

    async def remove(self, event_id):
        del self.records[event_id]

    async def panel(self, guild_id):
        return self.panels.get(guild_id)

    async def save_panel(self, guild_id, message):
        self.panels[guild_id] = {
            "channel_id": message.channel.id,
            "message_id": message.id,
        }


def http_error(module, kind="Forbidden"):
    status = 404 if kind == "NotFound" else 403
    return getattr(module.discord, kind)(
        SimpleNamespace(status=status, reason="test error"), "test error"
    )


@pytest.fixture
def env(module):
    d = module.discord
    guild = MagicMock(spec=d.Guild)
    guild.id = 100
    guild.unavailable = False
    guild.me = MagicMock(spec=d.Member)
    guild.me.id = 999
    member = MagicMock(spec=d.Member)
    member.id = 10
    member.guild = guild
    channels = {}
    events = {}
    perms = d.Permissions.all()
    bot_perms = d.Permissions.all()

    def add_channel(channel_id=1, name="VC1", visible=True):
        channel = MagicMock(spec=d.VoiceChannel)
        channel.id, channel.name, channel.guild = channel_id, name, guild
        channel.category = None

        def permissions_for(user):
            if user.id == guild.me.id:
                return bot_perms
            return perms if visible else d.Permissions.none()

        async def edit(**kwargs):
            channel.name = kwargs["name"]
            return channel

        channel.permissions_for.side_effect = permissions_for
        channel.edit = AsyncMock(side_effect=edit)
        channels[channel_id] = channel
        return channel

    def add_event(
        event_id=None,
        channel_id=1,
        name="ゲーム会",
        start_time=NOW + timedelta(hours=1),
        end_time=NOW + timedelta(hours=2),
        status=None,
    ):
        event_id = event_id or len(events) + 1000
        event = SimpleNamespace(
            id=event_id,
            guild_id=guild.id,
            channel_id=channel_id,
            name=name,
            start_time=start_time,
            end_time=end_time,
            status=status or d.EventStatus.scheduled,
            url=f"https://discord.com/events/{guild.id}/{event_id}",
        )

        async def set_status(status):
            event.status = status
            return event

        async def delete(**kwargs):
            events.pop(event.id, None)

        async def start(**kwargs):
            return await set_status(d.EventStatus.active)

        async def end(**kwargs):
            return await set_status(d.EventStatus.completed)

        async def cancel(**kwargs):
            return await set_status(d.EventStatus.cancelled)

        event.start = AsyncMock(side_effect=start)
        event.end = AsyncMock(side_effect=end)
        event.cancel = AsyncMock(side_effect=cancel)
        event.delete = AsyncMock(side_effect=delete)
        events[event.id] = event
        return event

    async def fetch_channels():
        return list(channels.values())

    async def fetch_channel(channel_id):
        if channel_id not in channels:
            raise http_error(module, "NotFound")
        return channels[channel_id]

    async def fetch_events():
        return [
            e
            for e in events.values()
            if e.status in (d.EventStatus.scheduled, d.EventStatus.active)
        ]

    async def fetch_event(event_id):
        if event_id not in events:
            raise http_error(module, "NotFound")
        return events[event_id]

    async def create(**kwargs):
        return add_event(
            channel_id=kwargs["channel"].id,
            name=kwargs["name"],
            start_time=kwargs["start_time"],
            end_time=kwargs["end_time"],
        )

    guild.fetch_channels = AsyncMock(side_effect=fetch_channels)
    guild.fetch_channel = AsyncMock(side_effect=fetch_channel)
    guild.fetch_scheduled_events = AsyncMock(side_effect=fetch_events)
    guild.fetch_scheduled_event = AsyncMock(side_effect=fetch_event)
    guild.create_scheduled_event = AsyncMock(side_effect=create)
    bot = MagicMock()
    bot.get_guild.return_value = guild
    cog = module.EventPanel(bot)
    cog.store = MemoryStore()
    interaction = SimpleNamespace(
        guild=guild,
        guild_id=guild.id,
        user=member,
        response=SimpleNamespace(
            defer=AsyncMock(),
            send_message=AsyncMock(),
            send_modal=AsyncMock(),
            edit_message=AsyncMock(),
            is_done=lambda: True,
        ),
        followup=SimpleNamespace(send=AsyncMock()),
        edit_original_response=AsyncMock(),
    )
    return SimpleNamespace(
        cog=cog,
        guild=guild,
        bot=bot,
        member=member,
        interaction=interaction,
        channel=add_channel(),
        channels=channels,
        events=events,
        add_channel=add_channel,
        add_event=add_event,
        perms=perms,
        bot_perms=bot_perms,
    )


async def reserve(env, **kwargs):
    fields = {
        "channel_id": 1,
        "name": "ゲーム会",
        "start": "2030/10/10 20:00",
        "duration": "60",
        "desc": "みんなで遊ぼう",
    }
    fields.update(kwargs)
    return await env.cog.create_event(env.interaction, **fields)


async def track(env, **kwargs):
    event = env.add_event(**kwargs)
    await env.cog.store.add(event, env.member.id, "VC1")
    return event


@pytest.mark.asyncio
async def test_creates_native_voice_event_without_member_management_rights(module, env):
    env.perms.manage_events = False
    env.perms.create_events = False
    env.perms.manage_channels = False
    event = await reserve(env)
    kwargs = env.guild.create_scheduled_event.call_args.kwargs
    assert kwargs["entity_type"] == module.discord.EntityType.voice
    assert kwargs["privacy_level"] == module.discord.PrivacyLevel.guild_only
    assert kwargs["start_time"].hour == 20
    assert kwargs["start_time"].utcoffset() == timedelta(hours=9)
    assert kwargs["end_time"] - kwargs["start_time"] == timedelta(hours=1)
    assert env.cog.store.records[event.id]["original_name"] == "VC1"
    env.channel.edit.assert_not_awaited()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"name": "  "},
        {"name": "x" * 101},
        {"start": "昨日 20:00"},
        {"start": "2030/02/30 20:00"},
        {"start": "明日 25:00"},
        {"start": "19:00"},
        {"duration": "4"},
        {"duration": "721"},
        {"duration": "1.5"},
        {"channel_id": 12345},
    ],
)
@pytest.mark.asyncio
async def test_invalid_form_has_no_discord_side_effect(env, kwargs):
    with pytest.raises(ValueError):
        await reserve(env, **kwargs)
    env.guild.create_scheduled_event.assert_not_awaited()


@pytest.mark.asyncio
async def test_tomorrow_crosses_year_boundary_and_uses_jst(module):
    now = datetime(2030, 12, 31, 14, tzinfo=timezone.utc)
    assert module.parse_start("明日 00:30", now) == datetime(
        2031, 1, 1, 0, 30, tzinfo=module.JST
    )


@pytest.mark.asyncio
async def test_channel_options_filter_sort_and_keep_renamed_identity(env):
    env.add_channel(10, "VC10")
    env.add_channel(2, "VC2")
    env.add_channel(11, "VC11")
    env.add_channel(3, "VC3", visible=False)
    env.add_channel(4, "スタッフVC")
    await track(env)
    env.channel.name = "開催中のゲーム会"
    channels = await env.cog.available_channels(env.interaction)
    assert [(c.id, name) for c, name in channels] == [
        (1, "VC1"),
        (2, "VC2"),
        (10, "VC10"),
    ]


@pytest.mark.asyncio
async def test_rechecks_member_and_bot_permissions_on_submit(env):
    env.perms.connect = False
    with pytest.raises(ValueError, match="利用できません"):
        await reserve(env)
    env.perms.connect = True
    env.bot_perms.manage_channels = False
    with pytest.raises(ValueError, match="Botに"):
        await reserve(env)
    env.guild.create_scheduled_event.assert_not_awaited()


@pytest.mark.asyncio
async def test_overlapping_submissions_are_serialized(env):
    results = await asyncio.gather(reserve(env), reserve(env), return_exceptions=True)
    assert sum(isinstance(r, ValueError) for r in results) == 1
    assert len(env.events) == 1
    assert len(env.cog.store.records) == 1


@pytest.mark.asyncio
async def test_respects_external_reservations_and_allows_adjacent_slot(env):
    env.add_event()
    with pytest.raises(ValueError, match="予約済み"):
        await reserve(env)
    event = await reserve(env, start="2030/10/10 21:00")
    assert event.start_time == NOW + timedelta(hours=2)


@pytest.mark.asyncio
async def test_event_without_end_time_blocks_later_reservations(env):
    env.add_event(end_time=None)
    with pytest.raises(ValueError, match="予約済み"):
        await reserve(env, start="明日 20:00")


@pytest.mark.asyncio
async def test_member_reservation_limit(env):
    for hour in (20, 21, 22):
        await reserve(env, start=f"2030/10/10 {hour}:00")
    with pytest.raises(ValueError, match="3件"):
        await reserve(env, start="2030/10/10 23:00")


@pytest.mark.asyncio
async def test_database_failure_removes_unmanaged_discord_event(env):
    env.cog.store.add = AsyncMock(side_effect=RuntimeError("DB unavailable"))
    with pytest.raises(RuntimeError):
        await reserve(env)
    assert not env.events


@pytest.mark.asyncio
async def test_starts_due_event_and_restores_after_restart(module, env):
    event = await track(env, start_time=NOW - timedelta(minutes=1))
    await env.cog.sync_guild(env.guild)
    event.start.assert_awaited_once()
    assert env.channel.name == "ゲーム会"
    assert env.cog.store.records[event.id]["renamed_to"] == "ゲーム会"
    await env.cog.sync_guild(env.guild)
    env.channel.edit.assert_awaited_once()

    restarted = module.EventPanel(env.bot)
    restarted.store = env.cog.store
    event.end_time = NOW
    await restarted.sync_guild(env.guild)
    event.end.assert_awaited_once()
    assert env.channel.name == "VC1"
    assert not restarted.store.records


@pytest.mark.asyncio
async def test_future_event_does_not_rename_but_manual_start_does(module, env):
    event = await track(env)
    await env.cog.sync_guild(env.guild)
    env.channel.edit.assert_not_awaited()
    event.status = module.discord.EventStatus.active
    await env.cog.on_scheduled_event_update(event, event)
    assert env.channel.name == event.name


@pytest.mark.asyncio
async def test_expired_unstarted_event_is_cancelled_without_rename(env):
    event = await track(env, start_time=NOW - timedelta(hours=2), end_time=NOW)
    await env.cog.sync_guild(env.guild)
    event.cancel.assert_awaited_once()
    event.start.assert_not_awaited()
    env.channel.edit.assert_not_awaited()
    assert not env.cog.store.records


@pytest.mark.asyncio
async def test_rename_failure_keeps_restore_information_and_retries(module, env):
    event = await track(env, start_time=NOW)
    edit = env.channel.edit.side_effect
    env.channel.edit.side_effect = http_error(module)
    await env.cog.sync_guild(env.guild)
    assert env.cog.store.records[event.id]["renamed_to"] == event.name
    assert env.channel.name == "VC1"
    env.channel.edit.side_effect = edit
    await env.cog.sync_guild(env.guild)
    assert env.channel.name == event.name


@pytest.mark.asyncio
async def test_restore_failure_blocks_next_event_then_recovers(module, env):
    first = await track(env, start_time=NOW - timedelta(hours=1))
    await env.cog.sync_guild(env.guild)
    first.end_time = NOW
    second = await track(env, name="次の会", start_time=NOW)
    edit = env.channel.edit.side_effect
    env.channel.edit.side_effect = http_error(module)
    await env.cog.sync_guild(env.guild)
    second.start.assert_not_awaited()
    assert first.id in env.cog.store.records
    env.channel.edit.side_effect = edit
    await env.cog.sync_guild(env.guild)
    assert first.id not in env.cog.store.records
    assert env.channel.name == "次の会"


@pytest.mark.asyncio
async def test_manual_channel_rename_is_preserved_on_finish(env):
    event = await track(env, start_time=NOW)
    await env.cog.sync_guild(env.guild)
    env.channel.name = "管理者による変更"
    event.end_time = NOW
    await env.cog.sync_guild(env.guild)
    assert env.channel.name == "管理者による変更"
    assert not env.cog.store.records


@pytest.mark.asyncio
async def test_deleted_event_restores_channel(env):
    event = await track(env, start_time=NOW)
    await env.cog.sync_guild(env.guild)
    del env.events[event.id]
    await env.cog.on_scheduled_event_delete(event)
    assert env.channel.name == "VC1"
    assert not env.cog.store.records


@pytest.mark.asyncio
async def test_deleted_channel_cleans_up_terminal_event(module, env):
    event = await track(env, start_time=NOW)
    await env.cog.sync_guild(env.guild)
    del env.channels[1]
    event.status = module.discord.EventStatus.completed
    await env.cog.sync_guild(env.guild)
    assert not env.cog.store.records


@pytest.mark.asyncio
async def test_untracked_events_are_never_started_or_renamed(env):
    event = env.add_event(start_time=NOW)
    await env.cog.sync_guild(env.guild)
    event.start.assert_not_awaited()
    env.channel.edit.assert_not_awaited()


@pytest.mark.asyncio
async def test_moved_event_restores_original_without_touching_new_channel(env):
    event = await track(env, start_time=NOW)
    await env.cog.sync_guild(env.guild)
    other = env.add_channel(2, "VC2")
    event.channel_id = 2
    await env.cog.sync_guild(env.guild)
    assert env.channel.name == "VC1"
    other.edit.assert_not_awaited()
    assert not env.cog.store.records


@pytest.mark.asyncio
async def test_other_active_event_prevents_start_and_rename(module, env):
    env.add_event(status=module.discord.EventStatus.active)
    event = await track(env, start_time=NOW)
    await env.cog.sync_guild(env.guild)
    event.start.assert_not_awaited()
    env.channel.edit.assert_not_awaited()


@pytest.mark.asyncio
async def test_same_name_event_does_not_repeat_rename(env):
    await track(env, start_time=NOW, name="VC1")
    await env.cog.sync_guild(env.guild)
    await env.cog.sync_guild(env.guild)
    env.channel.edit.assert_not_awaited()


@pytest.mark.asyncio
async def test_finish_rechecks_ownership_and_is_idempotent(env):
    event = await reserve(env)
    env.member.id = 20
    assert await env.cog.owned_events(env.interaction) == []
    with pytest.raises(ValueError, match="自分が作成"):
        await env.cog.finish_event(env.interaction, event.id)
    event.cancel.assert_not_awaited()
    env.member.id = 10
    assert await env.cog.owned_events(env.interaction) == [event]
    await env.cog.finish_event(env.interaction, event.id)
    event.cancel.assert_awaited_once()
    with pytest.raises(ValueError, match="既に終了"):
        await env.cog.finish_event(env.interaction, event.id)
    assert not env.cog.store.records


@pytest.mark.asyncio
async def test_host_can_finish_active_event_and_restore(env):
    event = await track(env, start_time=NOW)
    await env.cog.sync_guild(env.guild)
    await env.cog.finish_event(env.interaction, event.id)
    event.end.assert_awaited_once()
    assert env.channel.name == "VC1"


@pytest.mark.asyncio
async def test_persistent_panel_opens_private_select_and_modal(module, env):
    panel = module.PanelView(env.cog)
    assert panel.is_persistent()
    await panel.create.callback(env.interaction)
    kwargs = env.interaction.followup.send.call_args.kwargs
    assert kwargs["ephemeral"] is True
    view = kwargs["view"]
    select = view.children[0]
    assert select.options[0].label == "VC1"
    select._values = ["1"]
    await select.callback(env.interaction)
    modal = env.interaction.response.send_modal.call_args.args[0]
    assert isinstance(modal, module.EventModal)
    assert modal.channel_id == 1
    assert len(modal.children) == 4
    env.member.id = 20
    assert await view.interaction_check(env.interaction) is False


@pytest.mark.asyncio
async def test_modal_submits_and_shows_event_link(module, env):
    modal = module.EventModal(env.cog, env.member.id, 1)
    modal.event_name._value = "雑談会"
    modal.start._value = "明日 21:00"
    modal.duration._value = "30"
    modal.description._value = ""
    await modal.on_submit(env.interaction)
    assert len(env.events) == 1
    assert (
        "https://discord.com/events/" in env.interaction.followup.send.call_args.args[0]
    )
    assert env.interaction.followup.send.call_args.kwargs["ephemeral"] is True


@pytest.mark.asyncio
async def test_manage_panel_requires_confirmation(module, env):
    event = await reserve(env)
    panel = module.PanelView(env.cog)
    await panel.manage.callback(env.interaction)
    select = env.interaction.followup.send.call_args.kwargs["view"].children[0]
    select._values = [str(event.id)]
    await select.callback(env.interaction)
    event.cancel.assert_not_awaited()
    confirm = env.interaction.response.edit_message.call_args.kwargs["view"]
    await confirm.confirm.callback(env.interaction)
    event.cancel.assert_awaited_once()


@pytest.mark.asyncio
async def test_install_creates_dedicated_channel_and_reuses_message(module, env):
    channel = MagicMock(spec=module.discord.TextChannel)
    channel.id, channel.guild = 50, env.guild
    message = SimpleNamespace(
        id=60, channel=channel, jump_url="https://discord.com/test"
    )
    message.edit = AsyncMock(return_value=message)
    channel.send = AsyncMock(return_value=message)
    channel.fetch_message = AsyncMock(return_value=message)
    env.channels[channel.id] = channel
    env.guild.create_text_channel = AsyncMock(return_value=channel)
    result = await env.cog.place_panel(env.guild)
    assert result is message
    kwargs = env.guild.create_text_channel.call_args.kwargs
    assert kwargs["overwrites"][env.guild.default_role].send_messages is False
    assert kwargs["overwrites"][env.guild.me].send_messages is True
    assert channel.send.call_args.kwargs["view"].is_persistent()
    await env.cog.place_panel(env.guild)
    env.guild.create_text_channel.assert_awaited_once()
    channel.send.assert_awaited_once()
    message.edit.assert_awaited_once()
    await env.cog.cog_unload()
    assert all(view.is_finished() for view in env.cog.panel_views)


@pytest.mark.asyncio
async def test_extension_registers_reloads_and_unloads_without_discord_login(module):
    bot = module.commands.Bot(command_prefix="!", intents=module.discord.Intents.none())
    with patch.object(module.EventStore, "setup", new=AsyncMock()):
        async with bot:
            await module.setup(bot)
            command = bot.tree.get_command("イベントパネル")
            assert command is not None
            assert command.guild_only
            assert command.default_permissions.administrator
            user = SimpleNamespace(guild_permissions=module.discord.Permissions.none())
            with pytest.raises(module.app_commands.MissingPermissions):
                await command.checks[0](
                    SimpleNamespace(permissions=user.guild_permissions)
                )
            cog = bot.get_cog("EventPanel")
            assert cog.check_events.is_running()
            assert bot.persistent_views
            await bot.remove_cog("EventPanel")
            assert bot.tree.get_command("イベントパネル") is None
            assert all(v.is_finished() for v in cog.panel_views)
            await asyncio.sleep(0)
            assert not cog.check_events.is_running()
