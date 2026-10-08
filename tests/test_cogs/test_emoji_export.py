"""実際の Cog と ZIP を使い、Discord 通信だけを置き換えて検証する。"""

import asyncio
import importlib
import io
import json
import random
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from zipfile import ZipFile

import pytest

PNG = b"\x89PNG\r\n\x1a\npng payload"
GIF = b"GIF89a gif payload"
WEBP = b"RIFF\x10\x00\x00\x00WEBP webp payload"


@pytest.fixture
def export_module():
    # 共通 conftest の Discord 全体のモックを、この fixture 内だけ解除する。
    # 実 decorator / Cog 登録を検証し、他の既存テストには影響させない。
    with patch.dict(sys.modules):
        for name in list(sys.modules):
            if name == "discord" or name.startswith("discord."):
                del sys.modules[name]
        sys.modules.pop("cogs.manage.emoji_export", None)
        yield importlib.import_module("cogs.manage.emoji_export")


def make_emoji(emoji_id, name, data=PNG):
    return SimpleNamespace(id=emoji_id, name=name, read=AsyncMock(return_value=data))


@pytest.fixture
def export_context():
    attachments = []

    async def capture_send(content, *, file=None):
        if file is not None:
            attachments.append(
                (file.filename, file.fp.read(), Path(file.fp.name), file.fp)
            )

    return SimpleNamespace(
        guild=SimpleNamespace(
            id=123,
            filesize_limit=1024 * 1024,
            fetch_emojis=AsyncMock(return_value=[]),
            fetch_stickers=AsyncMock(return_value=[]),
        ),
        interaction=None,
        author=SimpleNamespace(guild_permissions=SimpleNamespace(administrator=True)),
        bot_permissions=SimpleNamespace(attach_files=True),
        defer=AsyncMock(),
        send=AsyncMock(side_effect=capture_send),
        attachments=attachments,
    )


async def run_export(module, ctx, command_name="export_emojis_temp"):
    cog = module.EmojiExport(SimpleNamespace())
    await getattr(cog, command_name).callback(cog, ctx)


@pytest.mark.asyncio
async def test_exports_non_m_prefix_with_original_names_and_bytes(
    export_module, export_context
):
    excluded = make_emoji(1, "m_member")
    included = [
        make_emoji(2, "Smile"),
        make_emoji(3, "dance", GIF),
        make_emoji(4, "wave", WEBP),
        make_emoji(5, "M_upper"),
        make_emoji(6, "team_m_member"),
    ]
    export_context.guild.fetch_emojis.return_value = [excluded, *included]

    await run_export(export_module, export_context)

    export_context.defer.assert_awaited_once()
    excluded.read.assert_not_awaited()
    assert len(export_context.attachments) == 1
    filename, data, path, stream = export_context.attachments[0]
    assert filename == "emojis_123.zip"
    with ZipFile(io.BytesIO(data)) as archive:
        assert {name: archive.read(name) for name in archive.namelist()} == {
            "Smile.png": PNG,
            "dance.gif": GIF,
            "wave.webp": WEBP,
            "M_upper.png": PNG,
            "team_m_member.png": PNG,
        }
    assert stream.closed
    assert not path.parent.exists()


@pytest.mark.asyncio
async def test_duplicate_names_keep_basename_in_id_directories(
    export_module, export_context
):
    export_context.guild.fetch_emojis.return_value = [
        make_emoji(1, "same"),
        make_emoji(2, "same"),
        make_emoji(3, "SAME"),
    ]
    await run_export(export_module, export_context)
    with ZipFile(io.BytesIO(export_context.attachments[0][1])) as archive:
        assert archive.namelist() == ["1/same.png", "2/same.png", "3/SAME.png"]


@pytest.mark.asyncio
@pytest.mark.parametrize("names", [[], ["m_one", "m_two"]])
async def test_no_matching_emojis_sends_no_empty_zip(
    export_module, export_context, names
):
    export_context.guild.fetch_emojis.return_value = [
        make_emoji(index, name) for index, name in enumerate(names)
    ]
    await run_export(export_module, export_context)
    assert not export_context.attachments
    assert "ありません" in export_context.send.call_args.args[0]


@pytest.mark.asyncio
@pytest.mark.parametrize("interaction_limit", [None, 150])
async def test_zip_parts_respect_actual_attachment_limit(
    export_module, export_context, interaction_limit
):
    export_context.guild.fetch_emojis.return_value = [
        make_emoji(1, "one"),
        make_emoji(2, "two"),
        make_emoji(3, "three"),
    ]
    if interaction_limit is None:
        export_context.guild.filesize_limit = 150
    else:
        export_context.interaction = SimpleNamespace(filesize_limit=interaction_limit)

    await run_export(export_module, export_context)

    assert [item[0] for item in export_context.attachments] == [
        "emojis_123_01.zip",
        "emojis_123_02.zip",
        "emojis_123_03.zip",
    ]
    images = {}
    for _, data, path, stream in export_context.attachments:
        assert len(data) <= 150
        with ZipFile(io.BytesIO(data)) as archive:
            images.update({name: archive.read(name) for name in archive.namelist()})
        assert stream.closed
        assert not path.parent.exists()
    assert images == {"one.png": PNG, "two.png": PNG, "three.png": PNG}


def test_single_image_zip_over_limit_is_rejected(export_module, tmp_path):
    source = tmp_path / "source"
    source.write_bytes(PNG)
    with pytest.raises(ValueError, match="添付上限"):
        export_module._build_archives([(source, "one.png")], tmp_path, 1)
    assert not list(tmp_path.glob("*.zip"))


def test_archive_equal_to_limit_is_allowed(export_module, tmp_path):
    source = tmp_path / "source"
    source.write_bytes(PNG)
    entries = [(source, "one.png")]
    archive = export_module._build_archives(entries, tmp_path, 1024)[0]
    limit = archive.stat().st_size
    assert (
        export_module._build_archives(entries, tmp_path, limit)[0].stat().st_size
        == limit
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["http", "timeout", "image"])
async def test_download_failure_reports_incomplete_and_cleans_up(
    export_module, export_context, failure, monkeypatch
):
    emoji = make_emoji(2, "broken", b"not an image")
    if failure == "http":
        emoji.read.side_effect = export_module.discord.HTTPException(
            SimpleNamespace(status=404, reason="Not Found"), "deleted"
        )
    elif failure == "timeout":
        emoji.read.side_effect = asyncio.TimeoutError()
    export_context.guild.fetch_emojis.return_value = [make_emoji(1, "ok"), emoji]
    paths = []
    original_write = Path.write_bytes

    def capture_write(path, data):
        paths.append(path)
        return original_write(path, data)

    monkeypatch.setattr(Path, "write_bytes", capture_write)
    await run_export(export_module, export_context)

    assert not export_context.attachments
    assert "全件の出力は完了していません" in export_context.send.call_args.args[0]
    assert paths and all(not path.parent.exists() for path in paths)


@pytest.mark.asyncio
async def test_send_failure_reports_number_already_sent(export_module, export_context):
    export_context.guild.filesize_limit = 150
    export_context.guild.fetch_emojis.return_value = [
        make_emoji(1, "one"),
        make_emoji(2, "two"),
    ]
    capture_send = export_context.send.side_effect

    async def fail_second(content, *, file=None):
        if file is not None and export_context.attachments:
            raise export_module.discord.HTTPException(
                SimpleNamespace(status=413, reason="Too Large"), "upload failed"
            )
        await capture_send(content, file=file)

    export_context.send.side_effect = fail_second
    await run_export(export_module, export_context)
    assert len(export_context.attachments) == 1
    assert "送信済み ZIP は 1 個" in export_context.send.call_args.args[0]
    assert not export_context.attachments[0][2].parent.exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("denied", ["dm", "administrator", "attach_files"])
@pytest.mark.parametrize("command_name", ["export_emojis_temp", "export_stickers_temp"])
async def test_command_checks_reject_invalid_context(
    export_module, export_context, denied, command_name
):
    errors = export_module.commands
    expected = errors.NoPrivateMessage
    if denied == "dm":
        export_context.guild = None
    elif denied == "administrator":
        export_context.author.guild_permissions.administrator = False
        expected = errors.MissingPermissions
    else:
        export_context.bot_permissions.attach_files = False
        expected = errors.BotMissingPermissions
    command = getattr(export_module.EmojiExport, command_name)
    with pytest.raises(expected):
        await export_module.discord.utils.async_all(
            check(export_context) for check in command.checks
        )
    if export_context.guild is not None:
        export_context.guild.fetch_emojis.assert_not_awaited()
        export_context.guild.fetch_stickers.assert_not_awaited()


@pytest.mark.asyncio
async def test_extension_registers_and_unloads_both_command_forms(export_module):
    bot = export_module.commands.Bot(
        command_prefix="comet/", intents=export_module.discord.Intents.none()
    )
    try:
        await bot.load_extension("cogs.manage.emoji_export")
        for name in ("export_emojis_temp", "export_stickers_temp"):
            command = bot.get_command(name)
            slash = bot.tree.get_command(name)
            assert command is not None
            assert slash is not None
            assert slash.guild_only
            assert slash.default_permissions.administrator
        await bot.unload_extension("cogs.manage.emoji_export")
        for name in ("export_emojis_temp", "export_stickers_temp"):
            assert bot.get_command(name) is None
            assert bot.tree.get_command(name) is None
    finally:
        await bot.close()


def make_sticker(module, sticker_id, name, data=PNG, format_name="png"):
    return SimpleNamespace(
        id=sticker_id,
        name=name,
        description="移行用の説明",
        emoji="wave",
        format=getattr(module.discord.StickerFormatType, format_name),
        read=AsyncMock(return_value=data),
    )


@pytest.mark.asyncio
async def test_stickers_preserve_formats_names_and_migration_metadata(
    export_module, export_context
):
    apng = PNG + b"acTL animation data"
    stickers = [
        make_sticker(export_module, 1, "こんにちは"),
        make_sticker(export_module, 2, "m_animated", apng, "apng"),
        make_sticker(export_module, 3, "dance", GIF, "gif"),
    ]
    export_context.guild.fetch_stickers.return_value = stickers
    await run_export(export_module, export_context, "export_stickers_temp")
    export_context.guild.fetch_emojis.assert_not_awaited()
    export_context.defer.assert_awaited_once()
    assert len(export_context.attachments) == 1
    filename, data, path, stream = export_context.attachments[0]
    assert filename == "stickers_123.zip"
    with ZipFile(io.BytesIO(data)) as archive:
        assert archive.read("こんにちは.png") == PNG
        assert archive.read("m_animated.png") == apng
        assert archive.read("dance.gif") == GIF
        metadata = json.loads(archive.read("_metadata/stickers.json"))
        assert [entry["name"] for entry in metadata] == [s.name for s in stickers]
        assert [entry["format"] for entry in metadata] == ["png", "apng", "gif"]
        assert all(entry["description"] == "移行用の説明" for entry in metadata)
        assert all(entry["emoji"] == "wave" for entry in metadata)
        assert all(entry["file"] in archive.namelist() for entry in metadata)
    assert stream.closed
    assert not path.parent.exists()


@pytest.mark.asyncio
async def test_sticker_paths_are_portable_and_do_not_collide(
    export_module, export_context
):
    names = [
        "../hello",
        "..\\hello",
        "SAME",
        "same",
        "CON",
        "...",
        "café",
        "cafe\u0301",
    ]
    export_context.guild.fetch_stickers.return_value = [
        make_sticker(export_module, index, name)
        for index, name in enumerate(names, start=1)
    ]
    await run_export(export_module, export_context, "export_stickers_temp")
    with ZipFile(io.BytesIO(export_context.attachments[0][1])) as archive:
        assert archive.namelist() == [
            "1/_hello.png",
            "2/_hello.png",
            "3/SAME.png",
            "4/same.png",
            "_CON.png",
            "sticker.png",
            "7/café.png",
            "8/café.png",
            "_metadata/stickers.json",
        ]
        assert [
            item["name"] for item in json.loads(archive.read("_metadata/stickers.json"))
        ] == names


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [b'{"v":"5.5.0","layers":[]}', b"invalid json"])
async def test_lottie_downloads_json_without_discord_read(
    export_module, export_context, payload, monkeypatch
):
    sticker = make_sticker(export_module, 42, "lottie", format_name="lottie")
    export_context.guild.fetch_stickers.return_value = [sticker]
    response = SimpleNamespace(
        raise_for_status=MagicMock(), read=AsyncMock(return_value=payload)
    )
    request = MagicMock()
    request.__aenter__ = AsyncMock(return_value=response)
    session = MagicMock()
    session.get.return_value = request
    session.__aenter__ = AsyncMock(return_value=session)
    client_session = MagicMock(return_value=session)
    monkeypatch.setattr(export_module.aiohttp, "ClientSession", client_session)

    await run_export(export_module, export_context, "export_stickers_temp")

    sticker.read.assert_not_awaited()
    session.get.assert_called_once_with("https://cdn.discordapp.com/stickers/42.json")
    response.raise_for_status.assert_called_once()
    if payload == b"invalid json":
        assert not export_context.attachments
        assert "全件の出力は完了していません" in export_context.send.call_args.args[0]
    else:
        with ZipFile(io.BytesIO(export_context.attachments[0][1])) as archive:
            assert archive.read("lottie.json") == payload


@pytest.mark.asyncio
async def test_no_stickers_sends_no_empty_zip(export_module, export_context):
    await run_export(export_module, export_context, "export_stickers_temp")
    assert not export_context.attachments
    assert "スタンプはありません" in export_context.send.call_args.args[0]


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["http", "timeout", "image"])
async def test_sticker_download_failure_reports_incomplete_and_cleans_up(
    export_module, export_context, failure, monkeypatch
):
    sticker = make_sticker(export_module, 2, "broken", b"not an image")
    if failure == "http":
        sticker.read.side_effect = export_module.discord.HTTPException(
            SimpleNamespace(status=404, reason="Not Found"), "deleted"
        )
    elif failure == "timeout":
        sticker.read.side_effect = asyncio.TimeoutError()
    export_context.guild.fetch_stickers.return_value = [
        make_sticker(export_module, 1, "ok"),
        sticker,
    ]
    paths = []
    original_write = Path.write_bytes

    def capture_write(path, data):
        paths.append(path)
        return original_write(path, data)

    monkeypatch.setattr(Path, "write_bytes", capture_write)
    await run_export(export_module, export_context, "export_stickers_temp")
    assert not export_context.attachments
    assert "スタンプ ZIP の出力に失敗" in export_context.send.call_args.args[0]
    assert paths and all(not path.parent.exists() for path in paths)


@pytest.mark.asyncio
@pytest.mark.parametrize("fail_send", [False, True])
async def test_sticker_zip_parts_respect_limit_and_report_partial_send(
    export_module, export_context, fail_send
):
    payload = PNG + random.Random(123).randbytes(400)
    export_context.interaction = SimpleNamespace(filesize_limit=650)
    export_context.guild.fetch_stickers.return_value = [
        make_sticker(export_module, index, f"sticker{index}", payload)
        for index in range(1, 4)
    ]
    capture_send = export_context.send.side_effect

    async def send(content, *, file=None):
        if fail_send and file is not None and export_context.attachments:
            raise export_module.discord.HTTPException(
                SimpleNamespace(status=403, reason="Forbidden"), "upload denied"
            )
        await capture_send(content, file=file)

    export_context.send.side_effect = send
    await run_export(export_module, export_context, "export_stickers_temp")
    if fail_send:
        assert len(export_context.attachments) == 1
        assert "送信済み ZIP は 1 個" in export_context.send.call_args.args[0]
    else:
        assert len(export_context.attachments) > 1
    entries = {}
    for index, (filename, data, path, stream) in enumerate(
        export_context.attachments, start=1
    ):
        assert filename == f"stickers_123_{index:02d}.zip"
        assert len(data) <= 650
        with ZipFile(io.BytesIO(data)) as archive:
            entries.update({name: archive.read(name) for name in archive.namelist()})
        assert stream.closed
        assert not path.parent.exists()
    if not fail_send:
        assert len(entries) == 4
        assert all(entries[f"sticker{index}.png"] == payload for index in range(1, 4))
        assert len(json.loads(entries["_metadata/stickers.json"])) == 3
