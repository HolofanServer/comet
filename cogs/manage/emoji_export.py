"""絵文字・スタンプの移行作業が終わったら Cog ごと削除できる一時コマンド。"""

import asyncio
import json
import re
import unicodedata
from collections import Counter
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from utils.logging import logger


def _image_extension(data: bytes) -> str:
    # discord.py のバージョンによってアニメ絵文字は GIF または WebP になる。
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "gif"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "webp"
    raise ValueError("取得した絵文字の画像形式を判別できませんでした。")


async def _download_emojis(
    emojis: list[discord.Emoji], directory: Path
) -> list[tuple[Path, str]]:
    names = Counter(emoji.name.casefold() for emoji in emojis)
    entries = []
    for emoji in emojis:
        data = await asyncio.wait_for(emoji.read(), timeout=30)
        filename = f"{emoji.name}.{_image_extension(data)}"
        # 大文字小文字を区別しない環境でも、同名画像を上書きさせない。
        archive_name = (
            f"{emoji.id}/{filename}" if names[emoji.name.casefold()] > 1 else filename
        )
        path = directory / str(emoji.id)
        await asyncio.to_thread(path.write_bytes, data)
        entries.append((path, archive_name))
    return entries


def _sticker_basename(name: str) -> str:
    # スタンプ名は絵文字より自由なので、展開先OSの禁止文字とパスを除く。
    name = unicodedata.normalize("NFC", name)
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f\x7f]', "_", name).strip(" .")
    if not name:
        return "sticker"
    if re.fullmatch(r"CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9]", name.split(".")[0], re.I):
        name = f"_{name}"
    return name


async def _download_stickers(
    stickers: list[discord.GuildSticker], directory: Path
) -> list[tuple[Path, str]]:
    basenames = [_sticker_basename(sticker.name) for sticker in stickers]
    names = Counter(name.casefold() for name in basenames)
    entries = []
    metadata = []
    for sticker, name in zip(stickers, basenames):
        if sticker.format == discord.StickerFormatType.lottie:
            # discord.py の read() は Lottie を拒否するため公開CDNから取得する。
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30)
            ) as session:
                async with session.get(
                    f"https://cdn.discordapp.com/stickers/{sticker.id}.json"
                ) as response:
                    response.raise_for_status()
                    data = await response.read()
            if not isinstance(json.loads(data), dict):
                raise ValueError("スタンプの Lottie JSON が不正です。")
            extension = "json"
        else:
            data = await asyncio.wait_for(sticker.read(), timeout=30)
            extension = _image_extension(data)
        filename = f"{name}.{extension}"
        archive_name = (
            f"{sticker.id}/{filename}" if names[name.casefold()] > 1 else filename
        )
        path = directory / str(sticker.id)
        await asyncio.to_thread(path.write_bytes, data)
        entries.append((path, archive_name))
        metadata.append(
            {
                "id": str(sticker.id),
                "name": sticker.name,
                "description": sticker.description,
                "emoji": sticker.emoji,
                "format": sticker.format.name,
                "file": archive_name,
            }
        )
    path = directory / "stickers.json"
    await asyncio.to_thread(
        path.write_text,
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    entries.append((path, "_metadata/stickers.json"))
    return entries


def _build_archives(
    entries: list[tuple[Path, str]], directory: Path, size_limit: int
) -> list[Path]:
    """ZIP のヘッダーも含む実サイズで分割し、各 ZIP を単独で展開可能にする。"""
    archives = []

    def pack(batch: list[tuple[Path, str]]) -> None:
        path = directory / f"emojis_{len(archives) + 1}.zip"
        with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
            for source, name in batch:
                archive.write(source, arcname=name)
        if path.stat().st_size <= size_limit:
            archives.append(path)
            return
        path.unlink()
        if len(batch) == 1:
            raise ValueError("ファイル1個の ZIP が添付上限を超えるため送信できません。")
        middle = len(batch) // 2
        pack(batch[:middle])
        pack(batch[middle:])

    if entries:
        pack(entries)
    return archives


class EmojiExport(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(
        name="export_emojis_temp",
        description="m_ 以外のサーバー絵文字を名前を保持した ZIP で送信（一時用）",
    )
    @commands.guild_only()
    @commands.has_guild_permissions(administrator=True)
    @commands.bot_has_permissions(attach_files=True)
    @commands.max_concurrency(1, per=commands.BucketType.guild, wait=False)
    @app_commands.default_permissions(administrator=True)
    async def export_emojis_temp(self, ctx: commands.Context) -> None:
        await self._export(ctx, stickers=False)

    @commands.hybrid_command(
        name="export_stickers_temp",
        description="サーバーのスタンプを元の形式と名前を保持した ZIP で送信（一時用）",
    )
    @commands.guild_only()
    @commands.has_guild_permissions(administrator=True)
    @commands.bot_has_permissions(attach_files=True)
    @commands.max_concurrency(1, per=commands.BucketType.guild, wait=False)
    @app_commands.default_permissions(administrator=True)
    async def export_stickers_temp(self, ctx: commands.Context) -> None:
        await self._export(ctx, stickers=True)

    async def _export(self, ctx: commands.Context, *, stickers: bool) -> None:
        await ctx.defer()
        guild = ctx.guild
        # guild_only に加えて型と直接呼び出し時の前提を明示する。
        if guild is None:
            await ctx.send("このコマンドはサーバー内で実行してください。")
            return

        label = "スタンプ" if stickers else "絵文字"
        prefix = "stickers" if stickers else "emojis"
        sent = 0
        with TemporaryDirectory(prefix=f"comet-{prefix}-export-") as temporary:
            directory = Path(temporary)
            try:
                if stickers:
                    assets = await guild.fetch_stickers()
                else:
                    assets = [
                        emoji
                        for emoji in await guild.fetch_emojis()
                        if not emoji.name.startswith("m_")
                    ]
                if not assets:
                    await ctx.send(
                        "サーバーのスタンプはありません。"
                        if stickers
                        else "m_ から始まるもの以外のサーバー絵文字はありません。"
                    )
                    return

                size_limit = min(
                    guild.filesize_limit,
                    getattr(ctx.interaction, "filesize_limit", guild.filesize_limit),
                )
                download = _download_stickers if stickers else _download_emojis
                entries = await asyncio.wait_for(
                    download(assets, directory), timeout=600
                )
                archives = await asyncio.to_thread(
                    _build_archives, entries, directory, size_limit
                )
                for index, path in enumerate(archives, start=1):
                    suffix = f"_{index:02d}" if len(archives) > 1 else ""
                    with closing(
                        discord.File(path, filename=f"{prefix}_{guild.id}{suffix}.zip")
                    ) as attachment:
                        await ctx.send(
                            f"{'スタンプ' if stickers else 'm_ 以外の絵文字'}: "
                            f"合計 {len(assets)} 個 "
                            f"（ZIP {index}/{len(archives)}）",
                            file=attachment,
                        )
                    sent += 1
            except (
                discord.HTTPException,
                aiohttp.ClientError,
                asyncio.TimeoutError,
                OSError,
                ValueError,
            ):
                logger.exception("%s ZIP の出力に失敗: guild_id=%s", label, guild.id)
                await ctx.send(
                    f"{label} ZIP の出力に失敗しました。"
                    f"送信済み ZIP は {sent} 個です。全件の出力は完了していません。"
                    "添付上限・Bot の権限・ログを確認して再実行してください。"
                )
                return

        logger.info(
            "%s ZIP を送信: guild_id=%s assets=%s archives=%s",
            label,
            guild.id,
            len(assets),
            sent,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(EmojiExport(bot))
