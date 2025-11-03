"""
サーバータグ自動モデレーション機能

サーバー参加時に自動でユーザーのサーバータグをチェックし、
禁止タグリストに一致する場合は自動でタイムアウトと警告送信を行います。
"""
from datetime import timedelta
from typing import Optional

import discord
import httpx
from discord.ext import commands

from config.setting import get_settings
from utils.commands_help import is_guild, is_moderator, log_commands
from utils.logging import setup_logging
from utils.tag_moderation_db import execute_tag_query

settings = get_settings()
logger = setup_logging("D")


class TagModerationCog(commands.Cog):
    """サーバータグベースの自動モデレーション機能"""

    def __init__(self, bot):
        self.bot = bot
        self.api_base_url = "https://discord.com/api/v10"

    async def fetch_user_server_tag(self, user_id: int) -> Optional[dict]:
        """
        Discord APIから指定ユーザーのサーバータグ情報を取得

        Args:
            user_id: 取得対象のユーザーID

        Returns:
            サーバータグ情報を含む辞書、存在しない場合はNone
        """
        url = f"{self.api_base_url}/users/{user_id}"
        headers = {
            "Authorization": f"Bot {settings.bot_token}"
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()

            return data.get("clan")

        except httpx.HTTPStatusError as e:
            logger.error(f"Discord API HTTPエラー: {e.response.status_code} - {e}")
            return None
        except httpx.RequestError as e:
            logger.error(f"Discord API リクエストエラー: {e}")
            return None
        except Exception as e:
            logger.error(f"サーバータグ取得中に予期しないエラー: {e}")
            return None

    async def get_moderation_config(self, guild_id: int) -> Optional[dict]:
        """
        タグモデレーション設定を取得

        Args:
            guild_id: ギルドID

        Returns:
            設定情報の辞書
        """
        try:
            result = await execute_tag_query(
                "SELECT * FROM tag_moderation_config WHERE guild_id = $1",
                guild_id, fetch_type='row'
            )
            return result if result else None
        except Exception as e:
            logger.error(f"モデレーション設定取得エラー: {e}")
            return None

    async def get_banned_tags(self, guild_id: int) -> list[dict]:
        """
        禁止タグリストを取得

        Args:
            guild_id: ギルドID

        Returns:
            禁止タグのリスト
        """
        try:
            results = await execute_tag_query(
                "SELECT tag, reason, added_by FROM banned_server_tags WHERE guild_id = $1",
                guild_id, fetch_type='all'
            )
            return results if results else []
        except Exception as e:
            logger.error(f"禁止タグリスト取得エラー: {e}")
            return []

    async def is_tag_banned(self, guild_id: int, tag: str) -> bool:
        """
        タグが禁止リストに含まれているかチェック

        Args:
            guild_id: ギルドID
            tag: チェックするタグ

        Returns:
            禁止されている場合True
        """
        try:
            result = await execute_tag_query(
                "SELECT id FROM banned_server_tags WHERE guild_id = $1 AND tag = $2",
                guild_id, tag, fetch_type='row'
            )
            return result is not None
        except Exception as e:
            logger.error(f"タグチェックエラー: {e}")
            return False

    async def log_moderation_action(self, guild_id: int, user_id: int, user_tag: str,
                                   banned_tag: str, action_taken: str, timeout_applied: bool,
                                   timeout_duration: Optional[int], alert_sent: bool,
                                   alert_channel_id: Optional[int]) -> None:
        """
        モデレーションアクションをログに記録

        Args:
            guild_id: ギルドID
            user_id: ユーザーID
            user_tag: ユーザーが装着していたタグ
            banned_tag: マッチした禁止タグ
            action_taken: 実行されたアクション
            timeout_applied: タイムアウトが適用されたか
            timeout_duration: タイムアウト期間（秒）
            alert_sent: 警告が送信されたか
            alert_channel_id: 警告送信先チャンネルID
        """
        try:
            await execute_tag_query(
                """
                INSERT INTO tag_moderation_logs
                (guild_id, user_id, user_tag, banned_tag, action_taken,
                 timeout_applied, timeout_duration, alert_sent, alert_channel_id, moderator_notified)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, true)
                """,
                guild_id, user_id, user_tag, banned_tag, action_taken,
                timeout_applied, timeout_duration, alert_sent, alert_channel_id,
                fetch_type='status'
            )
            logger.info(f"モデレーションアクションをログに記録: User {user_id}, Tag: {banned_tag}")
        except Exception as e:
            logger.error(f"モデレーションログ記録エラー: {e}")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        """
        メンバー参加時にサーバータグをチェックし、必要に応じてモデレーションアクションを実行

        Args:
            member: 参加したメンバー
        """
        # Botは無視
        if member.bot:
            return

        guild_id = member.guild.id

        # モデレーション設定を取得
        config = await self.get_moderation_config(guild_id)

        # 機能が無効、または設定が存在しない場合はスキップ
        if not config or not config.get('is_enabled'):
            return

        # ユーザーのサーバータグを取得
        clan = await self.fetch_user_server_tag(member.id)

        # タグが存在しない、または無効化されている場合はスキップ
        if not clan or not clan.get("identity_enabled"):
            return

        user_tag = clan.get("tag")
        if not user_tag:
            return

        # 禁止タグリストをチェック
        if not await self.is_tag_banned(guild_id, user_tag):
            return

        # 禁止タグが検出された場合の処理
        logger.warning(f"禁止タグ検出: User {member.id} ({member.display_name}), Tag: {user_tag}")

        # タイムアウトを適用
        timeout_applied = False
        timeout_duration = config.get('timeout_duration', 604800)  # デフォルト7日間

        if config.get('auto_timeout', True):
            try:
                await member.timeout(
                    timedelta(seconds=timeout_duration),
                    reason=f"禁止サーバータグ検出: {user_tag}"
                )
                timeout_applied = True
                logger.info(f"タイムアウト適用: User {member.id}, 期間: {timeout_duration}秒")
            except discord.Forbidden:
                logger.error(f"タイムアウト権限不足: User {member.id}")
            except Exception as e:
                logger.error(f"タイムアウト適用エラー: {e}")

        # 警告チャンネルに通知
        alert_sent = False
        alert_channel_id = config.get('alert_channel_id')

        if alert_channel_id:
            channel = member.guild.get_channel(alert_channel_id)
            if channel:
                embed = discord.Embed(
                    title="🚨 禁止サーバータグ検出",
                    description=f"{member.mention} が禁止されているサーバータグを装着しています。",
                    color=0xFF0000
                )

                embed.add_field(name="👤 ユーザー", value=f"{member.mention}\n`{member.id}`", inline=True)
                embed.add_field(name="🏷️ 検出タグ", value=f"`{user_tag}`", inline=True)
                embed.add_field(
                    name="⏱️ タイムアウト",
                    value="✅ 適用済み" if timeout_applied else "❌ 未適用",
                    inline=True
                )

                if timeout_applied:
                    days = timeout_duration // 86400
                    hours = (timeout_duration % 86400) // 3600
                    embed.add_field(
                        name="⏰ タイムアウト期間",
                        value=f"{days}日 {hours}時間",
                        inline=True
                    )

                embed.set_thumbnail(url=member.display_avatar.url)
                embed.set_footer(text=f"User ID: {member.id}")

                try:
                    await channel.send(embed=embed)
                    alert_sent = True
                    logger.info(f"警告送信成功: Channel {alert_channel_id}")
                except Exception as e:
                    logger.error(f"警告送信エラー: {e}")

        # ログに記録
        await self.log_moderation_action(
            guild_id, member.id, user_tag, user_tag,
            "auto_timeout" if timeout_applied else "alert_only",
            timeout_applied, timeout_duration, alert_sent, alert_channel_id
        )

    @commands.hybrid_group(name="tagmod", aliases=["タグモデレーション"])
    @is_guild()
    @is_moderator()
    @commands.has_permissions(moderate_members=True)
    async def tagmod_group(self, ctx) -> None:
        """サーバータグモデレーション関連のコマンドグループ"""
        if ctx.invoked_subcommand is None:
            await ctx.send(
                "サーバータグモデレーション機能です。\n"
                "使用可能なコマンド:\n"
                "• `/tagmod add <タグ> [理由]` - 禁止タグを追加\n"
                "• `/tagmod remove <タグ>` - 禁止タグを削除\n"
                "• `/tagmod list` - 禁止タグ一覧を表示\n"
                "• `/tagmod setchannel <チャンネル>` - 警告送信先を設定\n"
                "• `/tagmod toggle` - モデレーション機能のON/OFF\n"
                "• `/tagmod status` - 現在の設定を表示"
            )

    @tagmod_group.command(name="add", aliases=["追加"])
    @is_guild()
    @commands.has_permissions(moderate_members=True)
    @log_commands()
    async def tagmod_add(self, ctx, tag: str, *, reason: str = "管理者により禁止") -> None:
        """
        禁止タグリストに追加

        Args:
            tag: 禁止するタグ（最大4文字）
            reason: 禁止理由
        """
        await ctx.defer()

        # タグの長さチェック
        if len(tag) > 4:
            await ctx.send("❌ タグは最大4文字までです。")
            return

        guild_id = ctx.guild.id

        # 既に存在するかチェック
        if await self.is_tag_banned(guild_id, tag):
            await ctx.send(f"❌ タグ `{tag}` は既に禁止リストに登録されています。")
            return

        # DBに追加
        try:
            await execute_tag_query(
                """
                INSERT INTO banned_server_tags (guild_id, tag, reason, added_by)
                VALUES ($1, $2, $3, $4)
                """,
                guild_id, tag, reason, ctx.author.id, fetch_type='status'
            )

            embed = discord.Embed(
                title="✅ 禁止タグを追加しました",
                color=0x00FF00
            )
            embed.add_field(name="🏷️ タグ", value=f"`{tag}`", inline=True)
            embed.add_field(name="📝 理由", value=reason, inline=False)
            embed.set_footer(text=f"追加者: {ctx.author.display_name}")

            await ctx.send(embed=embed)
            logger.info(f"禁止タグ追加: {tag} by {ctx.author.id}")

        except Exception as e:
            logger.error(f"禁止タグ追加エラー: {e}")
            await ctx.send("❌ 禁止タグの追加中にエラーが発生しました。")

    @tagmod_group.command(name="remove", aliases=["削除"])
    @is_guild()
    @commands.has_permissions(moderate_members=True)
    @log_commands()
    async def tagmod_remove(self, ctx, tag: str) -> None:
        """
        禁止タグリストから削除

        Args:
            tag: 削除するタグ
        """
        await ctx.defer()

        guild_id = ctx.guild.id

        # 存在するかチェック
        if not await self.is_tag_banned(guild_id, tag):
            await ctx.send(f"❌ タグ `{tag}` は禁止リストに登録されていません。")
            return

        # DBから削除
        try:
            await execute_tag_query(
                "DELETE FROM banned_server_tags WHERE guild_id = $1 AND tag = $2",
                guild_id, tag, fetch_type='status'
            )

            embed = discord.Embed(
                title="✅ 禁止タグを削除しました",
                description=f"タグ `{tag}` を禁止リストから削除しました。",
                color=0x00FF00
            )
            embed.set_footer(text=f"削除者: {ctx.author.display_name}")

            await ctx.send(embed=embed)
            logger.info(f"禁止タグ削除: {tag} by {ctx.author.id}")

        except Exception as e:
            logger.error(f"禁止タグ削除エラー: {e}")
            await ctx.send("❌ 禁止タグの削除中にエラーが発生しました。")

    @tagmod_group.command(name="list", aliases=["一覧"])
    @is_guild()
    @commands.has_permissions(moderate_members=True)
    @log_commands()
    async def tagmod_list(self, ctx) -> None:
        """禁止タグ一覧を表示"""
        await ctx.defer()

        guild_id = ctx.guild.id
        banned_tags = await self.get_banned_tags(guild_id)

        if not banned_tags:
            embed = discord.Embed(
                title="📋 禁止タグ一覧",
                description="現在、禁止されているタグはありません。",
                color=0x99AAB5
            )
            await ctx.send(embed=embed)
            return

        embed = discord.Embed(
            title="📋 禁止タグ一覧",
            description=f"合計 {len(banned_tags)} 個の禁止タグが登録されています。",
            color=0xFF0000
        )

        for i, tag_info in enumerate(banned_tags, start=1):
            tag = tag_info['tag']
            reason = tag_info['reason'] or "理由なし"
            added_by_id = tag_info['added_by']

            # 追加者情報を取得
            added_by_member = ctx.guild.get_member(added_by_id)
            added_by_name = added_by_member.display_name if added_by_member else f"ID: {added_by_id}"

            embed.add_field(
                name=f"{i}. `{tag}`",
                value=f"📝 {reason}\n👤 追加者: {added_by_name}",
                inline=False
            )

        embed.set_footer(text=f"サーバー: {ctx.guild.name}")
        await ctx.send(embed=embed)

    @tagmod_group.command(name="setchannel", aliases=["チャンネル設定"])
    @is_guild()
    @commands.has_permissions(moderate_members=True)
    @log_commands()
    async def tagmod_setchannel(self, ctx, channel: discord.TextChannel) -> None:
        """
        警告送信先チャンネルを設定

        Args:
            channel: 警告を送信するチャンネル
        """
        await ctx.defer()

        guild_id = ctx.guild.id

        try:
            await execute_tag_query(
                """
                INSERT INTO tag_moderation_config (guild_id, alert_channel_id, updated_by)
                VALUES ($1, $2, $3)
                ON CONFLICT (guild_id)
                DO UPDATE SET
                    alert_channel_id = $2,
                    updated_by = $3,
                    updated_at = CURRENT_TIMESTAMP
                """,
                guild_id, channel.id, ctx.author.id, fetch_type='status'
            )

            embed = discord.Embed(
                title="✅ 警告送信先を設定しました",
                description=f"禁止タグ検出時の警告を {channel.mention} に送信します。",
                color=0x00FF00
            )
            embed.set_footer(text=f"設定者: {ctx.author.display_name}")

            await ctx.send(embed=embed)
            logger.info(f"警告チャンネル設定: {channel.id} by {ctx.author.id}")

        except Exception as e:
            logger.error(f"警告チャンネル設定エラー: {e}")
            await ctx.send("❌ 警告チャンネルの設定中にエラーが発生しました。")

    @tagmod_group.command(name="toggle", aliases=["切り替え"])
    @is_guild()
    @commands.has_permissions(moderate_members=True)
    @log_commands()
    async def tagmod_toggle(self, ctx) -> None:
        """タグモデレーション機能のON/OFF切り替え"""
        await ctx.defer()

        guild_id = ctx.guild.id
        config = await self.get_moderation_config(guild_id)

        # 現在の状態を反転
        current_state = config.get('is_enabled', True) if config else True
        new_state = not current_state

        try:
            await execute_tag_query(
                """
                INSERT INTO tag_moderation_config (guild_id, is_enabled, updated_by)
                VALUES ($1, $2, $3)
                ON CONFLICT (guild_id)
                DO UPDATE SET
                    is_enabled = $2,
                    updated_by = $3,
                    updated_at = CURRENT_TIMESTAMP
                """,
                guild_id, new_state, ctx.author.id, fetch_type='status'
            )

            status_text = "有効" if new_state else "無効"
            status_emoji = "✅" if new_state else "❌"

            embed = discord.Embed(
                title=f"{status_emoji} タグモデレーション機能を{status_text}にしました",
                description=f"サーバータグベースの自動モデレーションが{status_text}になりました。",
                color=0x00FF00 if new_state else 0xFF0000
            )
            embed.set_footer(text=f"変更者: {ctx.author.display_name}")

            await ctx.send(embed=embed)
            logger.info(f"タグモデレーション切り替え: {status_text} by {ctx.author.id}")

        except Exception as e:
            logger.error(f"タグモデレーション切り替えエラー: {e}")
            await ctx.send("❌ 設定の変更中にエラーが発生しました。")

    @tagmod_group.command(name="status", aliases=["ステータス"])
    @is_guild()
    @commands.has_permissions(moderate_members=True)
    @log_commands()
    async def tagmod_status(self, ctx) -> None:
        """現在のタグモデレーション設定を表示"""
        await ctx.defer()

        guild_id = ctx.guild.id
        config = await self.get_moderation_config(guild_id)
        banned_tags = await self.get_banned_tags(guild_id)

        embed = discord.Embed(
            title="⚙️ タグモデレーション設定",
            color=0x5865F2
        )

        # 機能の状態
        is_enabled = config.get('is_enabled', False) if config else False
        status_emoji = "✅ 有効" if is_enabled else "❌ 無効"
        embed.add_field(name="📊 機能状態", value=status_emoji, inline=True)

        # 禁止タグ数
        embed.add_field(name="🏷️ 禁止タグ数", value=f"{len(banned_tags)}個", inline=True)

        # 警告チャンネル
        if config and config.get('alert_channel_id'):
            channel = ctx.guild.get_channel(config['alert_channel_id'])
            channel_text = channel.mention if channel else "チャンネルが見つかりません"
        else:
            channel_text = "未設定"
        embed.add_field(name="📢 警告送信先", value=channel_text, inline=True)

        # タイムアウト設定
        if config:
            auto_timeout = config.get('auto_timeout', True)
            timeout_duration = config.get('timeout_duration', 604800)
            days = timeout_duration // 86400
            hours = (timeout_duration % 86400) // 3600

            timeout_text = f"{'✅ 有効' if auto_timeout else '❌ 無効'}\n期間: {days}日 {hours}時間"
        else:
            timeout_text = "デフォルト設定"

        embed.add_field(name="⏱️ 自動タイムアウト", value=timeout_text, inline=True)

        embed.set_footer(text=f"サーバー: {ctx.guild.name}")
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(TagModerationCog(bot))
