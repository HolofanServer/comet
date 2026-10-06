"""絵文字の移行作業が終わったら Cog ごと削除できる一時コマンド。"""

import asyncio
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
            raise ValueError("絵文字1個の ZIP が添付上限を超えるため送信できません。")
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
        await ctx.defer()
        guild = ctx.guild
        # guild_only に加えて型と直接呼び出し時の前提を明示する。
        if guild is None:
            await ctx.send("このコマンドはサーバー内で実行してください。")
            return

        sent = 0
        with TemporaryDirectory(prefix="comet-emoji-export-") as temporary:
            directory = Path(temporary)
            try:
                emojis = [
                    emoji
                    for emoji in await guild.fetch_emojis()
                    if not emoji.name.startswith("m_")
                ]
                if not emojis:
                    await ctx.send(
                        "m_ から始まるもの以外のサーバー絵文字はありません。"
                    )
                    return

                size_limit = min(
                    guild.filesize_limit,
                    getattr(ctx.interaction, "filesize_limit", guild.filesize_limit),
                )
                entries = await asyncio.wait_for(
                    _download_emojis(emojis, directory), timeout=600
                )
                archives = await asyncio.to_thread(
                    _build_archives, entries, directory, size_limit
                )
                for index, path in enumerate(archives, start=1):
                    suffix = f"_{index:02d}" if len(archives) > 1 else ""
                    with closing(
                        discord.File(path, filename=f"emojis_{guild.id}{suffix}.zip")
                    ) as attachment:
                        await ctx.send(
                            f"m_ 以外の絵文字: 合計 {len(emojis)} 個 "
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
                logger.exception("絵文字 ZIP の出力に失敗: guild_id=%s", guild.id)
                await ctx.send(
                    "絵文字 ZIP の出力に失敗しました。"
                    f"送信済み ZIP は {sent} 個です。全件の出力は完了していません。"
                    "添付上限・Bot の権限・ログを確認して再実行してください。"
                )
                return

        logger.info(
            "絵文字 ZIP を送信: guild_id=%s emojis=%s archives=%s",
            guild.id,
            len(emojis),
            sent,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(EmojiExport(bot))
