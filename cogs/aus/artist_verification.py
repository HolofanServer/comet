"""
AUS Artist Verification System
絵師認証システム
"""

import re

import discord
from discord import app_commands
from discord.ext import commands

from config.setting import get_settings
from utils.logging import setup_logging

from .database import DatabaseManager
from .views.verification_views import ArtistVerificationModal, VerificationButtons

logger = setup_logging()
settings = get_settings()


class ArtistVerification(commands.Cog):
    """絵師認証システム"""

    def __init__(self, bot: commands.Bot, db: DatabaseManager):
        self.bot = bot
        self.db = db

        # 認証チケット用カテゴリID
        self.ticket_category_id = settings.aus_ticket_category_id
        self.mod_role_id = settings.aus_mod_role_id

    @app_commands.command(
        name="verify_artist",
        description="絵師認証を申請します"
    )
    async def verify_artist(self, interaction: discord.Interaction):
        """絵師認証申請コマンド"""
        # 既に認証済みかチェック
        is_verified = await self.db.is_verified_artist(interaction.user.id)
        if is_verified:
            artist_info = await self.db.get_verified_artist(interaction.user.id)
            return await interaction.response.send_message(
                f"✅ あなたは既に認証済み絵師です\n"
                f"**Twitter:** {artist_info['twitter_handle']}",
                ephemeral=True
            )

        # 未解決チケットがあるかチェック
        pending_tickets = await self.db.get_user_pending_tickets(interaction.user.id)
        if pending_tickets:
            return await interaction.response.send_message(
                "⏳ 既に申請済みです。運営の審査をお待ちください。",
                ephemeral=True
            )

        # Modal表示
        modal = ArtistVerificationModal(self._handle_verification_submit)
        await interaction.response.send_modal(modal)

    async def _handle_verification_submit(
        self,
        interaction: discord.Interaction,
        twitter_handle: str,
        proof_description: str
    ):
        """認証申請Modal送信時の処理"""
        # Twitter URLを正規化
        twitter_url = self._normalize_twitter_url(twitter_handle)

        # チケットチャンネル作成
        channel = await self._create_ticket_channel(
            interaction.guild,
            interaction.user,
            twitter_handle
        )

        if not channel:
            return await interaction.response.send_message(
                "❌ チケットチャンネルの作成に失敗しました",
                ephemeral=True
            )

        # データベースにチケット作成
        ticket_id = await self.db.create_ticket(
            user_id=interaction.user.id,
            twitter_handle=twitter_handle,
            twitter_url=twitter_url,
            proof_description=proof_description,
            channel_id=channel.id
        )

        # チケット情報Embedを作成
        embed = discord.Embed(
            title="🎨 絵師認証申請",
            description=(
                "申請ありがとうございます！運営が確認後、認証処理を行います。\n"
                "本人確認が必要な場合、このチャンネルでやり取りを行います。"
            ),
            color=discord.Color.blue(),
            timestamp=interaction.created_at
        )

        embed.add_field(
            name="申請者",
            value=interaction.user.mention,
            inline=True
        )
        embed.add_field(
            name="Twitterハンドル",
            value=twitter_handle,
            inline=True
        )
        embed.add_field(
            name="Twitter URL",
            value=f"[プロフィール]({twitter_url})" if twitter_url else "未指定",
            inline=False
        )
        embed.add_field(
            name="本人確認方法",
            value=f"```\n{proof_description}\n```",
            inline=False
        )
        embed.add_field(
            name="チケットID",
            value=f"`#{ticket_id}`",
            inline=True
        )

        embed.set_footer(text=f"User ID: {interaction.user.id}")
        embed.set_thumbnail(url=interaction.user.display_avatar.url)

        # Viewボタン作成
        view = VerificationButtons(ticket_id)

        # チケットチャンネルに送信
        await channel.send(
            content=f"{interaction.user.mention} 運営ロール: <@&{self.mod_role_id}>",
            embed=embed,
            view=view
        )

        # 申請者に確認メッセージ
        await interaction.response.send_message(
            f"✅ 絵師認証申請を受け付けました\n"
            f"チケットチャンネル: {channel.mention}\n"
            f"チケットID: `#{ticket_id}`\n\n"
            f"運営が確認後、結果をDMで通知します。",
            ephemeral=True
        )

        logger.info(f"🎫 Verification ticket created: #{ticket_id} for {interaction.user}")

    def _normalize_twitter_url(self, input_str: str) -> str | None:
        """Twitter入力を正規化してURLを返す"""
        # 既にURLの場合
        if input_str.startswith('http'):
            # x.comをtwitter.comに統一
            return input_str.replace('x.com', 'twitter.com')

        # @で始まる場合は削除
        handle = input_str.lstrip('@')

        # 英数字とアンダースコアのみ許可
        if re.match(r'^[\w]+$', handle):
            return f"https://twitter.com/{handle}"

        return None

    async def _create_ticket_channel(
        self,
        guild: discord.Guild,
        user: discord.Member,
        twitter_handle: str
    ) -> discord.TextChannel | None:
        """チケット専用チャンネルを作成"""
        try:
            # カテゴリを取得
            category = None
            if self.ticket_category_id:
                category = guild.get_channel(self.ticket_category_id)

            # チャンネル名
            channel_name = f"ticket-{user.name}-{twitter_handle.lstrip('@')}"[:50]

            # 権限設定
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(
                    read_messages=False
                ),
                user: discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True,
                    attach_files=True
                ),
            }

            # 運営ロール権限
            if self.mod_role_id:
                mod_role = guild.get_role(self.mod_role_id)
                if mod_role:
                    overwrites[mod_role] = discord.PermissionOverwrite(
                        read_messages=True,
                        send_messages=True,
                        manage_messages=True
                    )

            # チャンネル作成
            channel = await guild.create_text_channel(
                name=channel_name,
                category=category,
                overwrites=overwrites,
                topic=f"絵師認証申請チケット - {user.name} ({user.id})"
            )

            return channel

        except discord.errors.Forbidden:
            logger.error("❌ Permission error: Cannot create ticket channel")
            return None
        except Exception as e:
            logger.error(f"❌ Error creating ticket channel: {e}")
            return None

    @app_commands.command(
        name="artist_info",
        description="絵師認証情報を表示します"
    )
    @app_commands.describe(user="確認するユーザー（省略時は自分）")
    async def artist_info(
        self,
        interaction: discord.Interaction,
        user: discord.User | None = None
    ):
        """絵師認証情報表示コマンド"""
        target_user = user or interaction.user

        # 認証情報を取得
        artist_info = await self.db.get_verified_artist(target_user.id)

        if not artist_info:
            return await interaction.response.send_message(
                f"❌ {target_user.mention} は絵師認証されていません",
                ephemeral=True
            )

        # Embed作成
        embed = discord.Embed(
            title="🎨 認証済み絵師情報",
            color=discord.Color.green()
        )

        embed.set_author(
            name=target_user.display_name,
            icon_url=target_user.display_avatar.url
        )

        embed.add_field(
            name="Twitterハンドル",
            value=artist_info['twitter_handle'],
            inline=True
        )
        embed.add_field(
            name="Twitter URL",
            value=f"[プロフィール]({artist_info['twitter_url']})",
            inline=True
        )
        embed.add_field(
            name="認証日時",
            value=f"<t:{int(artist_info['verified_at'].timestamp())}:F>",
            inline=False
        )

        if artist_info['notes']:
            notes = artist_info['notes']
            if len(notes) > 1024:
                notes = notes[:1021] + "…"
            embed.add_field(
                name="備考",
                value=notes,
                inline=False
            )

        embed.set_footer(text=f"User ID: {target_user.id}")

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    """Cog setup"""
    db = bot.db
    await bot.add_cog(ArtistVerification(bot, db))
