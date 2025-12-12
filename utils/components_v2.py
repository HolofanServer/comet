"""
Discord Components V2 ラッパー
discord.pyでComponents V2を簡単に使えるようにするユーティリティ

使用例:
    from bot.utils.components_v2 import ComponentsV2Message, Container, TextDisplay, Separator

    msg = ComponentsV2Message()
    msg.add(
        Container(color=0x8B5CF6)
        .add(TextDisplay("# タイトル"))
        .add(TextDisplay("本文テキスト"))
        .add(Separator())
        .add(TextDisplay("フッター"))
    )
    await channel.send(**msg.to_dict())
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

import discord


class ComponentType(IntEnum):
    """コンポーネントタイプ"""
    ACTION_ROW = 1
    BUTTON = 2
    STRING_SELECT = 3
    TEXT_INPUT = 4
    USER_SELECT = 5
    ROLE_SELECT = 6
    MENTIONABLE_SELECT = 7
    CHANNEL_SELECT = 8
    SECTION = 9
    TEXT_DISPLAY = 10
    THUMBNAIL = 11
    MEDIA_GALLERY = 12
    FILE = 13
    SEPARATOR = 14
    CONTAINER = 17


class SeparatorSpacing(IntEnum):
    """セパレーターの間隔"""
    SMALL = 1
    LARGE = 2


class ButtonStyle(IntEnum):
    """ボタンスタイル"""
    PRIMARY = 1      # 青
    SECONDARY = 2    # グレー
    SUCCESS = 3      # 緑
    DANGER = 4       # 赤
    LINK = 5         # リンク


# MessageFlags.IS_COMPONENTS_V2
IS_COMPONENTS_V2 = 1 << 15  # 32768


class BaseComponent:
    """コンポーネント基底クラス"""

    def to_dict(self) -> dict[str, Any]:
        """辞書に変換"""
        raise NotImplementedError


@dataclass
class TextDisplay(BaseComponent):
    """
    テキスト表示コンポーネント

    Args:
        content: マークダウン形式のテキスト
        id: コンポーネントID（省略可）

    使用例:
        TextDisplay("# 見出し")
        TextDisplay("**太字** と *斜体*")
    """
    content: str
    id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        data = {
            "type": ComponentType.TEXT_DISPLAY,
            "content": self.content,
        }
        if self.id is not None:
            data["id"] = self.id
        return data


@dataclass
class Separator(BaseComponent):
    """
    セパレーター（区切り線）コンポーネント

    Args:
        divider: 線を表示するか（デフォルト: True）
        spacing: 間隔サイズ（SMALL or LARGE）
        id: コンポーネントID（省略可）

    使用例:
        Separator()  # 線あり
        Separator(divider=False, spacing=SeparatorSpacing.LARGE)  # 線なし、大きい間隔
    """
    divider: bool = True
    spacing: SeparatorSpacing = SeparatorSpacing.SMALL
    id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        data = {
            "type": ComponentType.SEPARATOR,
            "divider": self.divider,
            "spacing": int(self.spacing),
        }
        if self.id is not None:
            data["id"] = self.id
        return data


@dataclass
class Thumbnail(BaseComponent):
    """
    サムネイル画像コンポーネント

    Args:
        url: 画像URL
        description: 代替テキスト（省略可）
        spoiler: スポイラー表示（省略可）
        id: コンポーネントID（省略可）
    """
    url: str
    description: str | None = None
    spoiler: bool = False
    id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        media = {"url": self.url}
        data = {
            "type": ComponentType.THUMBNAIL,
            "media": media,
            "spoiler": self.spoiler,
        }
        if self.description:
            data["description"] = self.description
        if self.id is not None:
            data["id"] = self.id
        return data


@dataclass
class MediaGalleryItem:
    """メディアギャラリーの項目"""
    url: str
    description: str | None = None
    spoiler: bool = False

    def to_dict(self) -> dict[str, Any]:
        data = {
            "media": {"url": self.url},
            "spoiler": self.spoiler,
        }
        if self.description:
            data["description"] = self.description
        return data


@dataclass
class MediaGallery(BaseComponent):
    """
    メディアギャラリーコンポーネント（複数画像）

    Args:
        items: MediaGalleryItemのリスト
        id: コンポーネントID（省略可）

    使用例:
        MediaGallery([
            MediaGalleryItem("https://example.com/image1.png"),
            MediaGalleryItem("https://example.com/image2.png", description="画像2"),
        ])
    """
    items: list[MediaGalleryItem] = field(default_factory=list)
    id: int | None = None

    def add(self, url: str, description: str = None, spoiler: bool = False) -> MediaGallery:
        """画像を追加"""
        self.items.append(MediaGalleryItem(url, description, spoiler))
        return self

    def to_dict(self) -> dict[str, Any]:
        data = {
            "type": ComponentType.MEDIA_GALLERY,
            "items": [item.to_dict() for item in self.items],
        }
        if self.id is not None:
            data["id"] = self.id
        return data


@dataclass
class Button(BaseComponent):
    """
    ボタンコンポーネント

    Args:
        label: ボタンラベル
        custom_id: カスタムID（インタラクション用）
        style: ボタンスタイル
        url: リンクURL（style=LINKの場合）
        emoji: 絵文字
        disabled: 無効化
    """
    label: str
    custom_id: str | None = None
    style: ButtonStyle = ButtonStyle.PRIMARY
    url: str | None = None
    emoji: str | None = None
    disabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        data = {
            "type": ComponentType.BUTTON,
            "style": int(self.style),
            "label": self.label,
            "disabled": self.disabled,
        }
        if self.style == ButtonStyle.LINK:
            data["url"] = self.url
        else:
            data["custom_id"] = self.custom_id
        if self.emoji:
            data["emoji"] = {"name": self.emoji}
        return data


@dataclass
class ActionRow(BaseComponent):
    """
    アクションロー（ボタン等のコンテナ）

    使用例:
        ActionRow().add(
            Button("ボタン1", "btn1"),
            Button("ボタン2", "btn2", style=ButtonStyle.SECONDARY),
        )
    """
    components: list[BaseComponent] = field(default_factory=list)
    id: int | None = None

    def add(self, *components: BaseComponent) -> ActionRow:
        """コンポーネントを追加"""
        self.components.extend(components)
        return self

    def to_dict(self) -> dict[str, Any]:
        data = {
            "type": ComponentType.ACTION_ROW,
            "components": [c.to_dict() for c in self.components],
        }
        if self.id is not None:
            data["id"] = self.id
        return data


@dataclass
class Section(BaseComponent):
    """
    セクションコンポーネント（テキスト + アクセサリ）

    Args:
        text_components: TextDisplayのリスト（最大3つ）
        accessory: ボタンまたはサムネイル
        id: コンポーネントID（省略可）

    使用例:
        Section()
        .add_text("**タイトル**")
        .add_text("説明文")
        .set_thumbnail("https://example.com/image.png")
    """
    text_components: list[TextDisplay] = field(default_factory=list)
    accessory: Button | Thumbnail | None = None
    id: int | None = None

    def add_text(self, content: str) -> Section:
        """テキストを追加（最大3つ）"""
        if len(self.text_components) < 3:
            self.text_components.append(TextDisplay(content))
        return self

    def set_button(self, label: str, custom_id: str, style: ButtonStyle = ButtonStyle.PRIMARY) -> Section:
        """ボタンアクセサリを設定"""
        self.accessory = Button(label, custom_id, style)
        return self

    def set_thumbnail(self, url: str, description: str = None) -> Section:
        """サムネイルアクセサリを設定"""
        self.accessory = Thumbnail(url, description)
        return self

    def to_dict(self) -> dict[str, Any]:
        data = {
            "type": ComponentType.SECTION,
            "components": [t.to_dict() for t in self.text_components],
        }
        if self.accessory:
            data["accessory"] = self.accessory.to_dict()
        if self.id is not None:
            data["id"] = self.id
        return data


@dataclass
class Container(BaseComponent):
    """
    コンテナコンポーネント（Embedの代替）

    Args:
        color: アクセントカラー（16進数）
        spoiler: スポイラー表示
        id: コンポーネントID（省略可）

    使用例:
        Container(color=0x8B5CF6)
        .add(TextDisplay("# タイトル"))
        .add(Separator())
        .add(TextDisplay("本文"))
        .add(ActionRow().add(Button("ボタン", "btn")))
    """
    color: int | None = None
    spoiler: bool = False
    components: list[BaseComponent] = field(default_factory=list)
    id: int | None = None

    def add(self, component: BaseComponent) -> Container:
        """コンポーネントを追加"""
        self.components.append(component)
        return self

    def add_text(self, content: str) -> Container:
        """テキストを追加"""
        self.components.append(TextDisplay(content))
        return self

    def add_separator(self, divider: bool = True, spacing: SeparatorSpacing = SeparatorSpacing.SMALL) -> Container:
        """セパレーターを追加"""
        self.components.append(Separator(divider, spacing))
        return self

    def add_section(self, section: Section) -> Container:
        """セクションを追加"""
        self.components.append(section)
        return self

    def add_buttons(self, *buttons: Button) -> Container:
        """ボタン行を追加"""
        self.components.append(ActionRow(list(buttons)))
        return self

    def add_gallery(self, *urls: str) -> Container:
        """画像ギャラリーを追加"""
        gallery = MediaGallery()
        for url in urls:
            gallery.add(url)
        self.components.append(gallery)
        return self

    def to_dict(self) -> dict[str, Any]:
        data = {
            "type": ComponentType.CONTAINER,
            "components": [c.to_dict() for c in self.components],
            "spoiler": self.spoiler,
        }
        if self.color is not None:
            data["accent_color"] = self.color
        if self.id is not None:
            data["id"] = self.id
        return data


class ComponentsV2Message:
    """
    Components V2メッセージビルダー

    使用例:
        msg = ComponentsV2Message()
        msg.add(TextDisplay("シンプルなテキスト"))
        msg.add(
            Container(color=0x8B5CF6)
            .add_text("# コンテナ内のテキスト")
            .add_separator()
            .add_buttons(
                Button("ボタン1", "btn1"),
                Button("ボタン2", "btn2", ButtonStyle.SECONDARY),
            )
        )
        await channel.send(**msg.to_dict())
    """

    def __init__(self):
        self.components: list[BaseComponent] = []

    def add(self, component: BaseComponent) -> ComponentsV2Message:
        """コンポーネントを追加"""
        self.components.append(component)
        return self

    def add_text(self, content: str) -> ComponentsV2Message:
        """テキストを追加"""
        self.components.append(TextDisplay(content))
        return self

    def add_separator(self, divider: bool = True) -> ComponentsV2Message:
        """セパレーターを追加"""
        self.components.append(Separator(divider))
        return self

    def add_container(self, container: Container) -> ComponentsV2Message:
        """コンテナを追加"""
        self.components.append(container)
        return self

    def to_dict(self) -> dict[str, Any]:
        """送信用の辞書に変換"""
        return {
            "components": [c.to_dict() for c in self.components],
            "flags": IS_COMPONENTS_V2,
        }

    async def send(self, target: discord.TextChannel | discord.Interaction) -> discord.Message:
        """メッセージを送信（非推奨: send_to_interactionを使用）"""
        data = self.to_dict()
        if isinstance(target, discord.Interaction):
            # deferされたinteractionの場合はAPI直接送信
            if target.response.is_done():
                return await send_components_v2_followup(target, self)
            else:
                return await target.response.send_message(**data)
        else:
            return await target.send(**data)


async def send_components_v2_response(
    interaction: discord.Interaction,
    message: ComponentsV2Message,
    ephemeral: bool = False,
) -> None:
    """
    Components V2メッセージをInteraction初期応答として送信（API直接）

    Args:
        interaction: Discord Interaction
        message: ComponentsV2Message
        ephemeral: 一時的なメッセージかどうか
    """
    import aiohttp

    flags = IS_COMPONENTS_V2
    if ephemeral:
        flags |= 64  # EPHEMERAL flag

    payload = {
        "type": 4,  # CHANNEL_MESSAGE_WITH_SOURCE
        "data": {
            "components": [c.to_dict() for c in message.components],
            "flags": flags,
        }
    }

    headers = {
        "Content-Type": "application/json",
    }

    url = f"https://discord.com/api/v10/interactions/{interaction.id}/{interaction.token}/callback"

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=headers) as resp:
            if resp.status not in (200, 204):
                error = await resp.text()
                raise Exception(f"Components V2送信エラー: {resp.status} - {error}")


async def send_components_v2_followup(
    interaction: discord.Interaction,
    message: ComponentsV2Message,
    edit_original: bool = False,
) -> discord.Message | None:
    """
    Components V2メッセージをfollowupとして送信（API直接）

    Args:
        interaction: Discord Interaction
        message: ComponentsV2Message
        edit_original: Trueの場合、元のメッセージを編集

    Returns:
        送信されたメッセージ（edit_originalの場合はNone）
    """
    import aiohttp

    app_id = interaction.application_id
    token = interaction.token

    payload = {
        "components": [c.to_dict() for c in message.components],
        "flags": IS_COMPONENTS_V2,
    }

    headers = {
        "Content-Type": "application/json",
    }

    async with aiohttp.ClientSession() as session:
        if edit_original:
            # 元のメッセージを編集
            url = f"https://discord.com/api/v10/webhooks/{app_id}/{token}/messages/@original"
            async with session.patch(url, json=payload, headers=headers) as resp:
                if resp.status not in (200, 204):
                    error = await resp.text()
                    raise Exception(f"Components V2送信エラー: {resp.status} - {error}")
                return None
        else:
            # 新しいメッセージを送信
            url = f"https://discord.com/api/v10/webhooks/{app_id}/{token}"
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status not in (200, 204):
                    error = await resp.text()
                    raise Exception(f"Components V2送信エラー: {resp.status} - {error}")
                return None


async def send_components_v2_to_channel(
    channel: discord.TextChannel,
    message: ComponentsV2Message,
    bot_token: str,
    content: str | None = None,
    view: discord.ui.View | None = None,
    allowed_mentions: discord.AllowedMentions | None = None,
) -> str | None:
    """
    Components V2メッセージをチャンネルに送信（API直接）

    Args:
        channel: 送信先チャンネル
        message: ComponentsV2Message
        bot_token: Botトークン
        content: メッセージコンテンツ（省略可）
        view: discord.ui.View（省略可）
        allowed_mentions: AllowedMentions設定（省略可）

    Returns:
        送信されたメッセージID
    """
    import aiohttp

    payload = {
        "components": [c.to_dict() for c in message.components],
        "flags": IS_COMPONENTS_V2,
    }

    # コンテンツを追加
    if content is not None:
        payload["content"] = content

    # Viewのコンポーネントを追加
    if view is not None:
        # discord.pyのViewをコンポーネント配列に変換
        view_dict = view.to_components()
        if view_dict:
            # Components V2とV1のコンポーネントを両方含める
            payload["components"].extend(view_dict)

    # AllowedMentionsを追加
    if allowed_mentions is not None:
        payload["allowed_mentions"] = allowed_mentions.to_dict()

    headers = {
        "Authorization": f"Bot {bot_token}",
        "Content-Type": "application/json",
    }

    url = f"https://discord.com/api/v10/channels/{channel.id}/messages"

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=headers) as resp:
            if resp.status not in (200, 201):
                error = await resp.text()
                raise Exception(f"Components V2送信エラー: {resp.status} - {error}")
            data = await resp.json()
            return data.get("id")


# ============================================
# 便利関数
# ============================================

def simple_container(
    title: str,
    description: str = "",
    color: int = 0x8B5CF6,
    footer: str = "",
    image_url: str = "",
    buttons: list[tuple[str, str]] = None,
) -> Container:
    """
    シンプルなコンテナを作成（Embedの代替）

    Args:
        title: タイトル（マークダウン可）
        description: 説明文
        color: アクセントカラー
        footer: フッターテキスト
        image_url: 画像URL
        buttons: ボタンリスト [(label, custom_id), ...]

    使用例:
        container = simple_container(
            title="# ミームタイトル",
            description="ミームの説明",
            color=0x8B5CF6,
            image_url="https://example.com/meme.png",
            buttons=[("ダウンロード", "download"), ("共有", "share")],
        )
    """
    c = Container(color=color)

    # タイトル
    c.add_text(title)

    # 説明
    if description:
        c.add_text(description)

    # 画像
    if image_url:
        c.add(MediaGallery().add(image_url))

    # フッター
    if footer:
        c.add_separator()
        c.add_text(footer)

    # ボタン
    if buttons:
        btn_list = [Button(label, cid) for label, cid in buttons]
        c.add_buttons(*btn_list)

    return c


def meme_card(
    title: str,
    image_url: str,
    tags: list[str] = None,
    download_count: int = 0,
    meme_id: str = "",
    color: int = 0x8B5CF6,
) -> Container:
    """
    ミームカード用のコンテナを作成

    Args:
        title: ミームタイトル
        image_url: 画像URL
        tags: タグリスト
        download_count: ダウンロード数
        meme_id: ミームID
        color: アクセントカラー
    """
    c = Container(color=color)

    # タイトル
    c.add_text(f"## {title}")

    # 画像
    c.add(MediaGallery().add(image_url))

    # 統計情報
    stats = f"💾 **{download_count:,}** 保存"
    if tags:
        stats += f"\n🏷️ {' '.join([f'`#{t}`' for t in tags[:5]])}"
    c.add_text(stats)

    # ボタン
    buttons = [
        Button("🔗 サイトで見る", url=f"https://holo.meme/meme/{meme_id}", style=ButtonStyle.LINK),
    ]
    if meme_id:
        buttons.append(Button("⭐ お気に入り", f"fav_add:{meme_id}", ButtonStyle.SECONDARY))

    c.add_buttons(*buttons)

    return c


def ranking_list(
    title: str,
    items: list[tuple[str, str, int]],  # [(name, url, count), ...]
    color: int = 0xFFD700,
) -> Container:
    """
    ランキングリスト用のコンテナを作成

    Args:
        title: タイトル
        items: [(名前, URL, カウント), ...]
        color: アクセントカラー
    """
    c = Container(color=color)
    c.add_text(f"# {title}")
    c.add_separator()

    medals = ["🥇", "🥈", "🥉"]
    lines = []
    for i, (name, url, count) in enumerate(items[:10]):
        medal = medals[i] if i < 3 else f"**{i+1}.**"
        lines.append(f"{medal} [{name}]({url}) - {count:,}")

    c.add_text("\n".join(lines))

    return c
