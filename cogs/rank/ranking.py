"""
HFS Rank コマンド

/rank, /rank top などのコマンドを実装
"""
import discord
from discord import app_commands
from discord.ext import commands

from utils.commands_help import is_guild_app, is_moderator_app
from utils.cv2 import (
    ComponentsV2Message,
    Container,
    Section,
    Separator,
    SeparatorSpacing,
    send_components_v2_followup,
)
from utils.logging import setup_logging

from .models import rank_db

logger = setup_logging(__name__)

# カラー定義
COLOR_RANK = 0x5865F2  # Discord Blurple
COLOR_REGULAR = 0x57F287  # Green
COLOR_GOLD = 0xFFD700  # Gold
COLOR_SETTINGS = 0x5865F2  # Settings blue


class RankCommands(commands.Cog):
    """Rankコマンド"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _format_xp(self, xp: int) -> str:
        """XPをフォーマット"""
        if xp >= 1000:
            return f"{xp:,}"
        return str(xp)

    def _get_level_progress(self, xp: int, level: int) -> tuple[int, int]:
        """現在レベルの進捗を取得 (current, required)"""
        thresholds = rank_db._level_thresholds
        current_req = 0
        next_req = 0

        for lv, req in thresholds:
            if lv == level:
                current_req = req
            elif lv == level + 1:
                next_req = req
                break

        if next_req == 0:
            next_req = current_req + 10000  # 最大レベル超えた場合

        progress = xp - current_req
        required = next_req - current_req
        return progress, required

    async def _get_username(self, user_id: int) -> str:
        """ユーザー名を取得"""
        try:
            user = await self.bot.fetch_user(user_id)
            return user.display_name
        except Exception:
            return f"User#{user_id}"

    def _create_progress_bar(self, pct: int, length: int = 12) -> str:
        """プログレスバーを作成"""
        filled = int(length * pct / 100)
        empty = length - filled
        return "▓" * filled + "░" * empty

    @app_commands.command(name="rank", description="あなたのランクを表示します")
    @app_commands.describe(user="ランクを表示するユーザー（省略時は自分）")
    @is_guild_app()
    async def rank(self, interaction: discord.Interaction, user: discord.User | None = None):
        """ランクを表示"""
        await interaction.response.defer()

        target_user = user or interaction.user
        rank_user = await rank_db.get_user(target_user.id, interaction.guild_id)

        if not rank_user:
            await interaction.followup.send(
                f"📊 {target_user.display_name} さんのランクデータがありません",
                ephemeral=True,
            )
            return

        # 順位取得
        user_rank = await rank_db.get_user_rank(target_user.id, interaction.guild_id)

        # レベル進捗
        progress, required = self._get_level_progress(rank_user.yearly_xp, rank_user.current_level)
        progress_pct = min(100, int((progress / required) * 100)) if required > 0 else 100
        progress_bar = self._create_progress_bar(progress_pct)

        # カラー決定
        color = COLOR_REGULAR if rank_user.is_regular else COLOR_RANK

        # Components V2メッセージ作成
        msg = ComponentsV2Message()

        container = Container(color=color)

        # ヘッダー（ユーザー名 + アバター）
        header_section = (
            Section()
            .add_text(f"# {target_user.display_name}")
            .add_text(f"{'🎖️ 常連メンバー' if rank_user.is_regular else '📊 HFS Rank'}")
            .set_thumbnail(target_user.display_avatar.url)
        )
        container.add(header_section)
        container.add_separator()

        # メイン統計
        rank_text = f"#{user_rank}" if user_rank else "N/A"
        container.add_text(
            f"🏆 **順位** {rank_text}　　"
            f"⭐ **Lv.{rank_user.current_level}**　　"
            f"✨ **{self._format_xp(rank_user.yearly_xp)} XP**"
        )

        # プログレスバー
        container.add(Separator(divider=False, spacing=SeparatorSpacing.SMALL))
        container.add_text(
            f"**次のレベルまで**\n"
            f"`{progress_bar}` **{progress_pct}%**\n"
            f"-# {self._format_xp(progress)} / {self._format_xp(required)} XP"
        )

        container.add_separator()

        # サブ統計
        container.add_text(
            f"📅 アクティブ日数: **{rank_user.active_days}日**\n"
            f"🌟 通算XP: **{self._format_xp(rank_user.lifetime_xp)}**"
        )

        # フッター
        container.add(Separator(divider=False, spacing=SeparatorSpacing.SMALL))
        container.add_text("-# HFS Rank System")

        msg.add(container)

        await send_components_v2_followup(interaction, msg)

    @app_commands.command(name="ranktop", description="XPランキングを表示します")
    @app_commands.describe(category="ランキングのカテゴリ")
    @is_guild_app()
    @app_commands.choices(
        category=[
            app_commands.Choice(name="✨ 今年のXP", value="yearly_xp"),
            app_commands.Choice(name="🌟 通算XP", value="lifetime_xp"),
            app_commands.Choice(name="📅 アクティブ日数", value="active_days"),
        ]
    )
    async def ranktop(
        self,
        interaction: discord.Interaction,
        category: str = "yearly_xp",
    ):
        """ランキングを表示"""
        await interaction.response.defer()

        rankings = await rank_db.get_rankings(interaction.guild_id, 10, category)

        if not rankings:
            await interaction.followup.send(
                "📊 ランキングデータがありません",
                ephemeral=True,
            )
            return

        # カテゴリ名マッピング
        category_names = {
            "yearly_xp": "✨ 今年のXP ランキング",
            "lifetime_xp": "🌟 通算XP ランキング",
            "active_days": "📅 アクティブ日数 ランキング",
        }

        # Components V2メッセージ作成
        msg = ComponentsV2Message()
        container = Container(color=COLOR_GOLD)

        container.add_text(f"# 🏆 {category_names.get(category, category)}")
        container.add_separator()

        # ランキング表示
        medals = ["🥇", "🥈", "🥉"]
        ranking_lines = []

        for i, u in enumerate(rankings):
            name = await self._get_username(u.user_id)
            medal = medals[i] if i < 3 else f"`{i + 1}.`"

            if category == "active_days":
                value_text = f"**{u.active_days}**日"
            elif category == "lifetime_xp":
                value_text = f"**{self._format_xp(u.lifetime_xp)}** XP"
            else:
                value_text = f"**{self._format_xp(u.yearly_xp)}** XP"

            ranking_lines.append(f"{medal} {name} `Lv.{u.current_level}` — {value_text}")

        container.add_text("\n".join(ranking_lines))

        # フッター
        container.add(Separator(divider=False, spacing=SeparatorSpacing.SMALL))
        container.add_text("-# HFS Rank System")

        msg.add(container)

        await send_components_v2_followup(interaction, msg)

    @app_commands.command(name="top", description="サーバーのランキング一覧を表示します")
    @is_guild_app()
    async def top(self, interaction: discord.Interaction):
        """サーバーランキング一覧"""
        await interaction.response.defer()

        guild_id = interaction.guild_id

        # 各カテゴリのTop5を取得
        from cogs.cp.stats import checkpoint_stats

        msg_rankings = await checkpoint_stats.get_rankings(guild_id, "messages", limit=5)
        vc_rankings = await checkpoint_stats.get_rankings(guild_id, "vc", limit=5)
        omikuji_rankings = await checkpoint_stats.get_rankings(guild_id, "omikuji", limit=5)
        xp_rankings = await rank_db.get_rankings(guild_id, 5, "yearly_xp")

        # Components V2メッセージ作成
        msg = ComponentsV2Message()
        container = Container(color=COLOR_GOLD)

        container.add_text("# 🏆 ギルドランキング")
        container.add_separator()

        # メッセージランキング
        if msg_rankings:
            lines = []
            for entry in msg_rankings:
                name = await self._get_username(entry.user_id)
                lines.append(f"`#{entry.rank}` {name} — **{entry.value:,}**件")
            container.add_text("💬 **メッセージ送信者**（Top5）\n" + "\n".join(lines))
        else:
            container.add_text("💬 **メッセージ送信者**\n-# データなし")

        container.add(Separator(divider=False, spacing=SeparatorSpacing.SMALL))

        # VCランキング
        if vc_rankings:
            lines = []
            for entry in vc_rankings:
                name = await self._get_username(entry.user_id)
                hours = entry.value // 3600
                mins = (entry.value % 3600) // 60
                time_str = f"{hours}h{mins}m" if hours > 0 else f"{mins}m"
                lines.append(f"`#{entry.rank}` {name} — **{time_str}**")
            container.add_text("🎤 **ボイチャ勢**（Top5）\n" + "\n".join(lines))
        else:
            container.add_text("🎤 **ボイチャ勢**\n-# データなし")

        container.add(Separator(divider=False, spacing=SeparatorSpacing.SMALL))

        # XPランキング
        if xp_rankings:
            lines = []
            for i, u in enumerate(xp_rankings):
                name = await self._get_username(u.user_id)
                lines.append(f"`#{i+1}` {name} `Lv.{u.current_level}` — **{self._format_xp(u.yearly_xp)}** XP")
            container.add_text("✨ **XPランキング**（Top5）\n" + "\n".join(lines))
        else:
            container.add_text("✨ **XPランキング**\n-# データなし")

        container.add(Separator(divider=False, spacing=SeparatorSpacing.SMALL))

        # おみくじランキング
        if omikuji_rankings:
            lines = []
            for entry in omikuji_rankings:
                name = await self._get_username(entry.user_id)
                lines.append(f"`#{entry.rank}` {name} — **{entry.value}**回")
            container.add_text("🎲 **おみくじ勢**（Top5）\n" + "\n".join(lines))
        else:
            container.add_text("🎲 **おみくじ勢**\n-# データなし")

        # フッター
        container.add_separator()
        container.add_text("-# `/ranktop` `/checkpoint-rankings` で詳細表示")

        msg.add(container)

        await send_components_v2_followup(interaction, msg)

    # ==================== 設定コマンド ====================

    rank_settings = app_commands.Group(
        name="rank-settings",
        description="Rankシステムの設定",
        default_permissions=discord.Permissions(administrator=True),
    )

    @rank_settings.command(name="view", description="現在の設定を表示します")
    @is_moderator_app()
    async def settings_view(self, interaction: discord.Interaction):
        """設定を表示"""
        await interaction.response.defer(ephemeral=True)

        config = await rank_db.get_config(interaction.guild_id)

        msg = ComponentsV2Message()
        container = Container(color=COLOR_SETTINGS)

        container.add_text("# ⚙️ Rank設定")
        container.add_separator()

        # 有効/無効
        status = "✅ 有効" if config.is_enabled else "❌ 無効"
        container.add_text(f"**ステータス:** {status}")

        container.add(Separator(divider=False, spacing=SeparatorSpacing.SMALL))

        # XP設定
        container.add_text(
            f"**XP設定**\n"
            f"💬 メッセージ: **{config.message_xp}** XP（{config.message_cooldown_seconds}秒CD）\n"
            f"🎲 おみくじ: **{config.omikuji_xp}** XP\n"
            f"🎤 VC: **{config.vc_xp_per_10min}** XP / 10分"
        )

        container.add(Separator(divider=False, spacing=SeparatorSpacing.SMALL))

        # 常連ロール設定
        regular_role_text = f"<@&{config.regular_role_id}>" if config.regular_role_id else "未設定"
        container.add_text(
            f"**常連ロール設定**\n"
            f"🎖️ ロール: {regular_role_text}\n"
            f"✨ 必要XP: **{config.regular_xp_threshold:,}** XP\n"
            f"📅 必要日数: **{config.regular_days_threshold}**日"
        )

        container.add(Separator(divider=False, spacing=SeparatorSpacing.SMALL))

        # 除外ロール
        if config.excluded_roles:
            role_mentions = [f"<@&{r}>" for r in config.excluded_roles]
            container.add_text(f"**除外ロール**\n{' '.join(role_mentions)}")
        else:
            container.add_text("**除外ロール**\n-# なし")

        container.add(Separator(divider=False, spacing=SeparatorSpacing.SMALL))

        # 除外チャンネル
        if config.excluded_channels:
            channel_mentions = [f"<#{c}>" for c in config.excluded_channels]
            container.add_text(f"**除外チャンネル**\n{' '.join(channel_mentions)}")
        else:
            container.add_text("**除外チャンネル**\n-# なし")

        msg.add(container)

        await send_components_v2_followup(interaction, msg)

    @rank_settings.command(name="toggle", description="Rankシステムの有効/無効を切り替えます")
    @is_moderator_app()
    async def settings_toggle(self, interaction: discord.Interaction):
        """有効/無効を切り替え"""
        config = await rank_db.get_config(interaction.guild_id)
        new_state = not config.is_enabled

        success = await rank_db.update_enabled(interaction.guild_id, new_state)

        if success:
            status = "✅ 有効" if new_state else "❌ 無効"
            await interaction.response.send_message(
                f"⚙️ Rankシステムを **{status}** にしました",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                "❌ 設定の更新に失敗しました",
                ephemeral=True,
            )

    @rank_settings.command(name="exclude-role", description="除外ロールを追加/削除します")
    @is_moderator_app()
    @app_commands.describe(
        action="追加または削除",
        role="対象のロール",
    )
    @app_commands.choices(
        action=[
            app_commands.Choice(name="追加", value="add"),
            app_commands.Choice(name="削除", value="remove"),
        ]
    )
    async def settings_exclude_role(
        self,
        interaction: discord.Interaction,
        action: str,
        role: discord.Role,
    ):
        """除外ロールを設定"""
        config = await rank_db.get_config(interaction.guild_id)
        current_roles = list(config.excluded_roles) if config.excluded_roles else []

        if action == "add":
            if role.id in current_roles:
                await interaction.response.send_message(
                    f"⚠️ {role.mention} は既に除外リストに含まれています",
                    ephemeral=True,
                )
                return
            current_roles.append(role.id)
            msg = f"✅ {role.mention} を除外ロールに追加しました"
        else:
            if role.id not in current_roles:
                await interaction.response.send_message(
                    f"⚠️ {role.mention} は除外リストに含まれていません",
                    ephemeral=True,
                )
                return
            current_roles.remove(role.id)
            msg = f"✅ {role.mention} を除外ロールから削除しました"

        success = await rank_db.update_excluded_roles(interaction.guild_id, current_roles)

        if success:
            await interaction.response.send_message(msg, ephemeral=True)
        else:
            await interaction.response.send_message(
                "❌ 設定の更新に失敗しました",
                ephemeral=True,
            )

    @rank_settings.command(name="exclude-channel", description="除外チャンネルを追加/削除します")
    @is_moderator_app()
    @app_commands.describe(
        action="追加または削除",
        channel="対象のチャンネル",
    )
    @app_commands.choices(
        action=[
            app_commands.Choice(name="追加", value="add"),
            app_commands.Choice(name="削除", value="remove"),
        ]
    )
    async def settings_exclude_channel(
        self,
        interaction: discord.Interaction,
        action: str,
        channel: discord.TextChannel,
    ):
        """除外チャンネルを設定"""
        config = await rank_db.get_config(interaction.guild_id)
        current_channels = list(config.excluded_channels) if config.excluded_channels else []

        if action == "add":
            if channel.id in current_channels:
                await interaction.response.send_message(
                    f"⚠️ {channel.mention} は既に除外リストに含まれています",
                    ephemeral=True,
                )
                return
            current_channels.append(channel.id)
            msg = f"✅ {channel.mention} を除外チャンネルに追加しました"
        else:
            if channel.id not in current_channels:
                await interaction.response.send_message(
                    f"⚠️ {channel.mention} は除外リストに含まれていません",
                    ephemeral=True,
                )
                return
            current_channels.remove(channel.id)
            msg = f"✅ {channel.mention} を除外チャンネルから削除しました"

        success = await rank_db.update_excluded_channels(interaction.guild_id, current_channels)

        if success:
            await interaction.response.send_message(msg, ephemeral=True)
        else:
            await interaction.response.send_message(
                "❌ 設定の更新に失敗しました",
                ephemeral=True,
            )

    @rank_settings.command(name="xp", description="XP設定を変更します")
    @is_moderator_app()
    @app_commands.describe(
        message_xp="メッセージXP（1通あたり）",
        omikuji_xp="おみくじXP（1回あたり）",
        vc_xp="VC XP（10分あたり）",
        cooldown="メッセージクールダウン（秒）",
    )
    async def settings_xp(
        self,
        interaction: discord.Interaction,
        message_xp: int | None = None,
        omikuji_xp: int | None = None,
        vc_xp: int | None = None,
        cooldown: int | None = None,
    ):
        """XP設定を変更"""
        if all(v is None for v in [message_xp, omikuji_xp, vc_xp, cooldown]):
            await interaction.response.send_message(
                "⚠️ 少なくとも1つの設定を指定してください",
                ephemeral=True,
            )
            return

        success = await rank_db.update_xp_settings(
            interaction.guild_id,
            message_xp=message_xp,
            omikuji_xp=omikuji_xp,
            vc_xp=vc_xp,
            cooldown=cooldown,
        )

        if success:
            changes = []
            if message_xp is not None:
                changes.append(f"💬 メッセージXP: **{message_xp}**")
            if omikuji_xp is not None:
                changes.append(f"🎲 おみくじXP: **{omikuji_xp}**")
            if vc_xp is not None:
                changes.append(f"🎤 VC XP: **{vc_xp}**/10分")
            if cooldown is not None:
                changes.append(f"⏱️ クールダウン: **{cooldown}**秒")

            await interaction.response.send_message(
                "✅ XP設定を更新しました\n" + "\n".join(changes),
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                "❌ 設定の更新に失敗しました",
                ephemeral=True,
            )

    @rank_settings.command(name="regular", description="常連ロールの設定を変更します")
    @is_moderator_app()
    @app_commands.describe(
        role="付与する常連ロール（解除する場合は空欄）",
        xp_threshold="常連認定に必要なXP",
        days_threshold="常連認定に必要なアクティブ日数",
    )
    async def settings_regular(
        self,
        interaction: discord.Interaction,
        role: discord.Role | None = None,
        xp_threshold: int | None = None,
        days_threshold: int | None = None,
    ):
        """常連ロール設定を変更"""
        # ロールIDの処理（Noneの場合は-1で解除とみなす）
        role_id = role.id if role else None

        if all(v is None for v in [role_id, xp_threshold, days_threshold]):
            # 現在の設定を表示
            config = await rank_db.get_config(interaction.guild_id)
            role_text = f"<@&{config.regular_role_id}>" if config.regular_role_id else "未設定"
            await interaction.response.send_message(
                f"🎖️ **常連ロール設定**\n"
                f"ロール: {role_text}\n"
                f"必要XP: **{config.regular_xp_threshold:,}** XP\n"
                f"必要日数: **{config.regular_days_threshold}**日",
                ephemeral=True,
            )
            return

        success = await rank_db.update_regular_settings(
            interaction.guild_id,
            role_id=role_id,
            xp_threshold=xp_threshold,
            days_threshold=days_threshold,
        )

        if success:
            changes = []
            if role:
                changes.append(f"🎖️ ロール: {role.mention}")
            if xp_threshold is not None:
                changes.append(f"✨ 必要XP: **{xp_threshold:,}**")
            if days_threshold is not None:
                changes.append(f"📅 必要日数: **{days_threshold}**日")

            await interaction.response.send_message(
                "✅ 常連ロール設定を更新しました\n" + "\n".join(changes),
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                "❌ 設定の更新に失敗しました",
                ephemeral=True,
            )

    @rank_settings.command(name="regular-clear", description="常連ロールの設定を解除します")
    @is_moderator_app()
    async def settings_regular_clear(self, interaction: discord.Interaction):
        """常連ロールを解除"""
        success = await rank_db.update_regular_settings(
            interaction.guild_id,
            role_id=0,  # 0で解除
        )

        if success:
            await interaction.response.send_message(
                "✅ 常連ロールの設定を解除しました",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                "❌ 設定の更新に失敗しました",
                ephemeral=True,
            )

    # ========== XP管理コマンド ==========
    rank_admin = app_commands.Group(
        name="rank-admin",
        description="ランクXP管理コマンド（モデレーター専用）",
        guild_only=True,
    )

    @rank_admin.command(name="add", description="ユーザーにXPを追加します")
    @is_moderator_app()
    @app_commands.describe(
        user="対象ユーザー",
        amount="追加するXP量",
    )
    async def admin_add_xp(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        amount: app_commands.Range[int, 1, 100000],
    ):
        """XPを追加"""
        result = await rank_db.modify_xp(user.id, interaction.guild_id, amount)
        if result:
            await interaction.response.send_message(
                f"✅ {user.mention} に **{amount:,}** XP を追加しました\n"
                f"現在: Lv.**{result.current_level}** / **{result.yearly_xp:,}** XP",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                "❌ XPの追加に失敗しました（ユーザーが存在しない可能性）",
                ephemeral=True,
            )

    @rank_admin.command(name="remove", description="ユーザーからXPを減らします")
    @is_moderator_app()
    @app_commands.describe(
        user="対象ユーザー",
        amount="減らすXP量",
    )
    async def admin_remove_xp(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        amount: app_commands.Range[int, 1, 100000],
    ):
        """XPを減らす"""
        result = await rank_db.modify_xp(user.id, interaction.guild_id, -amount)
        if result:
            await interaction.response.send_message(
                f"✅ {user.mention} から **{amount:,}** XP を減らしました\n"
                f"現在: Lv.**{result.current_level}** / **{result.yearly_xp:,}** XP",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                "❌ XPの減算に失敗しました（ユーザーが存在しない可能性）",
                ephemeral=True,
            )

    @rank_admin.command(name="set", description="ユーザーのXPを直接設定します")
    @is_moderator_app()
    @app_commands.describe(
        user="対象ユーザー",
        yearly_xp="年間XP（省略可）",
        lifetime_xp="累計XP（省略可）",
    )
    async def admin_set_xp(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        yearly_xp: app_commands.Range[int, 0, 10000000] | None = None,
        lifetime_xp: app_commands.Range[int, 0, 100000000] | None = None,
    ):
        """XPを直接設定"""
        if yearly_xp is None and lifetime_xp is None:
            await interaction.response.send_message(
                "❌ 少なくとも `yearly_xp` か `lifetime_xp` を指定してください",
                ephemeral=True,
            )
            return

        success = await rank_db.set_xp(
            user.id, interaction.guild_id,
            yearly_xp=yearly_xp,
            lifetime_xp=lifetime_xp,
        )
        if success:
            changes = []
            if yearly_xp is not None:
                changes.append(f"年間XP: **{yearly_xp:,}**")
            if lifetime_xp is not None:
                changes.append(f"累計XP: **{lifetime_xp:,}**")
            await interaction.response.send_message(
                f"✅ {user.mention} のXPを設定しました\n" + "\n".join(changes),
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                "❌ XPの設定に失敗しました（ユーザーが存在しない可能性）",
                ephemeral=True,
            )

    @rank_admin.command(name="reset", description="ユーザーのランクデータをリセットします")
    @is_moderator_app()
    @app_commands.describe(user="対象ユーザー")
    async def admin_reset(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
    ):
        """ユーザーをリセット"""
        success = await rank_db.reset_user(user.id, interaction.guild_id)
        if success:
            await interaction.response.send_message(
                f"✅ {user.mention} のランクデータをリセットしました",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                "❌ リセットに失敗しました",
                ephemeral=True,
            )

    @rank_admin.command(name="check", description="ユーザーのランク情報を確認します")
    @is_moderator_app()
    @app_commands.describe(user="対象ユーザー")
    async def admin_check(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
    ):
        """ユーザー情報を確認"""
        rank_user = await rank_db.get_user(user.id, interaction.guild_id)
        if not rank_user:
            await interaction.response.send_message(
                f"❌ {user.mention} のランクデータが見つかりません",
                ephemeral=True,
            )
            return

        user_rank = await rank_db.get_user_rank(user.id, interaction.guild_id)
        await interaction.response.send_message(
            f"📊 **{user.display_name}** のランク情報\n"
            f"順位: **#{user_rank}**\n"
            f"レベル: **Lv.{rank_user.current_level}**\n"
            f"年間XP: **{rank_user.yearly_xp:,}** XP\n"
            f"累計XP: **{rank_user.lifetime_xp:,}** XP\n"
            f"アクティブ日数: **{rank_user.active_days}**日\n"
            f"常連: {'✅' if rank_user.is_regular else '❌'}",
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    """Cog setup"""
    await bot.add_cog(RankCommands(bot))
