import discord
from discord.ext import commands
import traceback
from utils.logging import setup_logging
import httpx
import random
import os
import json
import re
import uuid

logger = setup_logging("D")

# --- 推しロールパネル用のCog ---
class OshiRolePanel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cv2_sender = CV2MessageSender(bot)
        self.role_emoji_mapping = {}
        self.load_role_emoji_mapping()
        # タレント名とファンネームのマッピングテーブル
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
            "reg_hajime": "読者",
            "reg_raden": "でん同士",
            "reg_kanade": "音の勢",
            "reg_ao": "秘書見習い",
            "reg_Ririka": "真っす組",
            # スタッフ
            "1_yagoo_": "YAGOO",
            
        }
        
    def load_role_emoji_mapping(self):
        """ロールと絵文字のマッピングをJSONファイルから読み込む"""
        data_dir = os.path.join(os.getcwd(), "data")
        file_path = os.path.join(data_dir, "role_emoji_mapping.json")
        
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    self.role_emoji_mapping = json.load(f)
                logger.info(f"ロール絵文字マッピングを読み込みました: {len(self.role_emoji_mapping)}件")
            except Exception as e:
                logger.error(f"ロール絵文字マッピングの読み込みに失敗: {e}")
                self.role_emoji_mapping = {}
        else:
            logger.info("ロール絵文字マッピングファイルが見つかりません")
            self.role_emoji_mapping = {}
        
    def save_role_emoji_mapping(self):
        """ロールと絵文字のマッピングをJSONファイルに保存"""
        data_dir = os.path.join(os.getcwd(), "data")
        os.makedirs(data_dir, exist_ok=True)
        file_path = os.path.join(data_dir, "role_emoji_mapping.json")
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.role_emoji_mapping, f, indent=4, ensure_ascii=False)
            logger.info(f"ロール絵文字マッピングを保存しました: {len(self.role_emoji_mapping)}件")
            return True
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
            
        # ロールアイコンの自動スキャン
        await self.scan_roles_for_icons(ctx.guild)
            
        # 添付画像があるか確認
        image_url = "https://images.frwi.net/data/images/31dd6e9b-25e3-4a15-a783-1c7b0054b10f.png"
        
        await ctx.send(f"{channel.mention}に推しロールパネルを作成します...")
        _text = "選択欄の横にある絵文字が付きます。\n\n仕様上リストの上のメンバーの絵文字から優先してつきますので、ご了承ください。\n\n《例》\nそらともと35Pを選択した場合は**そらちゃんのみ**名前の横に表示されます。"
        result = await self.cv2_sender.send_role_panel(channel_id=channel.id, image_url=image_url, text=_text)
        
        if result:
            await ctx.send("推しロールパネルを作成しました")
        else:
            await ctx.send("推しロールパネルの作成に失敗しました")
    
    @oshirole.command(name="listroles")
    @commands.has_permissions(administrator=True)
    async def list_roles(self, ctx):
        """サーバーのロール一覧をJSON形式で取得します（アイコンURL含む）"""
        guild = ctx.guild
        roles_data = {}
        
        # @everyone ロールを除外し、残りのロールを取得
        for role in guild.roles:
            if role.name != "@everyone":
                roles_data[role.name] = {
                    "id": role.id,
                    "color": role.color.value if role.color.value else 0,
                    "position": role.position,
                    "mentionable": role.mentionable,
                    "hoist": role.hoist,  # サーバーメンバーリストで別々に表示するか
                    "icon_url": role.icon.url if role.icon else None  # ロールアイコンのURL
                }
        
        # JSONファイルにロールデータを保存
        data_dir = os.path.join(os.getcwd(), "data")
        os.makedirs(data_dir, exist_ok=True)
        
        file_path = os.path.join(data_dir, f"roles_{guild.id}.json")
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(roles_data, f, indent=4, ensure_ascii=False)
        
        # ファイルを添付して送信
        with open(file_path, 'rb') as f:
            file = discord.File(f, filename=f"roles_{guild.id}.json")
            await ctx.send("ロール一覧を取得しました（アイコンURL含む）：", file=file)
            
        logger.info(f"ロール一覧を保存しました: {file_path}")
        
    @oshirole.command(name="exportconfig")
    @commands.has_permissions(administrator=True)
    async def export_config(self, ctx):
        """現在の推しロール設定をJSON形式でエクスポートします"""
        config_data = {
            "categories": self.cv2_sender.oshi_categories
        }
        
        # JSONファイルに設定データを保存
        data_dir = os.path.join(os.getcwd(), "data")
        os.makedirs(data_dir, exist_ok=True)
        
        file_path = os.path.join(data_dir, f"oshi_config_{ctx.guild.id}.json")
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=4, ensure_ascii=False)
        
        # ファイルを添付して送信
        with open(file_path, 'rb') as f:
            file = discord.File(f, filename=f"oshi_config_{ctx.guild.id}.json")
            await ctx.send("推しロール設定をエクスポートしました：", file=file)
            
        logger.info(f"推しロール設定をエクスポートしました: {file_path}")
        
    @oshirole.command(name="importconfig")
    @commands.has_permissions(administrator=True)
    async def import_config(self, ctx):
        """添付されたJSONファイルから推しロール設定をインポートします"""
        if not ctx.message.attachments:
            await ctx.send("設定ファイル（JSON）を添付してください")
            return
            
        attachment = ctx.message.attachments[0]
        if not attachment.filename.endswith('.json'):
            await ctx.send("JSONファイルを添付してください")
            return
            
        try:
            # ファイルをダウンロードして読み込む
            config_bytes = await attachment.read()
            config_data = json.loads(config_bytes.decode('utf-8'))
            
            # 設定をバリデーション
            if "categories" not in config_data:
                await ctx.send("無効な設定ファイルです：'categories'フィールドがありません")
                return
                
            # 設定を適用
            self.cv2_sender.oshi_categories = config_data["categories"]
            
            # 設定を保存（永続化する場合）
            data_dir = os.path.join(os.getcwd(), "data")
            os.makedirs(data_dir, exist_ok=True)
            
            file_path = os.path.join(data_dir, "oshi_config.json")
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=4, ensure_ascii=False)
            
            await ctx.send("推しロール設定をインポートしました")
            logger.info(f"推しロール設定をインポートしました: {attachment.filename}")
        except Exception as e:
            await ctx.send(f"設定のインポート中にエラーが発生しました: {e}")
            logger.error(f"設定インポート中にエラー: {e}\n{traceback.format_exc()}")
    
    @oshirole.command(name="setemoji")
    @commands.has_permissions(administrator=True)
    async def set_role_emoji(self, ctx, role: discord.Role, emoji: str):
        """ロールに絵文字を関連付けます"""
        # 絵文字として有効かどうかの簡易チェック（完璧ではない）
        # unicodeの絵文字または Discord カスタム絵文字の形式チェック
        if not re.match(r'[\u2600-\u27BF\U0001F300-\U0001F64F\U0001F680-\U0001F6FF\U0001F700-\U0001F77F\U0001F780-\U0001F7FF\U0001F800-\U0001F8FF\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF\U000E0020-\U000E007F]|<:[a-zA-Z0-9_]+:[0-9]+>$', emoji):
            await ctx.send("有効な絵文字を指定してください")
            return
            
        # ロールID（文字列）をキーとして絵文字を保存
        self.role_emoji_mapping[str(role.id)] = emoji
        self.save_role_emoji_mapping()
        
        await ctx.send(f"ロール「{role.name}」に絵文字 {emoji} を設定しました")
        
    @oshirole.command(name="removeemoji")
    @commands.has_permissions(administrator=True)
    async def remove_role_emoji(self, ctx, role: discord.Role):
        """ロールから絵文字の関連付けを削除します"""
        role_id = str(role.id)
        
        if role_id in self.role_emoji_mapping:
            emoji = self.role_emoji_mapping[role_id]
            del self.role_emoji_mapping[role_id]
            self.save_role_emoji_mapping()
            await ctx.send(f"ロール「{role.name}」から絵文字 {emoji} の関連付けを削除しました")
        else:
            await ctx.send(f"ロール「{role.name}」に関連付けられた絵文字はありません")
            
    @oshirole.command(name="listemojis")
    @commands.has_permissions(administrator=True)
    async def list_role_emojis(self, ctx):
        """ロールと絵文字のマッピング一覧を表示します"""
        if not self.role_emoji_mapping:
            await ctx.send("ロールに関連付けられた絵文字はありません")
            return
            
        guild = ctx.guild
        embed = discord.Embed(title="ロール絵文字マッピング", color=discord.Color.blue())
        
        for role_id, emoji in self.role_emoji_mapping.items():
            role = guild.get_role(int(role_id))
            if role:
                embed.add_field(name=role.name, value=f"{emoji} (ID: {role_id})", inline=True)
                
        await ctx.send(embed=embed)
        
    @oshirole.command(name="exportemojis")
    @commands.has_permissions(administrator=True)
    async def export_role_emojis(self, ctx):
        """ロールと絵文字のマッピングをJSONファイルでエクスポートします"""
        if not self.role_emoji_mapping:
            await ctx.send("エクスポートするデータがありません")
            return
            
        data_dir = os.path.join(os.getcwd(), "data")
        os.makedirs(data_dir, exist_ok=True)
        file_path = os.path.join(data_dir, "role_emoji_mapping.json")
        
        with open(file_path, 'rb') as f:
            file = discord.File(f, filename="role_emoji_mapping.json")
            await ctx.send("ロール絵文字マッピングをエクスポートしました：", file=file)
    
    @oshirole.command(name="listemoji")
    @commands.has_permissions(administrator=True)
    async def list_emoji(self, ctx, prefix: str = "m_", as_json: bool = False):
        """サーバー内の指定した接頭辞（デフォルト: m_）から始まる絵文字を一覧表示します。JSON形式の出力も可能です。"""
        guild = ctx.guild
        matching_emojis = [emoji for emoji in guild.emojis if emoji.name.startswith(prefix)]
        
        if not matching_emojis:
            await ctx.send(f"サーバー内に '{prefix}' から始まる絵文字は見つかりませんでした。")
            return
        
        # JSON形式での出力が要求された場合
        if as_json:
            # 絵文字情報をJSON形式のデータに変換
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
            
            # JSONファイルの保存先を設定
            data_dir = os.path.join(os.getcwd(), "data")
            os.makedirs(data_dir, exist_ok=True)
            file_path = os.path.join(data_dir, f"{prefix}_emojis.json")
            
            # データをJSONファイルに保存
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(emoji_data, f, indent=4, ensure_ascii=False)
            
            # ファイルを添付して送信
            with open(file_path, 'rb') as f:
                file = discord.File(f, filename=f"{prefix}_emojis.json")
                await ctx.send(f"'{prefix}'から始まる絵文字一覧 (合計: {len(matching_emojis)}個):", file=file)
            
            return
        
        # 通常のEmbedでの表示（既存の処理）
        # ページごとに表示する絵文字の数
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
                # 絵文字の情報を追加
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
        
        # セレクトメニューの処理
        if custom_id == "oshi_select":
            await self.cv2_sender.handle_oshi_select(interaction)
        # メンバーロール選択セレクトメニューの処理
        elif custom_id == "member_select":
            await self.cv2_sender.handle_member_select(interaction)
        # ロールボタンの処理
        elif custom_id.startswith("role_"):
            await self.cv2_sender.handle_role_button(interaction)
        # 言語選択ボタンの処理（英語、韓国語、中国語、日本語）
        elif custom_id in ["oshi_english", "oshi_korean", "oshi_chinese", "oshi_japanese"]:
            await self.cv2_sender.handle_oshi_language_button(interaction)

    async def scan_roles_for_icons(self, guild):
        """サーバー内のロールをスキャンして、「m_」で始まる絵文字を関連付ける"""
        logger.info(f"ロール絵文字スキャン開始: サーバー {guild.name}")
        roles_total = 0
        emojis_mapped = 0
        
        # サーバー内の「m_」で始まる絵文字を取得
        member_emojis = {}
        for emoji in guild.emojis:
            if emoji.name.startswith("m_"):
                # 「m_」の後の部分がタレント識別子と仮定
                talent_id = emoji.name[2:]
                member_emojis[talent_id] = emoji
                logger.info(f"ロール絵文字候補: {emoji.name} -> {talent_id}")
                    
        logger.info(f"'m_'で始まる絵文字を {len(member_emojis)} 個見つけました")
        
        # 各カテゴリのロールをチェック
        for category in self.cv2_sender.oshi_categories:
            for role_name, role_id in category["roles"].items():
                roles_total += 1
                role = guild.get_role(role_id)
                
                if not role:
                    logger.warning(f"ロールが見つかりません: {role_name} (ID: {role_id})")
                    continue
                    
                # ロール名から絵文字部分を削除して比較
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
                
                # このロール名に対応する絵文字を探す
                best_match = None
                best_match_path = None
                
                # 方法1: タレント名→ファンネーム変換マッピングを使用
                for talent_id, emoji in member_emojis.items():
                    # タレント名からファンネームへの変換を試みる
                    fanname = self.talent_to_fanname.get(talent_id, "")
                    
                    # ファンネームが取得できた場合
                    if fanname and (fanname.lower() == clean_role_name.lower() or 
                                   fanname.lower() in clean_role_name.lower() or 
                                   clean_role_name.lower() in fanname.lower()):
                        best_match = emoji
                        best_match_path = f"{talent_id} → {fanname} ≈ {clean_role_name}"
                        break
                
                # 方法2: 従来のマッチング方法（バックアップとして残す）
                if not best_match:
                    # 完全一致
                    if clean_role_name in member_emojis:
                        best_match = member_emojis[clean_role_name]
                        best_match_path = f"直接マッチ: {clean_role_name}"
                    else:
                        # 接頭辞一致
                        for emoji_name, emoji in member_emojis.items():
                            if clean_role_name.lower().startswith(emoji_name.lower()) or emoji_name.lower().startswith(clean_role_name.lower()):
                                best_match = emoji
                                best_match_path = f"接頭辞マッチ: {emoji_name} ≈ {clean_role_name}"
                                break
                        
                        # まだ見つからない場合は部分一致
                        if not best_match:
                            for emoji_name, emoji in member_emojis.items():
                                if emoji_name.lower() in clean_role_name.lower() or clean_role_name.lower() in emoji_name.lower():
                                    best_match = emoji
                                    best_match_path = f"部分マッチ: {emoji_name} ≈ {clean_role_name}"
                                    break
                
                # 一致する絵文字が見つかった場合
                if best_match:
                    emoji_str = f"<:{best_match.name}:{best_match.id}>"
                    self.role_emoji_mapping[str(role_id)] = emoji_str
                    emojis_mapped += 1
                    logger.info(f"ロール「{role_name}」に絵文字 {emoji_str} をマッピングしました (マッチ: {best_match_path})")
        
        # 結果をログに記録し保存
        self.save_role_emoji_mapping()
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

# --- CV2形式のメッセージ送信ユーティリティ ---
class CV2MessageSender:
    def __init__(self, bot):
        self.bot = bot
        self.api_version = "v10"
        self.base_url = f"https://discord.com/api/{self.api_version}"
        self.client = httpx.AsyncClient(timeout=30.0)
        
        # 簡単に編集できる設定部分
        self.oshi_categories = [
            {
                "name": "JP 0期〜2期生",
                "emoji": "🌟",
                "description": "ときのそら、AZKi、ロボ子、さくらみこ、星街すいせい、白上フブキなど",
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
                "description": "白上フブキ、大神ミオ、猫又おかゆ、戌神ころね、不知火フレア、白銀ノエル、宝鐘マリン、兎田ぺこらなど",
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
                "description": "天音かなた、角巻わため、常闇トワ、姫森ルーナ、雪花ラミィ、獅白ぼたんなど",
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
                "description": "ラプラス・ダークネス、鷹嶺ルイ、博衣こより、風真いろは、沙花叉クロヱ",
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
                "name": "hololive EN",
                "emoji": "🌎",
                "description": "Myth、Council、Adventureのメンバー",
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
                "name": "hololive ID",
                "emoji": "🌺",
                "description": "ID1期、ID2期、ID3期のメンバー",
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
            },
            {
                "name": "ReGLOSS",
                "emoji": "🎭",
                "description": "つぐみ、いぶちゃん、みけたん、ねね、ゆびたん",
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
                "name": "その他",
                "emoji": "👑",
                "description": "スタッフやその他の特別なロール",
                "value": "oshi_others",
                "roles": {
                    "YAGOO👨‍🎓": 1093018532519870534,
                    "えーちゃん👓": 1093019394172522517,
                    "春先のどか📝": 1093020217757671507
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
        
        # 虹色のカラーコード（Discord用の整数値）
        rainbow_colors = [
            15158332,  # 赤色 (0xE74C3C)
            16754470,  # オレンジ色 (0xFFA726) 
            15844367,  # 黄色 (0xF1C40F)
            5763719,   # 緑色 (0x57F287)
            3447003,   # 青色 (0x3498DB)
            7506394,   # 藍色 (0x7289DA)
            10181046   # 紫色 (0x9B59B6)
        ]
        
        # ランダムに色を選択
        accent_color = random.choice(rainbow_colors)
        
        # テキスト用の独立したコンポーネント
        text_component = None
        if text:
            text_component = {
                "type": 10,  # Text Display
                "content": text
            }
        
        # Container内のコンポーネント構築
        container_components = []
        
        # 画像の処理
        attachments = []
        
        # 添付画像がある場合
        if image_data:
            # 一意のIDを生成
            attachment_id = str(uuid.uuid4())
            filename = f"oshi_panel_{attachment_id}.png"
            
            # attachmentsを追加
            attachments = [{
                "id": "0",
                "filename": filename
            }]
            
            # Media Galleryをcontainer_componentsに追加
            container_components.append({
                "type": 12,  # Media Gallery
                "items": [
                    {
                        "media": {"url": f"attachment://{filename}"}
                    }
                ]
            })
        # 外部画像URLがある場合は直接参照
        elif image_url:
            container_components.append({
                "type": 12,  # Media Gallery
                "items": [
                    {
                        "media": {"url": image_url}
                    }
                ]
            })
        
        # タイトル
        container_components.append({
            "type": 10,  # Text Display
            "content": "## 🎭 推しメンバーロール選択"
        })
        
        # 説明
        description_text = "応援しているメンバーのロールを選択して、あなたの推しをアピールしましょう！\n"\
                          "以下のドロップダウンメニューからカテゴリを選ぶと、そのカテゴリ内のメンバーロールが表示されます。"
            
        container_components.append({
            "type": 10,  # Text Display
            "content": description_text
        })
        
        # 区切り線
        container_components.append({
            "type": 14,  # Separator
            "divider": True,
            "spacing": 1
        })
        
        # セレクトメニュー用オプション作成
        options = []
        for category in self.oshi_categories:
            options.append({
                "label": category["name"],
                "value": category["value"],
                "description": category["description"],
                "emoji": {"name": category["emoji"]}
            })
        
        # セレクトメニュー
        container_components.append({
            "type": 1,  # Action Row
            "components": [
                {
                    "type": 3,  # Select Menu
                    "custom_id": "oshi_select",
                    "placeholder": "カテゴリを選択",
                    "options": options,
                    "min_values": 1,
                    "max_values": 1
                }
            ]
        })
        
        # 注意書き
        container_components.append({
            "type": 10,  # Text Display
            "content": "*※カテゴリを選択すると、詳細なメンバー選択画面が表示されます*"
        })
        
        # 言語選択部分の前の区切り線
        container_components.append({
            "type": 14,  # Separator
            "divider": True,
            "spacing": 2  # 大きめの余白
        })
        
        # 言語選択の見出し
        container_components.append({
            "type": 10,  # Text Display
            "content": "### 言語選択 / Language / 언어 / 语言"
        })
        
        # 言語選択の説明
        container_components.append({
            "type": 10,  # Text Display
            "content": "If you need a language other than Japanese, please click one of the buttons below👇\n" +
                     "한국어/중국어 안내가 필요하신 분은 아래 버튼을 눌러주세요👇\n" +
                     "如需其他语言的说明，请点击下方按钮👇"
        })
        
        # 言語選択ボタンを横並びに配置
        container_components.append({
            "type": 1,  # Action Row
            "components": [
                {
                    "type": 2,  # Button
                    "style": 1,
                    "label": "English",
                    "custom_id": "oshi_english",
                    "emoji": {"name": "🇬🇧"}
                },
                {
                    "type": 2,  # Button
                    "style": 1,
                    "label": "한국어",
                    "custom_id": "oshi_korean",
                    "emoji": {"name": "🇰🇷"}
                },
                {
                    "type": 2,  # Button
                    "style": 1,
                    "label": "中文",
                    "custom_id": "oshi_chinese",
                    "emoji": {"name": "🇨🇳"}
                }
            ]
        })
        
        # Containerコンポーネント
        container = {
            "type": 17,  # Container
            "accent_color": accent_color,
            "components": container_components
        }
        
        # CV2形式の構造化されたコンポーネント
        components = []
        if text_component:
            components.append(text_component)
        components.append(container)
        
        # リクエストのベースとなるJSONデータ
        payload = {
            "flags": 32768,  # IS_COMPONENTS_V2 フラグ
            "components": components
        }
        
        # 添付ファイルがある場合に追加
        if attachments:
            payload["attachments"] = attachments
        
        # 共通のヘッダー
        headers = {
            "Authorization": f"Bot {self.bot.http.token}",
            "Content-Type": "application/json"
        }
        
        try:
            # HTTP POSTリクエスト送信
            if image_data:
                # 画像を含む場合はmultipart/form-dataリクエストを使用
                files = {
                    "files[0]": (attachments[0]["filename"], image_data, "image/png")
                }
                
                # multipart/form-dataリクエスト
                form = {"payload_json": json.dumps(payload)}
                
                # Authorizationヘッダーのみを設定し、Content-Typeはhttpxに自動設定させる
                custom_headers = {
                    "Authorization": f"Bot {self.bot.http.token}"
                }
                
                # デバッグ用ログ出力
                logger.debug(f"送信するフォームデータ: {form}")
                logger.debug(f"送信するファイル: {attachments[0]['filename']}")
                
                # HTTP POSTリクエスト送信
                response = await self.client.post(
                    endpoint,
                    headers=custom_headers,
                    data=form,
                    files=files
                )
            else:
                # 画像がない場合は通常のJSONリクエスト
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
        # 選択されたカテゴリの値を取得
        values = interaction.data.get("values", [])
        if not values:
            return
            
        category_value = values[0]
        
        # 選択されたカテゴリの情報を取得
        selected_category = None
        for category in self.oshi_categories:
            if category["value"] == category_value:
                selected_category = category
                break
                
        if not selected_category:
            await interaction.response.send_message("カテゴリが見つかりませんでした", ephemeral=True)
            return
        
        # 虹色のカラーコード（Discord用の整数値）
        rainbow_colors = [
            15158332,  # 赤色 (0xE74C3C)
            16754470,  # オレンジ色 (0xFFA726) 
            15844367,  # 黄色 (0xF1C40F)
            5763719,   # 緑色 (0x57F287)
            3447003,   # 青色 (0x3498DB)
            7506394,   # 藍色 (0x7289DA)
            10181046   # 紫色 (0x9B59B6)
        ]
        
        # ランダムに色を選択
        accent_color = random.choice(rainbow_colors)
        
        try:
            endpoint = f"{self.base_url}/interactions/{interaction.id}/{interaction.token}/callback"
            
            # Container内のコンポーネント
            container_components = []
            
            # タイトルとカテゴリ
            container_components.append({
                "type": 10,  # Text Display
                "content": f"## {selected_category['emoji']} {selected_category['name']}のメンバーロール"
            })
            
            # 説明
            container_components.append({
                "type": 10,  # Text Display
                "content": f"**{selected_category['description']}**\n\n推しメンバーのロールを選択してください："
            })
            
            # 区切り線
            container_components.append({
                "type": 14,  # Separator
                "divider": True,
                "spacing": 1
            })
            
            # カテゴリ選択セレクトメニュー用オプション作成
            category_options = []
            for category in self.oshi_categories:
                # 現在選択中のカテゴリを表示
                is_selected = category["value"] == category_value
                category_options.append({
                    "label": category["name"],
                    "value": category["value"],
                    "description": category["description"],
                    "emoji": {"name": category["emoji"]},
                    "default": is_selected  # 選択中のカテゴリをデフォルト表示
                })
            
            # カテゴリ選択セレクトメニュー
            container_components.append({
                "type": 1,  # Action Row
                "components": [
                    {
                        "type": 3,  # Select Menu
                        "custom_id": "oshi_select",
                        "placeholder": "カテゴリを選択",
                        "options": category_options,
                        "min_values": 1,
                        "max_values": 1
                    }
                ]
            })
            
            # メンバーロールセレクトメニュー用オプション作成
            member_options = []
            user_roles = [role.id for role in interaction.user.roles]  # ユーザーが持っているロールのID一覧
            
            for member_name, role_id in selected_category["roles"].items():
                # ロールを取得
                role = interaction.guild.get_role(role_id)
                
                # ロールが存在する場合のみ追加
                if role:
                    # ユーザーが既にロールを持っているかチェック
                    has_role = role_id in user_roles
                    
                    # 絵文字オブジェクト初期化
                    emoji_obj = None
                    
                    # 優先順位: 1.ロールアイコン 2.ロール絵文字マッピング
                    if role.icon:
                        # ロールアイコンがある場合の処理
                        logger.info(f"ロール {role.name} のアイコンURL: {role.icon.url}")
                        
                        # ロール絵文字マッピングからの取得を試みる（サーバー上のカスタム絵文字マッピング）
                        emoji_str = self.bot.get_cog("OshiRolePanel").role_emoji_mapping.get(str(role_id), "")
                        if emoji_str:
                            # カスタム絵文字かUnicode絵文字かを判断
                            if emoji_str.startswith("<") and emoji_str.endswith(">"):
                                # カスタム絵文字の場合、IDを抽出
                                emoji_parts = emoji_str.strip("<>").split(":")
                                if len(emoji_parts) == 3:
                                    emoji_obj = {
                                        "id": emoji_parts[2],
                                        "name": emoji_parts[1],
                                        "animated": emoji_parts[0] == "a"
                                    }
                            else:
                                # Unicode絵文字の場合
                                emoji_obj = {"name": emoji_str}
                    else:
                        # ロールアイコンがない場合、ロール絵文字マッピングを使用
                        emoji_str = self.bot.get_cog("OshiRolePanel").role_emoji_mapping.get(str(role_id), "")
                        if emoji_str:
                            # カスタム絵文字かUnicode絵文字かを判断
                            if emoji_str.startswith("<") and emoji_str.endswith(">"):
                                # カスタム絵文字の場合、IDを抽出
                                emoji_parts = emoji_str.strip("<>").split(":")
                                if len(emoji_parts) == 3:
                                    emoji_obj = {
                                        "id": emoji_parts[2],
                                        "name": emoji_parts[1],
                                        "animated": emoji_parts[0] == "a"
                                    }
                            else:
                                # Unicode絵文字の場合
                                emoji_obj = {"name": emoji_str}
                    
                    # メンバーオプションを追加
                    option = {
                        "label": member_name,
                        "value": f"role_{role_id}",
                        "default": has_role  # 既に持っているロールは選択済みとして表示
                    }
                    
                    # アイコン/絵文字の情報をdescriptionに追加
                    if role.icon:
                        option["description"] = "左のアイコンがつきます"
                    
                    # 絵文字があれば追加
                    if emoji_obj:
                        option["emoji"] = emoji_obj
                    
                    member_options.append(option)
            
            # メンバーロール選択セレクトメニュー（複数選択可能）
            if member_options:
                container_components.append({
                    "type": 1,  # Action Row
                    "components": [
                        {
                            "type": 3,  # Select Menu
                            "custom_id": "member_select",
                            "placeholder": "推しメンバーを選択（複数可）",
                            "options": member_options,
                            "min_values": 0,  # 選択解除も可能
                            "max_values": len(member_options)  # 全選択も可能
                        }
                    ]
                })
            else:
                container_components.append({
                    "type": 10,  # Text Display
                    "content": "*このカテゴリには選択可能なロールがありません*"
                })
            
            # 注意書き
            container_components.append({
                "type": 14,  # Separator
                "divider": True,
                "spacing": 1
            })
            
            container_components.append({
                "type": 10,  # Text Display
                "content": "*※セレクトメニューから推しメンバーを選択すると、対応するロールが付与または解除されます。\n複数選択が可能です。選択済みのものを外すと解除されます。*"
            })
            
            # 言語選択部分の区切り線
            container_components.append({
                "type": 14,  # Separator
                "divider": True,
                "spacing": 2  # 大きめの余白
            })
            
            # 言語選択の見出し
            container_components.append({
                "type": 10,  # Text Display
                "content": "### 言語選択 / Language / 언어 / 语言"
            })
            
            # 言語選択の説明
            container_components.append({
                "type": 10,  # Text Display
                "content": "If you need a language other than Japanese, please click one of the buttons below👇\n" +
                         "한국어/중국어 안내가 필요하신 분은 아래 버튼 중에서 선택해주세요👇"
            })
            
            # 言語選択ボタンを横並びに配置
            container_components.append({
                "type": 1,  # Action Row
                "components": [
                    {
                        "type": 2,  # Button
                        "style": 1,
                        "label": "English",
                        "custom_id": "oshi_english",
                        "emoji": {"name": "🇬🇧"}
                    },
                    {
                        "type": 2,  # Button
                        "style": 1,
                        "label": "한국어",
                        "custom_id": "oshi_korean",
                        "emoji": {"name": "🇰🇷"}
                    },
                    {
                        "type": 2,  # Button
                        "style": 1,
                        "label": "中文",
                        "custom_id": "oshi_chinese",
                        "emoji": {"name": "🇨🇳"}
                    }
                ]
            })
            
            # Containerコンポーネント
            container = {
                "type": 17,  # Container
                "accent_color": accent_color,
                "components": container_components
            }
            
            # CV2形式の構造化されたコンポーネント
            components = [container]
            
            response_data = {
                "type": 4,  # CHANNEL_MESSAGE_WITH_SOURCE
                "data": {
                    "flags": 32768 | 64,  # IS_COMPONENTS_V2 | EPHEMERAL
                    "components": components
                }
            }
            
            headers = {
                "Authorization": f"Bot {self.bot.http.token}",
                "Content-Type": "application/json"
            }
            
            # HTTP POSTリクエスト送信
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
        
        # ユーザーとロールを取得
        user = interaction.user
        guild = interaction.guild
        role = guild.get_role(role_id)
        
        if not role:
            await interaction.response.send_message(f"ロールが見つかりません (ID: {role_id})", ephemeral=True)
            logger.error(f"ロールが見つかりません: {role_id}, サーバー: {guild.name}")
            return
            
        try:
            # ロールの付与または解除
            if role in user.roles:
                await user.remove_roles(role)
                # ロール絵文字マッピングを使用
                emoji = self.bot.get_cog("OshiRolePanel").role_emoji_mapping.get(str(role_id), "")
                emoji_display = f"{emoji} " if emoji else ""
                await interaction.response.send_message(f"{emoji_display}**{role.name}**のロールを解除しました", ephemeral=True)
                logger.info(f"ロール解除: {role.name}, ユーザー: {user.name}")
            else:
                await user.add_roles(role)
                # ロール絵文字マッピングを使用
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
        
        # 虹色のカラーコード（Discord用の整数値）
        rainbow_colors = [
            15158332,  # 赤色 (0xE74C3C)
            16754470,  # オレンジ色 (0xFFA726) 
            15844367,  # 黄色 (0xF1C40F)
            5763719,   # 緑色 (0x57F287)
            3447003,   # 青色 (0x3498DB)
            7506394,   # 藍色 (0x7289DA)
            10181046   # 紫色 (0x9B59B6)
        ]
        
        # ランダムに色を選択
        accent_color = random.choice(rainbow_colors)
        
        # 言語に応じたタイトルと説明を取得
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
            # 未知のカスタムIDの場合
            logger.warning(f"未知の言語ボタンID: {custom_id}")
            return
            
        # インタラクションに応答
        try:
            endpoint = f"{self.base_url}/interactions/{interaction.id}/{interaction.token}/callback"
            
            # Container内のコンポーネント
            container_components = []
            
            # タイトル
            container_components.append({
                "type": 10,  # Text Display
                "content": f"## {title}"
            })
            
            # 説明
            container_components.append({
                "type": 10,  # Text Display
                "content": description
            })
            
            # 区切り線
            container_components.append({
                "type": 14,  # Separator
                "divider": True,
                "spacing": 1
            })
            
            # セレクトメニュー用オプション作成
            options = []
            for category in self.oshi_categories:
                options.append({
                    "label": category["name"],
                    "value": category["value"],
                    "description": category["description"],
                    "emoji": {"name": category["emoji"]}
                })
            
            # セレクトメニュー
            container_components.append({
                "type": 1,  # Action Row
                "components": [
                    {
                        "type": 3,  # Select Menu
                        "custom_id": "oshi_select",
                        "placeholder": category_placeholder,
                        "options": options,
                        "min_values": 1,
                        "max_values": 1
                    }
                ]
            })
            
            # 注意書き
            container_components.append({
                "type": 10,  # Text Display
                "content": notice
            })
            
            # 言語選択部分の前の区切り線
            container_components.append({
                "type": 14,  # Separator
                "divider": True,
                "spacing": 2  # 大きめの余白
            })
            
            # 言語選択の見出し
            container_components.append({
                "type": 10,  # Text Display
                "content": language_header
            })
            
            # 言語選択の説明
            container_components.append({
                "type": 10,  # Text Display
                "content": language_description
            })
            
            # 言語選択ボタンを横並びに配置
            container_components.append({
                "type": 1,  # Action Row
                "components": [
                    {
                        "type": 2,  # Button
                        "style": 1,
                        "label": "日本語",
                        "custom_id": "oshi_japanese",
                        "emoji": {"name": "🇯🇵"}
                    },
                    {
                        "type": 2,  # Button
                        "style": 1,
                        "label": "English",
                        "custom_id": "oshi_english",
                        "emoji": {"name": "🇬🇧"},
                        "disabled": custom_id == "oshi_english"
                    },
                    {
                        "type": 2,  # Button
                        "style": 1,
                        "label": "한국어",
                        "custom_id": "oshi_korean",
                        "emoji": {"name": "🇰🇷"},
                        "disabled": custom_id == "oshi_korean"
                    },
                    {
                        "type": 2,  # Button
                        "style": 1,
                        "label": "中文",
                        "custom_id": "oshi_chinese",
                        "emoji": {"name": "🇨🇳"},
                        "disabled": custom_id == "oshi_chinese"
                    }
                ]
            })
            
            # Containerコンポーネント
            container = {
                "type": 17,  # Container
                "accent_color": accent_color,
                "components": container_components
            }
            
            # CV2形式の構造化されたコンポーネント
            components = [container]
            
            response_data = {
                "type": 4,  # CHANNEL_MESSAGE_WITH_SOURCE
                "data": {
                    "flags": 32768 | 64,  # IS_COMPONENTS_V2 | EPHEMERAL
                    "components": components
                }
            }
            
            headers = {
                "Authorization": f"Bot {self.bot.http.token}",
                "Content-Type": "application/json"
            }
            
            # HTTP POSTリクエスト送信
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
        # 選択されたロール値を取得
        selected_values = interaction.data.get("values", [])
        logger.info(f"メンバーロール選択: ユーザー={interaction.user.name}, 選択値={selected_values}")
        
        # 選択中のカテゴリを特定
        selected_category = None
        message_components = interaction.message.components
        if message_components and len(message_components) > 0:
            # カテゴリ選択メニューを探す
            for component in message_components:
                if component.type == 1:  # ActionRow
                    for child in component.components:
                        if child.type == 3 and child.custom_id == "oshi_select":  # SelectMenu
                            # デフォルト値（現在選択中のカテゴリ）を取得
                            for option in child.options:
                                if option.default:
                                    for category in self.oshi_categories:
                                        if category["value"] == option.value:
                                            selected_category = category
                                            break
                                    break
                            break
                    if selected_category:
                        break
        
        if not selected_category:
            await interaction.response.send_message("カテゴリの特定に失敗しました。もう一度お試しください。", ephemeral=True)
            logger.error(f"カテゴリの特定に失敗: ユーザー={interaction.user.name}")
            return
        
        logger.info(f"対象カテゴリ: {selected_category['name']}")
        
        # ユーザーとギルドを取得
        user = interaction.user
        guild = interaction.guild
        
        # 選択されたロールIDを抽出
        selected_role_ids = [int(value.split("_")[1]) for value in selected_values if value.startswith("role_")]
        
        # ユーザーが現在持っているロールのIDリスト
        current_role_ids = [role.id for role in user.roles]
        
        # 現在選択中のカテゴリのロールIDを取得
        category_role_ids = set(selected_category["roles"].values())
        
        # 付与すべきロールと解除すべきロールを決定
        roles_to_add = []
        roles_to_remove = []
        
        # 選択されたロールを付与リストに追加
        for role_id in selected_role_ids:
            if role_id not in current_role_ids:  # まだ持っていないロールのみ
                role = guild.get_role(role_id)
                if role:
                    roles_to_add.append(role)
        
        # 現在のカテゴリの中で、選択されていないロールを解除リストに追加
        for role_id in category_role_ids:
            if role_id in current_role_ids and role_id not in selected_role_ids:
                role = guild.get_role(role_id)
                if role:
                    roles_to_remove.append(role)
        
        messages = []
        
        # ロールの付与処理
        try:
            if roles_to_add:
                await user.add_roles(*roles_to_add)
                add_names = [f"**{role.name}**" for role in roles_to_add]
                messages.append(f"付与したロール: {', '.join(add_names)}")
                logger.info(f"ロール付与: {[role.name for role in roles_to_add]}, ユーザー: {user.name}")
        except Exception as e:
            logger.error(f"ロール付与中にエラー: {e}")
            messages.append("❌ ロールの付与中にエラーが発生しました")
        
        # ロールの解除処理
        try:
            if roles_to_remove:
                await user.remove_roles(*roles_to_remove)
                remove_names = [f"**{role.name}**" for role in roles_to_remove]
                messages.append(f"解除したロール: {', '.join(remove_names)}")
                logger.info(f"ロール解除: {[role.name for role in roles_to_remove]}, ユーザー: {user.name}")
        except Exception as e:
            logger.error(f"ロール解除中にエラー: {e}")
            messages.append("❌ ロールの解除中にエラーが発生しました")
        
        # 何も変更がない場合
        if not messages:
            messages.append("ロールの変更はありませんでした")
        
        # ユーザーに結果を通知
        await interaction.response.send_message("\n".join(messages), ephemeral=True)

    async def __del__(self):
        # クライアントのクローズ処理
        if hasattr(self, 'client'):
            await self.client.aclose()

async def setup(bot):
    logger.info("OshiRolePanel Cogをセットアップ中...")
    try:
        await bot.add_cog(OshiRolePanel(bot))
        logger.info("OshiRolePanel Cogの登録が完了しました")
    except Exception as e:
        logger.error(f"OshiRolePanel Cogの登録に失敗しました: {e}\n{traceback.format_exc()}") 