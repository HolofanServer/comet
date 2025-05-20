# -*- coding: utf-8 -*-
"""cogs.cv2_demo_cog – granular examples for utils.future.cv2

This Cog provides **separate commands** to exercise each major helper in
``utils.future.cv2`` (Components V2).

Commands
========
``cv2panel``   — simple container with title / select / buttons
``cv2media``   — media‑gallery container for a given image URL
``cv2file``    — uploads a local spoiler image as FILE component
``cv2section`` — SECTION block with accessory button
``cv2colors``  — preview the accent colours used by ``container()``
"""
from __future__ import annotations

import pathlib
from typing import Final

from discord.ext import commands

from utils.future.cv2 import cv2

# ---------------------------------------------------------------------------
# constants
# ---------------------------------------------------------------------------

LOCAL_DEMO_IMG: Final[pathlib.Path] = pathlib.Path(__file__).with_suffix(".png")


# ---------------------------------------------------------------------------
# Cog implementation
# ---------------------------------------------------------------------------

class CV2Demo(commands.Cog):
    """Demonstrates the CV2 helper via standalone text commands."""

    def __init__(self, bot: commands.Bot) -> None:  # noqa: D401 – simple init
        self.bot = bot
        self.bot.loop.create_task(self._lazy_init_cv2())

    # ------------------------------------------------------------------
    # internal helpers
    # ------------------------------------------------------------------

    async def _lazy_init_cv2(self) -> None:
        if not cv2.is_ready:
            await cv2.initialize(self.bot)

    # ------------------------------------------------------------------
    # 1) container with title / text / select / buttons -----------------
    # ------------------------------------------------------------------

    @commands.command(name="cv2panel")
    async def send_demo_panel(self, ctx: commands.Context) -> None:
        """Send a basic panel demonstrating title / select / buttons."""
        components = [
            cv2.title("推しロール選択"),
            cv2.text("あなたの推しメンバーを選んでください！"),
            cv2.line(),
            cv2.select(
                "member_select",
                [
                    ("ホロ星人A", "a", "可愛い", "🌟"),
                    ("ホロ星人B", "b", "カッコいい", "💫"),
                ],
                placeholder="メンバーを選択",
            ),
            cv2.line(spacing=2),
            cv2.row(
                [
                    cv2.button("決定", custom_id="confirm_btn", style="success", emoji="✅"),
                    cv2.button("キャンセル", custom_id="cancel_btn", style="danger", emoji="✖"),
                ]
            ),
        ]
        await cv2.send(ctx.channel.id, components=components)

    # ------------------------------------------------------------------
    # 2) Media Gallery ---------------------------------------------------
    # ------------------------------------------------------------------

    @commands.command(name="cv2media")
    async def send_media_gallery(self, ctx: commands.Context, url: str) -> None:
        """Send a media‑gallery container for the given *url*."""
        await cv2.send(ctx.channel.id, media_urls=[url])

    # ------------------------------------------------------------------
    # 3) FILE component upload -----------------------------------------
    # ------------------------------------------------------------------

    @commands.command(name="cv2file")
    async def send_file_component(self, ctx: commands.Context) -> None:
        """Upload *LOCAL_DEMO_IMG* as a FILE component (spoiler)."""
        if not LOCAL_DEMO_IMG.exists():
            await ctx.reply("デモ画像 (cv2_demo_cog.png) が見つかりません。")
            return
        image_bytes = LOCAL_DEMO_IMG.read_bytes()
        await cv2.send(
            ctx.channel.id,
            file_bytes=image_bytes,
            file_name=LOCAL_DEMO_IMG.name,
            spoiler_file=True,
        )

    # ------------------------------------------------------------------
    # 4) SECTION component ---------------------------------------------
    # ------------------------------------------------------------------

    @commands.command(name="cv2section")
    async def send_section(self, ctx: commands.Context) -> None:
        """Demonstrate a SECTION block with an accessory button."""
        # セクションコンポーネントを作成
        section_comp = cv2.section(
            [
                "**お知らせ**",
                "CV2 の SECTION はテキスト 3 行まで配置できます。",
                "アクセサリとしてボタンや画像を付けることも可能！",
            ],
            accessory=cv2.button("了解", custom_id="section_ok", style="primary", emoji="👌"),
        )
        # セクションコンポーネントをコンテナーでラップして送信
        await cv2.send(ctx.channel.id, components=[cv2.container([section_comp])])

    # ------------------------------------------------------------------
    # 5) Accent‑colour preview -----------------------------------------
    # ------------------------------------------------------------------

    @commands.command(name="cv2colors")
    async def send_random_colours(self, ctx: commands.Context) -> None:
        """Preview the accent colours used by ``container()``."""
        containers = [
            cv2.container([cv2.text(f"accent_color = 0x{col:06X}")], accent_color=col)
            for col in cv2._ACCENT_COLOURS  # access is intentional for demo only
        ]
        await cv2.send(ctx.channel.id, components=containers)

    # ------------------------------------------------------------------
    # interaction listener – simple echo for confirm / cancel -----------
    # ------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_interaction(self, interaction) -> None:
        if not interaction.data or "custom_id" not in interaction.data:
            return

        cid: str = interaction.data["custom_id"]
        if cid == "confirm_btn":
            await cv2.reply(
                interaction,
                components=[cv2.title("ありがとう！"), cv2.text("ロール設定を保存しました。")],
                ephemeral=True,
            )
        elif cid == "cancel_btn":
            await cv2.reply(
                interaction,
                components=[cv2.title("キャンセルしました"), cv2.text("またいつでもやり直せます。")],
                ephemeral=True,
            )
        elif cid == "section_ok":
            await cv2.reply(interaction, components=[cv2.text("了解済み！")], ephemeral=True)


# ---------------------------------------------------------------------------
# setup entry‑point
# ---------------------------------------------------------------------------

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CV2Demo(bot))
