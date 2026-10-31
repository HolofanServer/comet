"""
Discord Bot Display Name Style Cog

Botの表示名スタイル（フォント、エフェクト、カラー）をギルドごとに
管理するためのCogです。DiscordのDisplay Name Style APIを使用します。

使用方法:
    !style set <font> <effect> [colors...]
    !style list
    !style reset
"""

from typing import Optional

import aiohttp
import discord
from discord import ui
from discord.ext import commands

from config.setting import get_settings
from utils.commands_help import is_guild, is_owner
from utils.logging import setup_logging

logger = setup_logging()

class DisplayNameStyle(commands.Cog):
    """
    Botの表示名スタイルをギルドごとに管理
    https://docs.discord.food/resources/user#display-name-style-object
    """

    FONTS = {
        "default": 11,
        "bangers": 1,
        "bio_rhyme": 2,
        "biorhyme": 2,
        "cherry_bomb": 3,
        "cherrybomb": 3,
        "chicle": 4,
        "compagnon": 5,
        "museo_moderno": 6,
        "museomoderno": 6,
        "neo_castel": 7,
        "neocastel": 7,
        "pixelify": 8,
        "pixelify_sans": 8,
        "ribes": 9,
        "sinistre": 10,
        "zilla_slab": 12,
        "zillaslab": 12,
    }

    EFFECTS = {
        "solid": 1,
        "none": 1,
        "gradient": 2,
        "neon": 3,
        "toon": 4,
        "pop": 5,
        "glow": 6,
    }

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.settings = get_settings()

    @staticmethod
    def hex_to_int(hex_color: str) -> int:
        """
        16進数カラーコードを整数に変換します。

        Args:
            hex_color (str): 16進数カラーコード（例: "FFFFFF" または "#FFFFFF"）

        Returns:
            int: カラー値の整数表現
        """
        hex_color = hex_color.lstrip("#")
        return int(hex_color, 16)

    @staticmethod
    def int_to_hex(color_int: int) -> str:
        """
        整数カラー値を16進数コードに変換します。

        Args:
            color_int (int): カラー値の整数表現

        Returns:
            str: 16進数カラーコード（例: "#FFFFFF"）
        """
        return f"#{color_int:06X}"

    async def patch_member_style(
        self,
        guild_id: int,
        font_id: Optional[int] = None,
        effect_id: Optional[int] = None,
        colors: Optional[list] = None
    ) -> tuple[bool, str]:
        """
        Discord APIを使用してギルドメンバーのスタイルを更新します。

        Args:
            guild_id (int): ギルドID
            font_id (Optional[int]): フォントID (0-8)
            effect_id (Optional[int]): エフェクトID (0-4)
            colors (Optional[list]): カラーコードのリスト（整数）

        Returns:
            Tuple[bool, str]: (成功フラグ, メッセージ)
        """
        payload = {}

        if font_id is not None:
            payload["display_name_font_id"] = font_id
        if effect_id is not None:
            payload["display_name_effect_id"] = effect_id
        if colors is not None:
            payload["display_name_colors"] = colors

        headers = {
            "Authorization": f"Bot {self.bot.http.token}",
            "Content-Type": "application/json"
        }

        url = f"https://discord.com/api/v10/guilds/{guild_id}/members/@me"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.patch(url, json=payload, headers=headers) as resp:
                    if resp.status == 200:
                        return True, "スタイルを更新しました"
                    else:
                        error_text = await resp.text()
                        return False, f"HTTP {resp.status}: {error_text}"
        except Exception as e:
            return False, f"エラー: {str(e)}"

    @commands.group(name="style", invoke_without_command=True)
    @is_guild()
    @is_owner()
    async def style_group(self, ctx: commands.Context):
        """Botの表示名スタイルを管理します"""
        if ctx.invoked_subcommand is None:
            view = ui.LayoutView()
            container = ui.Container(accent_colour=discord.Color.blurple())
            container.add_item(ui.TextDisplay("# Bot表示名スタイルマネージャー"))
            container.add_item(ui.TextDisplay("ギルドごとにBotの外観をカスタマイズできます"))
            container.add_item(ui.Separator())
            container.add_item(ui.TextDisplay(
                "**使用可能なコマンド**\n"
                "`!style set <font> <effect> [colors...]` - スタイルを設定\n"
                "`!style list` - 使用可能なオプションを表示\n"
                "`!style reset` - デフォルトにリセット"
            ))
            container.add_item(ui.Separator())
            container.add_item(ui.TextDisplay("**使用例**\n`!style set pixelify neon FFFFFF FF0000`"))
            view.add_item(container)
            await ctx.send(view=view)

    @style_group.command(name="set")
    async def set_style(
        self,
        ctx: commands.Context,
        font: str,
        effect: str,
        *,
        colors: Optional[str] = None
    ):
        """
        現在のギルドでの表示名スタイルを設定します。

        Args:
            font (str): フォント名（例: pixelify, bangers, cherry_bomb）
            effect (str): エフェクト名（例: neon, gradient, solid, glow）
            colors (Optional[str]): スペース区切りの16進数カラーコード（最大2色）

        使用例:
            !style set pixelify neon FFFFFF FF0000
            !style set bangers gradient 00FF00
        """
        font_lower = font.lower()
        if font_lower in self.FONTS:
            font_id = self.FONTS[font_lower]
        else:
            try:
                font_id = int(font)
                if not (1 <= font_id <= 12):
                    await ctx.send(f"❌ フォントIDは1から12の間である必要があります（入力値: {font_id}）")
                    return
            except ValueError:
                await ctx.send(f"❌ 不明なフォント: `{font}`\n`!style list` でオプションを確認してください")
                return

        effect_lower = effect.lower()
        if effect_lower in self.EFFECTS:
            effect_id = self.EFFECTS[effect_lower]
        else:
            try:
                effect_id = int(effect)
                if not (1 <= effect_id <= 6):
                    await ctx.send(f"❌ エフェクトIDは1から6の間である必要があります（入力値: {effect_id}）")
                    return
            except ValueError:
                await ctx.send(f"❌ 不明なエフェクト: `{effect}`\n`!style list` でオプションを確認してください")
                return

        color_list = []
        if colors:
            for color_code in colors.split():
                try:
                    color_int = self.hex_to_int(color_code)
                    color_list.append(color_int)
                except ValueError:
                    await ctx.send(f"❌ 無効なカラーコード: `{color_code}`")
                    return
        else:
            color_list = [16777215]

        success, message = await self.patch_member_style(
            ctx.guild.id,
            font_id=font_id,
            effect_id=effect_id,
            colors=color_list
        )

        if success:
            color_hex_display = " → ".join(
                [self.int_to_hex(c) for c in color_list]
            ) if colors else "#FFFFFF"

            view = ui.LayoutView()
            container = ui.Container(accent_colour=discord.Color.green())
            container.add_item(ui.TextDisplay("# ✅ スタイルを更新しました"))
            container.add_item(ui.Separator())
            container.add_item(ui.TextDisplay(
                f"**フォント:** {font.lower()}\n"
                f"**エフェクト:** {effect.lower()}\n"
                f"**カラー:** {color_hex_display}"
            ))
            view.add_item(container)
            await ctx.send(view=view)
        else:
            view = ui.LayoutView()
            container = ui.Container(accent_colour=discord.Color.red())
            container.add_item(ui.TextDisplay("# ❌ スタイルの更新に失敗しました"))
            container.add_item(ui.Separator())
            container.add_item(ui.TextDisplay(message))
            view.add_item(container)
            await ctx.send(view=view)

    @style_group.command(name="list")
    async def list_options(self, ctx: commands.Context):
        """使用可能なフォントとエフェクトを表示します"""
        fonts_str = ", ".join(f"`{k}`" for k in sorted(self.FONTS.keys()))
        effects_str = ", ".join(f"`{k}`" for k in sorted(self.EFFECTS.keys()))

        view = ui.LayoutView()
        container = ui.Container(accent_colour=discord.Color.blurple())
        container.add_item(ui.TextDisplay("# 使用可能な表示名スタイル"))
        container.add_item(ui.Separator())
        container.add_item(ui.TextDisplay(f"**フォント**\n{fonts_str}"))
        container.add_item(ui.Separator())
        container.add_item(ui.TextDisplay(f"**エフェクト**\n{effects_str}"))
        container.add_item(ui.Separator())
        container.add_item(ui.TextDisplay(
            "**カラー形式**\n16進数コード（例: `FFFFFF`, `FF0000`, `00FF00`）\n\n"
            "**使用例**\n`!style set pixelify neon FFFFFF FF0000`\n\n"
            "-# カラーは最大2色まで指定可能です"
        ))
        view.add_item(container)
        await ctx.send(view=view)

    @style_group.command(name="reset")
    async def reset_style(self, ctx: commands.Context):
        """表示名スタイルをデフォルトにリセットします"""
        success, message = await self.patch_member_style(
            ctx.guild.id,
            font_id=None,
            effect_id=None,
            colors=None
        )

        if success:
            view = ui.LayoutView()
            container = ui.Container(accent_colour=discord.Color.green())
            container.add_item(ui.TextDisplay("# ✅ スタイルをリセットしました"))
            container.add_item(ui.Separator())
            container.add_item(ui.TextDisplay("Botの表示名スタイルがデフォルトに戻りました"))
            view.add_item(container)
            await ctx.send(view=view)
        else:
            view = ui.LayoutView()
            container = ui.Container(accent_colour=discord.Color.red())
            container.add_item(ui.TextDisplay("# ❌ スタイルのリセットに失敗しました"))
            container.add_item(ui.Separator())
            container.add_item(ui.TextDisplay(message))
            view.add_item(container)
            await ctx.send(view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(DisplayNameStyle(bot))
