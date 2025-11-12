"""
AUS Verification Views
絵師認証用のComponent V2 Views
"""

import discord


class ArtistVerificationModal(discord.ui.Modal, title="🎨 絵師認証申請"):
    """絵師認証申請用Modal"""

    twitter_handle = discord.ui.TextInput(
        label="TwitterハンドルネームまたはURL",
        placeholder="例: @your_username または https://twitter.com/your_username",
        required=True,
        max_length=200
    )

    proof_description = discord.ui.TextInput(
        label="本人確認方法",
        placeholder="例: TwitterのDMで確認コードを送信します\nまたは: プロフィールに「Discord: username」を記載可能",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1000
    )

    def __init__(self, callback_func):
        """
        Args:
            callback_func: Modal送信時に呼び出される非同期コールバック関数
                           (interaction, twitter_handle, proof_description) を受け取る
        """
        super().__init__()
        self.callback_func = callback_func

    async def on_submit(self, interaction: discord.Interaction):
        """Modal送信時の処理"""
        await self.callback_func(
            interaction,
            self.twitter_handle.value,
            self.proof_description.value
        )


class VerificationButtons(discord.ui.View):
    """絵師認証チケット用のボタンView"""

    def __init__(self, ticket_id: int):
        super().__init__(timeout=None)  # Persistent View
        self.ticket_id = ticket_id
        # custom_idにticket_idを埋め込む
        self.approve_button.custom_id = f"aus:approve:{ticket_id}"
        self.reject_button.custom_id = f"aus:reject:{ticket_id}"

    @discord.ui.button(
        label="✅ 承認",
        style=discord.ButtonStyle.success,
        custom_id="aus:approve"
    )
    async def approve_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        """認証を承認"""
        # 権限チェック
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message(
                "❌ この操作には`manage_guild`権限が必要です",
                ephemeral=True
            )

        # custom_idからticket_idを抽出
        ticket_id = int(button.custom_id.split(':')[-1])

        # DatabaseManagerを取得
        db = interaction.client.db
        ticket = await db.get_ticket(ticket_id)

        if not ticket:
            return await interaction.response.send_message(
                "❌ チケットが見つかりませんでした",
                ephemeral=True
            )

        if ticket['status'] != 'pending':
            return await interaction.response.send_message(
                f"❌ このチケットは既に処理済みです（ステータス: {ticket['status']}）",
                ephemeral=True
            )

        # 承認処理
        success = await db.approve_ticket(
            ticket_id,
            interaction.user.id,
            ticket['twitter_handle'],
            ticket['twitter_url'] or f"https://twitter.com/{ticket['twitter_handle'].lstrip('@')}"
        )

        if success:
            # ボタンを無効化
            for item in self.children:
                item.disabled = True
            await interaction.message.edit(view=self)

            # ギルドメンバーを取得して通知
            guild = interaction.guild
            user = guild.get_member(ticket['user_id'])

            user_mention = user.mention if user else f"<@{ticket['user_id']}>"
            await interaction.response.send_message(
                f"✅ **認証を承認しました**\n"
                f"承認者: {interaction.user.mention}\n"
                f"絵師: {user_mention}\n"
                f"Twitter: {ticket['twitter_handle']}",
                ephemeral=False
            )

            # 申請者にDMで通知
            if user:
                try:
                    embed = discord.Embed(
                        title="🎉 絵師認証が承認されました！",
                        description=(
                            "おめでとうございます！絵師認証が承認されました。\n"
                            "これで、あなたの投稿する画像は無断転載チェックをスキップされます。"
                        ),
                        color=discord.Color.green()
                    )
                    embed.add_field(
                        name="認証されたTwitterアカウント",
                        value=ticket['twitter_handle']
                    )
                    embed.set_footer(text=f"承認者: {interaction.user.name}")
                    await user.send(embed=embed)
                except discord.errors.Forbidden:
                    pass  # DMが送信できない場合は無視
        else:
            await interaction.response.send_message(
                "❌ 承認処理に失敗しました",
                ephemeral=True
            )

    @discord.ui.button(
        label="❌ 却下",
        style=discord.ButtonStyle.danger,
        custom_id="aus:reject"
    )
    async def reject_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        """認証を却下（理由入力Modalを表示）"""
        # 権限チェック
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message(
                "❌ この操作には`manage_guild`権限が必要です",
                ephemeral=True
            )

        # custom_idからticket_idを抽出
        ticket_id = int(button.custom_id.split(':')[-1])

        # 却下理由入力Modalを表示
        modal = RejectReasonModal(ticket_id, interaction.client.db)
        await interaction.response.send_modal(modal)


class RejectReasonModal(discord.ui.Modal, title="❌ 認証却下理由"):
    """認証却下理由入力Modal"""

    rejection_reason = discord.ui.TextInput(
        label="却下理由",
        placeholder="申請者に通知される却下理由を入力してください",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1000
    )

    def __init__(self, ticket_id: int, db):
        super().__init__()
        self.ticket_id = ticket_id
        self.db = db

    async def on_submit(self, interaction: discord.Interaction):
        """却下処理"""
        ticket = await self.db.get_ticket(self.ticket_id)

        if not ticket:
            return await interaction.response.send_message(
                "❌ チケットが見つかりませんでした",
                ephemeral=True
            )

        if ticket['status'] != 'pending':
            return await interaction.response.send_message(
                f"❌ このチケットは既に処理済みです（ステータス: {ticket['status']}）",
                ephemeral=True
            )

        # 却下処理
        success = await self.db.reject_ticket(
            self.ticket_id,
            interaction.user.id,
            self.rejection_reason.value
        )

        if success:
            # 元のメッセージのボタンを無効化
            original_message = interaction.message
            if original_message:
                view = discord.ui.View.from_message(original_message)
                for item in view.children:
                    item.disabled = True
                await original_message.edit(view=view)

            # ギルドメンバーを取得
            guild = interaction.guild
            user = guild.get_member(ticket['user_id'])

            user_mention = user.mention if user else f"<@{ticket['user_id']}>"
            await interaction.response.send_message(
                f"❌ **認証を却下しました**\n"
                f"却下者: {interaction.user.mention}\n"
                f"申請者: {user_mention}\n"
                f"理由: {self.rejection_reason.value}",
                ephemeral=False
            )

            # 申請者にDMで通知
            if user:
                try:
                    embed = discord.Embed(
                        title="❌ 絵師認証が却下されました",
                        description=(
                            "申し訳ございませんが、絵師認証申請が却下されました。"
                        ),
                        color=discord.Color.red()
                    )
                    embed.add_field(
                        name="却下理由",
                        value=self.rejection_reason.value,
                        inline=False
                    )
                    embed.add_field(
                        name="再申請について",
                        value="理由を確認の上、必要であれば再度申請してください。",
                        inline=False
                    )
                    embed.set_footer(text=f"処理者: {interaction.user.name}")
                    await user.send(embed=embed)
                except discord.errors.Forbidden:
                    pass  # DMが送信できない場合は無視
        else:
            await interaction.response.send_message(
                "❌ 却下処理に失敗しました",
                ephemeral=True
            )
