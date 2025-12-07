"""
MyHFS Linked Roles Cog

Discord Linked Roles APIを管理するCog

機能:
- メタデータスキーマの登録
- ユーザーメタデータの一括更新（バッチ処理）
- 手動同期コマンド

Discord Developer Portal設定が必要:
- General Information > LINKED ROLES VERIFICATION URL
- OAuth2 > Redirects

詳細は docs/myhfs-linked-roles-spec-v2.md を参照
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Optional

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks

from config.setting import get_settings
from utils.logging import setup_logging

logger = setup_logging()


class LinkedRolesCog(commands.Cog):
    """Linked Roles機能を管理するCog"""

    DISCORD_API_BASE = "https://discord.com/api/v10"

    # メタデータスキーマ定義（最大5個まで）
    METADATA_SCHEMA = [
        {
            "type": 7,  # BOOLEAN_EQUAL
            "key": "card_created",
            "name": "カード作成済み",
            "name_localizations": {"en-US": "Card Created"},
            "description": "MyHFSでカードを作成済み",
            "description_localizations": {"en-US": "Has created MyHFS card"},
        },
        {
            "type": 2,  # INTEGER_GREATER_THAN_OR_EQUAL
            "key": "member_number",
            "name": "メンバー番号",
            "name_localizations": {"en-US": "Member Number"},
            "description": "MyHFSメンバー番号",
            "description_localizations": {"en-US": "MyHFS member number"},
        },
        {
            "type": 6,  # DATETIME_GREATER_THAN_OR_EQUAL
            "key": "joined_at",
            "name": "参加日",
            "name_localizations": {"en-US": "Joined Date"},
            "description": "HFS参加日からの経過日数",
            "description_localizations": {"en-US": "Days since joining HFS"},
        },
        {
            "type": 2,  # INTEGER_GREATER_THAN_OR_EQUAL
            "key": "oshi_count",
            "name": "推し人数",
            "name_localizations": {"en-US": "Oshi Count"},
            "description": "登録した推しメンバーの人数",
            "description_localizations": {
                "en-US": "Number of registered oshi members"
            },
        },
    ]

    def __init__(self, bot: commands.Bot) -> None:
        """
        LinkedRolesCogの初期化

        Args:
            bot: Botインスタンス
        """
        self.bot = bot
        self.session: Optional[aiohttp.ClientSession] = None

        # 設定から取得
        settings = get_settings()
        self.client_id = settings.discord_client_id
        self.client_secret = settings.discord_client_secret
        self.bot_token = settings.bot_token
        self.myhfs_api_base = settings.myhfs_linked_roles_api_url
        self.myhfs_bot_token = settings.myhfs_linked_roles_token

    async def cog_load(self) -> None:
        """Cog読み込み時の初期化"""
        self.session = aiohttp.ClientSession()
        logger.info("LinkedRolesCog を読み込みました")

        # バッチ更新タスク開始
        if not self.batch_update_metadata.is_running():
            self.batch_update_metadata.start()

    async def cog_unload(self) -> None:
        """Cog解除時のクリーンアップ"""
        if self.session:
            await self.session.close()

        if self.batch_update_metadata.is_running():
            self.batch_update_metadata.cancel()

        logger.info("LinkedRolesCog を解除しました")

    # ========================================
    # Discord API ヘルパー関数
    # ========================================

    async def _api_request(
        self,
        method: str,
        endpoint: str,
        *,
        headers: Optional[dict[str, str]] = None,
        json_data: Optional[Any] = None,
        form_data: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        """
        Discord APIリクエストヘルパー

        Args:
            method: HTTPメソッド
            endpoint: APIエンドポイント
            headers: リクエストヘッダー
            json_data: JSONボディ
            form_data: フォームデータ

        Returns:
            APIレスポンス

        Raises:
            Exception: API リクエスト失敗時
        """
        if not self.session:
            raise RuntimeError("セッションが初期化されていません")

        url = f"{self.DISCORD_API_BASE}{endpoint}"

        async with self.session.request(
            method,
            url,
            headers=headers,
            json=json_data,
            data=form_data,
        ) as response:
            if response.status == 429:
                # レート制限
                retry_after = float(response.headers.get("Retry-After", 5))
                logger.warning(f"レート制限を受けました。{retry_after}秒後にリトライします")
                await asyncio.sleep(retry_after)
                return await self._api_request(
                    method,
                    endpoint,
                    headers=headers,
                    json_data=json_data,
                    form_data=form_data,
                )

            response_data = await response.json() if response.content_length else {}

            if not response.ok:
                logger.error(
                    f"APIリクエスト失敗: {response.status} - {response_data}"
                )
                raise Exception(f"APIリクエスト失敗: {response.status}")

            return response_data

    # ========================================
    # メタデータスキーマ管理
    # ========================================

    async def register_metadata_schema(self) -> list[dict[str, Any]]:
        """
        メタデータスキーマをDiscordに登録

        Returns:
            登録されたスキーマ
        """
        return await self._api_request(
            "PUT",
            f"/applications/{self.client_id}/role-connections/metadata",
            headers={
                "Authorization": f"Bot {self.bot_token}",
                "Content-Type": "application/json",
            },
            json_data=self.METADATA_SCHEMA,
        )

    async def get_metadata_schema(self) -> list[dict[str, Any]]:
        """
        登録済みメタデータスキーマを取得

        Returns:
            現在のスキーマ
        """
        return await self._api_request(
            "GET",
            f"/applications/{self.client_id}/role-connections/metadata",
            headers={"Authorization": f"Bot {self.bot_token}"},
        )

    # ========================================
    # ユーザーメタデータ更新
    # ========================================

    async def update_user_metadata(
        self,
        access_token: str,
        platform_name: str,
        platform_username: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        """
        ユーザーのLinked Rolesメタデータを更新

        Args:
            access_token: ユーザーのOAuth2アクセストークン
            platform_name: プラットフォーム名（例: "MyHFS"）
            platform_username: 表示名（例: "35P"）
            metadata: メタデータ辞書

        Returns:
            更新結果
        """
        return await self._api_request(
            "PUT",
            f"/users/@me/applications/{self.client_id}/role-connection",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json_data={
                "platform_name": platform_name,
                "platform_username": platform_username,
                "metadata": metadata,
            },
        )

    async def refresh_user_token(self, refresh_token: str) -> dict[str, Any]:
        """
        ユーザーのOAuth2トークンをリフレッシュ

        Args:
            refresh_token: リフレッシュトークン

        Returns:
            新しいトークン情報
        """
        return await self._api_request(
            "POST",
            "/oauth2/token",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            form_data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
        )

    # ========================================
    # MyHFS API連携
    # ========================================

    async def fetch_linked_users_from_myhfs(self) -> list[dict[str, Any]]:
        """
        MyHFS APIから連携ユーザー一覧を取得

        Returns:
            連携ユーザーリスト
        """
        if not self.session:
            raise RuntimeError("セッションが初期化されていません")

        async with self.session.get(
            f"{self.myhfs_api_base}/bot/linked-roles",
            headers={"Authorization": f"Bearer {self.myhfs_bot_token}"},
        ) as response:
            if not response.ok:
                error_text = await response.text()
                raise Exception(f"MyHFS APIエラー: {response.status} - {error_text}")
            data = await response.json()
            return data.get("users", [])

    async def notify_token_refresh_to_myhfs(
        self,
        user_id: str,
        access_token: str,
        refresh_token: str,
        expires_at: str,
    ) -> None:
        """
        新しいトークンをMyHFSに通知

        Args:
            user_id: ユーザーID
            access_token: 新しいアクセストークン
            refresh_token: 新しいリフレッシュトークン
            expires_at: 有効期限（ISO8601形式）
        """
        if not self.session:
            return

        try:
            async with self.session.post(
                f"{self.myhfs_api_base}/bot/linked-roles/token-refresh",
                headers={
                    "Authorization": f"Bearer {self.myhfs_bot_token}",
                    "Content-Type": "application/json",
                },
                json={
                    "userId": user_id,
                    "accessToken": access_token,
                    "refreshToken": refresh_token,
                    "tokenExpiresAt": expires_at,
                },
            ) as response:
                if not response.ok:
                    logger.warning(
                        f"トークン更新通知失敗: {user_id} - {response.status}"
                    )
        except Exception as e:
            logger.error(f"トークン更新通知エラー: {e}")

    # ========================================
    # バッチ処理
    # ========================================

    @tasks.loop(hours=24)
    async def batch_update_metadata(self) -> None:
        """全連携ユーザーのメタデータを定期更新（1日1回）"""
        logger.info("バッチメタデータ更新を開始します...")

        try:
            users = await self.fetch_linked_users_from_myhfs()
            logger.info(f"{len(users)}人の連携ユーザーを取得しました")

            success_count = 0
            error_count = 0

            for user_data in users:
                try:
                    access_token = user_data["accessToken"]
                    user_id = user_data["userId"]
                    discord_id = user_data.get("discordId", "unknown")

                    # トークン期限チェック
                    expires_at = datetime.fromisoformat(
                        user_data["tokenExpiresAt"].replace("Z", "+00:00")
                    )

                    if expires_at < datetime.now(timezone.utc):
                        # トークンリフレッシュ
                        try:
                            new_tokens = await self.refresh_user_token(
                                user_data["refreshToken"]
                            )
                            access_token = new_tokens["access_token"]

                            # 新しい有効期限を計算
                            new_expires_at = datetime.now(timezone.utc).isoformat()

                            # MyHFSにトークン更新を通知
                            await self.notify_token_refresh_to_myhfs(
                                user_id,
                                new_tokens["access_token"],
                                new_tokens["refresh_token"],
                                new_expires_at,
                            )

                        except Exception as e:
                            logger.warning(
                                f"トークンリフレッシュ失敗 (Discord ID: {discord_id}): {e}"
                            )
                            error_count += 1
                            continue

                    # メタデータ更新
                    metadata_payload = user_data["metadata"]
                    await self.update_user_metadata(
                        access_token,
                        metadata_payload["platform_name"],
                        metadata_payload["platform_username"],
                        metadata_payload["metadata"],
                    )

                    success_count += 1

                    # レート制限対策
                    await asyncio.sleep(0.1)

                except Exception as e:
                    logger.error(
                        f"ユーザー更新失敗 (Discord ID: {user_data.get('discordId')}): {e}"
                    )
                    error_count += 1

            logger.info(
                f"バッチ更新完了: 成功={success_count}, エラー={error_count}"
            )

        except Exception as e:
            logger.error(f"バッチ更新失敗: {e}")

    @batch_update_metadata.before_loop
    async def before_batch_update(self) -> None:
        """Bot準備完了まで待機"""
        await self.bot.wait_until_ready()

    # ========================================
    # 管理者コマンド
    # ========================================

    @app_commands.command(
        name="linkedroles-setup",
        description="Linked Rolesのメタデータスキーマを登録します",
    )
    @app_commands.default_permissions(administrator=True)
    async def setup_linked_roles(self, interaction: discord.Interaction) -> None:
        """
        メタデータスキーマをDiscordに登録

        Args:
            interaction: インタラクション
        """
        await interaction.response.defer(ephemeral=True)

        try:
            result = await self.register_metadata_schema()

            schema_list = "\n".join(
                [
                    f"• `{s['key']}`: {s['name']} (type={s['type']})"
                    for s in result
                ]
            )

            embed = discord.Embed(
                title="✅ Linked Roles スキーマ登録完了",
                description=f"以下のメタデータを登録しました:\n\n{schema_list}",
                color=discord.Color.green(),
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.exception("スキーマ登録エラー")
            await interaction.followup.send(
                f"❌ スキーマ登録に失敗しました: {e}",
                ephemeral=True,
            )

    @app_commands.command(
        name="linkedroles-schema",
        description="現在のLinked Rolesスキーマを表示します",
    )
    @app_commands.default_permissions(administrator=True)
    async def show_schema(self, interaction: discord.Interaction) -> None:
        """
        現在のスキーマを表示

        Args:
            interaction: インタラクション
        """
        await interaction.response.defer(ephemeral=True)

        try:
            schema = await self.get_metadata_schema()

            if not schema:
                await interaction.followup.send(
                    "スキーマが登録されていません。`/linkedroles-setup`を実行してください。",
                    ephemeral=True,
                )
                return

            schema_list = "\n".join(
                [f"• `{s['key']}`: {s['name']} (type={s['type']})" for s in schema]
            )

            embed = discord.Embed(
                title="📋 Linked Roles スキーマ",
                description=schema_list,
                color=discord.Color.blue(),
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.exception("スキーマ取得エラー")
            await interaction.followup.send(
                f"❌ スキーマ取得に失敗しました: {e}",
                ephemeral=True,
            )

    @app_commands.command(
        name="linkedroles-batch",
        description="全ユーザーのLinked Rolesメタデータを手動更新します",
    )
    @app_commands.default_permissions(administrator=True)
    async def manual_batch_update(self, interaction: discord.Interaction) -> None:
        """
        手動バッチ更新

        Args:
            interaction: インタラクション
        """
        await interaction.response.defer(ephemeral=True)

        try:
            await interaction.followup.send(
                "🔄 バッチ更新を開始します...",
                ephemeral=True,
            )

            # バッチ処理を即座に実行
            await self.batch_update_metadata()

            await interaction.edit_original_response(
                content="✅ バッチ更新が完了しました"
            )

        except Exception as e:
            logger.exception("バッチ更新エラー")
            await interaction.edit_original_response(
                content=f"❌ バッチ更新に失敗しました: {e}"
            )

    @app_commands.command(
        name="linkedroles-status",
        description="Linked Roles連携の統計情報を表示します",
    )
    @app_commands.default_permissions(administrator=True)
    async def show_status(self, interaction: discord.Interaction) -> None:
        """
        ステータス表示

        Args:
            interaction: インタラクション
        """
        await interaction.response.defer(ephemeral=True)

        try:
            users = await self.fetch_linked_users_from_myhfs()

            embed = discord.Embed(
                title="📊 Linked Roles ステータス",
                color=discord.Color.blue(),
            )
            embed.add_field(
                name="連携ユーザー数",
                value=f"{len(users)}人",
                inline=True,
            )
            embed.add_field(
                name="バッチ更新",
                value="実行中" if self.batch_update_metadata.is_running() else "停止中",
                inline=True,
            )

            next_run = self.batch_update_metadata.next_iteration
            embed.add_field(
                name="次回バッチ",
                value=next_run.strftime("%Y-%m-%d %H:%M:%S") if next_run else "未定",
                inline=True,
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.exception("ステータス取得エラー")
            await interaction.followup.send(
                f"❌ ステータス取得に失敗しました: {e}",
                ephemeral=True,
            )

    @app_commands.command(
        name="linkedroles-test",
        description="Linked Roles設定のテストを行います",
    )
    @app_commands.default_permissions(administrator=True)
    async def test_connection(self, interaction: discord.Interaction) -> None:
        """
        接続テスト

        Args:
            interaction: インタラクション
        """
        await interaction.response.defer(ephemeral=True)

        results = []

        # 1. 設定値チェック
        if self.client_id:
            results.append("✅ DISCORD_CLIENT_ID: 設定済み")
        else:
            results.append("❌ DISCORD_CLIENT_ID: 未設定")

        if self.client_secret:
            results.append("✅ DISCORD_CLIENT_SECRET: 設定済み")
        else:
            results.append("❌ DISCORD_CLIENT_SECRET: 未設定")

        if self.myhfs_api_base:
            results.append(f"✅ MyHFS API URL: {self.myhfs_api_base}")
        else:
            results.append("❌ MyHFS API URL: 未設定")

        if self.myhfs_bot_token:
            results.append("✅ MyHFS Bot Token: 設定済み")
        else:
            results.append("❌ MyHFS Bot Token: 未設定")

        # 2. Discord APIテスト
        try:
            schema = await self.get_metadata_schema()
            if schema:
                results.append(f"✅ Discord API: スキーマ {len(schema)}件取得成功")
            else:
                results.append("⚠️ Discord API: スキーマ未登録")
        except Exception as e:
            results.append(f"❌ Discord API: {e}")

        # 3. MyHFS APIテスト
        try:
            users = await self.fetch_linked_users_from_myhfs()
            results.append(f"✅ MyHFS API: {len(users)}人の連携ユーザー取得成功")
        except Exception as e:
            results.append(f"❌ MyHFS API: {e}")

        embed = discord.Embed(
            title="🔧 Linked Roles 接続テスト",
            description="\n".join(results),
            color=discord.Color.blue(),
        )

        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(LinkedRolesCog(bot))
