# -*- coding: utf-8 -*-
"""cogs.cv2_demo_cog – **slash‑command** examples for utils.future.cv2

* discord.py ≥ 2.4 / app_commands only
* メディアギャラリー複数 URL・File コンポーネント URL 取得に対応
"""
from __future__ import annotations

import pathlib
from typing import Final, Sequence

import discord
from discord import app_commands
from discord.ext import commands
import httpx

from utils.future.cv2 import CV2Error, cv2

from utils.logging import setup_logging
from utils.commands_help import is_guild_app, is_owner_app

logger = setup_logging("D")

LOCAL_DEMO_IMG: Final[pathlib.Path] = pathlib.Path(__file__).with_suffix(".png")
MAX_MEDIA_ITEMS: Final[int] = 4


class CV2Demo(commands.Cog):
    """Slash‑command based CV2 demo (multi‑media capable)."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # lifecycle --------------------------------------------------------
    async def cog_load(self) -> None:
        if not cv2.is_ready:
            await cv2.initialize(self.bot)

    # helper -----------------------------------------------------------
    async def _err(self, interaction: discord.Interaction, exc: Exception):
        msg = f"CV2 エラー: {exc}"
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)

    # -----------------------------------------------------------------
    # 1) basic panel ---------------------------------------------------
    # -----------------------------------------------------------------
    @app_commands.command(name="cv2panel", description="推しロール選択パネルを送信")
    @is_guild_app()
    @is_owner_app()
    async def cv2panel(self, interaction: discord.Interaction):
        comps = [
            cv2.title("推しロール選択"),
            cv2.text("あなたの推しメンバーを選んでください！"),
            cv2.line(),
            cv2.select(
                "member_select",
                [
                    ("ホロ星人A", "a", "可愛い", "🌟"),
                    ("ホロ星人B", "b", "カッコいい", "💫"),
                ],
                placeholder="メンバーを選択",
            ),
            cv2.line(spacing=2),
            cv2.row(
                [
                    cv2.button("決定", custom_id="confirm_btn", style="success", emoji="✅"),
                    cv2.button("キャンセル", custom_id="cancel_btn", style="danger", emoji="✖"),
                ]
            ),
        ]
        await interaction.response.defer(ephemeral=True)
        try:
            await cv2.send(interaction.channel_id, components=comps)  # type: ignore[attr-defined]
            await interaction.followup.send("パネルを送信しました ✅", ephemeral=True)
        except CV2Error as e:
            await self._err(interaction, e)

    # -----------------------------------------------------------------
    # 2) media gallery (multi URL) ------------------------------------
    # -----------------------------------------------------------------
    @app_commands.command(name="cv2media", description="複数 URL でメディアギャラリー送信 (最大4件)")
    @app_commands.describe(urls="スペース区切りで画像 URL を 1〜4 件")
    @is_guild_app()
    @is_owner_app()
    async def cv2media(self, interaction: discord.Interaction, urls: str):
        url_list: Sequence[str] = [u for u in urls.strip().split() if u.startswith("http")][:MAX_MEDIA_ITEMS]
        if not url_list:
            await interaction.response.send_message("URL を 1 件以上入力してください。", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            await cv2.send(interaction.channel_id, media_urls=url_list)  # type: ignore[attr-defined]
            await interaction.followup.send("送信しました ✅", ephemeral=True)
        except CV2Error as e:
            await self._err(interaction, e)

    # -----------------------------------------------------------------
    # 3) file component (local or URL) --------------------------------
    # -----------------------------------------------------------------
    @app_commands.command(name="cv2file", description="画像ファイルを File コンポーネントで送信")
    @app_commands.describe(url="(任意) 画像 URL。未指定ならローカルのデモ画像を送信")
    @is_guild_app()
    @is_owner_app()
    async def cv2file(self, interaction: discord.Interaction, url: str | None = None):
        await interaction.response.defer(ephemeral=True)
        try:
            if url:
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.get(url)
                if resp.status_code != 200:
                    raise CV2Error(f"画像取得失敗 ({resp.status_code})")
                data = resp.content
                fname = pathlib.Path(url).name or "image.jpg"
            else:
                if not LOCAL_DEMO_IMG.exists():
                    await interaction.followup.send("デモ画像が見つかりません。", ephemeral=True)
                    return
                data = LOCAL_DEMO_IMG.read_bytes()
                fname = LOCAL_DEMO_IMG.name
            await cv2.send(
                interaction.channel_id,  # type: ignore[attr-defined]
                file_bytes=data,
                file_name=fname,
                spoiler_file=True,
            )
            await interaction.followup.send("送信しました ✅", ephemeral=True)
        except (CV2Error, httpx.HTTPError) as e:
            await self._err(interaction, e)

    # -----------------------------------------------------------------
    # 4) section demo --------------------------------------------------
    # -----------------------------------------------------------------
    @app_commands.command(name="cv2section", description="SECTION コンポーネント例")
    @is_guild_app()
    @is_owner_app()
    async def cv2section(self, interaction: discord.Interaction):
        section = cv2.section(
            [
                "**お知らせ**",
                "CV2 SECTION はテキスト 3 行まで！",
                "アクセサリでボタンも置けます。",
            ],
            accessory=cv2.button("了解", custom_id="section_ok", emoji="👌"),
        )
        await interaction.response.defer(ephemeral=True)
        try:
            await cv2.send(interaction.channel_id, components=[section])  # type: ignore[attr-defined]
            await interaction.followup.send("送信しました ✅", ephemeral=True)
        except CV2Error as e:
            await self._err(interaction, e)

    # -----------------------------------------------------------------
    # 5) colour preview -----------------------------------------------
    # -----------------------------------------------------------------
    @app_commands.command(name="cv2colors", description="Container のアクセントカラー一覧")
    @is_guild_app()
    @is_owner_app()
    async def cv2colors(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        cards = [cv2.container([cv2.text(f"0x{c:06X}")], accent_color=c) for c in cv2._PALETTE]
        try:
            await cv2.send(interaction.channel_id, components=cards)  # type: ignore[attr-defined]
            await interaction.followup.send("送信しました ✅", ephemeral=True)
        except CV2Error as e:
            await self._err(interaction, e)

    # interaction listener – custom_id dispatch -----------------------
    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type.name != "component" or not interaction.data:
            return
        cid = interaction.data.get("custom_id")
        if cid == "confirm_btn":
            await cv2.reply(interaction, components=[cv2.text("ロール設定を保存しました ✅")], ephemeral=True)
        elif cid == "cancel_btn":
            await cv2.reply(interaction, components=[cv2.text("キャンセルしました")], ephemeral=True)
        elif cid == "section_ok":
            await cv2.reply(interaction, components=[cv2.text("了解です！")], ephemeral=True)


    # -----------------------------------------------------------------
    # Mega Demo (all features in one panel!) ------------------------------
    # -----------------------------------------------------------------
    @app_commands.command(name="cv2demo", description="CV2の全機能を組み込んだ総合デモパネルを送信")
    @app_commands.describe(
        url1="画像 URL 1 (メディアギャラリーで表示)",
        url2="画像 URL 2 (メディアギャラリーで表示)",
        url3="画像 URL 3 (メディアギャラリーで表示)",
        url4="画像 URL 4 (メディアギャラリーとFileコンポーネント両方で表示)"
    )
    @is_guild_app()
    @is_owner_app()
    async def cv2demo(self, interaction: discord.Interaction, url1: str = "", url2: str = "", url3: str = "", url4: str = ""):
        await interaction.response.defer(ephemeral=True)
        
        # 有効な URL をフィルタリング
        media_urls = [u for u in [url1, url2, url3, url4] if u and u.startswith("http")][:4]
        file_url = url4 if url4 and url4.startswith("http") else ""
        
        try:
            # 1. メディアギャラリー用とファイル用のデータを準備
            file_data = None
            file_name = None
            
            if file_url:
                try:
                    async with httpx.AsyncClient(timeout=10) as client:
                        resp = await client.get(file_url)
                    if resp.status_code == 200:
                        file_data = resp.content
                        file_name = pathlib.Path(file_url).name or "image.jpg"
                    else:
                        logger.error(f"ファイル取得エラー: {resp.status_code}")
                except Exception as e:
                    logger.error(f"ファイル取得中にエラー発生: {e}")
            
            logger.info("CV2デモパネルの作成開始")
            # 2. 主要コンポーネントを作成
            components = [
                # タイトルと説明
                cv2.title("CV2 総合デモパネル", level=1),
                cv2.text("すべての CV2 コンポーネント機能を一つのパネルに表示しています。"),
                cv2.line(),
                
                # セクションコンポーネント
                cv2.section(
                    [
                        "## セクションコンポーネント",
                        "テキストが 3 行まで配置可能",
                        "右側にアクセサリも表示できます",
                    ],
                    accessory=cv2.button("セクションボタン", custom_id="section_demo", emoji="👍"),
                ),
                
                # セパレータで区切り
                cv2.separator(divider=True, spacing=2),
                
                # 選択メニュー
                cv2.select(
                    "demo_select",
                    [
                        ("オプション 1", "option1", "説明も表示できます", "🌟"),
                        ("オプション 2", "option2", "絵文字付きオプション", "👌"),
                        ("オプション 3", "option3", "複数選択可能", "👍"),
                    ],
                    placeholder="オプションを選択してください",
                    min_values=1,
                    max_values=2,
                ),
                
                # ユーザー選択メニュー
                cv2.user_select(
                    "demo_user_select",
                    placeholder="ユーザーを選択",
                    min_values=0,
                    max_values=1,
                ),
                
                # ロール選択メニュー
                cv2.role_select(
                    "demo_role_select",
                    placeholder="ロールを選択",
                    min_values=0,
                    max_values=1,
                ),
                
                # ボタン行
                cv2.row([
                    cv2.button("プライマリ", custom_id="btn_primary", style="primary", emoji="🔵"),
                    cv2.button("セカンダリ", custom_id="btn_secondary", style="secondary", emoji="⚪"),
                    cv2.button("サクセス", custom_id="btn_success", style="success", emoji="🟢"),
                    cv2.button("デンジャー", custom_id="btn_danger", style="danger", emoji="🔴"),
                    cv2.button("リンク", url="https://hfs.jp/bot", style="link", emoji="🔗"),
                ]),
            ]
            
            logger.info(f"CV2デモパネルのコンポーネント作成完了: {len(components)} 個")
            
            # コンポーネントの種類を詳細に記録
            component_types = []
            for comp in components:
                if isinstance(comp, dict) and "type" in comp:
                    component_types.append(f"{comp['type']}")
                elif hasattr(comp, "__dict__"):
                    component_types.append(f"{type(comp).__name__}")
                else:
                    component_types.append(f"{type(comp).__name__}")
            
            logger.info(f"コンポーネント種類: {', '.join(component_types)}")
            
            # まずメディアやファイルなしで試す
            logger.info("コンポーネントのみで送信試行")
            
            # UIコンポーネントのみで送信
            logger.info("UIコンポーネントのみで送信試行")
            ui_components = components.copy()
            test_message = await cv2.send(
                interaction.channel_id,  # type: ignore[attr-defined]
                components=ui_components,
                single_container=True
            )
            logger.info(f"UIコンポーネントのみの送信成功: {test_message}")
            
            # 3. 送信実行 - 単一コンテナモードで送信
            logger.info(f"CV2送信開始: media_urls={bool(media_urls)}, file_data={bool(file_data)}, components={len(components)}個")
            try:
                # 単一コンテナモードを有効化
                logger.info("単一コンテナモードで送信します")
                
                # コンポーネントの種類を詳細に記録
                component_types = []
                for comp in components:
                    if isinstance(comp, dict) and "type" in comp:
                        component_types.append(f"{comp['type']}")
                    elif hasattr(comp, "__dict__"):
                        component_types.append(f"{type(comp).__name__}")
                    else:
                        component_types.append(f"{type(comp).__name__}")
                
                logger.info(f"コンポーネント種類: {', '.join(component_types)}")
                
                # すべてを含めて送信
                logger.info("メディア・ファイル含む完全版を送信")
                await cv2.send(
                    interaction.channel_id,  # type: ignore[attr-defined]
                    components=components,
                    media_urls=media_urls if media_urls else None,
                    file_bytes=file_data,
                    file_name=file_name,
                    spoiler_file=True if file_data else False,
                    single_container=True  # 単一コンテナモードを使用
                )
                # 4. 結果メッセージ
                result_msg = "総合デモパネルを送信しました ✅\n"
                if media_urls:
                    result_msg += f"\nメディアギャラリー: {len(media_urls)} 個の画像"
                if file_data:
                    result_msg += f"\nFileコンポーネント: {file_name}"
                    
                await interaction.followup.send(result_msg, ephemeral=True)
                logger.info("CV2送信成功")
            except Exception as send_error:
                logger.error(f"CV2.send() 中にエラー発生: {send_error}")
                await interaction.followup.send(f"CV2デモパネルの送信中にエラーが発生しました: {send_error}", ephemeral=True)
            
        except CV2Error as e:
            await self._err(interaction, e)
        except Exception as e:
            logger.error(f"CV2デモパネル送信中に予期せぬエラーが発生: {e}")
            await interaction.followup.send(f"CV2デモパネル送信中にエラーが発生しました: {e}", ephemeral=True)


    # -----------------------------------------------------------------
    # Demo 2: 複数コンテナモード ----------------------------------------
    # -----------------------------------------------------------------
    @app_commands.command(name="cv2multi", description="複数コンテナモードでCV2デモパネルを送信")
    @app_commands.describe(
        url1="画像 URL 1 (メディアギャラリーで表示)",
        url2="画像 URL 2 (メディアギャラリーで表示)"
    )
    @is_guild_app()
    @is_owner_app()
    async def cv2multi(self, interaction: discord.Interaction, url1: str = "", url2: str = ""):
        await interaction.response.defer(ephemeral=True)
        
        # 有効な URL をフィルタリング
        media_urls = [u for u in [url1, url2] if u and u.startswith("http")][:2]
        
        try:
            # ボタンとテキストのコンテナ
            container1 = cv2.container([
                cv2.title("複数コンテナモードデモ", level=1),
                cv2.text("このメッセージは複数の別々のコンテナで構成されています。"),
                cv2.text("シンプルなコンテナで構成されています。"),
            ])
            
            # ボタン行のコンテナ
            container2 = cv2.container([
                cv2.title("ボタン行", level=2),
                cv2.row([
                    cv2.button("プライマリ", custom_id="btn_primary_multi", style="primary", emoji="🔵"),
                    cv2.button("セカンダリ", custom_id="btn_secondary_multi", style="secondary", emoji="⚪"),
                    cv2.button("サクセス", custom_id="btn_success_multi", style="success", emoji="🟢"),
                ]),
            ])
            
            # セレクトメニューのコンテナ
            container3 = cv2.container([
                cv2.title("選択メニュー", level=2),
                cv2.select(
                    "demo_select_multi",
                    [
                        ("オプション 1", "option1_multi", "説明付き", "🌟"),
                        ("オプション 2", "option2_multi", "絵文字付き", "👌"),
                    ],
                    placeholder="選択してください",
                ),
            ])
            
            # 全コンテナの送信
            components = [container1, container2, container3]
            
            if media_urls:
                media_container = cv2.container([cv2.text("メディアギャラリー"), cv2.line()])
                components.append(media_container)
            
            logger.info(f"CV2マルチコンテナ送信開始: コンテナ数={len(components)}")
            
            await cv2.send(
                interaction.channel_id,  # type: ignore[attr-defined]
                components=components,
                media_urls=media_urls if media_urls else None,
                single_container=False  # 複数コンテナモードを指定
            )
            
            result_msg = "複数コンテナモードのデモパネルを送信しました ✅\n"
            if media_urls:
                result_msg += f"\nメディアギャラリー: {len(media_urls)} 個の画像"
                
            await interaction.followup.send(result_msg, ephemeral=True)
            logger.info("CV2マルチコンテナ送信成功")
            
        except CV2Error as e:
            await self._err(interaction, e)
        except Exception as e:
            logger.error(f"CV2マルチコンテナ送信中にエラー発生: {e}")
            await interaction.followup.send(f"CV2デモパネルの送信中にエラーが発生しました: {e}", ephemeral=True)
    
    # -----------------------------------------------------------------
    # Demo 3: メディアギャラリー特化 --------------------------------
    # -----------------------------------------------------------------
    @app_commands.command(name="cv2media4", description="メディアギャラリーが4つ並ぶCV2デモ")
    @app_commands.describe(
        url1="画像 URL 1",
        url2="画像 URL 2",
        url3="画像 URL 3",
        url4="画像 URL 4"
    )
    @is_guild_app()
    @is_owner_app()
    async def cv2media4(self, interaction: discord.Interaction, url1: str = "", url2: str = "", url3: str = "", url4: str = ""):
        await interaction.response.defer(ephemeral=True)
        
        # 有効な URL をフィルタリング
        media_urls = [u for u in [url1, url2, url3, url4] if u and u.startswith("http")][:4]
        
        if not media_urls:
            await interaction.followup.send("有効なURLを少なくとも1つ指定してください。", ephemeral=True)
            return
        
        try:
            # メディアギャラリーとテキストのコンテナ
            components = [
                cv2.title("メディアギャラリーデモ", level=1),
                cv2.text(f"このデモでは {len(media_urls)} 個の画像をメディアギャラリーで表示しています。"),
                cv2.text("ディスコードのメディアギャラリーは最大4つまでの画像を表示できます。"),
                cv2.line(),
                cv2.row([
                    cv2.button("他の画像を表示", custom_id="media4_refresh", emoji="🔄"),
                ])
            ]
            
            logger.info(f"CV2メディアギャラリー送信開始: 画像数={len(media_urls)}")
            
            await cv2.send(
                interaction.channel_id,  # type: ignore[attr-defined]
                components=components,
                media_urls=media_urls,
                single_container=True
            )
            
            await interaction.followup.send(f"メディアギャラリーデモを送信しました ✅\n{len(media_urls)} 個の画像を表示しています", ephemeral=True)
            logger.info("CV2メディアギャラリー送信成功")
            
        except CV2Error as e:
            await self._err(interaction, e)
    
    # -----------------------------------------------------------------
    # Demo 4: UI要素特化 -------------------------------------------
    # -----------------------------------------------------------------
    @app_commands.command(name="cv2ui", description="UI要素を多用したCV2デモ")
    @is_guild_app()
    @is_owner_app()
    async def cv2ui(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        try:
            components = [
                cv2.title("CV2 UI要素デモ", level=1),
                cv2.text("このデモではさまざまなボタンや選択メニューなどのUI要素を表示しています。"),
                cv2.line(),
                
                # セクション
                cv2.section(
                    [
                        "セクションコンポーネント",
                        "テキストとアクセサリをまとめて表示",
                        "ボタンやアイコンも表示できます",
                    ],
                    accessory=cv2.button("セクションボタン", custom_id="section_ui", emoji="👍"),
                ),
                
                cv2.separator(divider=True, spacing=2),
                
                # ボタン行 - スタイルごと
                cv2.title("ボタンスタイル全種類", level=2),
                cv2.row([
                    cv2.button("プライマリ", custom_id="ui_primary", style="primary"),
                    cv2.button("セカンダリ", custom_id="ui_secondary", style="secondary"),
                ]),
                cv2.row([
                    cv2.button("サクセス", custom_id="ui_success", style="success"),
                    cv2.button("デンジャー", custom_id="ui_danger", style="danger"),
                    cv2.button("リンク", url="https://hfs.jp/bot", style="link"),
                ]),
                
                cv2.separator(divider=True, spacing=1),
                
                # 選択メニュー各種
                cv2.title("選択メニュー全種類", level=2),
                cv2.select(
                    "ui_string_select",
                    [
                        ("文字列選択メニュー", "string1", "通常の選択メニュー", "📝"),
                        ("複数選択可能", "string2", "複数の選択肢を選べます", "🔍"),
                    ],
                    placeholder="文字列選択メニュー",
                    min_values=1,
                    max_values=2,
                ),
                
                cv2.user_select(
                    "ui_user_select",
                    placeholder="ユーザー選択メニュー",
                ),
                
                cv2.role_select(
                    "ui_role_select",
                    placeholder="ロール選択メニュー",
                ),
                
                cv2.channel_select(
                    "ui_channel_select",
                    placeholder="チャンネル選択メニュー",
                ),
                
                cv2.mentionable_select(
                    "ui_mentionable_select",
                    placeholder="メンション可能選択メニュー",
                ),
            ]
            
            logger.info("CV2 UI要素デモ送信開始")
            
            await cv2.send(
                interaction.channel_id,  # type: ignore[attr-defined]
                components=components,
                single_container=True
            )
            
            await interaction.followup.send("UI要素デモを送信しました ✅", ephemeral=True)
            logger.info("CV2 UI要素デモ送信成功")
            
        except CV2Error as e:
            await self._err(interaction, e)

async def setup(bot: commands.Bot):
    await bot.add_cog(CV2Demo(bot))
