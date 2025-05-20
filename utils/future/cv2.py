# -*- coding: utf-8 -*-
"""utils.future.cv2 – Async‑only Components‑V2 toolkit (rev. 2025‑05‑20)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Designed **from the ground up for discord.py v2.4+**. Every public method is an
*async* coroutine; no blocking I/O sneaks in.  Drop‑in usage:

```py
from utils.future.cv2 import cv2

@bot.event
async def setup_hook():
    await cv2.initialize(bot)  # once, anywhere (Cog / setup_hook / on_ready)
```

### Discord‑py alignment
* **Token reuse** – Grabs `bot.http.token`; no extra secrets required.
* **No duplicated ratelimits** – We hit the REST endpoint *once* just like
  `Messageable.send()`. Library keeps its own httpx client so gateway latency
  stays unaffected.
* **Graceful shutdown** – Call `await cv2.close()` on logout; or rely on
  `bot.add_listener("on_close")` helper.
"""
from __future__ import annotations

import asyncio
import logging
import random
import textwrap
from typing import TYPE_CHECKING, Any, Mapping, MutableMapping, Sequence, TypeVar, Union

import httpx

if TYPE_CHECKING:  # pragma: no cover – only for type‑checkers / IDEs
    import discord

__all__ = [
    "CV2",
    "cv2",
    "CV2Error",
    "CV2PayloadError",
]

T = TypeVar("T")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------


class CV2Error(RuntimeError):
    """Base error for any CV2 runtime issue."""


class CV2PayloadError(CV2Error):
    """Violation of Discord's CV2 payload rules."""


# ---------------------------------------------------------------------------
# Enums (synced 2025‑04‑26)
# ---------------------------------------------------------------------------


class _ComponentTypes:
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


class _ButtonStyles:
    PRIMARY, SECONDARY, SUCCESS, DANGER, LINK = range(1, 6)
    _alias = {
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
    def coerce(cls, value: str | int) -> int:
        if isinstance(value, int):
            return value
        return cls._alias.get(value.lower(), cls.PRIMARY)


class _Flags:
    IS_COMPONENTS_V2 = 1 << 15
    EPHEMERAL = 1 << 6


# ---------------------------------------------------------------------------
# Decorator helper
# ---------------------------------------------------------------------------


class _CommandDecorator:
    """Simple registry for misc coroutine utilities."""

    def __init__(self, cv2: "CV2") -> None:
        self._cv2 = cv2
        self._handlers: dict[str, Mapping[str, Any]] = {}

    def __call__(self, name: str | None = None, description: str | None = None):
        def register(coro):
            self._handlers[name or coro.__name__] = {
                "func": coro,
                "description": description or (coro.__doc__ or "(no description)"),
            }
            return coro

        return register

    @property
    def handlers(self):
        return self._handlers


# ---------------------------------------------------------------------------
# Core helper (all‑async)
# ---------------------------------------------------------------------------


class CV2:
    """Async helper that plays nice with discord.py."""

    types = _ComponentTypes
    styles = _ButtonStyles
    flags = _Flags

    _PALETTE = (0xE74C3C, 0xFFA726, 0xF1C40F, 0x57F287, 0x3498DB, 0x7289DA, 0x9B59B6)
    _MAX_TEXT = 4000
    _API_BASE = "https://discord.com/api/v10"

    # ---- life‑cycle -------------------------------------------------

    def __init__(self, bot: "discord.Client | None" = None):
        self.bot = bot
        self._http: httpx.AsyncClient | None = None
        self._lock = asyncio.Lock()
        self._ready = False
        self.command = _CommandDecorator(self)

    async def initialize(self, bot: "discord.Client" | None = None):
        """Call once after your discord.py client is ready."""
        if bot:
            self.bot = bot
        if not self.bot:
            raise CV2Error("initialize(): discord.Client is required")
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=30)
        self._ready = True
        log.info("CV2 initialized (token: %s...)", self.bot.http.token[:6])  # type: ignore[attr-defined]

    @property
    def is_ready(self):
        return self._ready and self.bot is not None

    async def close(self):
        if self._http:
            await self._http.aclose()
            self._http = None
            self._ready = False
            log.debug("CV2 HTTP session closed")

    # allow `async with cv2:` usage
    async def __aenter__(self):
        if not self.is_ready:
            await self.initialize()
        return self

    async def __aexit__(self, *exc):
        await self.close()

    # ---- HTTP --------------------------------------------------------

    def _ep(self, tmpl: str, **kw):
        return f"{self._API_BASE}/{tmpl.lstrip('/').format(**kw)}"

    async def _request(self, method: str, url: str, *, json: Any = None, files: Any = None):
        if not self.is_ready:
            raise CV2Error("CV2 not initialized; call await cv2.initialize(bot)")
        assert self._http and self.bot
        headers = {"Authorization": f"Bot {self.bot.http.token}"}  # type: ignore[attr-defined]
        if files is None:
            headers["Content-Type"] = "application/json"
        async with self._lock:  # naive global lock – avoids flood on same route
            r = await self._http.request(method, url, headers=headers, json=json, files=files)
        if r.status_code not in (200, 201, 204):
            raise CV2Error(f"Discord API {r.status_code}: {textwrap.shorten(r.text, 100, placeholder='…')}")
        return None if r.status_code == 204 else r.json()

    # ---- public I/O --------------------------------------------------

    async def send(self, channel_id: int, **kw):
        payload, files = self._build_root(**kw)
        self._validate(payload)
        
        # デバッグ用にペイロードの構造をログに出力
        import json
        debug_payload = json.dumps(payload, indent=2, ensure_ascii=False)
        log.info(f"CV2 送信ペイロード:\n{debug_payload}")
        
        return await self._request("POST", self._ep("channels/{cid}/messages", cid=channel_id), json=payload, files=files)

    async def reply(self, interaction: "discord.Interaction", **kw):
        payload, _ = self._build_root(interaction=True, **kw)
        self._validate(payload["data"])
        return await self._request(
            "POST",
            self._ep("interactions/{id}/{token}/callback", id=interaction.id, token=interaction.token),
            json=payload,
        )

    # ---- builders & validators --------------------------------------

    def _build_root(self, *, components=None, media_urls=None, file_bytes=None, file_name=None, spoiler_file=False, flags=None, interaction=False, ephemeral=True, single_container=False):
        if not any((components, media_urls, file_bytes)):
            raise CV2PayloadError("At least one of components / media_urls / file_bytes is required")
        flags = (flags or 0) | self.flags.IS_COMPONENTS_V2
        if interaction and ephemeral:
            flags |= self.flags.EPHEMERAL
        
        # single_containerモード - すべてを1つのコンテナにまとめる
        if single_container:
            all_components = []
            
            # UIコンポーネントを最初に追加
            if components:
                if components[0].get("type") == self.types.CONTAINER:
                    # 既にコンテナの場合はその中身を取り出す
                    for container in components:
                        if container.get("components"):
                            all_components.extend(container.get("components"))
                else:
                    # 通常のコンポーネントの場合はそのまま追加
                    all_components.extend(components)
            
            # メディアギャラリーを後に追加
            if media_urls:
                all_components.append(self.media_gallery(media_urls))
                
            # ファイルを最後に追加
            if file_bytes:
                all_components.append(self.file(file_bytes, file_name or "upload.bin", spoiler_file))
                    
            # すべてのコンポーネントを1つのコンテナに格納
            conts = [self.container(all_components)]
        
        # 従来の複数コンテナモード
        else:
            conts: list[dict[str, Any]] = []
            if media_urls:
                conts.append(self.container([self.media_gallery(media_urls)]))
            if file_bytes:
                conts.append(self.container([self.file(file_bytes, file_name or "upload.bin", spoiler_file)]))
            if components:
                if components[0].get("type") == self.types.CONTAINER:
                    conts.extend(components)
                else:
                    conts.append(self.container(list(components)))
        base = {"components": conts, "flags": flags}
        files = None
        if file_bytes:
            fname = ("SPOILER_" if spoiler_file else "") + (file_name or "upload.bin")
            files = {"files[0]": (fname, file_bytes)}
        return ({"type": 4, "data": base} if interaction else base), files

    def _validate(self, payload: Mapping[str, Any]):
        if any(k in payload for k in ("content", "embeds")):
            raise CV2PayloadError("CV2 forbids 'content' and 'embeds'")
        total = sum(len(t) for t in self._collect_text(payload))
        if total > self._MAX_TEXT:
            raise CV2PayloadError("Markdown text exceeds 4000 characters")

    def _collect_text(self, comp):
        txt = [comp.get("content")] if isinstance(comp.get("content"), str) else []
        for k in ("components", "text"):
            for c in comp.get(k, []):
                txt.extend(self._collect_text(c))
        return txt

    # ---- component helpers (unchanged API) --------------------------

    def text_display(self, content: str, *, heading: int | None = None):
        if heading:
            content = f"{'#' * heading} {content}"
        return {"type": self.types.TEXT_DISPLAY, "content": content}

    def separator(self, *, divider=True, spacing=1):
        return {"type": self.types.SEPARATOR, "divider": divider, "spacing": max(1, min(3, spacing))}

    def media_gallery(self, urls: Sequence[str]):
        return {"type": self.types.MEDIA_GALLERY, "items": [{"media": {"url": u}} for u in urls]}

    def file(self, data: bytes, name: str, spoiler=False):
        if spoiler and not name.startswith("SPOILER_"):
            name = f"SPOILER_{name}"
        return {"type": self.types.FILE, "media": {"id": 0, "filename": name}}

    def button(self, label: str, *, custom_id=None, style: Union[str, int] = "primary", emoji=None, url=None, disabled=False):
        style_val = self.styles.coerce(style)
        if style_val == self.styles.LINK and not url:
            raise CV2PayloadError("LINK button needs 'url'")
        if style_val != self.styles.LINK and not custom_id:
            raise CV2PayloadError("custom_id missing for non‑LINK button")
        btn: MutableMapping[str, Any] = {"type": self.types.BUTTON, "style": style_val, "label": label, "disabled": disabled}
        btn["url" if style_val == self.styles.LINK else "custom_id"] = url or custom_id
        if emoji:
            btn["emoji"] = {"name": emoji} if isinstance(emoji, str) else dict(emoji)
        return btn

    def string_select(self, custom_id: str, options: Sequence[Union[str, tuple, Mapping]], *, placeholder=None, min_values=1, max_values=1, disabled=False):
        opts = []
        for o in options:
            if isinstance(o, str):
                opts.append({"label": o, "value": o})
            elif isinstance(o, tuple):
                label, value, *extra = o
                entry: dict[str, Any] = {"label": label, "value": value}
                if extra:
                    if len(extra) > 0 and extra[0]:
                        entry["description"] = extra[0]
                    if len(extra) > 1 and extra[1]:
                        entry["emoji"] = {"name": extra[1]} if isinstance(extra[1], str) else dict(extra[1])
                opts.append(entry)
            else:
                opts.append(dict(o))
        comp = {"type": self.types.STRING_SELECT, "custom_id": custom_id, "options": opts, "min_values": min_values, "max_values": max_values, "disabled": disabled}
        if placeholder:
            comp["placeholder"] = placeholder
        return {"type": self.types.ACTION_ROW, "components": [comp]}

    def _generic_select(self, type_id, custom_id, **kw):
        sel = {"type": type_id, "custom_id": custom_id, "min_values": kw.get("min_values", 1), "max_values": kw.get("max_values", 1), "disabled": kw.get("disabled", False)}
        if ph := kw.get("placeholder"):
            sel["placeholder"] = ph
        if ct := kw.get("channel_types"):
            sel["channel_types"] = list(ct)
        return {"type": self.types.ACTION_ROW, "components": [sel]}

    def user_select(self, cid, **kw):
        return self._generic_select(self.types.USER_SELECT, cid, **kw)

    def role_select(self, cid, **kw):
        return self._generic_select(self.types.ROLE_SELECT, cid, **kw)

    def mentionable_select(self, cid, **kw):
        return self._generic_select(self.types.MENTIONABLE_SELECT, cid, **kw)

    def channel_select(self, cid, **kw):
        return self._generic_select(self.types.CHANNEL_SELECT, cid, **kw)

    def container(self, comps: Sequence[dict[str, Any]], *, accent_color=None, spoiler=False):
        return {"type": self.types.CONTAINER, "accent_color": accent_color or random.choice(self._PALETTE), "spoiler": spoiler, "components": list(comps)}

    def section(self, lines: Sequence[Union[str, dict]], *, accessory=None):
        txts = [self.text_display(line) if isinstance(line, str) else line for line in lines][:3]
        sec: MutableMapping[str, Any] = {"type": self.types.SECTION, "text": txts}
        if accessory:
            sec["accessory"] = accessory
        return sec

    # convenience ------------------------------------------------------

    def title(self, text, level=2):
        return self.text_display(text, heading=level)

    def text(self, content):
        return self.text_display(content)

    def line(self, *, divider=True, spacing=1):
        return self.separator(divider=divider, spacing=spacing)

    def row(self, comps):
        return {"type": self.types.ACTION_ROW, "components": list(comps)}

    # alias
    select = string_select


# ---------------------------------------------------------------------------
# Singleton instance
# ---------------------------------------------------------------------------

cv2 = CV2()
