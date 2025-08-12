import discord
from discord.ext import commands
from discord import app_commands
import traceback
from utils.logging import setup_logging
import httpx
import random
import os
import json
import re
import uuid

from utils.db_manager import db

logger = setup_logging("D")

# --- 推しロールパネル用のCog ---
class OshiRolePanel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cv2_sender = CV2MessageSender(bot)
        self.role_emoji_mapping = {}
        self.analytics_data = {
            "role_assignments": [],
            "role_stats": {},
            "user_stats": {},
            "role_counts": {},
            "initial_counts": {},
            "last_updated": None
        }
        # 非同期でロール絵文字マッピングをロード
        bot.loop.create_task(self._init_role_emoji())
        self.load_analytics_data()
        self.cv2_sender.analytics_callback = self.record_role_event
        self.talent_to_fanname = {
            # JP 0期
            "jp0_sora": "そらとも",
            "jp0_roboco": "ろぼさー",
            "jp0_miko": "35p",
            "jp0_suisei": "星詠み",
            "jp0_azki": "開拓者",
            "jp0_achan": "えーちゃん",
            # JP 1期
            "jp1_fubuki": "すこん部",
            "jp1_matsuri": "まつりす",
            "jp1_haato": "はあとん",
            "jp1_akirosenthal": "ロゼ隊",
            # JP 2期
            "jp2_aqua": "あくあクルー",
            "jp2_shion": "塩っ子",
            "jp2_ayame": "百鬼組",
            "jp2_choco": "ちょこめいと",
            "jp2_subaru": "スバ友",
            # Gamers
            "jpg_fubuki": "すこん部",
            "jpg_mio": "ミオファ",
            "jpg_okayu": "おにぎりゃー",
            "jpg_korone": "ころねすきー",
            # JP 3期
            "jp3_pekora": "野うさぎ同盟",
            "jp3_rushia": "ふぁんでっと",
            "jp3_flare": "エルフレ",
            "jp3_noel": "白銀聖騎士団",
            "jp3_marine": "宝鐘の一味",
            # JP 4期
            "jp4_kanata": "へい民",
            "jp4_coco": "桐生会",
            "jp4_watame": "わためいと",
            "jp4_towa": "常闇眷属",
            "jp4_luna": "ルーナイト",
            # JP 5期
            "jp5_lamy": "雪民",
            "jp5_nene": "ねっ子",
            "jp5_botan": "SSRB",
            "jp5_polka": "おまる座",
            # JP 6期 (holoX)
            "jp6_laplus": "ぷらすめいと",
            "jp6_lui": "ルイ友",
            "jp6_koyori": "こよりの助手くん",
            "jp6_chloe": "飼育員",
            "jp6_iroha": "かざま隊",
            # EN 0期 (IRyS)
            "en0_irys": "IRyStocrats",
            # EN 1期 (Myth)
            "en1_calliope": "Dead Beats",
            "en1_kiara": "kfp",
            "en1_inanis": "tentacult",
            "en1_gura": "chumbuds",
            "en1_amelia": "teamates",
            # EN 2期 (Council)
            "en2_fauna": "Saplings",
            "en2_kronii": "Kronies",
            "en2_mumei": "Hoomans",
            "en2_baelz": "Brats",
            # EN 3期 (Adventure)
            "en3_shiori": "Novelites",
            "en3_bijou": "Pebbles",
            "en3_rissa": "Jailbirds",
            "en3_mococo": "RUFFIANS",
            # ID 1期
            "id1_risu": "Risuners",
            "id1_moona": "Moonafic",
            "id1_iofi": "IOFORIA",
            # ID 2期
            "id2_ollie": "ZOMRADE",
            "id2_anya": "MelFriends",
            "id2_reine": "MERAKyats",
            # ID 3期
            "id3_zeta": "Zecretary",
            "id3_kaela": "Pemaloe",
            "id3_kobo": "Kobokerz",
            # ReGLOSS
            "reg_ao": "読者",
            "reg_raden": "でん同士",
            "reg_kanade": "音の勢",
            "reg_Ririka": "秘書見習い",
            "reg_hajime": "真っす組",
            # スタッフ
            "1_yagoo_": "YAGOO",
            # FlowGlow
            
            # Justice
            
        }
        
    async def load_role_emoji_mapping(self):
        """DBからロール絵文字マッピングを取得し、旧JSONがあればマージしてDBへ反映"""
        # DB取得
        try:
            self.role_emoji_mapping = await db.get_role_emoji_mapping_dict()
        except Exception as e:
            logger.error(f"DB取得失敗: {e}")
            self.role_emoji_mapping = {}

        legacy_changed = False
        data_dir = os.path.join(os.getcwd(), "data")
        file_path = os.path.join(data_dir, "role_emoji_mapping.json")
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    legacy_data = json.load(f)
                for k, v in legacy_data.items():
                    if k not in self.role_emoji_mapping:
                        self.role_emoji_mapping[k] = v
                        legacy_changed = True
            except Exception as e:
                logger.error(f"旧JSON読み込み失敗: {e}")

        if legacy_changed:
            await self.save_role_emoji_mapping()
            logger.info("旧JSONマッピングをDBへマージしました")

    async def _init_role_emoji(self):
        """Cog起動時に呼ばれる非同期初期化"""
        await self.load_role_emoji_mapping()
        """role_emoji_mappings テーブルからマッピングを取得し、旧JSONをマージしてDBに反映"""
        # 1. DB から取得
        try:
            self.role_emoji_mapping = await db.get_role_emoji_mapping_dict()
        except Exception as e:
            logger.error(f"DB取得失敗: {e}")
            self.role_emoji_mapping = {}

        legacy_changed = False
        data_dir = os.path.join(os.getcwd(), "data")
        file_path = os.path.join(data_dir, "role_emoji_mapping.json")

        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    legacy_data = json.load(f)
                for k, v in legacy_data.items():
                    if k not in self.role_emoji_mapping:
                        self.role_emoji_mapping[k] = v
                        legacy_changed = True
            except Exception as e:
                logger.error(f"ロール絵文字マッピングの読み込みに失敗: {e}")
                self.role_emoji_mapping = {}
        
    async def save_role_emoji_mapping(self, guild_id: int = None):
        """ロールと絵文字のマッピングをDBへ保存"""
        try:
            if guild_id is not None:
                await db.upsert_role_emoji_mapping_dict(self.role_emoji_mapping, guild_id)
                logger.info(f"ロール絵文字マッピングをDBへ保存: {len(self.role_emoji_mapping)}件")
            else:
                logger.info(f"初期化時のguild_idなしでDB保存をスキップ: {len(self.role_emoji_mapping)}件")
            
            # file_pathを定義
            data_dir = os.path.join(os.getcwd(), "data")
            file_path = os.path.join(data_dir, "role_emoji_mapping.json")
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.role_emoji_mapping, f, indent=4, ensure_ascii=False)
            logger.info(f"ロール絵文字マッピングを保存しました: {len(self.role_emoji_mapping)}件")
            return True
        except Exception as e:
            logger.error(f"ロール絵文字マッピングDB保存失敗: {e}")
            return False

    async def _init_role_emoji(self):
        """Cog 起動時に呼ばれる非同期初期化"""
        await self.load_role_emoji_mapping()
        """ロールと絵文字のマッピングをDBへ保存"""
        try:
            # save_role_emoji_mappingメソッドを使用
            return await self.save_role_emoji_mapping()
        except Exception as e:
            logger.error(f"ロール絵文字マッピングの保存に失敗: {e}")
            return False
        
    @commands.hybrid_group(name="oshirole")
    async def oshirole(self, ctx):
        """推しロール関連コマンドのグループ"""
        if ctx.invoked_subcommand is None:
            await ctx.send("サブコマンドを指定してください。`panel`、`edit`など")
    
    @oshirole.command(name="panel")
    @commands.has_permissions(administrator=True)
    async def create_panel(self, ctx, channel: discord.TextChannel = None):
        """CV2形式の推しロールパネルを作成します"""
        if channel is None:
            channel = ctx.channel
            
        await self.scan_roles_for_icons(ctx.guild)
            
        image_url = "https://images.frwi.net/data/images/31dd6e9b-25e3-4a15-a783-1c7b0054b10f.png"
        
        await ctx.send(f"{channel.mention}に推しロールパネルを作成します...")
        _text = "選択欄の横にある絵文字が付きます。\n\n仕様上リストの上のメンバーの絵文字から優先してつきますので、ご了承ください。\n\n《例》\nそらともと35Pを選択した場合は**そらちゃんのみ**名前の横に表示されます。"
        result = await self.cv2_sender.send_role_panel(channel_id=channel.id, image_url=image_url, text=_text)
        
        if result:
            await ctx.send("推しロールパネルを作成しました")
        else:
            await ctx.send("推しロールパネルの作成に失敗しました")
    
    @oshirole.command(name="scanroles")
    @commands.has_permissions(administrator=True)
    async def scan_all_roles(self, ctx):
        """推しロールを走査して、各ロールの絵文字を取得し、初期人数も記録する"""
        guild = ctx.guild
        
        # oshi_categories に含まれるロールIDのセットを作成
        oshi_role_ids = set()
        oshi_role_names = {}
        
        logger.info(f"推しロールカテゴリ数: {len(self.cv2_sender.oshi_categories)}個")
        for category in self.cv2_sender.oshi_categories:
            category_name = category.get("name", "不明")
            roles_count = len(category.get("roles", {}))
            logger.info(f"カテゴリ '{category_name}' にロール {roles_count}個")
            
            for role_name, role_id in category.get("roles", {}).items():
                oshi_role_ids.add(role_id)
                oshi_role_names[role_id] = role_name
                logger.debug(f"推しロールID登録: {role_name} -> {role_id}")
        
        logger.info(f"対象の推しロール数: {len(oshi_role_ids)}個")
        
        role_emoji_mapping = {}
        initial_counts = {}
        role_counts = {}
        scanned_roles = 0
        
        # 全ロールから推しロールだけをフィルタリング
        for role in guild.roles:
            if role.id in oshi_role_ids:
                scanned_roles += 1
                role_name = oshi_role_names[role.id]
                
                emoji_match = re.search(r'([\u00a9\u00ae\u2000-\u3300\ud83c\ud000-\ud83e\udfff\ufe0f]+)', role.name)
                if emoji_match:
                    emoji = emoji_match.group(1)
                    if emoji.startswith('<') and emoji.endswith('>'):
                        emoji_parts = emoji.strip('<>').split(':')
                        if len(emoji_parts) == 3:
                            role_emoji_mapping[str(role.id)] = {
                                "name": role.name,
                                "emoji_id": emoji_parts[2],
                                "emoji_name": emoji_parts[1],
                                "animated": emoji_parts[0] == "a"
                            }
                        else:
                            role_emoji_mapping[str(role.id)] = {
                                "name": role.name
                            }
                    else:
                        role_emoji_mapping[str(role.id)] = {
                            "name": role.name,
                            "unicode_emoji": emoji
                        }
                
                member_count = len(role.members)
                role_counts[role_name] = member_count
                
                if "initial_counts" not in self.analytics_data:
                    self.analytics_data["initial_counts"] = {}
                
                if role_name not in self.analytics_data["initial_counts"]:
                    initial_counts[role_name] = member_count
                    
                logger.info(f"推しロール '{role_name}' をスキャン: メンバー数 {member_count}人")
                
        # 既存のロール絵文字マッピングを上書きしないように、新しいマッピングだけを追加する
        for role_id, emoji_data in role_emoji_mapping.items():
            if role_id not in self.role_emoji_mapping:
                self.role_emoji_mapping[role_id] = emoji_data
                logger.info(f"新しいロール絵文字マッピングを追加: {role_id} -> {emoji_data}")
        
        await self.save_role_emoji_mapping(guild.id)
        
        if initial_counts:
            if "initial_counts" not in self.analytics_data:
                self.analytics_data["initial_counts"] = {}
            self.analytics_data["initial_counts"].update(initial_counts)
            
        self.analytics_data["role_counts"] = role_counts
        
        # ロール統計データを更新して初期メンバー数と現在のメンバー数を追加する
        for role_name, member_count in role_counts.items():
            initial_count = initial_counts.get(role_name, member_count)
            
            if role_name not in self.analytics_data["role_stats"]:
                self.analytics_data["role_stats"][role_name] = {
                    "count": 0,
                    "last_selected": None,
                    "initial_members": initial_count,
                    "current_members": member_count
                }
            else:
                # 既存のロール統計に初期メンバー数と現在のメンバー数を追加
                self.analytics_data["role_stats"][role_name]["initial_members"] = initial_count
                self.analytics_data["role_stats"][role_name]["current_members"] = member_count
        
        self.save_analytics_data()
        
        await ctx.send(f"{len(role_emoji_mapping)}個のロールと絵文字のマッピング、および各ロールの現在の所持人数を保存しました。", ephemeral=True)
    
    @oshirole.command(name="listroles")
    @commands.has_permissions(administrator=True)
    async def list_roles(self, ctx):
        """サーバーのロール一覧をJSON形式で取得します（アイコンURL含む）"""
        guild = ctx.guild
        roles_data = {}
        
        for role in guild.roles:
            if role.name != "@everyone":
                roles_data[role.name] = {
                    "id": role.id,
                    "color": role.color.value if role.color.value else 0,
                    "position": role.position,
                    "mentionable": role.mentionable,
                    "hoist": role.hoist,
                    "icon_url": role.icon.url if role.icon else None
                }
        
        data_dir = os.path.join(os.getcwd(), "data")
        os.makedirs(data_dir, exist_ok=True)
        
        file_path = os.path.join(data_dir, f"roles_{guild.id}.json")
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(roles_data, f, indent=4, ensure_ascii=False)
        
        with open(file_path, 'rb') as f:
            file = discord.File(f, filename=f"roles_{guild.id}.json")
            await ctx.send("ロール一覧を取得しました（アイコンURL含む）：", file=file)
            
        logger.info(f"ロール一覧を保存しました: {file_path}")
        

    @oshirole.command(name="listemoji")
    @commands.has_permissions(administrator=True)
    async def list_emoji(self, ctx, prefix: str = "m_", as_json: bool = False):
        """サーバー内の指定した接頭辞（デフォルト: m_）から始まる絵文字を一覧表示します。JSON形式の出力も可能です。"""
        guild = ctx.guild
        matching_emojis = [emoji for emoji in guild.emojis if emoji.name.startswith(prefix)]
        
        if not matching_emojis:
            await ctx.send(f"サーバー内に '{prefix}' から始まる絵文字は見つかりませんでした。")
            return
        
        if as_json:
            emoji_data = []
            for emoji in matching_emojis:
                emoji_data.append({
                    "name": emoji.name,
                    "id": str(emoji.id),
                    "url": str(emoji.url),
                    "display": f"<:{emoji.name}:{emoji.id}>",
                    "copy_format": f"<:{emoji.name}:{emoji.id}>",
                    "animated": emoji.animated
                })
            
            data_dir = os.path.join(os.getcwd(), "data")
            os.makedirs(data_dir, exist_ok=True)
            file_path = os.path.join(data_dir, f"{prefix}_emojis.json")
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(emoji_data, f, indent=4, ensure_ascii=False)
            
            with open(file_path, 'rb') as f:
                file = discord.File(f, filename=f"{prefix}_emojis.json")
                await ctx.send(f"'{prefix}'から始まる絵文字一覧 (合計: {len(matching_emojis)}個):", file=file)
            
            return
        
        emojis_per_page = 10
        total_pages = (len(matching_emojis) + emojis_per_page - 1) // emojis_per_page
        
        for page in range(total_pages):
            start_idx = page * emojis_per_page
            end_idx = min(start_idx + emojis_per_page, len(matching_emojis))
            page_emojis = matching_emojis[start_idx:end_idx]
            
            embed = discord.Embed(
                title=f"'{prefix}'から始まる絵文字一覧 ({start_idx+1}-{end_idx}/{len(matching_emojis)})",
                description="以下の絵文字をロールアイコンとして使用できます。\n`/oshirole setemoji @ロール <絵文字>` で設定できます。",
                color=discord.Color.blue()
            )
            
            for emoji in page_emojis:
                emoji_display = f"<:{emoji.name}:{emoji.id}>"
                emoji_copy = f"`<:{emoji.name}:{emoji.id}>`"
                embed.add_field(
                    name=f":{emoji.name}:",
                    value=f"ID: {emoji.id}\n表示: {emoji_display}\nコピー用: {emoji_copy}\nURL: [画像リンク]({emoji.url})",
                    inline=False
                )
            
            embed.set_footer(text=f"ページ {page+1}/{total_pages} - 合計: {len(matching_emojis)}個の絵文字")
            await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_interaction(self, interaction):
        """インタラクション処理"""
        if not interaction.data:
            return
            
        custom_id = interaction.data.get("custom_id", "")
        logger.debug(f"インタラクション受信: custom_id={custom_id}")
        
        if custom_id == "oshi_select":
            await self.cv2_sender.handle_oshi_select(interaction)
        elif custom_id == "member_select" or custom_id.startswith("member_select:"):
            await self.cv2_sender.handle_member_select(interaction)
        elif custom_id.startswith("role_"):
            await self.cv2_sender.handle_role_button(interaction)
        elif custom_id in ["oshi_english", "oshi_korean", "oshi_chinese", "oshi_japanese"]:
            await self.cv2_sender.handle_oshi_language_button(interaction)
        elif custom_id == "close_analytics":
            try:
                # メッセージを削除
                await interaction.response.defer()
                if hasattr(interaction, "message") and interaction.message:
                    await interaction.message.delete()
                    logger.info(f"アナリティクスメッセージを削除しました: ユーザー={interaction.user.name}")
            except Exception as e:
                logger.error(f"アナリティクスメッセージの削除中にエラー: {e}")
                await interaction.followup.send("メッセージを削除できませんでした。", ephemeral=True)
        elif custom_id.startswith("analytics_switch:"):
            # アナリティクス切り替え処理
            try:
                # custom_id から パラメータを取得
                parts = custom_id.split(":")[1:]
                if len(parts) >= 3:
                    switch_type = parts[0]
                    switch_count = int(parts[1])
                    switch_sort_by = parts[2]
                    
                    await interaction.response.defer(ephemeral=True)
                    await self._show_analytics_cv2(interaction, switch_type, switch_count, switch_sort_by)
                    logger.info(f"アナリティクス切り替え: {switch_type}, ソート={switch_sort_by}, ユーザー={interaction.user.name}")
                else:
                    logger.error(f"不正なアナリティクス切り替えパラメータ: {custom_id}")
                    await interaction.response.send_message("パラメータエラー。もう一度試してください。", ephemeral=True)
            except Exception as e:
                logger.error(f"アナリティクス切り替え中にエラー: {e}")
                await interaction.response.send_message(f"エラーが発生しました: {e}", ephemeral=True)

    async def scan_roles_for_icons(self, guild):
        """サーバー内のロールをスキャンして、「m_」で始まる絵文字を関連付ける"""
        logger.info(f"ロール絵文字スキャン開始: サーバー {guild.name}")
        roles_total = 0
        emojis_mapped = 0
        
        member_emojis = {}
        for emoji in guild.emojis:
            if emoji.name.startswith("m_"):
                talent_id = emoji.name[2:]
                member_emojis[talent_id] = emoji
                logger.info(f"ロール絵文字候補: {emoji.name} -> {talent_id}")
                    
        logger.info(f"'m_'で始まる絵文字を {len(member_emojis)} 個見つけました")
        
        for category in self.cv2_sender.oshi_categories:
            for role_name, role_id in category["roles"].items():
                roles_total += 1
                role = guild.get_role(role_id)
                
                if not role:
                    logger.warning(f"ロールが見つかりません: {role_name} (ID: {role_id})")
                    continue
                    
                clean_role_name = role_name
                for emoji_marker in ["🐻‍💿", "🤖", "☄️", "🌸", "🌽", "🏮", "❤", "🍎", "🌟", "⚒️", 
                                     "🌲", "🍙", "🥐", "🔥", "⚔️", "🏴‍☠️", "👯‍♀️", "🚑", "⚓", "💋", 
                                     "😈", "🌙", "💫", "🐑", "👾", "🍬", "☃", "🍑🥟", "♌", "🎪", "🐉",
                                     "🛸💜", "🥀", "🧪", "🍃", "🎣", "💎", "🔎", "🔱", "🐙", "🐔",
                                     "💀", "🌿", "⏳", "🪶", "🎲", "👁️‍🗨️", "🗿", "🎼", "🐾", "🐿",
                                     "🔮", "🎨", "🧟‍♀️", "🦚", "🍂", "📜", "🔨", "☔", "🖋️", "🐚",
                                     "🎹✨", "🌃", "🐧⚡️", "👨‍🎓", "👓", "📝"]:
                    if emoji_marker in clean_role_name:
                        clean_role_name = clean_role_name.replace(emoji_marker, "").strip()
                
                best_match = None
                best_match_path = None
                
                for talent_id, emoji in member_emojis.items():
                    fanname = self.talent_to_fanname.get(talent_id, "")
                    
                    if fanname and (fanname.lower() == clean_role_name.lower() or 
                                   fanname.lower() in clean_role_name.lower() or 
                                   clean_role_name.lower() in fanname.lower()):
                        best_match = emoji
                        best_match_path = f"{talent_id} → {fanname} ≈ {clean_role_name}"
                        break
                
                if not best_match:
                    if clean_role_name in member_emojis:
                        best_match = member_emojis[clean_role_name]
                        best_match_path = f"直接マッチ: {clean_role_name}"
                    else:
                        for emoji_name, emoji in member_emojis.items():
                            if clean_role_name.lower().startswith(emoji_name.lower()) or emoji_name.lower().startswith(clean_role_name.lower()):
                                best_match = emoji
                                best_match_path = f"接頭辞マッチ: {emoji_name} ≈ {clean_role_name}"
                                break
                        
                        if not best_match:
                            for emoji_name, emoji in member_emojis.items():
                                if emoji_name.lower() in clean_role_name.lower() or clean_role_name.lower() in emoji_name.lower():
                                    best_match = emoji
                                    best_match_path = f"部分マッチ: {emoji_name} ≈ {clean_role_name}"
                                    break
                
                if best_match:
                    emoji_str = f"<:{best_match.name}:{best_match.id}>"
                    self.role_emoji_mapping[str(role_id)] = emoji_str
                    emojis_mapped += 1
                    logger.info(f"ロール「{role_name}」に絵文字 {emoji_str} をマッピングしました (マッチ: {best_match_path})")
        
        await self.save_role_emoji_mapping(guild.id)
        logger.info(f"ロール絵文字スキャン完了: {roles_total}個のロール、{emojis_mapped}個の絵文字をマッピング")
        
        return roles_total, emojis_mapped
        
    @oshirole.command(name="scanemojis")
    @commands.has_permissions(administrator=True)
    async def scan_member_emojis(self, ctx):
        """サーバー内の「m_」から始まる絵文字をスキャンし、ロールに自動マッピングします"""
        async with ctx.typing():
            roles_total, emojis_mapped = await self.scan_roles_for_icons(ctx.guild)
            
        embed = discord.Embed(
            title="メンバー絵文字スキャン結果",
            description="サーバー内の「m_」から始まる絵文字をスキャンし、対応するロールに自動マッピングしました。",
            color=discord.Color.blue()
        )
        
        embed.add_field(name="対象ロール数", value=f"{roles_total}個", inline=True)
        embed.add_field(name="マッピングされた絵文字", value=f"{emojis_mapped}個", inline=True)
        embed.add_field(name="マッピング率", value=f"{emojis_mapped/roles_total*100:.1f}%" if roles_total > 0 else "0%", inline=True)
        
        embed.set_footer(text="絵文字の命名規則: m_[メンバー名] (例: m_そらとも)")
        
        await ctx.send(embed=embed)
        
    def load_analytics_data(self):
        """アナリティクスデータをJSONファイルから読み込む"""
        base_dir = os.path.join(os.getcwd(), "data", "analytics", "oshi_roles")
        os.makedirs(base_dir, exist_ok=True)
        
        events_path = os.path.join(base_dir, "events.json")
        roles_path = os.path.join(base_dir, "roles.json")
        users_path = os.path.join(base_dir, "users.json")
        summary_path = os.path.join(base_dir, "summary.json")
        
        legacy_path = os.path.join(os.getcwd(), "data", "role_analytics.json")
        
        self.analytics_data = {
            "role_assignments": [],
            "role_stats": {},
            "user_stats": {},
            "initial_counts": {},
            "role_counts": {},
            "last_updated": None
        }
        
        if os.path.exists(legacy_path) and not os.path.exists(events_path):
            try:
                with open(legacy_path, 'r', encoding='utf-8') as f:
                    legacy_data = json.load(f)
                self.analytics_data = legacy_data
                logger.info("従来のアナリティクスデータを読み込みました。新形式に移行します。")
                self.save_analytics_data()
                logger.info("データ移行が完了しました。")
                return
            except Exception as e:
                logger.error(f"従来のデータ移行中にエラー: {e}")
        
        if os.path.exists(events_path):
            try:
                with open(events_path, 'r', encoding='utf-8') as f:
                    self.analytics_data["role_assignments"] = json.load(f)
                logger.info(f"イベントデータを読み込みました: {len(self.analytics_data['role_assignments'])}件")
            except Exception as e:
                logger.error(f"イベントデータの読み込みに失敗: {e}")
        
        if os.path.exists(roles_path):
            try:
                with open(roles_path, 'r', encoding='utf-8') as f:
                    self.analytics_data["role_stats"] = json.load(f)
                logger.info(f"ロール統計データを読み込みました: {len(self.analytics_data['role_stats'])}件")
            except Exception as e:
                logger.error(f"ロール統計データの読み込みに失敗: {e}")
        
        if os.path.exists(users_path):
            try:
                with open(users_path, 'r', encoding='utf-8') as f:
                    self.analytics_data["user_stats"] = json.load(f)
                logger.info(f"ユーザー統計データを読み込みました: {len(self.analytics_data['user_stats'])}件")
            except Exception as e:
                logger.error(f"ユーザー統計データの読み込みに失敗: {e}")
        
        if os.path.exists(summary_path):
            try:
                with open(summary_path, 'r', encoding='utf-8') as f:
                    summary_data = json.load(f)
                    self.analytics_data["last_updated"] = summary_data.get("last_updated")
                logger.info("サマリーデータを読み込みました")
            except Exception as e:
                logger.error(f"サマリーデータの読み込みに失敗: {e}")
        
    def save_analytics_data(self):
        """アナリティクスデータをJSON形式で種類ごとに保存"""
        base_dir = os.path.join(os.getcwd(), "data", "analytics", "oshi_roles")
        os.makedirs(base_dir, exist_ok=True)
        
        events_path = os.path.join(base_dir, "events.json")
        roles_path = os.path.join(base_dir, "roles.json")
        users_path = os.path.join(base_dir, "users.json")
        summary_path = os.path.join(base_dir, "summary.json")
        
        current_time = discord.utils.utcnow().isoformat()
        self.analytics_data["last_updated"] = current_time
        
        success = True
        
        try:
            with open(events_path, 'w', encoding='utf-8') as f:
                json.dump(self.analytics_data["role_assignments"], f, indent=4, ensure_ascii=False)
            logger.info(f"イベントデータを保存しました: {len(self.analytics_data['role_assignments'])}件")
        except Exception as e:
            logger.error(f"イベントデータの保存に失敗: {e}")
            success = False
        
        try:
            with open(roles_path, 'w', encoding='utf-8') as f:
                json.dump(self.analytics_data["role_stats"], f, indent=4, ensure_ascii=False)
            logger.info(f"ロール統計データを保存しました: {len(self.analytics_data['role_stats'])}件")
        except Exception as e:
            logger.error(f"ロール統計データの保存に失敗: {e}")
            success = False
        
        try:
            with open(users_path, 'w', encoding='utf-8') as f:
                json.dump(self.analytics_data["user_stats"], f, indent=4, ensure_ascii=False)
            logger.info(f"ユーザー統計データを保存しました: {len(self.analytics_data['user_stats'])}件")
        except Exception as e:
            logger.error(f"ユーザー統計データの保存に失敗: {e}")
            success = False
        
        try:
            summary_data = {
                "last_updated": current_time,
                "total_events": len(self.analytics_data["role_assignments"]),
                "total_roles": len(self.analytics_data["role_stats"]),
                "total_users": len(self.analytics_data["user_stats"])
            }
            with open(summary_path, 'w', encoding='utf-8') as f:
                json.dump(summary_data, f, indent=4, ensure_ascii=False)
            logger.info("サマリーデータを保存しました")
        except Exception as e:
            logger.error(f"サマリーデータの保存に失敗: {e}")
            success = False
            
        return success
            
    def record_role_event(self, event_type, user_id, user_name, roles, category=""):
        """ロールの付与または解除イベントを記録する
        
        Parameters:
        -----------
        event_type : str
            イベントタイプ（"add" または "remove"）
        user_id : int
            ユーザーID
        user_name : str
            ユーザー名
        roles : List[Dict]
            対象のロールのリスト（各ロールは {id, name} の辞書）
        category : str, optional
            ロールのカテゴリ名
        """
        import datetime
        from zoneinfo import ZoneInfo
        
        now = datetime.datetime.now(ZoneInfo("Asia/Tokyo"))
        timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
        
        event_data = {
            "user_id": str(user_id),
            "user_name": user_name,
            "event_type": "追加しました" if event_type == "add" else "解除しました",
            "roles": roles,
            "category": category,
            "timestamp": timestamp
        }
        
        for role in roles:
            role_name = role.get("name", "不明")
            
            if role_name not in self.analytics_data["role_stats"]:
                # 初期メンバー数を取得（存在しない場合は0）
                initial_count = self.analytics_data.get("initial_counts", {}).get(role_name, 0)
                # 現在のメンバー数を取得（存在しない場合は初期カウント）
                current_count = self.analytics_data.get("role_counts", {}).get(role_name, initial_count)
                
                self.analytics_data["role_stats"][role_name] = {
                    "count": 0,
                    "last_selected": None,
                    "initial_members": initial_count,
                    "current_members": current_count
                }
            
            if event_type == "add":
                self.analytics_data["role_stats"][role_name]["count"] += 1
            
            self.analytics_data["role_stats"][role_name]["last_selected"] = timestamp
            
            if role_name in self.analytics_data["role_counts"]:
                if event_type == "add":
                    self.analytics_data["role_counts"][role_name] += 1
                    # 現在のメンバー数も更新
                    if "current_members" in self.analytics_data["role_stats"][role_name]:
                        self.analytics_data["role_stats"][role_name]["current_members"] += 1
                elif event_type == "remove" and self.analytics_data["role_counts"][role_name] > 0:
                    self.analytics_data["role_counts"][role_name] -= 1
                    # 現在のメンバー数も更新
                    if "current_members" in self.analytics_data["role_stats"][role_name] and self.analytics_data["role_stats"][role_name]["current_members"] > 0:
                        self.analytics_data["role_stats"][role_name]["current_members"] -= 1
        
        user_id_str = str(user_id)
        if user_id_str not in self.analytics_data["user_stats"]:
            self.analytics_data["user_stats"][user_id_str] = {
                "name": user_name,
                "total_changes": 0,
                "last_change": None
            }
        
        self.analytics_data["user_stats"][user_id_str]["total_changes"] += 1
        self.analytics_data["user_stats"][user_id_str]["last_change"] = timestamp
        
        self.analytics_data["role_assignments"].append(event_data)
        
        self.analytics_data["last_updated"] = timestamp
        
        self.save_analytics_data()
        
        if len(self.analytics_data["role_assignments"]) % 10 == 0:
            self.save_analytics_data()
    
    @app_commands.command(name="analytics", description="ロールアナリティクスデータを表示します")
    @app_commands.describe(
        type="表示するデータの種類",
        count="表示するデータの数",
        sort_by="ソート順（人気/非アクティブロールの場合のみ有効）"
    )
    @app_commands.choices(type=[
        app_commands.Choice(name="サマリー", value="summary"),
        app_commands.Choice(name="人気ロール", value="popular"),
        app_commands.Choice(name="非アクティブロール", value="inactive"),
        app_commands.Choice(name="アクティブユーザー", value="users"),
        app_commands.Choice(name="最近のアクティビティ", value="recent")
    ])
    @app_commands.choices(sort_by=[
        app_commands.Choice(name="選択回数順", value="count"),
        app_commands.Choice(name="メンバー数順", value="members")
    ])
    async def show_analytics(self, interaction: discord.Interaction, type: str = "popular", count: int = 10, sort_by: str = "count"):
        """ロールアナリティクスデータを表示します"""
        # 管理者権限の確認
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("このコマンドは管理者のみ使用できます。", ephemeral=True)
            return
        
        # データが存在するか確認
        if not self.analytics_data.get("role_assignments") and not self.analytics_data.get("role_stats"):
            await interaction.response.send_message("アナリティクスデータがまだ収集されていません。", ephemeral=True)
            return
            
        # 表示件数を制限
        count = max(1, min(count, 25))
        
        # 応答を遅延する（重要！）
        await interaction.response.defer(thinking=True)
        
        # CV2形式でアナリティクスデータを表示
        await self._show_analytics_cv2(interaction, type, count, sort_by)
        
    async def _show_analytics_cv2(self, interaction: discord.Interaction, type: str, count: int, sort_by: str = "count"):
        """
CV2形式でアナリティクスデータを表示する
        """
        # ソート方法に応じたテキストを設定
        sort_text = "選択回数順" if sort_by == "count" else "メンバー数順"
        title = "推しロールアナリティクス"
        description = ""
        
        if type == "popular":
            top_roles = sorted(self.analytics_data.get("role_stats", {}).items(), 
                              key=lambda x: x[1].get("count", 0), 
                              reverse=True)[:count]
            
            description = f"**人気ロールランキング (トップ{len(top_roles)})**\n\n"
            
            for i, (role_name, stats) in enumerate(top_roles):
                count_value = stats.get('count', 0)
                current_members = stats.get('current_members', 0)
                description += f"**{i+1}.** {role_name}\n"
                description += f"　　選択回数: {count_value}回 | 現在のメンバー数: {current_members}人\n\n"
                
        elif type == "inactive":
            bottom_roles = sorted(self.analytics_data.get("role_stats", {}).items(), 
                                 key=lambda x: x[1].get("count", 0))[:count]
            
            description = f"**非アクティブロールランキング (下位{len(bottom_roles)})**\n\n"
            
            for i, (role_name, stats) in enumerate(bottom_roles):
                count_value = stats.get('count', 0)
                current_members = stats.get('current_members', 0)
                description += f"**{i+1}.** {role_name}\n"
                description += f"　　選択回数: {count_value}回 | 現在のメンバー数: {current_members}人\n\n"
                
        elif type == "users":
            top_users = sorted(self.analytics_data.get("user_stats", {}).items(), 
                              key=lambda x: x[1].get("total_changes", 0), 
                              reverse=True)[:count]
            
            description = f"**アクティブユーザーランキング (トップ{len(top_users)})**\n\n"
            
            for i, (user_id, stats) in enumerate(top_users):
                user_name = stats.get("name", "不明")
                total_changes = stats.get("total_changes", 0)
                last_change = stats.get("last_change", "不明")
                description += f"**{i+1}.** {user_name}\n"
                description += f"　　変更回数: {total_changes}回 | 最終変更: {last_change}\n\n"
        
        if type == "summary":
            title = "推しロールアナリティクス - サマリー"
            
            total_assignments = len(self.analytics_data.get("role_assignments", []))
            total_roles = len(self.analytics_data.get("role_stats", {}))
            total_users = len(self.analytics_data.get("user_stats", {}))
            
            description = "### 全体サマリー\n\n"
            description += f"**総ロール変更回数**: {total_assignments}\n"
            description += f"**アクティブロール数**: {total_roles}\n"
            description += f"**アクティブユーザー数**: {total_users}\n"
            
            if self.analytics_data.get("initial_counts") and self.analytics_data.get("role_counts"):
                description += "\n### ロール所持人数の変化\n\n"
                sorted_roles = sorted(self.analytics_data["role_counts"].items(), 
                                     key=lambda x: x[1],
                                     reverse=True)[:5]
                
                for role_name, current_count in sorted_roles:
                    initial = self.analytics_data["initial_counts"].get(role_name, 0)
                    change = current_count - initial
                    change_str = f"+{change}" if change > 0 else str(change)
                    description += f"**{role_name}**: {current_count}人 ({change_str})\n"
                
                description += "\n"
            
            top_roles = sorted(self.analytics_data.get("role_stats", {}).items(), 
                              key=lambda x: x[1].get("count", 0), 
                              reverse=True)[:3]
            
            if top_roles:
                description += "### 人気トップ3ロール\n\n"
                for i, (role_name, stats) in enumerate(top_roles):
                    description += f"**{i+1}. {role_name}**: {stats.get('count', 0)}回\n"
                description += "\n"
            
            recent_events = self.analytics_data.get("role_assignments", [])[-3:]
            recent_events.reverse()
            
            if recent_events:
                description += "### 最近のアクティビティ\n\n"
                for event in recent_events:
                    event_time = event.get("timestamp", "不明")
                    user_name = event.get("user_name", "不明")
                    event_type = event.get("event_type", "不明")
                    roles_text = ", ".join([r.get("name", "不明") for r in event.get("roles", [])])
                    
                    description += f"**{event_time}**: {user_name} が {event_type} **{roles_text}**\n"
            
        elif type == "popular":
            title = "推しロールアナリティクス - 人気ロールランキング"
            
            top_roles = sorted(self.analytics_data.get("role_stats", {}).items(), 
                              key=lambda x: x[1].get("count", 0), 
                              reverse=True)[:count]
            
            description = f"### 人気ロールランキング (トップ{len(top_roles)})\n\n"
            for i, (role_name, stats) in enumerate(top_roles):
                description += f"### {i+1}. {role_name}\n"
                description += f"**選択回数**: {stats.get('count', 0)}回\n"
                description += f"**最終選択**: {stats.get('last_selected', '不明')}\n\n"
                
        elif type == "recent":
            title = "推しロールアナリティクス - 最近のアクティビティ"
            
            recent_events = self.analytics_data.get("role_assignments", [])[-count:]
            recent_events.reverse()
            
            description = f"### 最近の{len(recent_events)}件のアクティビティ\n\n"
            for event in recent_events:
                event_time = event.get("timestamp", "不明")
                user_name = event.get("user_name", "不明")
                event_type = event.get("event_type", "不明")
                roles_text = ", ".join([r.get("name", "不明") for r in event.get("roles", [])])
                
                description += f"### {event_time}\n"
                description += f"**{user_name}** が {event_type} **{roles_text}**\n\n"
                
        elif type == "users":
            title = "推しロールアナリティクス - アクティブユーザー"
            
            top_users = sorted(self.analytics_data.get("user_stats", {}).items(), 
                              key=lambda x: x[1].get("total_changes", 0), 
                              reverse=True)[:count]
            
            description = f"### アクティブユーザーランキング (トップ{len(top_users)})\n\n"
            for i, (user_id, stats) in enumerate(top_users):
                user_name = stats.get("name", "不明")
                description += f"### {i+1}. {user_name}\n"
                description += f"**変更回数**: {stats.get('total_changes', 0)}回\n"
                description += f"**最終変更**: {stats.get('last_change', '不明')}\n\n"
                
        elif type == "inactive":
            title = "推しロールアナリティクス - 非アクティブロール"
            
            bottom_roles = sorted(self.analytics_data.get("role_stats", {}).items(), 
                                 key=lambda x: x[1].get("count", 0))[:count]
            
            description = f"### 非アクティブロールランキング (下位{len(bottom_roles)})\n\n"
            for i, (role_name, stats) in enumerate(bottom_roles):
                description += f"### {i+1}. {role_name}\n"
                description += f"**選択回数**: {stats.get('count', 0)}回\n"
                description += f"**最終選択**: {stats.get('last_selected', '不明')}\n\n"
        
        if isinstance(interaction, discord.Interaction):
            # CV2形式のコンポーネントを作成
            rainbow_colors = [
                15158332,
                16754470,
                15844367,
                5763719,
                3447003,
                7506394,
                10181046
            ]
            accent_color = random.choice(rainbow_colors)
            
            # APIリクエスト用のコンポーネント用意
            container_components = []
            
            # タイトルと説明を追加
            container_components.append({
                "type": 10,  # TEXT_DISPLAY
                "content": f"# {title}"
            })
            
            container_components.append({
                "type": 10,  # TEXT_DISPLAY
                "content": "推しロールのアナリティクスデータです。"
            })
            
            # 区切り線を追加
            container_components.append({
                "type": 14,  # SEPARATOR
                "divider": True,
                "spacing": 1
            })
            
            # アナリティクスタイプに応じたデータを表示
            if type == "popular":
                # sort_byパラメータに応じてソート関数を定義
                def get_sort_key(x):
                    if sort_by == "members":
                        return x[1].get("current_members", 0)
                    else:  # sort_by == "count"
                        return x[1].get("count", 0)
                top_roles = sorted(self.analytics_data.get("role_stats", {}).items(), 
                                   key=get_sort_key, 
                                   reverse=True)[:count]
                
                container_components.append({
                    "type": 10,  # TEXT_DISPLAY
                    "content": f"## 人気ロールランキング (トップ{len(top_roles)}) - {sort_text}"
                })
                
                for i, (role_name, stats) in enumerate(top_roles):
                    count_value = stats.get('count', 0)
                    current_members = stats.get('current_members', 0)
                    container_components.append({
                        "type": 10,  # TEXT_DISPLAY
                        "content": f"{i+1}. {role_name}\n"
                        f"　　選択回数: {count_value}回 | 現在のメンバー数: {current_members}人"
                    })
                    
                    # 各エントリ間に適切なスペースを設定
                    if i < len(top_roles) - 1:
                        container_components.append({
                            "type": 14,  # SEPARATOR
                            "divider": False,
                            "spacing": 1
                        })
            
            elif type == "inactive":
                # sort_byパラメータに応じてソート関数を定義
                def get_sort_key(x):
                    if sort_by == "members":
                        return x[1].get("current_members", 0)
                    else:  # sort_by == "count"
                        return x[1].get("count", 0)
                        
                bottom_roles = sorted(self.analytics_data.get("role_stats", {}).items(), 
                                      key=get_sort_key)[:count]
                
                container_components.append({
                    "type": 10,  # TEXT_DISPLAY
                    "content": f"## 非アクティブロールランキング (下位{len(bottom_roles)}) - {sort_text}"
                })
                
                for i, (role_name, stats) in enumerate(bottom_roles):
                    count_value = stats.get('count', 0)
                    current_members = stats.get('current_members', 0)
                    container_components.append({
                        "type": 10,  # TEXT_DISPLAY
                        "content": f"{i+1}. {role_name}\n"
                        f"　　選択回数: {count_value}回 | 現在のメンバー数: {current_members}人"
                    })
                    
                    if i < len(bottom_roles) - 1:
                        container_components.append({
                            "type": 14,  # SEPARATOR
                            "divider": False,
                            "spacing": 1
                        })
            
            elif type == "users":
                top_users = sorted(self.analytics_data.get("user_stats", {}).items(), 
                                  key=lambda x: x[1].get("total_changes", 0), 
                                  reverse=True)[:count]
                
                container_components.append({
                    "type": 10,  # TEXT_DISPLAY
                    "content": f"## アクティブユーザーランキング (トップ{len(top_users)})"
                })
                
                for i, (user_id, stats) in enumerate(top_users):
                    user_name = stats.get("name", "不明")
                    total_changes = stats.get("total_changes", 0)
                    last_change = stats.get("last_change", "不明")
                    container_components.append({
                        "type": 10,  # TEXT_DISPLAY
                        "content": f"{i+1}. {user_name}\n"
                        f"　　変更回数: {total_changes}回 | 最終変更: {last_change}"
                    })
                    
                    if i < len(top_users) - 1:
                        container_components.append({
                            "type": 14,  # SEPARATOR
                            "divider": False,
                            "spacing": 1
                        })
            
            # ここにボタンを追加
            container_components.append({
                "type": 14,  # SEPARATOR
                "divider": True,
                "spacing": 2
            })
            
            container_components.append({
                "type": 1,  # ACTION_ROW
                "components": [
                    {
                        "type": 2,  # BUTTON
                        "style": 2,  # SECONDARY
                        "label": "閉じる",
                        "custom_id": "close_analytics"
                    }
                ]
            })
            
            # 最終更新時間を整形して表示
            last_updated = self.analytics_data.get('last_updated', '不明')
            
            # ISO形式の日付を日本語形式に整形
            if last_updated != '不明' and 'T' in last_updated:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(last_updated.replace('Z', '+00:00'))
                    # 日本時間に変換 (9時間追加)
                    dt = dt.astimezone()
                    formatted_date = dt.strftime('%Y年%m月%d日 %H:%M:%S')
                    last_updated = formatted_date
                except Exception as e:
                    logger.error(f"日付変換エラー: {e}")
            
            # 区切り線
            container_components.append({
                "type": 14,  # SEPARATOR
                "divider": True,
                "spacing": 1
            })
            
            # フッターを追加
            container_components.append({
                "type": 10,  # TEXT_DISPLAY
                "content": f"*最終更新: {last_updated}*"
            })
            
            # カテゴリー切り替えボタンを追加
            category_buttons = [
                {
                    "type": 2,  # BUTTON
                    "style": 2,  # SECONDARY
                    "label": "サマリー",
                    "custom_id": f"analytics_switch:summary:{count}:{sort_by}"
                },
                {
                    "type": 2,  # BUTTON
                    "style": 2,  # SECONDARY
                    "label": "人気ロール",
                    "custom_id": f"analytics_switch:popular:{count}:{sort_by}"
                },
                {
                    "type": 2,  # BUTTON
                    "style": 2,  # SECONDARY
                    "label": "非アクティブロール",
                    "custom_id": f"analytics_switch:inactive:{count}:{sort_by}"
                },
                {
                    "type": 2,  # BUTTON
                    "style": 2,  # SECONDARY
                    "label": "アクティブユーザー",
                    "custom_id": f"analytics_switch:users:{count}:{sort_by}"
                }
            ]
            
            # 現在のタイプのボタンをハイライト
            for button in category_buttons:
                if ("サマリー" in button["label"] and type == "summary") or \
                   ("人気ロール" in button["label"] and type == "popular") or \
                   ("非アクティブロール" in button["label"] and type == "inactive") or \
                   ("アクティブユーザー" in button["label"] and type == "users"):
                    button["style"] = 1  # PRIMARY

            # ソート切り替えボタン（人気と非アクティブロールのみ表示）
            sort_row = None
            if type in ["popular", "inactive"]:
                sort_buttons = [
                    {
                        "type": 2,  # BUTTON
                        "style": 2 if sort_by != "count" else 1,  # SECONDARY or PRIMARY
                        "label": "選択回数順",
                        "custom_id": f"analytics_switch:{type}:{count}:count"
                    },
                    {
                        "type": 2,  # BUTTON
                        "style": 2 if sort_by != "members" else 1,  # SECONDARY or PRIMARY
                        "label": "メンバー数順",
                        "custom_id": f"analytics_switch:{type}:{count}:members"
                    }
                ]
                sort_row = {
                    "type": 1,  # ACTION_ROW
                    "components": sort_buttons
                }
            
            # カテゴリーボタン行
            category_row = {
                "type": 1,  # ACTION_ROW
                "components": category_buttons
            }
            
            # CV2コンテナを作成
            container = {
                "type": 17,  # CONTAINER
                "accent_color": accent_color,
                "components": container_components
            }
            
            # ペイロードにコンテナを追加
            components = [container]
            
            # ボタン行を追加
            if sort_row:
                components.append(sort_row)
            components.append(category_row)
            
            # httpxを使用して直接APIにリクエストを送信
            url = f"https://discord.com/api/v10/webhooks/{self.bot.user.id}/{interaction.token}/messages/@original"
            
            headers = {
                "Authorization": f"Bot {self.bot.http.token}",
                "Content-Type": "application/json"
            }
            
            # CV2フラグを含むペイロード
            payload = {
                "components": components,
                "flags": 32768 | 64  # IS_COMPONENTS_V2 | EPHEMERAL
            }
            
            try:
                # 一時的なhttpx.AsyncClientを使用
                async with httpx.AsyncClient() as client:
                    response = await client.patch(url, json=payload, headers=headers)
                    response.raise_for_status()
                    logger.info(f"アナリティクスデータのCV2表示に成功: {type}")
            except Exception as e:
                logger.error(f"CV2形式での表示中にエラー発生: {e}")
                # エラー時の代替手段を試みる
                
                # エラーハンドリング：よりシンプルな方法で再試行
                try:
                    # 簡素なメッセージで再試行
                    simple_view = discord.ui.View()
                    simple_view.add_item(discord.ui.Button(style=discord.ButtonStyle.secondary, label="閉じる", custom_id="close_analytics"))
                    simple_message = f"# {title}\n\nアナリティクスデータを取得しました。\n詳細はコマンドを実行し直してご確認ください。"
                    await interaction.followup.send(content=simple_message, ephemeral=True, view=simple_view)
                    logger.info(f"アナリティクスデータのシンプル表示に成功: {type}")
                except Exception as final_e:
                    logger.error(f"最終的なフォールバックでもエラー発生: {final_e}")
                    # 最終的なフォールバックとして、エラーメッセージだけを送信
                    await interaction.followup.send("アナリティクスデータの表示中にエラーが発生しました。", ephemeral=True)
        else:
            await interaction.channel.send(f"# {title}\n\n{description}")
        
# --- CV2形式のメッセージ送信ユーティリティ ---
class CV2MessageSender:
    def __init__(self, bot):
        self.bot = bot
        self.api_version = "v10"
        self.base_url = f"https://discord.com/api/{self.api_version}"
        self.client = httpx.AsyncClient(timeout=30.0)
        self.analytics_callback = None
        
        self.oshi_categories = [
            {
                "name": "JP 0期〜2期生",
                "emoji": "🌟",
                "description": "0期〜2期生の推しロールはこちら",
                "value": "oshi_jp_0_2",
                "roles": {
                    "そらとも🐻‍💿": 1092330136617107476,
                    "ろぼさー🤖": 1092330955533987911,
                    "星詠み☄️": 1092331097519558729,
                    "35p🌸": 1092331216256127078,
                    "開拓者⚒️": 1092331366768709632,
                    "かぷ民🌟": 1092334343487230013,
                    "ロゼ隊🍎": 1092334411967639564,
                    "はあとん❤": 1092334442359566422,
                    "まつりす🏮": 1092334488404639795,
                    "すこん部🌽": 1092334542620201052,
                    "塩っ子🌙": 1092334644164304916,
                    "百鬼組😈": 1092334720127348748,
                    "ちょこめいと💋": 1092334776683339876,
                    "あくあクルー⚓": 1092334611444551752,
                    "スバ友🚑": 1092334841179164753
                }
            },
            {
                "name": "JP Gamers〜3期生",
                "emoji": "🎮",
                "description": "ゲーマーズ〜3期生の推しロールはこちら",
                "value": "oshi_jp_gamer_3",
                "roles": {
                    "ミオファ🌲": 1092334904827719770,
                    "おにぎりゃー🍙": 1092334981176639518,
                    "ころねすきー🥐": 1092344624141574144,
                    "野うさぎ同盟👯‍♀️": 1092344689274929242,
                    "ふぁんでっと🦋": 1092344741858918451,
                    "エルフレ🔥": 1092344824729968701,
                    "白銀聖騎士団⚔️": 1092345001259843676,
                    "宝鐘の一味🏴‍☠️": 1092345067844423700
                }
            },
            {
                "name": "JP 4期〜5期生",
                "emoji": "✨",
                "description": "4期生〜5期生の推しロールはこちら",
                "value": "oshi_jp_4_5",
                "roles": {
                    "へい民💫": 1092345135444000869,
                    "桐生会🐉": 1092345206139015228,
                    "わためいと🐑": 1092345283024785441,
                    "常闇眷属👾": 1092345352406978600,
                    "ルーナイト🍬": 1092345422888050810,
                    "雪民☃": 1092345507717849129,
                    "ねっ子🍑🥟": 1092345581650841630,
                    "SSRB♌": 1092345633114951680,
                    "おまる座🎪": 1092345861943591052
                }
            },
            {
                "name": "JP 秘密結社holoX",
                "emoji": "🦊",
                "description": "holoXの推しロールはこちら",
                "value": "oshi_jp_holox",
                "roles": {
                    "ぷらすめいと🛸💜": 1092345928813400135,
                    "ルイ友🥀": 1092346020437962842,
                    "こよりの助手くん🧪": 1092346113060773969,
                    "飼育員🎣": 1092346162259959849,
                    "かざま隊🍃": 1092346259303571496
                }
            },
            {
                "name": "ReGLOSS",
                "emoji": "🎭",
                "description": "ReGLOSSの推しロールはこちら",
                "value": "oshi_regloss",
                "roles": {
                    "読者🖋️": 1148152861830692894,
                    "でん同士🐚": 1148152923260473384,
                    "音の勢🎹✨": 1148152983234822216,
                    "秘書見習い🌃": 1148153052705067028,
                    "真っす組🐧⚡️": 1148153107407192084
                }
            },
            {
                "name": "FlowGlow",
                "emoji": "⚖️",
                "description": "FlowGlowの推しロールはこちら",
                "value": "oshi_flowglow",
                "roles": {
                    "響咲連合🎤👑": 1374947544982880357,
                    "ニコ担😊🐅": 1374947583734190150,
                    "すうりす💬🔁💙": 1374947951931035791,
                    "ちはニック🎧🔧": 1374948001931595826,
                    "vivid💅✨": 1374948068314841128,
                }
            },
            {
                "name": "その他",
                "emoji": "👑",
                "description": "スタッフやその他の特別なロール",
                "value": "oshi_others",
                "roles": {
                    "YAGOO👨‍🎓": 1093018532519870534,
                    "えーちゃん👓": 1093019394172522517,
                    "春先のどか📝": 1093020217757671507
                }
            },
            {
                "name": "hololive EN",
                "emoji": "🌎",
                "description": "hololive ENの推しロールはこちら",
                "value": "oshi_en",
                "roles": {
                    "Dead Beats💀": 1116480201229090956,
                    "kfp🐔": 1116480437213200514,
                    "tentacult🐙": 1116480505077055578,
                    "chumbuds🔱": 1116480594562519131,
                    "teamates🔎": 1116480645598818424,
                    "IRyStocrats💎": 1116480647758884925,
                    "Saplings🌿": 1116481163125608519,
                    "Kronies⏳": 1116481236928569485,
                    "Hoomans🪶": 1116481302426816522,
                    "Brats🎲": 1116481368378069082,
                    "Novelites👁️‍🗨️": 1133609378214330398,
                    "Pebbles🗿": 1133609488138637373,
                    "Jailbirds 🎼": 1133609781412761631,
                    "RUFFIANS🐾": 1133610126260060302
                }
            },
            {
              "name": "Justice",
              "emoji": "⚖️",
              "description": "Justiceの推しロールはこちら",
              "value": "oshi_justice",
              "roles": {
                "Rosarians💄": 1374947341416665100,
                "Gremurins👧": 1374947385645731910,
                "Otomos🍵": 1374947434911891528,
                "Chattino🐱": 1374947483054248107,
              }
            },
            {
                "name": "hololive ID",
                "emoji": "🌺",
                "description": "IDの推しロールはこちら",
                "value": "oshi_id",
                "roles": {
                    "Risuners🐿": 1116481367501447288,
                    "Moonafic🔮": 1116481830732955749,
                    "IOFORIA🎨": 1116481890577301565,
                    "ZOMRADE🧟‍♀️": 1116481893349728256,
                    "MelFriends🍂": 1116481895748862004,
                    "MERAKyats🦚": 1116481898768769034,
                    "Zecretary📜": 1116481901415374928,
                    "Pemaloe🔨": 1116481903864844408,
                    "Kobokerz☔": 1116481906356261115
                }
            }
        ]
        
    async def send_role_panel(self, channel_id, image_data=None, image_url=None, text=None):
        """
        CV2形式の推しロールパネルを送信する
        
        Parameters:
        -----------
        channel_id : int
            メッセージを送信するチャンネルID
        image_data : bytes, optional
            添付画像のバイナリデータ
        image_url : str, optional
            画像のURL（直接参照されます）
        text : str, optional
            追加のプレーンテキスト（独立したコンポーネントとして表示）
        """
        logger.info(f"CV2形式の推しロールパネルを送信: チャンネルID={channel_id}")
        
        endpoint = f"{self.base_url}/channels/{channel_id}/messages"
        
        rainbow_colors = [
            15158332,
            16754470,
            15844367,
            5763719,
            3447003,
            7506394,
            10181046
        ]
        
        accent_color = random.choice(rainbow_colors)
        
        text_component = None
        if text:
            text_component = {
                "type": 10,
                "content": text
            }
        
        container_components = []
        
        attachments = []
        
        if image_data:
            attachment_id = str(uuid.uuid4())
            filename = f"oshi_panel_{attachment_id}.png"
            
            attachments = [{
                "id": "0",
                "filename": filename
            }]
            
            container_components.append({
                "type": 12,
                "items": [
                    {
                        "media": {"url": f"attachment://{filename}"}
                    }
                ]
            })
        elif image_url:
            container_components.append({
                "type": 12,
                "items": [
                    {
                        "media": {"url": image_url}
                    }
                ]
            })
        
        container_components.append({
            "type": 10,
            "content": "## 🎭 推しメンバーロール選択"
        })
        
        description_text = "応援しているメンバーのロールを選択して、あなたの推しをアピールしましょう！\n"\
                          "以下のドロップダウンメニューからカテゴリを選ぶと、そのカテゴリ内のメンバーロールが表示されます。"
            
        container_components.append({
            "type": 10,
            "content": description_text
        })
        
        container_components.append({
            "type": 14,
            "divider": True,
            "spacing": 1
        })
        
        options = []
        for category in self.oshi_categories:
            options.append({
                "label": category["name"],
                "value": category["value"],
                "description": category["description"],
                "emoji": {"name": category["emoji"]}
            })
        
        container_components.append({
            "type": 1,
            "components": [
                {
                    "type": 3,
                    "custom_id": "oshi_select",
                    "placeholder": "カテゴリを選択",
                    "options": options,
                    "min_values": 1,
                    "max_values": 1
                }
            ]
        })
        
        container_components.append({
            "type": 10,
            "content": "*※カテゴリを選択すると、詳細なメンバー選択画面が表示されます*"
        })
        
        container_components.append({
            "type": 14,
            "divider": True,
            "spacing": 2
        })
        
        container_components.append({
            "type": 10,
            "content": "### 言語選択 / Language / 언어 / 语言"
        })
        
        container_components.append({
            "type": 10,
            "content": "If you need a language other than Japanese, please click one of the buttons below👇\n" +
                     "한국어/중국어 안내가 필요하신 분은 아래 버튼을 눌러주세요👇\n" +
                     "如需其他语言的说明，请点击下方按钮👇"
        })
        
        container_components.append({
            "type": 1,
            "components": [
                {
                    "type": 2,
                    "style": 1,
                    "label": "English",
                    "custom_id": "oshi_english",
                    "emoji": {"name": "🇬🇧"}
                },
                {
                    "type": 2,
                    "style": 1,
                    "label": "한국어",
                    "custom_id": "oshi_korean",
                    "emoji": {"name": "🇰🇷"}
                },
                {
                    "type": 2,
                    "style": 1,
                    "label": "中文",
                    "custom_id": "oshi_chinese",
                    "emoji": {"name": "🇨🇳"}
                }
            ]
        })
        
        container = {
            "type": 17,
            "accent_color": accent_color,
            "components": container_components
        }
        
        components = []
        if text_component:
            components.append(text_component)
        components.append(container)
        
        payload = {
            "flags": 32768,
            "components": components
        }
        
        if attachments:
            payload["attachments"] = attachments
        
        headers = {
            "Authorization": f"Bot {self.bot.http.token}",
            "Content-Type": "application/json"
        }
        
        try:
            if image_data:
                files = {
                    "files[0]": (attachments[0]["filename"], image_data, "image/png")
                }
                
                form = {"payload_json": json.dumps(payload)}
                
                custom_headers = {
                    "Authorization": f"Bot {self.bot.http.token}"
                }
                
                logger.debug(f"送信するフォームデータ: {form}")
                logger.debug(f"送信するファイル: {attachments[0]['filename']}")
                
                response = await self.client.post(
                    endpoint,
                    headers=custom_headers,
                    data=form,
                    files=files
                )
            else:
                response = await self.client.post(
                    endpoint,
                    headers=headers,
                    json=payload
                )
            
            if response.status_code in (200, 201):
                logger.info(f"CV2推しロールパネル送信成功: チャンネルID={channel_id}")
                return response.json()
            else:
                logger.error(f"CV2推しロールパネル送信失敗: ステータス={response.status_code}, エラー={response.text}")
                return None
        except Exception as e:
            logger.error(f"CV2推しロールパネル送信中にエラー: {e}\n{traceback.format_exc()}")
            return None

    async def handle_oshi_select(self, interaction):
        """
        推しロール選択メニューのインタラクション処理
        
        Parameters:
        -----------
        interaction : discord.Interaction
            セレクトメニュー選択時のインタラクション
        """
        values = interaction.data.get("values", [])
        if not values:
            return
            
        category_value = values[0]
        
        selected_category = None
        for category in self.oshi_categories:
            if category["value"] == category_value:
                selected_category = category
                break
                
        if not selected_category:
            await interaction.response.send_message("カテゴリが見つかりませんでした", ephemeral=True)
            return
        
        rainbow_colors = [
            15158332,
            16754470,
            15844367,
            5763719,
            3447003,
            7506394,
            10181046
        ]
        
        accent_color = random.choice(rainbow_colors)
        
        try:
            endpoint = f"{self.base_url}/interactions/{interaction.id}/{interaction.token}/callback"
            
            container_components = []
            
            container_components.append({
                "type": 10,
                "content": f"## {selected_category['emoji']} {selected_category['name']}のメンバーロール"
            })
            
            container_components.append({
                "type": 10,
                "content": f"**{selected_category['description']}**\n\n推しメンバーのロールを選択してください："
            })
            
            container_components.append({
                "type": 14,
                "divider": True,
                "spacing": 1
            })
            
            category_options = []
            for category in self.oshi_categories:
                is_selected = category["value"] == category_value
                category_options.append({
                    "label": category["name"],
                    "value": category["value"],
                    "description": category["description"],
                    "emoji": {"name": category["emoji"]},
                    "default": is_selected
                })
            
            container_components.append({
                "type": 1,
                "components": [
                    {
                        "type": 3,
                        "custom_id": "oshi_select",
                        "placeholder": "カテゴリを選択",
                        "options": category_options,
                        "min_values": 1,
                        "max_values": 1
                    }
                ]
            })
            
            member_options = []
            user_roles = [role.id for role in interaction.user.roles]
            
            for member_name, role_id in selected_category["roles"].items():
                role = interaction.guild.get_role(role_id)
                
                if role:
                    has_role = role_id in user_roles
                    
                    emoji_obj = None
                    
                    if role.icon:
                        logger.info(f"ロール {role.name} のアイコンURL: {role.icon.url}")
                        
                        emoji_data = self.bot.get_cog("OshiRolePanel").role_emoji_mapping.get(str(role_id), "")
                        
                        if emoji_data:
                            # DBからの新しい形式: {"emoji_id": "id", "emoji_name": "name", "animated": bool}
                            if isinstance(emoji_data, dict) and "emoji_id" in emoji_data and emoji_data["emoji_id"]:
                                emoji_obj = {
                                    "id": emoji_data["emoji_id"],
                                    "name": emoji_data["emoji_name"]
                                }
                                if emoji_data.get("animated", False):
                                    emoji_obj["animated"] = True
                            # 旧形式の文字列形式もサポート: <:name:id>
                            elif isinstance(emoji_data, dict) and "emoji" in emoji_data:
                                emoji_str = emoji_data["emoji"]
                                if isinstance(emoji_str, str) and emoji_str.startswith("<") and emoji_str.endswith(">"): 
                                    emoji_parts = emoji_str.strip("<>").split(":")
                                    if len(emoji_parts) == 3:
                                        emoji_obj = {
                                            "id": emoji_parts[2],
                                            "name": emoji_parts[1]
                                        }
                                        if emoji_parts[0] == "a":
                                            emoji_obj["animated"] = True
                            # 直接の文字列形式: <:name:id>
                            elif isinstance(emoji_data, str) and emoji_data.startswith("<") and emoji_data.endswith(">"): 
                                emoji_parts = emoji_data.strip("<>").split(":")
                                if len(emoji_parts) == 3:
                                    emoji_obj = {
                                        "id": emoji_parts[2],
                                        "name": emoji_parts[1]
                                    }
                                    if emoji_parts[0] == "a":
                                        emoji_obj["animated"] = True
                    else:
                        emoji_data = self.bot.get_cog("OshiRolePanel").role_emoji_mapping.get(str(role_id), "")
                        
                        if emoji_data:
                            # DBからの新しい形式: {"emoji_id": "id", "emoji_name": "name", "animated": bool}
                            if isinstance(emoji_data, dict) and "emoji_id" in emoji_data and emoji_data["emoji_id"]:
                                emoji_obj = {
                                    "id": emoji_data["emoji_id"],
                                    "name": emoji_data["emoji_name"]
                                }
                                if emoji_data.get("animated", False):
                                    emoji_obj["animated"] = True
                            # 旧形式の文字列形式もサポート: <:name:id>
                            elif isinstance(emoji_data, dict) and "emoji" in emoji_data:
                                emoji_str = emoji_data["emoji"]
                                if isinstance(emoji_str, str) and emoji_str.startswith("<") and emoji_str.endswith(">"): 
                                    emoji_parts = emoji_str.strip("<>").split(":")
                                    if len(emoji_parts) == 3:
                                        emoji_obj = {
                                            "id": emoji_parts[2],
                                            "name": emoji_parts[1]
                                        }
                                        if emoji_parts[0] == "a":
                                            emoji_obj["animated"] = True
                            # 直接の文字列形式: <:name:id>
                            elif isinstance(emoji_data, str) and emoji_data.startswith("<") and emoji_data.endswith(">"): 
                                emoji_parts = emoji_data.strip("<>").split(":")
                                if len(emoji_parts) == 3:
                                    emoji_obj = {
                                        "id": emoji_parts[2],
                                        "name": emoji_parts[1]
                                    }
                                    if emoji_parts[0] == "a":
                                        emoji_obj["animated"] = True
                    
                    option = {
                        "label": member_name,
                        "value": f"role_{role_id}",
                        "default": has_role
                    }
                    
                    if role.icon:
                        option["description"] = "左のアイコンがつきます"
                    
                    if emoji_obj and "id" in emoji_obj:
                        option["emoji"] = emoji_obj
                    
                    member_options.append(option)
            
            member_select_custom_id = f"member_select:{selected_category['value']}"
            
            if member_options:
                container_components.append({
                    "type": 1,
                    "components": [
                        {
                            "type": 3,
                            "custom_id": member_select_custom_id,
                            "placeholder": "推しメンバーを選択（複数可）",
                            "options": member_options,
                            "min_values": 0,
                            "max_values": len(member_options)
                        }
                    ]
                })
            else:
                container_components.append({
                    "type": 10,
                    "content": "*このカテゴリには選択可能なロールがありません*"
                })
            
            container_components.append({
                "type": 14,
                "divider": True,
                "spacing": 1
            })
            
            container_components.append({
                "type": 10,
                "content": "*※セレクトメニューから推しメンバーを選択すると、対応するロールが付与または解除されます。\n複数選択が可能です。選択済みのものを外すと解除されます。*"
            })
            
            container_components.append({
                "type": 14,
                "divider": True,
                "spacing": 2
            })
            
            container_components.append({
                "type": 10,
                "content": "### 言語選択 / Language / 언어 / 语言"
            })
            
            container_components.append({
                "type": 10,
                "content": "If you need a language other than Japanese, please click one of the buttons below👇\n" +
                         "한국어/중국어 안내가 필요하신 분은 아래 버튼 중에서 선택해주세요👇"
            })
            
            container_components.append({
                "type": 1,
                "components": [
                    {
                        "type": 2,
                        "style": 1,
                        "label": "English",
                        "custom_id": "oshi_english",
                        "emoji": {"name": "🇬🇧"}
                    },
                    {
                        "type": 2,
                        "style": 1,
                        "label": "한국어",
                        "custom_id": "oshi_korean",
                        "emoji": {"name": "🇰🇷"}
                    },
                    {
                        "type": 2,
                        "style": 1,
                        "label": "中文",
                        "custom_id": "oshi_chinese",
                        "emoji": {"name": "🇨🇳"}
                    }
                ]
            })
            
            container = {
                "type": 17,
                "accent_color": accent_color,
                "components": container_components
            }
            
            components = [container]
            
            response_data = {
                "type": 4,
                "data": {
                    "flags": 32768 | 64,
                    "components": components
                }
            }
            
            headers = {
                "Authorization": f"Bot {self.bot.http.token}",
                "Content-Type": "application/json"
            }
            
            response = await self.client.post(
                endpoint,
                headers=headers,
                json=response_data
            )
            
            if response.status_code in (200, 201, 204):
                logger.info(f"CV2推しロール選択応答成功: カテゴリ={category_value}")
            else:
                logger.error(f"CV2推しロール選択応答失敗: ステータス={response.status_code}, エラー={response.text}")
        except Exception as e:
            logger.error(f"CV2推しロール選択応答中にエラー: {e}\n{traceback.format_exc()}")
    
    async def handle_role_button(self, interaction):
        """
        ロールボタン押下時の処理
        """
        custom_id = interaction.data.get("custom_id", "")
        role_id = int(custom_id.split("_")[1])
        
        user = interaction.user
        guild = interaction.guild
        role = guild.get_role(role_id)
        
        if not role:
            await interaction.response.send_message(f"ロールが見つかりません (ID: {role_id})", ephemeral=True)
            logger.error(f"ロールが見つかりません: {role_id}, サーバー: {guild.name}")
            return
            
        try:
            if role in user.roles:
                await user.remove_roles(role)
                emoji = self.bot.get_cog("OshiRolePanel").role_emoji_mapping.get(str(role_id), "")
                emoji_display = f"{emoji} " if emoji else ""
                await interaction.response.send_message(f"{emoji_display}**{role.name}**のロールを解除しました", ephemeral=True)
                logger.info(f"ロール解除: {role.name}, ユーザー: {user.name}")
            else:
                await user.add_roles(role)
                emoji = self.bot.get_cog("OshiRolePanel").role_emoji_mapping.get(str(role_id), "")
                emoji_display = f"{emoji} " if emoji else ""
                await interaction.response.send_message(f"{emoji_display}**{role.name}**のロールを付与しました", ephemeral=True)
                logger.info(f"ロール付与: {role.name}, ユーザー: {user.name}")
        except discord.Forbidden:
            await interaction.response.send_message("ロールの変更権限がありません", ephemeral=True)
            logger.error(f"ロール変更権限なし: {role.name}, ユーザー: {user.name}")
        except Exception as e:
            await interaction.response.send_message("ロールの変更中にエラーが発生しました", ephemeral=True)
            logger.error(f"ロール変更中にエラー: {e}\n{traceback.format_exc()}")
            
    async def handle_oshi_language_button(self, interaction):
        """
        言語選択ボタンが押された時の処理
        
        Parameters:
        -----------
        interaction : discord.Interaction
            ボタン押下時のインタラクション
        """
        custom_id = interaction.data.get("custom_id", "")
        logger.info(f"言語選択ボタン押下: {custom_id}, ユーザー={interaction.user.display_name}({interaction.user.id})")
        
        rainbow_colors = [
            15158332,
            16754470,
            15844367,
            5763719,
            3447003,
            7506394,
            10181046
        ]
        
        accent_color = random.choice(rainbow_colors)
        
        if custom_id == "oshi_english":
            title = "🎭 Oshi Member Role Selection"
            description = "Select the roles of the members you support to show off your oshi!\n"\
                         "Choose a category from the dropdown menu below to see member roles in that category."
            notice = "*※When you select a category, a detailed member selection screen will be displayed*"
            category_placeholder = "Select a category"
            language_header = "### Language Selection / 言語選択 / 언어 / 语言"
            language_description = "If you prefer a different language, please select from the buttons below👇"
            
        elif custom_id == "oshi_korean":
            title = "🎭 추천 멤버 역할 선택"
            description = "응원하는 멤버의 역할을 선택하여 당신의 추천을 어필하세요!\n"\
                         "아래 드롭다운 메뉴에서 카테고리를 선택하면 해당 카테고리의 멤버 역할이 표시됩니다."
            notice = "*※카테고리를 선택하면 상세한 멤버 선택 화면이 표시됩니다*"
            category_placeholder = "카테고리 선택"
            language_header = "### 언어 선택 / Language / 言語選択 / 语言"
            language_description = "다른 언어를 원하시면 아래 버튼 중에서 선택해주세요👇"
            
        elif custom_id == "oshi_chinese":
            title = "🎭 推成员角色选择"
            description = "选择你支持的成员角色来展示你的推!\n"\
                         "从下面的下拉菜单中选择一个类别，查看该类别中的成员角色。"
            notice = "*※选择类别后，将显示详细的成员选择界面*"
            category_placeholder = "选择类别"
            language_header = "### 语言选择 / Language / 言語選択 / 언어"
            language_description = "如果您需要其他语言，请点击下方按钮👇"
            
        elif custom_id == "oshi_japanese":
            title = "🎭 推しメンバーロール選択"
            description = "応援しているメンバーのロールを選択して、あなたの推しをアピールしましょう！\n"\
                         "以下のドロップダウンメニューからカテゴリを選ぶと、そのカテゴリ内のメンバーロールが表示されます。"
            notice = "*※カテゴリを選択すると、詳細なメンバー選択画面が表示されます*"
            category_placeholder = "カテゴリを選択"
            language_header = "### 言語選択 / Language / 언어 / 语言"
            language_description = "他の言語が必要な場合は、以下のボタンから選択してください👇"
        else:
            logger.warning(f"未知の言語ボタンID: {custom_id}")
            return
            
        self.analytics_callback = None
        
        try:
            endpoint = f"{self.base_url}/interactions/{interaction.id}/{interaction.token}/callback"
            
            container_components = []
            
            container_components.append({
                "type": 10,
                "content": f"## {title}"
            })
            
            container_components.append({
                "type": 10,
                "content": description
            })
            
            container_components.append({
                "type": 14,
                "divider": True,
                "spacing": 1
            })
            
            options = []
            for category in self.oshi_categories:
                options.append({
                    "label": category["name"],
                    "value": category["value"],
                    "description": category["description"],
                    "emoji": {"name": category["emoji"]}
                })
            
            container_components.append({
                "type": 1,
                "components": [
                    {
                        "type": 3,
                        "custom_id": "oshi_select",
                        "placeholder": category_placeholder,
                        "options": options,
                        "min_values": 1,
                        "max_values": 1
                    }
                ]
            })
            
            container_components.append({
                "type": 10,
                "content": notice
            })
            
            container_components.append({
                "type": 14,
                "divider": True,
                "spacing": 2
            })
            
            container_components.append({
                "type": 10,
                "content": language_header
            })
            
            container_components.append({
                "type": 10,
                "content": language_description
            })
            
            container_components.append({
                "type": 1,
                "components": [
                    {
                        "type": 2,
                        "style": 1,
                        "label": "日本語",
                        "custom_id": "oshi_japanese",
                        "emoji": {"name": "🇯🇵"}
                    },
                    {
                        "type": 2,
                        "style": 1,
                        "label": "English",
                        "custom_id": "oshi_english",
                        "emoji": {"name": "🇬🇧"},
                        "disabled": custom_id == "oshi_english"
                    },
                    {
                        "type": 2,
                        "style": 1,
                        "label": "한국어",
                        "custom_id": "oshi_korean",
                        "emoji": {"name": "🇰🇷"},
                        "disabled": custom_id == "oshi_korean"
                    },
                    {
                        "type": 2,
                        "style": 1,
                        "label": "中文",
                        "custom_id": "oshi_chinese",
                        "emoji": {"name": "🇨🇳"},
                        "disabled": custom_id == "oshi_chinese"
                    }
                ]
            })
            
            container = {
                "type": 17,
                "accent_color": accent_color,
                "components": container_components
            }
            
            components = [container]
            
            response_data = {
                "type": 4,
                "data": {
                    "flags": 32768 | 64,
                    "components": components
                }
            }
            
            headers = {
                "Authorization": f"Bot {self.bot.http.token}",
                "Content-Type": "application/json"
            }
            
            response = await self.client.post(
                endpoint,
                headers=headers,
                json=response_data
            )
            
            if response.status_code in (200, 201, 204):
                logger.info(f"CV2言語選択応答成功: 言語={custom_id}")
            else:
                logger.error(f"CV2言語選択応答失敗: ステータス={response.status_code}, エラー={response.text}")
        except Exception as e:
            logger.error(f"CV2言語選択応答中にエラー: {e}\n{traceback.format_exc()}")
    
    async def handle_member_select(self, interaction):
        """
        メンバーロール選択セレクトメニューのインタラクション処理
        
        Parameters:
        -----------
        interaction : discord.Interaction
            セレクトメニュー選択時のインタラクション
        """
        selected_values = interaction.data.get("values", [])
        logger.info(f"メンバーロール選択: ユーザー={interaction.user.name}, 選択値={selected_values}")
        
        selected_category = None
        selected_role_ids = [int(value.split("_")[1]) for value in selected_values if value.startswith("role_")]
        
        logger.debug(f"デバッグ: インタラクションデータ={interaction.data}")
        logger.debug(f"デバッグ: 選択されたロールID={selected_role_ids}")
        
        custom_id = interaction.data.get("custom_id", "")
        logger.debug(f"デバッグ: カスタムID={custom_id}")
        
        if ":" in custom_id:
            try:
                category_value = custom_id.split(":")[1]
                logger.debug(f"デバッグ: 埋め込まれたカテゴリ値={category_value}")
                
                for category in self.oshi_categories:
                    if category["value"] == category_value:
                        selected_category = category
                        logger.info(f"埋め込みカテゴリ値からカテゴリを特定: {category['name']}")
                        break
            except Exception as e:
                logger.error(f"埋め込みカテゴリ値からのカテゴリ特定中にエラー: {e}", exc_info=True)
                
        if not selected_category:
            try:
                logger.debug("デバッグ: 方法1開始 - メッセージコンポーネントからカテゴリを特定")
                message_components = interaction.message.components
                logger.debug(f"デバッグ: メッセージコンポーネント数={len(message_components) if message_components else 0}")
                
                if message_components and len(message_components) > 0:
                    for i, component in enumerate(message_components):
                        logger.debug(f"デバッグ: コンポーネント[{i}].type={component.type}")
                        if component.type == 1:
                            for j, child in enumerate(component.components):
                                logger.debug(f"デバッグ: 子コンポーネント[{j}].type={child.type}, custom_id={getattr(child, 'custom_id', 'なし')}")
                                if child.type == 3 and child.custom_id == "oshi_select":
                                    logger.debug(f"デバッグ: oshi_selectメニュー発見、オプション数={len(child.options)}")
                                    for option in child.options:
                                        logger.debug(f"デバッグ: オプション={option.label}, default={getattr(option, 'default', False)}")
                                        if getattr(option, 'default', False):
                                            for category in self.oshi_categories:
                                                if category["value"] == option.value:
                                                    selected_category = category
                                                    logger.info(f"メッセージコンポーネントからカテゴリを特定: {category['name']}")
                                                    break
                                            break
                                    break
                            if selected_category:
                                break
            except Exception as e:
                logger.error(f"メッセージコンポーネントからのカテゴリ特定中にエラー: {e}", exc_info=True)
        
        if not selected_category and selected_role_ids:
            logger.debug("デバッグ: 方法2開始 - ロールIDからカテゴリを逆引き")
            first_role_id = selected_role_ids[0]
            logger.debug(f"デバッグ: 最初のロールID={first_role_id}")
            
            for category in self.oshi_categories:
                logger.debug(f"デバッグ: カテゴリ '{category['name']}' のロール数={len(category['roles'])}")
                for role_name, role_id in category["roles"].items():
                    logger.debug(f"デバッグ: 比較 {role_id} == {first_role_id}")
                    if role_id == first_role_id:
                        selected_category = category
                        logger.info(f"ロールIDからカテゴリを逆引き: {category['name']}")
                        break
                if selected_category:
                    break
                    
        if not selected_category:
            selected_category = self.oshi_categories[0]
            logger.warning(f"カテゴリ特定失敗、フォールバックを使用: {selected_category['name']}")
            messages = ["⚠️ カテゴリの特定に失敗しましたが、処理を続行します。"]
        else:
            logger.info(f"対象カテゴリ: {selected_category['name']}")
            messages = []
        
        user = interaction.user
        guild = interaction.guild
        
        current_role_ids = [role.id for role in user.roles]
        
        category_role_ids = set(selected_category["roles"].values())
        
        roles_to_add = []
        roles_to_remove = []
        
        for role_id in selected_role_ids:
            if role_id not in current_role_ids:
                role = guild.get_role(role_id)
                
                if role:
                    roles_to_add.append(role)
        
        for role_id in category_role_ids:
            if role_id in current_role_ids and role_id not in selected_role_ids:
                role = guild.get_role(role_id)
                
                if role:
                    roles_to_remove.append(role)
        
        try:
            if roles_to_add:
                await user.add_roles(*roles_to_add)
                add_names = [f"**{role.name}**" for role in roles_to_add]
                messages.append(f"付与したロール: {', '.join(add_names)}")
                logger.info(f"ロール付与: {[role.name for role in roles_to_add]}, ユーザー: {user.name}")
                
                if self.analytics_callback:
                    role_data = [
                        {"id": role.id, "name": role.name} 
                        for role in roles_to_add
                    ]
                    self.analytics_callback(
                        "add", user.id, user.name, role_data, 
                        selected_category.get("name", "不明")
                    )
        except Exception as e:
            logger.error(f"ロール付与中にエラー: {e}")
            messages.append("❌ ロールの付与中にエラーが発生しました")
        
        try:
            if roles_to_remove:
                await user.remove_roles(*roles_to_remove)
                remove_names = [f"**{role.name}**" for role in roles_to_remove]
                messages.append(f"解除したロール: {', '.join(remove_names)}")
                logger.info(f"ロール解除: {[role.name for role in roles_to_remove]}, ユーザー: {user.name}")
                
                if self.analytics_callback:
                    role_data = [
                        {"id": role.id, "name": role.name} 
                        for role in roles_to_remove
                    ]
                    self.analytics_callback(
                        "remove", user.id, user.name, role_data, 
                        selected_category.get("name", "不明")
                    )
        except Exception as e:
            logger.error(f"ロール解除中にエラー: {e}")
            messages.append("❌ ロールの解除中にエラーが発生しました")
        
        if len(messages) == 0 or (len(messages) == 1 and messages[0].startswith("⚠️")):
            messages.append("ロールの変更はありませんでした")
        
        try:
            await interaction.response.send_message("\n".join(messages), ephemeral=True)
        except discord.errors.InteractionResponded:
            logger.warning(f"インタラクションは既に応答済み: ユーザー={user.name}")
            try:
                await interaction.followup.send("\n".join(messages), ephemeral=True)
            except Exception as e:
                logger.error(f"フォローアップメッセージ送信中にエラー: {e}")

    def __del__(self):
        if hasattr(self, 'client'):
            logger.info("CV2MessageSender instance is being destroyed, but client.aclose() cannot be awaited in __del__")
            
    async def close(self):
        if hasattr(self, 'client'):
            await self.client.aclose()
            logger.info("CV2MessageSender client closed successfully")

async def setup(bot):
    try:
        await bot.add_cog(OshiRolePanel(bot))
    except Exception as e:
        logger.error(f"OshiRolePanel Cogの登録に失敗しました: {e}\n{traceback.format_exc()}")
