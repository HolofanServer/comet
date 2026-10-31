"""実際の discord.py 権限計算で閉鎖計画とコマンドを検証する。通信は行わない。"""

import asyncio
import copy
import importlib
import json
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

STAFF = 1093678152317935696
BOT_ROLE = 1093387737840746646
BOT2 = 1092988310378512434
OWNER, STAFF_USER, GENERAL, MULTI_ROLE, INDIVIDUAL, BOT = range(1, 7)
NORMAL_ROLE, DENY_ROLE, ADMIN_ROLE, MANAGED_BOT = range(101, 105)
CATEGORY, TEXT, PRIVATE, VOICE, STAGE, FORUM, NEWS, MEDIA = range(201, 209)


@pytest.fixture
def close_module():
    # 既存 conftest の全体モックをこのテストだけ解除し、他テストに漏らさない。
    with patch.dict(sys.modules):
        for name in list(sys.modules):
            if name == "discord" or name.startswith("discord."):
                del sys.modules[name]
        sys.modules.pop("cogs.manage.server_close", None)
        yield importlib.import_module("cogs.manage.server_close")


def overwrite(target, *, kind=0, allow=0, deny=0):
    return {"id": str(target), "type": kind, "allow": str(allow), "deny": str(deny)}


@pytest.fixture
def payload(close_module):
    module = close_module
    guild_id = module.GUILD_ID
    roles = [
        (guild_id, "@everyone", 1024 | 2048 | 65536),
        (STAFF, "Staff", 1024),
        (BOT_ROLE, "bot", 0),
        (BOT2, "bot2", 1024),
        (NORMAL_ROLE, "general", 1024),
        (DENY_ROLE, "restricted", 0),
        (ADMIN_ROLE, "admin", 8),
        (MANAGED_BOT, "COMET", 8),
    ]
    users = [
        (OWNER, [ADMIN_ROLE]),
        (STAFF_USER, [STAFF, NORMAL_ROLE]),
        (GENERAL, [NORMAL_ROLE]),
        (MULTI_ROLE, [NORMAL_ROLE, DENY_ROLE]),
        (INDIVIDUAL, []),
        (BOT, [BOT_ROLE, MANAGED_BOT]),
        (next(iter(module.EXEMPT_MEMBER_IDS)), [ADMIN_ROLE]),
    ]
    synced = [
        overwrite(guild_id, deny=2048),
        overwrite(NORMAL_ROLE, allow=1024 | 65536),
        overwrite(DENY_ROLE, deny=1024),
        overwrite(INDIVIDUAL, kind=1, allow=1024 | 2048),
        overwrite(999, kind=1, allow=1024),  # キャッシュ外・退会済みの許可
        overwrite(998, allow=1024),  # キャッシュ外・削除済みロール
    ]
    channels = [
        {
            "id": str(cid),
            "name": f"channel-{cid}",
            "type": kind,
            "position": index,
            "bitrate": 64000,
            "user_limit": 0,
            "parent_id": str(CATEGORY) if cid == TEXT else None,
            "permission_overwrites": copy.deepcopy(synced),
        }
        for index, (cid, kind) in enumerate(
            [
                (CATEGORY, 4),
                (TEXT, 0),
                (PRIVATE, 0),
                (VOICE, 2),
                (STAGE, 13),
                (FORUM, 15),
                (NEWS, 5),
                (MEDIA, 16),
                (module.EXCLUDED_CHANNEL_ID, 0),
            ]
        )
    ]
    channels[2]["permission_overwrites"] = [
        overwrite(guild_id, deny=1024),
        overwrite(STAFF, allow=1024),
        overwrite(STAFF_USER, kind=1, deny=1024),
    ]
    channels[-1]["permission_overwrites"] = [overwrite(guild_id, deny=1024)]
    return {
        "id": str(guild_id),
        "name": "HFS test",
        "owner_id": str(OWNER),
        "roles": [
            {
                "id": str(rid),
                "name": name,
                "permissions": str(permissions),
                "position": index,
                "managed": rid == MANAGED_BOT,
                **({"tags": {"bot_id": str(BOT)}} if rid == MANAGED_BOT else {}),
            }
            for index, (rid, name, permissions) in enumerate(roles)
        ],
        "members": [
            {
                "user": {
                    "id": str(uid),
                    "username": f"user-{uid}",
                    "discriminator": "0",
                    "avatar": None,
                    "bot": uid == BOT,
                },
                "roles": list(map(str, rids)),
                "joined_at": "2026-01-01T00:00:00+00:00",
                "flags": 0,
            }
            for uid, rids in users
        ],
        "channels": channels,
    }


def snapshot_from(module, data):
    client = module.discord.Client(intents=module.discord.Intents.all())
    guild = module.discord.Guild(data=copy.deepcopy(data), state=client._connection)
    return module.Snapshot(guild, guild.channels, {m.id: m for m in guild.members})


def apply_to_payload(module, payload, plan):
    data = copy.deepcopy(payload)
    changes = {change.channel.id: change for change in plan.changes}
    for channel in data["channels"]:
        if int(channel["id"]) in changes:
            channel["permission_overwrites"] = module._serialize(
                changes[int(channel["id"])].after
            )
    return data


def test_closes_every_channel_type_and_individual_escape_routes(close_module, payload):
    module = close_module
    before = snapshot_from(module, payload)
    plan = module._plan(before, BOT)
    assert not plan.blockers
    assert len(plan.changes) == 7
    assert PRIVATE not in {change.channel.id for change in plan.changes}
    assert plan.changes[-1].channel.id == CATEGORY
    after = snapshot_from(module, apply_to_payload(module, payload, plan))
    for channel in after.channels:
        old = before.guild.get_channel(channel.id)
        if channel.id == module.EXCLUDED_CHANNEL_ID:
            assert module._overwrites(channel) == module._overwrites(old)
            continue
        for uid in (GENERAL, MULTI_ROLE, INDIVIDUAL):
            assert not channel.permissions_for(after.members[uid]).view_channel
        for uid in (OWNER, STAFF_USER, BOT, *module.EXEMPT_MEMBER_IDS):
            assert channel.permissions_for(after.members[uid]).view_channel == (
                old.permissions_for(before.members[uid]).view_channel
            )
        assert (
            module._overwrites(channel)
            .get((1, 999), module.discord.PermissionOverwrite())
            .view_channel
            is not True
        )
        assert (
            module._overwrites(channel)
            .get((0, 998), module.discord.PermissionOverwrite())
            .view_channel
            is not True
        )
    assert not module._plan(after, BOT).changes
    module._verify(plan, after, BOT)


def test_preserves_other_permission_bits_and_source_objects(close_module, payload):
    module = close_module
    snapshot = snapshot_from(module, payload)
    original = {
        c.id: module._serialize(module._overwrites(c)) for c in snapshot.channels
    }
    plan = module._plan(snapshot, BOT)
    for change in plan.changes:
        for key, overwrite_before in change.before.items():
            old_allow, old_deny = overwrite_before.pair()
            new_allow, new_deny = change.after[key].pair()
            assert old_allow.value & ~1024 == new_allow.value & ~1024
            assert old_deny.value & ~1024 == new_deny.value & ~1024
        assert original[change.channel.id] == module._serialize(
            module._overwrites(change.channel)
        )


def test_excluded_parent_unchanged_but_sibling_closed(close_module, payload):
    payload["channels"][-1]["parent_id"] = str(CATEGORY)
    payload["channels"][-1]["permission_overwrites"] = copy.deepcopy(
        payload["channels"][0]["permission_overwrites"]
    )
    snapshot = snapshot_from(close_module, payload)
    assert snapshot.guild.get_channel(
        close_module.EXCLUDED_CHANNEL_ID
    ).permissions_synced
    plan = close_module._plan(snapshot, BOT)
    ids = {c.channel.id for c in plan.changes}
    assert CATEGORY not in ids
    assert close_module.EXCLUDED_CHANNEL_ID not in ids
    assert TEXT in ids


def test_preserves_staff_access_through_another_role(close_module, payload):
    payload["channels"][1]["permission_overwrites"].extend(
        [overwrite(STAFF, deny=1024), overwrite(BOT_ROLE, deny=1024)]
    )
    # Staff 自体の許可はなくても、一般ロールの許可で見えていた個人を保護。
    snapshot = snapshot_from(close_module, payload)
    assert (
        snapshot.guild.get_channel(TEXT)
        .permissions_for(snapshot.members[STAFF_USER])
        .view_channel
    )
    plan = close_module._plan(snapshot, BOT)
    after = snapshot_from(close_module, apply_to_payload(close_module, payload, plan))
    assert (
        after.guild.get_channel(TEXT)
        .permissions_for(after.members[STAFF_USER])
        .view_channel
    )
    assert (
        after.guild.get_channel(TEXT)
        .overwrites_for(after.members[STAFF_USER])
        .view_channel
    )


def test_does_not_widen_staff_access_when_another_role_denied_view(
    close_module, payload
):
    payload["members"][1]["roles"] = [str(STAFF), str(DENY_ROLE)]
    snapshot = snapshot_from(close_module, payload)
    assert (
        not snapshot.guild.get_channel(TEXT)
        .permissions_for(snapshot.members[STAFF_USER])
        .view_channel
    )
    plan = close_module._plan(snapshot, BOT)
    after = snapshot_from(close_module, apply_to_payload(close_module, payload, plan))
    assert (
        not after.guild.get_channel(TEXT)
        .permissions_for(after.members[STAFF_USER])
        .view_channel
    )


def test_unprotected_administrator_blocks_but_named_exception_does_not(
    close_module, payload
):
    snapshot = snapshot_from(close_module, payload)
    assert not close_module._plan(snapshot, BOT).blockers
    payload["members"][2]["roles"].append(str(ADMIN_ROLE))
    plan = close_module._plan(snapshot_from(close_module, payload), BOT)
    assert plan.blockers == [f"保護対象外の管理者: {GENERAL}"]


@pytest.mark.parametrize("missing", ["role", "channel", "bot"])
def test_missing_required_information_aborts(close_module, payload, missing):
    if missing == "role":
        payload["roles"] = [r for r in payload["roles"] if int(r["id"]) != STAFF]
    elif missing == "channel":
        payload["channels"].pop()
    else:
        payload["members"] = [
            m for m in payload["members"] if int(m["user"]["id"]) != BOT
        ]
    with pytest.raises(ValueError):
        close_module._plan(snapshot_from(close_module, payload), BOT)


def test_backup_contains_all_original_overwrites_and_no_member_directory(
    close_module, payload, tmp_path, monkeypatch
):
    monkeypatch.setattr(close_module, "BACKUP_DIRECTORY", tmp_path)
    snapshot = snapshot_from(close_module, payload)
    plan = close_module._plan(snapshot, BOT)
    first = close_module._save_backup(plan, OWNER)
    second = close_module._save_backup(plan, OWNER)
    assert first != second
    backup = json.loads(first.read_text())
    assert len(backup["channels"]) == len(snapshot.channels)
    assert "members" not in backup
    assert backup["actor_id"] == str(OWNER)
    for channel in backup["channels"]:
        assert channel["permission_overwrites"] == close_module._serialize(
            close_module._overwrites(snapshot.guild.get_channel(int(channel["id"])))
        )


@pytest.mark.parametrize("drift", ["new_channel", "role", "exception", "individual"])
def test_verification_detects_changes_during_execution(close_module, payload, drift):
    plan = close_module._plan(snapshot_from(close_module, payload), BOT)
    updated = apply_to_payload(close_module, payload, plan)
    if drift == "new_channel":
        updated["channels"].append(
            {
                "id": "999999",
                "name": "new",
                "type": 0,
                "position": 0,
                "permission_overwrites": [],
            }
        )
    elif drift == "role":
        updated["roles"][4]["permissions"] = str(1024 | 2048)
    elif drift == "exception":
        updated["channels"][-1]["permission_overwrites"] = []
    else:
        updated["channels"][1]["permission_overwrites"].append(
            overwrite(GENERAL, kind=1, allow=1024)
        )
    with pytest.raises(ValueError):
        close_module._verify(plan, snapshot_from(close_module, updated), BOT)


@pytest.fixture
def execution(close_module, payload, monkeypatch, tmp_path):
    module = close_module
    initial = snapshot_from(module, payload)
    plan = module._plan(initial, BOT)
    final = snapshot_from(module, apply_to_payload(module, payload, plan))
    bot = SimpleNamespace(user=SimpleNamespace(id=BOT))
    cog = module.ServerClose(bot)
    ctx = SimpleNamespace(
        guild=initial.guild,
        author=initial.members[OWNER],
        interaction=SimpleNamespace(),
        bot_permissions=SimpleNamespace(attach_files=True),
        defer=AsyncMock(),
        send=AsyncMock(),
    )
    collector = AsyncMock(side_effect=[initial, final])
    monkeypatch.setattr(module, "_snapshot", collector)
    monkeypatch.setattr(module, "BACKUP_DIRECTORY", tmp_path)
    edits = AsyncMock()

    async def fetch_channel(guild, channel_id):
        original = guild.get_channel(channel_id)
        return SimpleNamespace(
            id=original.id,
            overwrites=original.overwrites,
            category_id=original.category_id,
            edit=edits,
        )

    monkeypatch.setattr(module.discord.Guild, "fetch_channel", fetch_channel)
    return SimpleNamespace(
        cog=cog, ctx=ctx, edits=edits, collector=collector, initial=initial, plan=plan
    )


@pytest.mark.asyncio
async def test_preview_never_writes(close_module, execution, tmp_path):
    await execution.cog.server_close.callback(execution.cog, execution.ctx)
    execution.edits.assert_not_awaited()
    assert "プレビューのみ" in execution.ctx.send.call_args.args[0]
    assert not list(tmp_path.iterdir())


@pytest.mark.asyncio
async def test_execute_backs_up_before_edit_and_verifies(close_module, execution):
    module = close_module
    observed = []

    async def edit(**kwargs):
        assert list(module.BACKUP_DIRECTORY.glob("*.json"))
        assert "file" in execution.ctx.send.call_args.kwargs
        observed.append(kwargs)

    execution.edits.side_effect = edit
    await execution.cog.server_close.callback(
        execution.cog, execution.ctx, execute=True
    )
    assert len(observed) == 7
    assert "権限検証が完了" in execution.ctx.send.call_args.args[0]
    assert execution.collector.await_count == 2
    assert all("reason" in item for item in observed)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["backup", "attachment", "second_edit", "verify"])
async def test_failures_never_claim_success(
    close_module, execution, monkeypatch, failure
):
    module = close_module
    http_error = module.discord.Forbidden(
        SimpleNamespace(status=403, reason="Forbidden"), "missing permissions"
    )
    if failure == "backup":
        monkeypatch.setattr(
            module, "_save_backup", lambda *args: (_ for _ in ()).throw(OSError("full"))
        )
    elif failure == "attachment":
        execution.ctx.send.side_effect = [http_error, None]
    elif failure == "second_edit":
        execution.edits.side_effect = [None, http_error]
    else:
        execution.collector.side_effect = [execution.initial, execution.initial]
    await execution.cog.server_close.callback(
        execution.cog, execution.ctx, execute=True
    )
    assert "閉鎖は完了していません" in execution.ctx.send.call_args.args[0]
    expected = {"backup": 0, "attachment": 0, "second_edit": 2, "verify": 7}[failure]
    assert execution.edits.await_count == expected
    if failure == "second_edit":
        assert "更新成功: 1" in execution.ctx.send.call_args.args[0]


@pytest.mark.asyncio
async def test_permission_race_aborts_before_write(
    close_module, execution, monkeypatch
):
    async def changed(guild, channel_id):
        return SimpleNamespace(id=channel_id, overwrites={}, category_id=None)

    monkeypatch.setattr(close_module.discord.Guild, "fetch_channel", changed)
    await execution.cog.server_close.callback(
        execution.cog, execution.ctx, execute=True
    )
    execution.edits.assert_not_awaited()
    assert "閉鎖は完了していません" in execution.ctx.send.call_args.args[0]


@pytest.mark.asyncio
async def test_unprotected_admin_prevents_backup_and_edit(
    close_module, execution, payload, tmp_path
):
    payload["members"][2]["roles"].append(str(ADMIN_ROLE))
    execution.collector.side_effect = [snapshot_from(close_module, payload)]
    await execution.cog.server_close.callback(
        execution.cog, execution.ctx, execute=True
    )
    assert "実行不可（変更なし）" in execution.ctx.send.call_args.args[0]
    execution.edits.assert_not_awaited()
    assert not list(tmp_path.iterdir())


@pytest.mark.asyncio
@pytest.mark.parametrize("denied", ["dm", "administrator", "attach_files"])
async def test_command_permission_checks(close_module, execution, denied):
    ctx = execution.ctx
    if denied == "dm":
        ctx.guild = None
        expected = close_module.commands.NoPrivateMessage
    elif denied == "administrator":
        ctx.author = execution.initial.members[GENERAL]
        expected = close_module.commands.MissingPermissions
    else:
        ctx.bot_permissions.attach_files = False
        expected = close_module.commands.BotMissingPermissions
    with pytest.raises(expected):
        await close_module.discord.utils.async_all(
            check(ctx) for check in execution.cog.server_close.checks
        )


@pytest.mark.asyncio
async def test_command_only_runs_in_target_guild(close_module, execution):
    execution.ctx.guild = SimpleNamespace(id=999)
    await execution.cog.server_close.callback(
        execution.cog, execution.ctx, execute=True
    )
    execution.collector.assert_not_awaited()
    assert "HFS サーバー専用" in execution.ctx.send.call_args.args[0]


@pytest.mark.asyncio
async def test_prefix_execute_does_not_publish_private_backup(close_module, execution):
    execution.ctx.interaction = None
    await execution.cog.server_close.callback(
        execution.cog, execution.ctx, execute=True
    )
    execution.collector.assert_not_awaited()
    execution.edits.assert_not_awaited()
    assert "/server_close execute:true" in execution.ctx.send.call_args.args[0]


@pytest.mark.asyncio
async def test_extension_registers_and_unloads_hybrid_command(close_module):
    bot = close_module.commands.Bot(
        command_prefix="comet/", intents=close_module.discord.Intents.none()
    )
    try:
        await bot.load_extension("cogs.manage.server_close")
        assert bot.get_command("server_close") is not None
        slash = bot.tree.get_command("server_close")
        assert slash.guild_only
        assert slash.default_permissions.administrator
        assert slash.parameters[0].default is False
        await bot.unload_extension("cogs.manage.server_close")
        assert bot.get_command("server_close") is None
        assert bot.tree.get_command("server_close") is None
    finally:
        await bot.close()


def test_admin_bot_role_does_not_gain_redundant_overwrite(close_module, payload):
    plan = close_module._plan(snapshot_from(close_module, payload), BOT)
    for change in plan.changes:
        assert (0, MANAGED_BOT) not in change.after
    final = snapshot_from(close_module, apply_to_payload(close_module, payload, plan))
    assert not close_module._plan(final, BOT).changes
    close_module._verify(plan, final, BOT)


def test_overwrite_limit_blocks_before_execution(close_module, payload):
    channel = payload["channels"][1]
    channel["permission_overwrites"] = [
        overwrite(10000 + index, kind=1) for index in range(999)
    ] + [overwrite(close_module.GUILD_ID)]
    plan = close_module._plan(snapshot_from(close_module, payload), BOT)
    assert any(str(TEXT) in item and "1000" in item for item in plan.blockers)


@pytest.mark.asyncio
async def test_third_edit_reports_http_failure_and_channel(close_module, execution):
    error = close_module.discord.Forbidden(
        SimpleNamespace(status=403, reason="Forbidden"),
        {"code": 50013, "message": "Missing Permissions " + "x" * 3000},
    )
    execution.edits.side_effect = [None, None, error]
    await execution.cog.server_close.callback(
        execution.cog, execution.ctx, execute=True
    )
    message = execution.ctx.send.call_args.args[0]
    assert "更新成功: 2" in message
    assert "処理: 権限更新" in message
    assert f"チャンネル: {execution.plan.changes[2].channel.id}" in message
    assert "403" in message and "50013" in message
    assert "原因:" in message
    assert len(message) <= 2000
    assert execution.edits.await_count == 3
    mentions = execution.ctx.send.call_args.kwargs["allowed_mentions"]
    assert not mentions.everyone and not mentions.users and not mentions.roles


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("failure", "phase", "cause"),
    [
        ("timeout", "チャンネル取得", "タイムアウト"),
        ("backup", "バックアップ保存", "disk full"),
        ("verify", "最終検証", "未閉鎖"),
    ],
)
async def test_failures_report_phase_and_cause(
    close_module, execution, monkeypatch, failure, phase, cause
):
    if failure == "timeout":
        monkeypatch.setattr(
            close_module.discord.Guild,
            "fetch_channel",
            AsyncMock(side_effect=asyncio.TimeoutError()),
        )
    elif failure == "backup":

        def fail_backup(*args):
            raise OSError("disk full")

        monkeypatch.setattr(close_module, "_save_backup", fail_backup)
    else:
        execution.collector.side_effect = [execution.initial, execution.initial]
    await execution.cog.server_close.callback(
        execution.cog, execution.ctx, execute=True
    )
    message = execution.ctx.send.call_args.args[0]
    assert f"処理: {phase}" in message
    assert "原因:" in message and cause in message
    assert len(message) <= 2000
    mentions = execution.ctx.send.call_args.kwargs["allowed_mentions"]
    assert not mentions.everyone and not mentions.users and not mentions.roles


def test_exact_overwrite_limit_is_allowed(close_module, payload):
    channel = payload["channels"][1]
    channel["permission_overwrites"] = [
        overwrite(10000 + index, kind=1) for index in range(996)
    ] + [overwrite(close_module.GUILD_ID)]
    plan = close_module._plan(snapshot_from(close_module, payload), BOT)
    change = next(change for change in plan.changes if change.channel.id == TEXT)
    assert len(change.after) == 1000
    assert not plan.blockers


@pytest.mark.asyncio
async def test_overwrite_limit_aborts_before_backup_or_edit(
    close_module, execution, payload, tmp_path
):
    payload["channels"][1]["permission_overwrites"] = [
        overwrite(10000 + index, kind=1) for index in range(999)
    ] + [overwrite(close_module.GUILD_ID)]
    execution.collector.side_effect = [snapshot_from(close_module, payload)]
    await execution.cog.server_close.callback(
        execution.cog, execution.ctx, execute=True
    )
    execution.edits.assert_not_awaited()
    assert not list(tmp_path.iterdir())
    message = execution.ctx.send.call_args.args[0]
    assert "実行不可（変更なし）" in message
    assert "1000" in message and str(TEXT) in message


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("enabled", "default_ids", "blocked"),
    [(True, [TEXT], True), (False, [TEXT], False), (True, [], False)],
)
async def test_onboarding_default_channels_checked_before_backup(
    close_module, execution, monkeypatch, tmp_path, enabled, default_ids, blocked
):
    execution.initial.guild.features.append("COMMUNITY")
    fetch = AsyncMock(
        return_value=SimpleNamespace(
            enabled=enabled, default_channel_ids=set(default_ids)
        )
    )
    monkeypatch.setattr(close_module.discord.Guild, "onboarding", fetch)
    await execution.cog.server_close.callback(
        execution.cog, execution.ctx, execute=True
    )
    fetch.assert_awaited_once()
    message = execution.ctx.send.call_args.args[0]
    if blocked:
        execution.edits.assert_not_awaited()
        assert not list(tmp_path.iterdir())
        for expected in ("オンボーディング", "350003", str(TEXT), "解除"):
            assert expected in message
    else:
        assert "権限検証が完了" in message


@pytest.mark.asyncio
async def test_onboarding_exception_channel_does_not_block(
    close_module, execution, monkeypatch
):
    execution.initial.guild.features.append("COMMUNITY")
    monkeypatch.setattr(
        close_module.discord.Guild,
        "onboarding",
        AsyncMock(
            return_value=SimpleNamespace(
                enabled=True, default_channel_ids={close_module.EXCLUDED_CHANNEL_ID}
            )
        ),
    )
    await execution.cog.server_close.callback(
        execution.cog, execution.ctx, execute=True
    )
    assert "権限検証が完了" in execution.ctx.send.call_args.args[0]


@pytest.mark.asyncio
async def test_onboarding_fetch_failure_prevents_all_writes(
    close_module, execution, monkeypatch, tmp_path
):
    execution.initial.guild.features.append("COMMUNITY")
    monkeypatch.setattr(
        close_module.discord.Guild,
        "onboarding",
        AsyncMock(
            side_effect=close_module.discord.Forbidden(
                SimpleNamespace(status=403, reason="Forbidden"),
                {"code": 50013, "message": "Missing Permissions"},
            )
        ),
    )
    await execution.cog.server_close.callback(
        execution.cog, execution.ctx, execute=True
    )
    execution.edits.assert_not_awaited()
    assert not list(tmp_path.iterdir())
    message = execution.ctx.send.call_args.args[0]
    assert "処理: オンボーディング確認" in message
    assert "50013" in message


@pytest.mark.asyncio
async def test_onboarding_http_race_explains_settings_removal(close_module, execution):
    execution.edits.side_effect = close_module.discord.HTTPException(
        SimpleNamespace(status=400, reason="Bad Request"),
        {
            "code": 350003,
            "message": "Onboarding channels must be readable by everyone.",
        },
    )
    await execution.cog.server_close.callback(
        execution.cog, execution.ctx, execute=True
    )
    message = execution.ctx.send.call_args.args[0]
    for expected in ("350003", "オンボーディング", "解除"):
        assert expected in message
