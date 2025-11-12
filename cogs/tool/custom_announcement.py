import json
import os
from datetime import datetime
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands

from utils.commands_help import is_owner_app
from utils.future.cv2 import cv2
from utils.logging import setup_logging

logger = setup_logging("D")

class CustomAnnouncement(commands.Cog):
    """カスタムアナウンス機能 - インタラクティブにメッセージをカスタマイズして送信"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.sessions: dict[str, dict[str, Any]] = {}
        self.data_dir = 'data/custom_announcements'
        self.templates_file = f'{self.data_dir}/templates.json'

        os.makedirs(self.data_dir, exist_ok=True)

        self.templates = self._load_templates()

    def _load_templates(self) -> dict[str, Any]:
        """保存されたテンプレートをロード"""
        if os.path.exists(self.templates_file):
            try:
                with open(self.templates_file, encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                logger.error(f"テンプレートファイルの読み込みエラー: {self.templates_file}")
        return {"templates": []}

    def _save_templates(self):
        """テンプレートを保存"""
        try:
            with open(self.templates_file, 'w', encoding='utf-8') as f:
                json.dump(self.templates, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"テンプレート保存エラー: {e}")

    @app_commands.command(name="カスタムアナウンス", description="CV2を使ったカスタマイズ可能なアナウンスを作成")
    @app_commands.describe(
        action="実行するアクション",
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="作成", value="create"),
        app_commands.Choice(name="テンプレート保存", value="save_template"),
        app_commands.Choice(name="テンプレート一覧", value="list_templates"),
        app_commands.Choice(name="テンプレート使用", value="use_template"),
    ])
    @is_owner_app()
    async def custom_announcement(
        self,
        interaction: discord.Interaction,
        action: app_commands.Choice[str]
    ):
        """カスタムアナウンスコマンドのエントリーポイント"""
        # ログ記録
        logger.info(f"カスタムアナウンスコマンド実行: {interaction.user.name} - {action.name}")

        if action.value == "create":
            await self.start_create_session(interaction)
        elif action.value == "save_template":
            await self.save_template(interaction)
        elif action.value == "list_templates":
            await self.list_templates(interaction)
        elif action.value == "use_template":
            await self.use_template(interaction)

    async def start_create_session(self, interaction: discord.Interaction):
        """新しいアナウンス作成セッションを開始"""
        session_id = f"{interaction.user.id}_{datetime.now().timestamp()}"

        self.sessions[session_id] = {
            "user_id": interaction.user.id,
            "channel_id": interaction.channel_id,
            "components": [],
            "created_at": datetime.now().timestamp(),
        }

        await self.show_editor(interaction, session_id)

    async def show_editor(self, interaction: discord.Interaction, session_id: str):
        """エディタUI表示"""
        session = self.sessions.get(session_id)
        if not session:
            await interaction.response.send_message("セッションが見つかりません。再度コマンドを実行してください。", ephemeral=True)
            return

        # CV2を使用する場合は、cv2.reply()メソッドを使用する
        components = [
            cv2.container([
                cv2.section([
                    cv2.text_display("📝 アナウンスをカスタマイズ"),
                    cv2.text_display("以下のボタンを使って、メッセージの内容や外観を編集できます")
                ]),
                cv2.section([
                    cv2.button("要素を追加", style="primary", custom_id=f"ca:add:{session_id}"),
                    cv2.button("プレビュー", style="secondary", custom_id=f"ca:preview:{session_id}"),
                    cv2.button("送信", style="success", custom_id=f"ca:send:{session_id}"),
                    cv2.button("キャンセル", style="danger", custom_id=f"ca:cancel:{session_id}")
                ])
            ])
        ]

        # タイトルも含めてcv2.reply()で送信
        await cv2.reply(
            interaction,
            components=components,
            ephemeral=True
        )

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        """インタラクションイベントを処理"""
        if not interaction.data:
            return

        if interaction.type == discord.InteractionType.modal_submit:
            custom_id = interaction.data.get("custom_id", "")
            if custom_id.startswith("ca:modal:"):
                if hasattr(self.bot, "modal_callbacks") and custom_id in self.bot.modal_callbacks:
                    callback = self.bot.modal_callbacks.pop(custom_id)
                    await callback(interaction)
                return

        if not interaction.data.get("custom_id"):
            return

        custom_id = interaction.data["custom_id"]

        if not custom_id.startswith("ca:"):
            return

        parts = custom_id.split(":")
        if len(parts) < 3:
            return

        action = parts[1]
        session_id = parts[2]

        if session_id not in self.sessions:
            await interaction.response.send_message("セッションが終了したか見つかりません。再度コマンドを実行してください。", ephemeral=True)
            return

        if interaction.user.id != self.sessions[session_id]["user_id"]:
            await interaction.response.send_message("このセッションを操作する権限がありません。", ephemeral=True)
            return

        if action == "add":
            await self.show_add_element_menu(interaction, session_id)
        elif action == "preview":
            await self.show_preview(interaction, session_id)
        elif action == "send":
            await self.show_send_options(interaction, session_id)
        elif action == "cancel":
            await self.cancel_session(interaction, session_id)
        elif action == "back":
            await self.show_editor(interaction, session_id)
        elif action == "add_text":
            text_type = parts[3] if len(parts) > 3 else "normal"
            await self.add_text_element(interaction, session_id, text_type)
        elif action == "add_button":
            await self.add_button_element(interaction, session_id)
        elif action == "add_select":
            await self.add_select_element(interaction, session_id)
        elif action == "add_media":
            await self.add_media_element(interaction, session_id)
        elif action == "remove":
            index = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else -1
            await self.remove_element(interaction, session_id, index)
        elif action == "select_channel":
            try:
                selected_value = interaction.data["values"][0]
                await self.send_announcement(interaction, session_id, selected_value)
            except (KeyError, IndexError):
                await interaction.response.send_message("チャンネルの選択に問題が発生しました。再度お試しください。", ephemeral=True)
        elif action == "confirm_send":
            channel_id = parts[3] if len(parts) > 3 else None
            await self.send_announcement(interaction, session_id, channel_id)

    async def show_add_element_menu(self, interaction: discord.Interaction, session_id: str):
        """要素追加メニューを表示"""
        await interaction.response.send_message(
            "追加する要素を選択",
            flags=cv2.flags.IS_COMPONENTS_V2 | cv2.flags.EPHEMERAL,
            components=[
                cv2.container(
                    cv2.section(
                        cv2.text_display("🧩 要素タイプを選択"),
                        cv2.text_display("追加したい要素のタイプを選択してください")
                    ),
                    cv2.section(
                        cv2.button("テキスト", style="primary", custom_id=f"ca:add_text:normal:{session_id}"),
                        cv2.button("見出し", style="primary", custom_id=f"ca:add_text:heading:{session_id}"),
                        cv2.button("区切り線", style="secondary", custom_id=f"ca:add_text:separator:{session_id}")
                    ),
                    cv2.section(
                        cv2.button("ボタン", style="success", custom_id=f"ca:add_button:{session_id}"),
                        cv2.button("セレクトメニュー", style="success", custom_id=f"ca:add_select:{session_id}")
                    ),
                    cv2.section(
                        cv2.button("メディア", style="secondary", custom_id=f"ca:add_media:{session_id}"),
                        cv2.button("戻る", style="danger", custom_id=f"ca:back:{session_id}")
                    )
                )
            ]
        )

    async def add_text_element(self, interaction: discord.Interaction, session_id: str, text_type: str):
        """テキスト要素を追加するモーダルを表示"""
        if text_type == "separator":
            element = {"type": "separator"}
            self.sessions[session_id]["components"].append(element)
            await self.show_editor(interaction, session_id)
            return

        modal = TextElementModal(text_type)
        modal.custom_id = f"ca:modal:text:{text_type}:{session_id}"

        async def modal_callback(modal_interaction: discord.Interaction):
            if text_type == "heading":
                text = modal_interaction.data["components"][0]["components"][0]["value"]
                level_str = modal_interaction.data["components"][1]["components"][0]["value"]
                try:
                    level = int(level_str)
                    if level < 1 or level > 3:
                        level = 2
                except ValueError:
                    level = 2

                element = {
                    "type": "text",
                    "text_type": "heading",
                    "content": text,
                    "heading_level": level
                }
            else:
                text = modal_interaction.data["components"][0]["components"][0]["value"]
                element = {
                    "type": "text",
                    "text_type": "normal",
                    "content": text
                }

            self.sessions[session_id]["components"].append(element)
            await self.show_editor(modal_interaction, session_id)

        self.bot.modal_callbacks[modal.custom_id] = modal_callback

        await interaction.response.send_modal(modal)

    async def add_button_element(self, interaction: discord.Interaction, session_id: str):
        """ボタン要素を追加するモーダルを表示"""
        modal = ButtonElementModal()
        modal.custom_id = f"ca:modal:button:{session_id}"

        async def modal_callback(modal_interaction: discord.Interaction):
            label = modal_interaction.data["components"][0]["components"][0]["value"]
            custom_id = modal_interaction.data["components"][1]["components"][0]["value"]
            style = modal_interaction.data["components"][2]["components"][0]["value"].lower()
            emoji = modal_interaction.data["components"][3]["components"][0]["value"]

            valid_styles = ["primary", "secondary", "success", "danger", "link"]
            if style not in valid_styles:
                style = "primary"

            element = {
                "type": "button",
                "label": label,
                "custom_id": custom_id,
                "style": style,
                "emoji": emoji if emoji else None
            }

            self.sessions[session_id]["components"].append(element)
            await self.show_editor(modal_interaction, session_id)

        self.bot.modal_callbacks[modal.custom_id] = modal_callback
        await interaction.response.send_modal(modal)

    async def add_select_element(self, interaction: discord.Interaction, session_id: str):
        """セレクトメニュー要素を追加するモーダルを表示"""
        modal = SelectElementModal()
        modal.custom_id = f"ca:modal:select:{session_id}"

        async def modal_callback(modal_interaction: discord.Interaction):
            custom_id = modal_interaction.data["components"][0]["components"][0]["value"]
            placeholder = modal_interaction.data["components"][1]["components"][0]["value"]
            options_text = modal_interaction.data["components"][2]["components"][0]["value"]

            options = []
            for line in options_text.split("\n"):
                if not line.strip():
                    continue

                parts = line.split("|", 2)
                if len(parts) >= 2:
                    label = parts[0].strip()
                    value = parts[1].strip()
                    desc = parts[2].strip() if len(parts) > 2 else None

                    option = {"label": label, "value": value}
                    if desc:
                        option["description"] = desc
                    options.append(option)
                else:
                    label = line.strip()
                    options.append({"label": label, "value": label})

            if not options:
                await modal_interaction.response.send_message("有効なオプションが指定されていません。再度試してください。", ephemeral=True)
                return

            element = {
                "type": "select",
                "custom_id": custom_id,
                "placeholder": placeholder,
                "options": options
            }

            self.sessions[session_id]["components"].append(element)
            await self.show_editor(modal_interaction, session_id)

        self.bot.modal_callbacks[modal.custom_id] = modal_callback
        await interaction.response.send_modal(modal)

    async def add_media_element(self, interaction: discord.Interaction, session_id: str):
        """メディア要素を追加するモーダルを表示"""
        modal = MediaElementModal()
        modal.custom_id = f"ca:modal:media:{session_id}"

        async def modal_callback(modal_interaction: discord.Interaction):
            urls_text = modal_interaction.data["components"][0]["components"][0]["value"]

            urls = [url.strip() for url in urls_text.split("\n") if url.strip()]

            if not urls:
                await modal_interaction.response.send_message("有効なURLが指定されていません。再度試してください。", ephemeral=True)
                return

            element = {
                "type": "media",
                "urls": urls
            }

            self.sessions[session_id]["components"].append(element)
            await self.show_editor(modal_interaction, session_id)

        self.bot.modal_callbacks[modal.custom_id] = modal_callback
        await interaction.response.send_modal(modal)

    async def show_preview(self, interaction: discord.Interaction, session_id: str):
        """プレビューを表示"""
        session = self.sessions.get(session_id)
        if not session or not session.get("components"):
            await interaction.response.send_message("プレビューする要素がありません。要素を追加してください。", ephemeral=True)
            return

        cv2_components = await self.convert_to_cv2_components(session["components"])

        await interaction.response.send_message(
            "プレビュー",
            flags=cv2.flags.IS_COMPONENTS_V2 | cv2.flags.EPHEMERAL,
            components=[
                cv2.container(
                    cv2.section(
                        cv2.text_display("👁️ プレビュー"),
                        cv2.text_display("これが実際に送信されるメッセージです")
                    )
                ),
                *cv2_components,
                cv2.container(
                    cv2.section(
                        cv2.button("編集に戻る", style="secondary", custom_id=f"ca:back:{session_id}")
                    )
                )
            ]
        )

    async def show_send_options(self, interaction: discord.Interaction, session_id: str):
        """送信オプションを表示"""
        guild = interaction.guild
        if not guild:
            await interaction.response.send_message("サーバー内でのみ使用できます。", ephemeral=True)
            return

        text_channels = [
            (channel.name, str(channel.id))
            for channel in guild.text_channels
            if channel.permissions_for(guild.me).send_messages
        ]

        if not text_channels:
            await interaction.response.send_message("送信可能なチャンネルがありません。", ephemeral=True)
            return

        channel_options = [
            {"label": f"#{name}", "value": channel_id}
            for name, channel_id in text_channels
        ]

        await interaction.response.send_message(
            "送信先を選択",
            flags=cv2.flags.IS_COMPONENTS_V2 | cv2.flags.EPHEMERAL,
            components=[
                cv2.container(
                    cv2.section(
                        cv2.text_display("📩 送信先チャンネルを選択"),
                        cv2.text_display("メッセージを送信するチャンネルを選択してください")
                    ),
                    cv2.row([
                        cv2.string_select(
                            custom_id=f"ca:select_channel:{session_id}",
                            options=channel_options,
                            placeholder="送信先チャンネルを選択"
                        )
                    ]),
                    cv2.section(
                        cv2.button("戻る", style="secondary", custom_id=f"ca:back:{session_id}")
                    )
                )
            ]
        )

    async def cancel_session(self, interaction: discord.Interaction, session_id: str):
        """セッションをキャンセル"""
        if session_id in self.sessions:
            del self.sessions[session_id]

        await interaction.response.send_message("カスタムアナウンスの作成をキャンセルしました。", ephemeral=True)

    async def convert_to_cv2_components(self, components: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """コンポーネント定義をCV2形式に変換"""
        cv2_components = []
        section_items = []

        for comp in components:
            comp_type = comp.get("type")

            if comp_type == "text":
                text_type = comp.get("text_type", "normal")
                content = comp.get("content", "")

                if text_type == "heading":
                    heading_level = comp.get("heading_level", 2)
                    section_items.append(cv2.text_display(content, heading=heading_level))
                else:
                    section_items.append(cv2.text_display(content))

            elif comp_type == "separator":
                if section_items:
                    cv2_components.append(cv2.container([cv2.section(section_items)]))
                    section_items = []

                cv2_components.append(cv2.container([cv2.separator()]))

            elif comp_type == "button":
                label = comp.get("label", "ボタン")
                style = comp.get("style", "primary")
                custom_id = comp.get("custom_id", f"button_{len(section_items)}")
                emoji = comp.get("emoji")

                button_args = {
                    "label": label,
                    "style": style,
                    "custom_id": custom_id
                }

                if emoji:
                    button_args["emoji"] = emoji

                section_items.append(cv2.button(**button_args))

            elif comp_type == "select":
                if section_items:
                    cv2_components.append(cv2.container([cv2.section(section_items)]))
                    section_items = []

                custom_id = comp.get("custom_id", f"select_{len(cv2_components)}")
                placeholder = comp.get("placeholder", "選択してください")
                options = comp.get("options", [])

                select_menu = cv2.string_select(
                    custom_id=custom_id,
                    options=options,
                    placeholder=placeholder
                )

                cv2_components.append(cv2.container([cv2.row([select_menu])]))

            elif comp_type == "media":
                if section_items:
                    cv2_components.append(cv2.container([cv2.section(section_items)]))
                    section_items = []

                urls = comp.get("urls", [])
                if urls:
                    cv2_components.append(cv2.container([cv2.media_gallery(urls)]))

        if section_items:
            cv2_components.append(cv2.container([cv2.section(section_items)]))

        return cv2_components

    async def send_announcement(self, interaction: discord.Interaction, session_id: str, channel_id: str = None):
        """アナウンスを送信"""
        if not channel_id:
            await interaction.response.send_message("送信先チャンネルが指定されていません。", ephemeral=True)
            return

        session = self.sessions.get(session_id)
        if not session or not session.get("components"):
            await interaction.response.send_message("送信する要素がありません。", ephemeral=True)
            return

        try:
            channel = self.bot.get_channel(int(channel_id))
            if not channel:
                await interaction.response.send_message("チャンネルが見つかりません。", ephemeral=True)
                return
        except (ValueError, TypeError):
            await interaction.response.send_message("無効なチャンネルIDです。", ephemeral=True)
            return

        cv2_components = await self.convert_to_cv2_components(session["components"])

        try:
            await cv2.send(
                channel_id=channel.id,
                components=cv2_components
            )

            await interaction.response.send_message(f"{channel.mention} にメッセージを送信しました。", ephemeral=True)

            if session_id in self.sessions:
                del self.sessions[session_id]
        except Exception as e:
            logger.error(f"メッセージ送信エラー: {e}")
            await interaction.response.send_message(f"メッセージ送信中にエラーが発生しました: {e}", ephemeral=True)

class TextElementModal(discord.ui.Modal):
    def __init__(self, text_type="normal"):
        super().__init__(title="テキスト要素の追加")

        self.add_item(discord.ui.TextInput(
            label="テキスト内容",
            style=discord.TextStyle.paragraph,
            placeholder="表示するテキストを入力してください",
            required=True
        ))

        if text_type == "heading":
            self.add_item(discord.ui.TextInput(
                label="見出しレベル (1-3)",
                style=discord.TextStyle.short,
                placeholder="1, 2, または 3 を入力",
                required=True,
                default="2",
                max_length=1
            ))


class ButtonElementModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="ボタン要素の追加")

        self.add_item(discord.ui.TextInput(
            label="ボタンテキスト",
            style=discord.TextStyle.short,
            placeholder="ボタンに表示するテキスト",
            required=True
        ))

        self.add_item(discord.ui.TextInput(
            label="カスタムID",
            style=discord.TextStyle.short,
            placeholder="ボタンのカスタムID (例: button_action)",
            required=True
        ))

        self.add_item(discord.ui.TextInput(
            label="スタイル",
            style=discord.TextStyle.short,
            placeholder="primary, secondary, success, danger, link",
            default="primary",
            required=True
        ))

        self.add_item(discord.ui.TextInput(
            label="絵文字 (オプション)",
            style=discord.TextStyle.short,
            placeholder="例: 📝, 🔍, 👍",
            required=False
        ))


class SelectElementModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="セレクトメニューの追加")

        self.add_item(discord.ui.TextInput(
            label="カスタムID",
            style=discord.TextStyle.short,
            placeholder="セレクトメニューのカスタムID (例: select_option)",
            required=True
        ))

        self.add_item(discord.ui.TextInput(
            label="プレースホルダー",
            style=discord.TextStyle.short,
            placeholder="未選択時に表示されるテキスト",
            required=False
        ))

        self.add_item(discord.ui.TextInput(
            label="オプション",
            style=discord.TextStyle.paragraph,
            placeholder="各行に個別のオプションを指定してください。\n書式: ラベル|値|説明(オプション)\n例1: オプション1|option1|オプション1の説明\n例2: オプション2|option2\n例3: シンプルオプション",
            required=True
        ))


class MediaElementModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="メディアの追加")

        self.add_item(discord.ui.TextInput(
            label="画像URL",
            style=discord.TextStyle.paragraph,
            placeholder="画像のURLを入力してください。複数の場合は各行に1つずつ入力してください。",
            required=True
        ))


async def setup(bot: commands.Bot):
    if not hasattr(bot, "modal_callbacks"):
        bot.modal_callbacks = {}

    await cv2.initialize(bot)
    await bot.add_cog(CustomAnnouncement(bot))
