# -*- coding: utf-8 -*-
"""utils.future.cv2 – Components V2 helper (rev. 2025-05-20)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
A *thin* convenience wrapper for Discord **Components V2 (CV2)** REST endpoints
compatible with **discord.py v2.4+**. This is **not** an official binding – it
only assembles the raw JSON payloads required by the HTTP API.

Key features
============
* Build containers / sections / buttons / selects / media galleries easily.
* Auto-apply the `IS_COMPONENTS_V2` flag and (optionally) `EPHEMERAL`.
* Lightweight `cv2.command` decorator for coroutine callbacks in legacy bots.

> ⚠ **Current Discord limitation**  
> While the CV2 flag is present, the *content*, *embeds*, *stickers* and *polls*
> fields are ignored by the server. An attempt to send them raises
> `ValueError` in this helper.
"""
from __future__ import annotations

import logging
import random
from typing import (
    TYPE_CHECKING,
    Any,
    Mapping,
    Sequence,
    TypeVar,
    Union,
)

import httpx

if TYPE_CHECKING:  # pragma: no cover – only for type-checkers / IDEs
    import discord  # noqa: F401 – referenced in type hints only

__all__ = ["CV2", "cv2"]

logger = logging.getLogger(__name__)
T = TypeVar("T")

# ---------------------------------------------------------------------------
# Enumerations – synced with discord-api-types (v10 – 2025-04-26)
# ---------------------------------------------------------------------------


class _ComponentTypes:
    ACTION_ROW: int = 1
    BUTTON: int = 2
    STRING_SELECT: int = 3  # ⇔ SelectMenu
    TEXT_INPUT: int = 4
    USER_SELECT: int = 5
    ROLE_SELECT: int = 6
    MENTIONABLE_SELECT: int = 7
    CHANNEL_SELECT: int = 8
    SECTION: int = 9
    TEXT_DISPLAY: int = 10
    THUMBNAIL: int = 11
    MEDIA_GALLERY: int = 12
    FILE: int = 13
    SEPARATOR: int = 14
    CONTENT_INVENTORY_ENTRY: int = 16  # experimental / undocumented
    CONTAINER: int = 17


class _ButtonStyles:
    PRIMARY = 1
    SECONDARY = 2
    SUCCESS = 3
    DANGER = 4
    LINK = 5

    _map = {
        "primary": PRIMARY,
        "blue": PRIMARY,
        "secondary": SECONDARY,
        "grey": SECONDARY,
        "gray": SECONDARY,
        "success": SUCCESS,
        "green": SUCCESS,
        "danger": DANGER,
        "red": DANGER,
        "link": LINK,
        "url": LINK,
    }

    @classmethod
    def from_str(cls, style: str | int) -> int:
        if isinstance(style, int):
            return style
        return cls._map.get(style.lower(), cls.PRIMARY)


class _Flags:
    IS_COMPONENTS_V2: int = 1 << 15  # 32768
    EPHEMERAL: int = 1 << 6          # 64


# ---------------------------------------------------------------------------
# Decorator for lightweight prefix commands (optional sugar)
# ---------------------------------------------------------------------------


class _CommandDecorator:
    def __init__(self, cv2: "CV2") -> None:
        self._cv2 = cv2
        self._registry: dict[str, dict[str, Any]] = {}

    def __call__(self, name: str | None = None, description: str | None = None):
        """Register *func* under **name** for later manual dispatch."""

        def wrapper(func):
            cmd_name = name or func.__name__
            self._registry[cmd_name] = {
                "func": func,
                "description": description or (func.__doc__ or "(no description)"),
            }
            return func

        return wrapper

    @property
    def handlers(self) -> Mapping[str, Mapping[str, Any]]:
        return self._registry


# ---------------------------------------------------------------------------
# Main helper class
# ---------------------------------------------------------------------------


class CV2:
    """Convenience wrapper for Discord **Components V2** REST calls."""

    types = _ComponentTypes  # re-export enums
    styles = _ButtonStyles
    flags = _Flags

    _ACCENT_COLOURS = (
        0xE74C3C,  # red
        0xFFA726,  # orange
        0xF1C40F,  # yellow
        0x57F287,  # green
        0x3498DB,  # blue
        0x7289DA,  # blurple
        0x9B59B6,  # purple
    )

    def __init__(self, bot: "discord.Client | None" = None):  # type: ignore[name-defined]
        self.bot = bot
        self._http: httpx.AsyncClient | None = None
        self._ready = False
        self.command = _CommandDecorator(self)

    # ------------------------------------------------------------------
    # life-cycle helpers
    # ------------------------------------------------------------------

    async def initialize(self, bot: "discord.Client" | None = None) -> bool:  # type: ignore[name-defined]
        if bot:
            self.bot = bot
        if not self.bot:
            raise RuntimeError("CV2.initialize: bot instance is required")
        if not self._http:
            self._http = httpx.AsyncClient(timeout=30)
        self._ready = True
        logger.info("CV2 initialized – Components V2 support enabled")
        return True

    @property
    def is_ready(self) -> bool:
        return self._ready and self.bot is not None

    async def close(self) -> None:
        if self._http:
            await self._http.aclose()
            self._http = None
            logger.debug("CV2 httpx client closed")
        self._ready = False

    # ------------------------------------------------------------------
    # low-level request helper
    # ------------------------------------------------------------------

    _API_BASE = "https://discord.com/api/v10"

    def _endpoint(self, path: str, **params: Any) -> str:
        return f"{self._API_BASE}/{path.lstrip('/').format(**params)}"

    async def _request(
        self,
        method: str,
        url: str,
        *,
        json_payload: dict[str, Any] | None = None,
        files: dict[str, tuple] | None = None,
    ) -> Any:
        if not self.is_ready:
            raise RuntimeError("CV2 is not ready – call initialize() first")
        assert self._http is not None and self.bot is not None

        headers = {"Authorization": f"Bot {self.bot.http.token}"}  # type: ignore[attr-defined]
        if files is None:
            headers["Content-Type"] = "application/json"

        resp = await self._http.request(method, url, headers=headers, json=json_payload, files=files)
        if resp.status_code in (200, 201, 204):
            return None if resp.status_code == 204 else resp.json()
        logger.error("CV2 HTTP %s %s failed: %s – %s", method, url, resp.status_code, resp.text)
        resp.raise_for_status()

    # ------------------------------------------------------------------
    # public send / reply helpers
    # ------------------------------------------------------------------

    async def send(
        self,
        channel_id: int,
        *,
        components: Sequence[dict[str, Any]] | None = None,
        media_urls: Sequence[str] | None = None,
        file_bytes: bytes | None = None,
        file_name: str | None = None,
        spoiler_file: bool = False,
        flags: int | None = None,
    ) -> Any:
        if components is None and media_urls is None and file_bytes is None:
            raise ValueError("send: at least one of components / media_urls / file_bytes is required")

        flags = (flags or 0) | self.flags.IS_COMPONENTS_V2
        top_components: list[dict[str, Any]] = []

        if media_urls:
            top_components.append(self.container([self.media_gallery(media_urls)]))
        if file_bytes is not None:
            top_components.append(self.container([self.file(file_bytes, file_name or "upload.bin", spoiler_file)]))
        if components:
            if components and components[0].get("type") == self.types.CONTAINER:
                top_components.extend(components)
            else:
                top_components.append(self.container(list(components)))

        payload = {"components": top_components, "flags": flags}

        files = None
        if file_bytes is not None:
            name = file_name or "upload.bin"
            if spoiler_file and not name.startswith("SPOILER_"):
                name = f"SPOILER_{name}"
            files = {"files[0]": (name, file_bytes)}

        return await self._request(
            "POST",
            self._endpoint("channels/{cid}/messages", cid=channel_id),
            json_payload=payload,
            files=files,
        )

    async def reply(
        self,
        interaction: "discord.Interaction",  # type: ignore[name-defined]
        *,
        components: Sequence[dict[str, Any]] | None = None,
        media_urls: Sequence[str] | None = None,
        flags: int | None = None,
        ephemeral: bool = True,
    ) -> Any:
        if components is None and media_urls is None:
            raise ValueError("reply: components or media_urls is required")

        flags = (flags or 0) | self.flags.IS_COMPONENTS_V2
        if ephemeral:
            flags |= self.flags.EPHEMERAL

        top_components: list[dict[str, Any]] = []
        if media_urls:
            top_components.append(self.container([self.media_gallery(media_urls)]))
        if components:
            if components and components[0].get("type") == self.types.CONTAINER:
                top_components.extend(components)
            else:
                top_components.append(self.container(list(components)))

        data = {"flags": flags, "components": top_components}
        payload = {"type": 4, "data": data}
        return await self._request(
            "POST",
            self._endpoint("interactions/{id}/{token}/callback", id=interaction.id, token=interaction.token),
            json_payload=payload,
        )

    # ------------------------------------------------------------------
    # Component builders
    # ------------------------------------------------------------------

    # text / separator ---------------------------------------------------

    def text_display(self, content: str, *, heading: int | None = None) -> dict[str, Any]:
        if heading is not None:
            content = f"{'#' * max(1, min(3, heading))} {content}"
        return {"type": self.types.TEXT_DISPLAY, "content": content}

    def separator(self, *, divider: bool = True, spacing: int = 1) -> dict[str, Any]:
        return {
            "type": self.types.SEPARATOR,
            "divider": divider,
            "spacing": max(1, min(3, spacing)),
        }

    # media / file -------------------------------------------------------

    def media_gallery(self, urls: Sequence[str]) -> dict[str, Any]:
        return {
            "type": self.types.MEDIA_GALLERY,
            "items": [{"media": {"url": u}} for u in urls],
        }

    def thumbnail(self, url: str) -> dict[str, Any]:
        return {
            "type": self.types.THUMBNAIL,
            "media": {"url": url},
        }

    def file(self, data: bytes, filename: str, spoiler: bool = False) -> dict[str, Any]:
        if spoiler and not filename.startswith("SPOILER_"):
            filename = f"SPOILER_{filename}"
        return {
            "type": self.types.FILE,
            "media": {"id": 0, "filename": filename},
        }

    # buttons & selects --------------------------------------------------

    def button(
        self,
        label: str,
        *,
        custom_id: str | None = None,
        style: Union[str, int] = "primary",
        emoji: Union[str, Mapping[str, Any], None] = None,
        url: str | None = None,
        disabled: bool = False,
    ) -> dict[str, Any]:
        style_val = self.styles.from_str(style) if isinstance(style, (str, int)) else self.styles.PRIMARY
        payload: dict[str, Any] = {
            "type": self.types.BUTTON,
            "style": style_val,
            "label": label,
            "disabled": disabled,
        }
        if style_val == self.styles.LINK:
            if not url:
                raise ValueError("LINK style button requires 'url' parameter")
            payload["url"] = url
        else:
            if not custom_id:
                raise ValueError("Non-LINK button requires 'custom_id'")
            payload["custom_id"] = custom_id
        if emoji:
            payload["emoji"] = {"name": emoji} if isinstance(emoji, str) else dict(emoji)
        return payload

    def string_select(
        self,
        custom_id: str,
        options: Sequence[Union[str, tuple[str, str], Mapping[str, Any]]],
        *,
        placeholder: str | None = None,
        min_values: int = 1,
        max_values: int = 1,
        disabled: bool = False,
    ) -> dict[str, Any]:
        opts: list[dict[str, Any]] = []
        for opt in options:
            if isinstance(opt, str):
                opts.append({"label": opt, "value": opt})
            elif isinstance(opt, tuple):
                label, value = opt[:2]
                desc = opt[2] if len(opt) > 2 else None
                emoji = opt[3] if len(opt) > 3 else None
                entry: dict[str, Any] = {"label": label, "value": value}
                if desc:
                    entry["description"] = desc
                if emoji:
                    entry["emoji"] = {"name": emoji} if isinstance(emoji, str) else dict(emoji)
                opts.append(entry)
            else:
                opts.append(dict(opt))

        select_component = {
            "type": self.types.STRING_SELECT,
            "custom_id": custom_id,
            "options": opts,
            "min_values": max(0, min(25, min_values)),
            "max_values": max(1, min(25, max_values)),
            "disabled": disabled,
        }
        if placeholder:
            select_component["placeholder"] = placeholder

        # must be wrapped in ActionRow for CV2
        return {"type": self.types.ACTION_ROW, "components": [select_component]}

    # generic selects ----------------------------------------------------

    def _generic_select(
        self,
        type_id: int,
        custom_id: str,
        *,
        placeholder: str | None = None,
        min_values: int = 1,
        max_values: int = 1,
        disabled: bool = False,
    ) -> dict[str, Any]:
        base = {
            "type": type_id,
            "custom_id": custom_id,
            "min_values": max(0, min(25, min_values)),
            "max_values": max(1, min(25, max_values)),
            "disabled": disabled,
        }
        if placeholder:
            base["placeholder"] = placeholder
        return {"type": self.types.ACTION_ROW, "components": [base]}

    def user_select(self, custom_id: str, **kw) -> dict[str, Any]:
        return self._generic_select(self.types.USER_SELECT, custom_id, **kw)

    def role_select(self, custom_id: str, **kw) -> dict[str, Any]:
        return self._generic_select(self.types.ROLE_SELECT, custom_id, **kw)

    def mentionable_select(self, custom_id: str, **kw) -> dict[str, Any]:
        return self._generic_select(self.types.MENTIONABLE_SELECT, custom_id, **kw)

    def channel_select(
        self,
        custom_id: str,
        *,
        channel_types: Sequence[int] | None = None,
        **kw,
    ) -> dict[str, Any]:
        comp = self._generic_select(self.types.CHANNEL_SELECT, custom_id, **kw)
        if channel_types:
            comp["components"][0]["channel_types"] = list(channel_types)
        return comp

    # higher-level containers ------------------------------------------

    def container(
        self,
        comps: Sequence[dict[str, Any]],
        *,
        accent_color: int | None = None,
        spoiler: bool = False,
    ) -> dict[str, Any]:
        return {
            "type": self.types.CONTAINER,
            "accent_color": accent_color or random.choice(self._ACCENT_COLOURS),
            "spoiler": spoiler,
            "components": list(comps),
        }

    def section(
        self,
        texts: Sequence[Union[str, dict[str, Any]]],
        *,
        accessory: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        text_components: list[dict[str, Any]] = []
        for item in texts[:3]:
            if isinstance(item, str):
                text_components.append(self.text_display(item))
            else:
                text_components.append(item)
        payload: dict[str, Any] = {"type": self.types.SECTION, "text": text_components}
        if accessory is not None:
            payload["accessory"] = accessory
        return payload

    # convenience wrappers (no lambda to satisfy Ruff)

    def title(self, text: str, heading_level: int = 2) -> dict[str, Any]:
        return self.text_display(text, heading=heading_level)

    def text(self, content: str) -> dict[str, Any]:
        return self.text_display(content)

    def line(self, *, divider: bool = True, spacing: int = 1) -> dict[str, Any]:
        return self.separator(divider=divider, spacing=spacing)

    def row(self, components: Sequence[dict[str, Any]]) -> dict[str, Any]:
        return {"type": self.types.ACTION_ROW, "components": list(components)}

    # legacy alias
    select = string_select


# ---------------------------------------------------------------------------
# Public singleton instance (optional sugar)
# ---------------------------------------------------------------------------

cv2 = CV2()
