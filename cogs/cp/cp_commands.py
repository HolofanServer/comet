"""
Checkpoint コマンド

/checkpoint と /checkpoint-rankings を実装
"""
from datetime import date

import discord
from discord import app_commands
from discord.ext import commands

from utils.cv2 import (
    ComponentsV2Message,
    Container,
    Section,
    Separator,
    SeparatorSpacing,
    send_components_v2_followup,
)
from utils.logging import setup_logging

from .db import checkpoint_db
from .stats import checkpoint_stats

logger = setup_logging(__name__)

# カラー定義
COLOR_CHECKPOINT = 0x8B5CF6  # Purple
COLOR_GOLD = 0xFFD700  # Gold


class CheckpointCommands(commands.Cog):
    """Checkpointコマンド"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _format_vc_time(self, seconds: int) -> str:
        """VC時間をフォーマット"""
        if seconds < 60:
            return f"{seconds}秒"
        elif seconds < 3600:
            return f"{seconds // 60}分"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours}時間{minutes}分"

    def _format_emoji(self, emoji_data: dict) -> str:
        """絵文字をフォーマット"""
        if emoji_data.get("id"):
            animated = "a" if emoji_data.get("animated") else ""
            return f"<{animated}:{emoji_data['name']}:{emoji_data['id']}>"
        return emoji_data["name"]

    async def _get_username(self, user_id: int) -> str:
        """ユーザー名を取得"""
        try:
            user = await self.bot.fetch_user(user_id)
            return user.display_name
        except Exception:
            return f"User#{user_id}"

    @app_commands.command(name="checkpoint", description="あなたの活動統計を表示します")
    @app_commands.describe(
        user="統計を表示するユーザー（省略時は自分）",
        year="対象年（省略時は今年）",
    )
    async def checkpoint(
        self,
        interaction: discord.Interaction,
        user: discord.User | None = None,
        year: int | None = None,
    ):
        """ユーザーの活動統計を表示"""
        await interaction.response.defer()

        target_user = user or interaction.user
        target_year = year or date.today().year

        if not checkpoint_db._initialized:
            await interaction.followup.send(
                "❌ 統計システムが利用できません", ephemeral=True
            )
            return

        # 統計取得
        stats = await checkpoint_stats.get_user_stats(
            target_user.id, interaction.guild_id, target_year
        )

        if not stats:
            await interaction.followup.send(
                f"📊 {target_user.display_name} さんの {target_year}年 の統計データがありません",
                ephemeral=True,
            )
            return

        # 絵文字統計
        top_emojis = await checkpoint_stats.get_top_emojis(
            target_user.id, interaction.guild_id, limit=5
        )

        # メンション相関
        mention_network = await checkpoint_stats.get_mention_network(
            target_user.id, interaction.guild_id, limit=3
        )

        # Components V2メッセージ作成
        msg = ComponentsV2Message()
        container = Container(color=COLOR_CHECKPOINT)

        # ヘッダー
        header_section = (
            Section()
            .add_text(f"# {target_user.display_name}")
            .add_text(f"📊 {target_year}年 活動統計")
            .set_thumbnail(target_user.display_avatar.url)
        )
        container.add(header_section)
        container.add_separator()

        # メイン統計（グリッド風）
        container.add_text(
            f"💬 **メッセージ** {stats.total_messages:,} 件　　"
            f"🎉 **リアクション** {stats.total_reactions:,} 回　　"
            f"🎤 **VC** {self._format_vc_time(stats.total_vc_seconds)}"
        )
        container.add_text(
            f"📢 **メンション送信** {stats.total_mentions_sent:,} 回　　"
            f"📥 **メンション受信** {stats.total_mentions_received:,} 回　　"
            f"🎲 **おみくじ** {stats.total_omikuji:,} 回"
        )

        # よく使う絵文字
        if top_emojis:
            container.add(Separator(divider=False, spacing=SeparatorSpacing.SMALL))
            emoji_text = " ".join(
                f"{self._format_emoji(e)}×{e['count']}" for e in top_emojis[:5]
            )
            container.add_text(f"⭐ **よく使う絵文字**\n{emoji_text}")

        # メンション相関
        if mention_network["sent_to"]:
            container.add(Separator(divider=False, spacing=SeparatorSpacing.SMALL))
            sent_names = []
            for m in mention_network["sent_to"][:3]:
                name = await self._get_username(m["user_id"])
                sent_names.append(f"{name}({m['count']})")
            container.add_text(f"💬 **よくメンションする人**\n{', '.join(sent_names)}")

        # フッター
        container.add(Separator(divider=False, spacing=SeparatorSpacing.SMALL))
        container.add_text("-# HFS Checkpoint 2026")

        msg.add(container)

        await send_components_v2_followup(interaction, msg)

    @app_commands.command(
        name="checkpoint-rankings", description="サーバー内のランキングを表示します"
    )
    @app_commands.describe(
        category="ランキングのカテゴリ",
        year="対象年（省略時は今年）",
    )
    @app_commands.choices(
        category=[
            app_commands.Choice(name="💬 メッセージ数", value="messages"),
            app_commands.Choice(name="🎉 リアクション数", value="reactions"),
            app_commands.Choice(name="🎤 VC時間", value="vc"),
            app_commands.Choice(name="📢 メンション送信", value="mentions_sent"),
            app_commands.Choice(name="📥 メンション受信", value="mentions_received"),
            app_commands.Choice(name="🎲 おみくじ回数", value="omikuji"),
        ]
    )
    async def checkpoint_rankings(
        self,
        interaction: discord.Interaction,
        category: str,
        year: int | None = None,
    ):
        """ランキングを表示"""
        await interaction.response.defer()

        target_year = year or date.today().year

        if not checkpoint_db._initialized:
            await interaction.followup.send(
                "❌ 統計システムが利用できません", ephemeral=True
            )
            return

        rankings = await checkpoint_stats.get_rankings(
            interaction.guild_id, category, target_year, limit=10
        )

        if not rankings:
            await interaction.followup.send(
                f"📊 {target_year}年 の {category} ランキングデータがありません",
                ephemeral=True,
            )
            return

        # カテゴリ名マッピング
        category_names = {
            "messages": "💬 メッセージ数",
            "reactions": "🎉 リアクション数",
            "vc": "🎤 VC時間",
            "mentions_sent": "📢 メンション送信",
            "mentions_received": "📥 メンション受信",
            "omikuji": "🎲 おみくじ回数",
        }

        # Components V2メッセージ作成
        msg = ComponentsV2Message()
        container = Container(color=COLOR_GOLD)

        container.add_text(f"# 🏆 {target_year}年 {category_names.get(category, category)} ランキング")
        container.add_separator()

        # ランキング表示
        medals = ["🥇", "🥈", "🥉"]
        ranking_lines = []

        for entry in rankings:
            name = await self._get_username(entry.user_id)
            medal = medals[entry.rank - 1] if entry.rank <= 3 else f"`{entry.rank}.`"

            if category == "vc":
                value_text = f"**{self._format_vc_time(entry.value)}**"
            else:
                value_text = f"**{entry.value:,}**"

            ranking_lines.append(f"{medal} {name} — {value_text}")

        container.add_text("\n".join(ranking_lines))

        # フッター
        container.add(Separator(divider=False, spacing=SeparatorSpacing.SMALL))
        container.add_text("-# HFS Checkpoint 2026")

        msg.add(container)

        await send_components_v2_followup(interaction, msg)


async def setup(bot: commands.Bot):
    """Cog setup"""
    await bot.add_cog(CheckpointCommands(bot))
