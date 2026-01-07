"""
高機能AutoPurge（メッセージ一括削除）システム

多彩なフィルター条件でメッセージを一括削除する機能を提供します。
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks

from utils.database import execute_query
from utils.logging import setup_logging

logger = setup_logging()


class PurgeConfirmView(discord.ui.View):
    """削除確認用のView"""

    def __init__(self, author_id: int, messages_to_delete: list, channel: discord.TextChannel):
        super().__init__(timeout=60)
        self.author_id = author_id
        self.messages_to_delete = messages_to_delete
        self.channel = channel
        self.confirmed = False

    @discord.ui.button(label="削除実行", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def confirm_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "この操作を実行する権限がありません。",
                ephemeral=True
            )
            return

        self.confirmed = True
        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(
            content="🔄 削除中...",
            view=self
        )

        # メッセージを削除
        deleted_count = 0
        try:
            # 14日以内のメッセージは一括削除可能
            recent_messages = [m for m in self.messages_to_delete
                             if (datetime.now(timezone.utc) - m.created_at).days < 14]
            old_messages = [m for m in self.messages_to_delete
                          if (datetime.now(timezone.utc) - m.created_at).days >= 14]

            # 一括削除（14日以内）
            if recent_messages:
                for i in range(0, len(recent_messages), 100):
                    batch = recent_messages[i:i+100]
                    await self.channel.delete_messages(batch)
                    deleted_count += len(batch)

            # 個別削除（14日以上）
            for msg in old_messages:
                try:
                    await msg.delete()
                    deleted_count += 1
                except discord.NotFound:
                    pass

            await interaction.edit_original_response(
                content=f"✅ {deleted_count} 件のメッセージを削除しました。",
                view=None
            )
        except discord.Forbidden:
            await interaction.edit_original_response(
                content="❌ メッセージの削除権限がありません。",
                view=None
            )
        except Exception as e:
            logger.error(f"メッセージ削除エラー: {e}")
            await interaction.edit_original_response(
                content=f"❌ エラーが発生しました: {e}",
                view=None
            )

        self.stop()

    @discord.ui.button(label="キャンセル", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "この操作を実行する権限がありません。",
                ephemeral=True
            )
            return

        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(
            content="❌ 削除をキャンセルしました。",
            view=self
        )
        self.stop()


class AutoPurge(commands.Cog):
    """高機能メッセージ削除機能を提供するCog"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.auto_purge_task.start()

    async def cog_load(self):
        """Cogロード時にテーブルを作成"""
        await self._setup_table()

    async def cog_unload(self):
        """Cogアンロード時にタスクを停止"""
        self.auto_purge_task.cancel()

    async def _setup_table(self):
        """AutoPurge設定テーブルを作成"""
        await execute_query(
            '''
            CREATE TABLE IF NOT EXISTS auto_purge_settings (
                id SERIAL PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                channel_id BIGINT NOT NULL,
                filter_type TEXT NOT NULL,
                filter_value TEXT,
                interval_hours INT NOT NULL DEFAULT 24,
                max_age_hours INT NOT NULL DEFAULT 24,
                last_run TIMESTAMP WITH TIME ZONE,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                UNIQUE(guild_id, channel_id, filter_type)
            )
            ''',
            fetch_type='status'
        )
        logger.info("AutoPurge設定テーブルを確認・作成しました")

    @tasks.loop(minutes=30)
    async def auto_purge_task(self):
        """自動削除タスク"""
        try:
            now = datetime.now(timezone.utc)
            settings = await execute_query(
                '''
                SELECT id, guild_id, channel_id, filter_type, filter_value,
                       interval_hours, max_age_hours, last_run
                FROM auto_purge_settings
                WHERE is_active = TRUE
                  AND (last_run IS NULL OR last_run + interval_hours * INTERVAL '1 hour' <= $1)
                ''',
                now,
                fetch_type='all'
            )

            for setting in settings:
                await self._execute_auto_purge(setting)
                # 最終実行時刻を更新
                await execute_query(
                    "UPDATE auto_purge_settings SET last_run = $1 WHERE id = $2",
                    now,
                    setting['id'],
                    fetch_type='status'
                )

        except Exception as e:
            logger.error(f"AutoPurgeタスクエラー: {e}")

    @auto_purge_task.before_loop
    async def before_auto_purge_task(self):
        await self.bot.wait_until_ready()

    async def _execute_auto_purge(self, setting: dict):
        """自動削除を実行"""
        try:
            channel = self.bot.get_channel(setting['channel_id'])
            if not channel:
                return

            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=setting['max_age_hours'])

            def check(message):
                if message.created_at >= cutoff_time:
                    return False  # 新しすぎるメッセージは削除しない
                return self._apply_filter(message, setting['filter_type'], setting['filter_value'])

            # メッセージを収集
            messages_to_delete = []
            async for message in channel.history(limit=500, before=cutoff_time):
                if check(message):
                    messages_to_delete.append(message)

            # 削除実行
            if messages_to_delete:
                deleted = await channel.purge(limit=len(messages_to_delete), check=check)
                logger.info(f"AutoPurge: {channel.name} で {len(deleted)} 件削除")

        except Exception as e:
            logger.error(f"AutoPurge実行エラー (channel_id={setting['channel_id']}): {e}")

    def _apply_filter(self, message: discord.Message, filter_type: str, filter_value: Optional[str]) -> bool:
        """フィルター条件を適用"""
        if filter_type == "all":
            return True
        elif filter_type == "bot":
            return message.author.bot
        elif filter_type == "human":
            return not message.author.bot
        elif filter_type == "user":
            if filter_value:
                try:
                    return message.author.id == int(filter_value)
                except ValueError:
                    return False
        elif filter_type == "contains":
            if filter_value:
                return filter_value.lower() in message.content.lower()
        elif filter_type == "links":
            return any(x in message.content.lower() for x in ['http://', 'https://', 'discord.gg/'])
        elif filter_type == "attachments":
            return len(message.attachments) > 0
        elif filter_type == "embeds":
            return len(message.embeds) > 0
        elif filter_type == "mentions":
            return len(message.mentions) > 0 or len(message.role_mentions) > 0
        elif filter_type == "no_attachments":
            return len(message.attachments) == 0
        return False

    purge_group = app_commands.Group(
        name="purge",
        description="メッセージ一括削除コマンド",
        default_permissions=discord.Permissions(manage_messages=True)
    )

    @purge_group.command(name="messages", description="指定した件数のメッセージを削除します")
    @app_commands.describe(
        count="削除するメッセージ数（1-500）",
        user="特定ユーザーのメッセージのみ",
        contains="この文字列を含むメッセージのみ",
        bots_only="BOTのメッセージのみ削除",
        humans_only="人間のメッセージのみ削除",
        has_attachments="添付ファイル付きのみ",
        has_links="リンク含むメッセージのみ",
        dry_run="削除せずに対象件数のみ確認"
    )
    async def purge_messages(
        self,
        interaction: discord.Interaction,
        count: app_commands.Range[int, 1, 500],
        user: Optional[discord.User] = None,
        contains: Optional[str] = None,
        bots_only: bool = False,
        humans_only: bool = False,
        has_attachments: bool = False,
        has_links: bool = False,
        dry_run: bool = False
    ):
        """条件付きメッセージ削除"""
        await interaction.response.defer(ephemeral=True)

        def check(message):
            # BOTのみ / 人間のみフィルター
            if bots_only and not message.author.bot:
                return False
            if humans_only and message.author.bot:
                return False
            # 特定ユーザーフィルター
            if user and message.author.id != user.id:
                return False
            # 文字列含むフィルター
            if contains and contains.lower() not in message.content.lower():
                return False
            # 添付ファイルフィルター
            if has_attachments and len(message.attachments) == 0:
                return False
            # リンクフィルター
            if has_links and not any(x in message.content.lower() for x in ['http://', 'https://', 'discord.gg/']):
                return False
            return True

        # メッセージを収集
        messages_to_delete = []
        async for message in interaction.channel.history(limit=count * 3):  # 余裕を持って取得
            if check(message):
                messages_to_delete.append(message)
                if len(messages_to_delete) >= count:
                    break

        if not messages_to_delete:
            await interaction.followup.send("❌ 条件に一致するメッセージが見つかりませんでした。")
            return

        if dry_run:
            # ドライラン: 削除せずに件数だけ報告
            await interaction.followup.send(
                f"📊 **ドライラン結果**\n"
                f"条件に一致するメッセージ: **{len(messages_to_delete)}** 件\n\n"
                f"実際に削除するには `dry_run: False` で実行してください。"
            )
            return

        # 確認View表示
        view = PurgeConfirmView(interaction.user.id, messages_to_delete, interaction.channel)
        await interaction.followup.send(
            f"⚠️ **{len(messages_to_delete)} 件のメッセージを削除しますか？**\n"
            f"この操作は取り消せません。",
            view=view
        )

    @purge_group.command(name="user", description="特定ユーザーのメッセージを削除します")
    @app_commands.describe(
        user="対象ユーザー",
        count="削除するメッセージ数（1-500）",
        dry_run="削除せずに対象件数のみ確認"
    )
    async def purge_user(
        self,
        interaction: discord.Interaction,
        user: discord.User,
        count: app_commands.Range[int, 1, 500] = 100,
        dry_run: bool = False
    ):
        """特定ユーザーのメッセージを削除"""
        await interaction.response.defer(ephemeral=True)

        messages_to_delete = []
        async for message in interaction.channel.history(limit=count * 5):
            if message.author.id == user.id:
                messages_to_delete.append(message)
                if len(messages_to_delete) >= count:
                    break

        if not messages_to_delete:
            await interaction.followup.send(f"❌ {user.mention} のメッセージが見つかりませんでした。")
            return

        if dry_run:
            await interaction.followup.send(
                f"📊 **ドライラン結果**\n"
                f"{user.mention} のメッセージ: **{len(messages_to_delete)}** 件"
            )
            return

        view = PurgeConfirmView(interaction.user.id, messages_to_delete, interaction.channel)
        await interaction.followup.send(
            f"⚠️ **{user.mention} のメッセージ {len(messages_to_delete)} 件を削除しますか？**",
            view=view
        )

    @purge_group.command(name="bots", description="BOTのメッセージを削除します")
    @app_commands.describe(
        count="削除するメッセージ数（1-500）",
        dry_run="削除せずに対象件数のみ確認"
    )
    async def purge_bots(
        self,
        interaction: discord.Interaction,
        count: app_commands.Range[int, 1, 500] = 100,
        dry_run: bool = False
    ):
        """BOTのメッセージを削除"""
        await interaction.response.defer(ephemeral=True)

        messages_to_delete = []
        async for message in interaction.channel.history(limit=count * 3):
            if message.author.bot:
                messages_to_delete.append(message)
                if len(messages_to_delete) >= count:
                    break

        if not messages_to_delete:
            await interaction.followup.send("❌ BOTのメッセージが見つかりませんでした。")
            return

        if dry_run:
            await interaction.followup.send(
                f"📊 **ドライラン結果**\n"
                f"BOTのメッセージ: **{len(messages_to_delete)}** 件"
            )
            return

        view = PurgeConfirmView(interaction.user.id, messages_to_delete, interaction.channel)
        await interaction.followup.send(
            f"⚠️ **BOTのメッセージ {len(messages_to_delete)} 件を削除しますか？**",
            view=view
        )

    @purge_group.command(name="links", description="リンクを含むメッセージを削除します")
    @app_commands.describe(
        count="削除するメッセージ数（1-500）",
        dry_run="削除せずに対象件数のみ確認"
    )
    async def purge_links(
        self,
        interaction: discord.Interaction,
        count: app_commands.Range[int, 1, 500] = 100,
        dry_run: bool = False
    ):
        """リンク含むメッセージを削除"""
        await interaction.response.defer(ephemeral=True)

        messages_to_delete = []
        link_keywords = ['http://', 'https://', 'discord.gg/', 'discord.com/invite/']

        async for message in interaction.channel.history(limit=count * 3):
            if any(kw in message.content.lower() for kw in link_keywords):
                messages_to_delete.append(message)
                if len(messages_to_delete) >= count:
                    break

        if not messages_to_delete:
            await interaction.followup.send("❌ リンクを含むメッセージが見つかりませんでした。")
            return

        if dry_run:
            await interaction.followup.send(
                f"📊 **ドライラン結果**\n"
                f"リンク含むメッセージ: **{len(messages_to_delete)}** 件"
            )
            return

        view = PurgeConfirmView(interaction.user.id, messages_to_delete, interaction.channel)
        await interaction.followup.send(
            f"⚠️ **リンク含むメッセージ {len(messages_to_delete)} 件を削除しますか？**",
            view=view
        )

    @purge_group.command(name="attachments", description="添付ファイル付きメッセージを削除します")
    @app_commands.describe(
        count="削除するメッセージ数（1-500）",
        dry_run="削除せずに対象件数のみ確認"
    )
    async def purge_attachments(
        self,
        interaction: discord.Interaction,
        count: app_commands.Range[int, 1, 500] = 100,
        dry_run: bool = False
    ):
        """添付ファイル付きメッセージを削除"""
        await interaction.response.defer(ephemeral=True)

        messages_to_delete = []
        async for message in interaction.channel.history(limit=count * 3):
            if len(message.attachments) > 0:
                messages_to_delete.append(message)
                if len(messages_to_delete) >= count:
                    break

        if not messages_to_delete:
            await interaction.followup.send("❌ 添付ファイル付きメッセージが見つかりませんでした。")
            return

        if dry_run:
            await interaction.followup.send(
                f"📊 **ドライラン結果**\n"
                f"添付ファイル付きメッセージ: **{len(messages_to_delete)}** 件"
            )
            return

        view = PurgeConfirmView(interaction.user.id, messages_to_delete, interaction.channel)
        await interaction.followup.send(
            f"⚠️ **添付ファイル付きメッセージ {len(messages_to_delete)} 件を削除しますか？**",
            view=view
        )

    # === AutoPurge設定コマンド ===

    autopurge_group = app_commands.Group(
        name="autopurge",
        description="自動メッセージ削除設定",
        default_permissions=discord.Permissions(manage_messages=True)
    )

    @autopurge_group.command(name="set", description="自動削除を設定します")
    @app_commands.describe(
        channel="対象チャンネル",
        filter_type="削除対象のフィルター",
        interval_hours="削除実行間隔（時間）",
        max_age_hours="この時間より古いメッセージを削除"
    )
    @app_commands.choices(filter_type=[
        app_commands.Choice(name="すべてのメッセージ", value="all"),
        app_commands.Choice(name="BOTのメッセージのみ", value="bot"),
        app_commands.Choice(name="人間のメッセージのみ", value="human"),
        app_commands.Choice(name="リンク含むメッセージ", value="links"),
        app_commands.Choice(name="添付ファイル付き", value="attachments"),
    ])
    async def autopurge_set(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        filter_type: str,
        interval_hours: app_commands.Range[int, 1, 168] = 24,
        max_age_hours: app_commands.Range[int, 1, 336] = 24
    ):
        """自動削除設定を追加"""
        await execute_query(
            '''
            INSERT INTO auto_purge_settings (guild_id, channel_id, filter_type, interval_hours, max_age_hours)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (guild_id, channel_id, filter_type)
            DO UPDATE SET interval_hours = $4, max_age_hours = $5, is_active = TRUE
            ''',
            interaction.guild.id,
            channel.id,
            filter_type,
            interval_hours,
            max_age_hours,
            fetch_type='status'
        )

        filter_names = {
            "all": "すべてのメッセージ",
            "bot": "BOTのメッセージ",
            "human": "人間のメッセージ",
            "links": "リンク含むメッセージ",
            "attachments": "添付ファイル付き"
        }

        embed = discord.Embed(
            title="✅ 自動削除を設定しました",
            color=discord.Color.green()
        )
        embed.add_field(name="チャンネル", value=channel.mention, inline=True)
        embed.add_field(name="フィルター", value=filter_names.get(filter_type, filter_type), inline=True)
        embed.add_field(name="実行間隔", value=f"{interval_hours}時間ごと", inline=True)
        embed.add_field(name="対象", value=f"{max_age_hours}時間以上前のメッセージ", inline=True)

        await interaction.response.send_message(embed=embed)

    @autopurge_group.command(name="list", description="自動削除設定一覧を表示します")
    async def autopurge_list(self, interaction: discord.Interaction):
        """自動削除設定一覧"""
        settings = await execute_query(
            '''
            SELECT id, channel_id, filter_type, interval_hours, max_age_hours, last_run, is_active
            FROM auto_purge_settings
            WHERE guild_id = $1
            ORDER BY channel_id
            ''',
            interaction.guild.id,
            fetch_type='all'
        )

        if not settings:
            await interaction.response.send_message(
                "📭 自動削除設定はありません。",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="📋 自動削除設定一覧",
            color=discord.Color.blue()
        )

        filter_names = {
            "all": "すべて",
            "bot": "BOT",
            "human": "人間",
            "links": "リンク",
            "attachments": "添付"
        }

        for setting in settings:
            status = "✅ 有効" if setting['is_active'] else "❌ 無効"
            last_run = ""
            if setting['last_run']:
                last_run = f"\n最終実行: <t:{int(setting['last_run'].timestamp())}:R>"

            embed.add_field(
                name=f"#{setting['id']} - <#{setting['channel_id']}>",
                value=(
                    f"{status} | {filter_names.get(setting['filter_type'], setting['filter_type'])}\n"
                    f"間隔: {setting['interval_hours']}h | 対象: {setting['max_age_hours']}h以上前{last_run}"
                ),
                inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @autopurge_group.command(name="remove", description="自動削除設定を削除します")
    @app_commands.describe(setting_id="削除する設定のID")
    async def autopurge_remove(self, interaction: discord.Interaction, setting_id: int):
        """自動削除設定を削除"""
        result = await execute_query(
            "DELETE FROM auto_purge_settings WHERE id = $1 AND guild_id = $2 RETURNING id",
            setting_id,
            interaction.guild.id,
            fetch_type='row'
        )

        if not result:
            await interaction.response.send_message(
                "❌ 指定された設定が見つかりません。",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            f"✅ 自動削除設定 #{setting_id} を削除しました。",
            ephemeral=True
        )

    @autopurge_group.command(name="toggle", description="自動削除設定を有効/無効にします")
    @app_commands.describe(setting_id="切り替える設定のID")
    async def autopurge_toggle(self, interaction: discord.Interaction, setting_id: int):
        """自動削除設定を切り替え"""
        result = await execute_query(
            '''
            UPDATE auto_purge_settings
            SET is_active = NOT is_active
            WHERE id = $1 AND guild_id = $2
            RETURNING is_active
            ''',
            setting_id,
            interaction.guild.id,
            fetch_type='row'
        )

        if not result:
            await interaction.response.send_message(
                "❌ 指定された設定が見つかりません。",
                ephemeral=True
            )
            return

        status = "✅ 有効" if result['is_active'] else "❌ 無効"
        await interaction.response.send_message(
            f"自動削除設定 #{setting_id} を **{status}** にしました。",
            ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(AutoPurge(bot))
