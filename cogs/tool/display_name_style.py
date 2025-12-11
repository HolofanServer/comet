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
from discord.ext import commands

from config.setting import get_settings
from utils.commands_help import is_guild, is_owner
from utils.logging import setup_logging

logger = setup_logging()

class DisplayNameStyle(commands.Cog):
    """Botの表示名スタイルをギルドごとに管理します"""

    # フォントIDマッピング
    FONTS = {
        "default": 0,
        "gg_sans": 0,
        "jujisands": 1,
        "tempo": 2,
        "sakura": 3,
        "jellybean": 4,
        "modern": 5,
        "medieval": 6,
        "8bit": 7,
        "vampire": 8,
    }

    # エフェクトIDマッピング
    EFFECTS = {
        "solid": 0,
        "none": 0,
        "gradient": 1,
        "neon": 2,
        "toon": 3,
        "pop": 4,
    }

    def __init__(self, bot: commands.Bot):
        """
        DisplayNameStyle Cogを初期化します。

        Args:
            bot (commands.Bot): Botインスタンス
        """
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
            embed = discord.Embed(
                title="Bot表示名スタイルマネージャー",
                description="ギルドごとにBotの外観をカスタマイズできます",
                color=discord.Color.blurple()
            )
            embed.add_field(
                name="使用可能なコマンド",
                value="""
                `!style set <font> <effect> [colors...]` - スタイルを設定
                `!style list` - 使用可能なオプションを表示
                `!style reset` - デフォルトにリセット
                """,
                inline=False
            )
            embed.add_field(
                name="使用例",
                value="`!style set sakura neon FFFFFF FF0000`",
                inline=False
            )
            await ctx.send(embed=embed)

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
            font (str): フォント名（例: sakura, modern, 8bit）
            effect (str): エフェクト名（例: neon, gradient, solid）
            colors (Optional[str]): スペース区切りの16進数カラーコード

        使用例:
            !style set sakura neon FFFFFF FF0000
            !style set modern gradient 00FF00
        """
        # フォントIDを解析
        font_lower = font.lower()
        if font_lower in self.FONTS:
            font_id = self.FONTS[font_lower]
        else:
            try:
                font_id = int(font)
                if not (0 <= font_id <= 8):
                    await ctx.send(f"❌ フォントIDは0から8の間である必要があります（入力値: {font_id}）")
                    return
            except ValueError:
                await ctx.send(f"❌ 不明なフォント: `{font}`\n`!style list` でオプションを確認してください")
                return

        # エフェクトIDを解析
        effect_lower = effect.lower()
        if effect_lower in self.EFFECTS:
            effect_id = self.EFFECTS[effect_lower]
        else:
            try:
                effect_id = int(effect)
                if not (0 <= effect_id <= 4):
                    await ctx.send(f"❌ エフェクトIDは0から4の間である必要があります（入力値: {effect_id}）")
                    return
            except ValueError:
                await ctx.send(f"❌ 不明なエフェクト: `{effect}`\n`!style list` でオプションを確認してください")
                return

        # カラーを解析
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
            # デフォルトは白
            color_list = [16777215]

        # APIリクエストを送信
        success, message = await self.patch_member_style(
            ctx.guild.id,
            font_id=font_id,
            effect_id=effect_id,
            colors=color_list
        )

        if success:
            # カラー表示をフォーマット
            color_hex_display = " → ".join(
                [self.int_to_hex(c) for c in color_list]
            ) if colors else "#FFFFFF"

            embed = discord.Embed(
                title="✅ スタイルを更新しました",
                color=discord.Color.green()
            )
            embed.add_field(name="フォント", value=font.lower(), inline=True)
            embed.add_field(name="エフェクト", value=effect.lower(), inline=True)
            embed.add_field(name="カラー", value=color_hex_display, inline=False)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="❌ スタイルの更新に失敗しました",
                description=message,
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)

    @style_group.command(name="list")
    async def list_options(self, ctx: commands.Context):
        """使用可能なフォントとエフェクトを表示します"""
        fonts_str = ", ".join(f"`{k}`" for k in sorted(self.FONTS.keys()))
        effects_str = ", ".join(f"`{k}`" for k in sorted(self.EFFECTS.keys()))

        embed = discord.Embed(
            title="使用可能な表示名スタイル",
            color=discord.Color.blurple()
        )
        embed.add_field(
            name="フォント",
            value=fonts_str,
            inline=False
        )
        embed.add_field(
            name="エフェクト",
            value=effects_str,
            inline=False
        )
        embed.add_field(
            name="カラー形式",
            value="16進数コード（例: `FFFFFF`, `FF0000`, `00FF00`）",
            inline=False
        )
        embed.add_field(
            name="使用例",
            value="`!style set sakura neon FFFFFF FF0000`",
            inline=False
        )

        await ctx.send(embed=embed)

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
            embed = discord.Embed(
                title="✅ スタイルをリセットしました",
                description="Botの表示名スタイルがデフォルトに戻りました",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="❌ スタイルのリセットに失敗しました",
                description=message,
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    """Cogをロードします"""
    await bot.add_cog(DisplayNameStyle(bot))
