import discord
from discord.ext import commands

import asyncio
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from utils.logging import setup_logging
from utils.commands_help import is_guild, is_owner, is_booster, log_commands
from utils.database import execute_query

from config.setting import get_settings

settings = get_settings()

logger = setup_logging("D")

class HololiveOmikujiCog(commands.Cog):
    """ホロライブおみくじ機能を提供するCogクラス"""
    
    def __init__(self, bot):
        self.bot = bot
        self.streak_reset_enabled = True
        # ホロライブメンバーのイメージカラー
        self.holo_colors = {
            "ホロブルー": 0x1E90FF,
            "さくらピンク": 0xFF69B4,
            "スバルイエロー": 0xFFD700,
            "マリンレッド": 0xFF0000,
            "ぺこらオレンジ": 0xFF8C00,
            "フブキホワイト": 0xF0F8FF,
            "アクアミント": 0x00FFFF,
            "ころねゴールド": 0xDAA520,
            "おかゆパープル": 0x9370DB,
            "わためベージュ": 0xF5F5DC
        }

    async def get_user_last_omikuji(self, user_id: int, guild_id: int) -> Optional[str]:
        """ユーザーの最後のおみくじ日付を取得"""
        try:
            result = await execute_query(
                "SELECT drawn_date FROM user_omikuji_history WHERE user_id = $1 AND guild_id = $2 ORDER BY drawn_date DESC LIMIT 1",
                user_id, guild_id, fetch_type='row'
            )
            return result['drawn_date'].isoformat() if result else None
        except Exception as e:
            logger.error(f"おみくじ履歴取得エラー: {e}")
            return None
    
    async def get_user_last_fortune(self, user_id: int, guild_id: int) -> Optional[str]:
        """ユーザーの最後の運勢日付を取得"""
        try:
            result = await execute_query(
                "SELECT drawn_date FROM user_fortune_history WHERE user_id = $1 AND guild_id = $2 ORDER BY drawn_date DESC LIMIT 1",
                user_id, guild_id, fetch_type='row'
            )
            return result['drawn_date'].isoformat() if result else None
        except Exception as e:
            logger.error(f"運勢履歴取得エラー: {e}")
            return None
    
    async def get_user_streak(self, user_id: int, guild_id: int) -> Dict[str, int]:
        """ユーザーのストリーク情報を取得"""
        try:
            result = await execute_query(
                "SELECT current_streak, max_streak, last_draw_date FROM user_omikuji_streaks WHERE user_id = $1 AND guild_id = $2",
                user_id, guild_id, fetch_type='row'
            )
            if result:
                return {
                    'streak': result['current_streak'],
                    'max_streak': result['max_streak'],
                    'last_date': result['last_draw_date'].isoformat() if result['last_draw_date'] else None
                }
            return {'streak': 0, 'max_streak': 0, 'last_date': None}
        except Exception as e:
            logger.error(f"ストリーク取得エラー: {e}")
            return {'streak': 0, 'max_streak': 0, 'last_date': None}
    
    async def update_user_streak(self, user_id: int, guild_id: int, streak: int, draw_date: str) -> None:
        """ユーザーのストリーク情報を更新"""
        try:
            await execute_query(
                """
                INSERT INTO user_omikuji_streaks (user_id, guild_id, current_streak, max_streak, last_draw_date)
                VALUES ($1, $2, $3, $3, $4)
                ON CONFLICT (user_id, guild_id)
                DO UPDATE SET 
                    current_streak = $3,
                    max_streak = GREATEST(user_omikuji_streaks.max_streak, $3),
                    last_draw_date = $4,
                    updated_at = CURRENT_TIMESTAMP
                """,
                user_id, guild_id, streak, draw_date, fetch_type='status'
            )
        except Exception as e:
            logger.error(f"ストリーク更新エラー: {e}")
    
    async def get_fortunes(self) -> List[Dict]:
        """運勢マスターデータを取得"""
        try:
            result = await execute_query(
                "SELECT id, name, display_name, weight, is_special FROM omikuji_fortunes ORDER BY weight DESC",
                fetch_type='all'
            )
            return result if result else []
        except Exception as e:
            logger.error(f"運勢マスター取得エラー: {e}")
            return []
    
    async def save_omikuji_result(self, user_id: int, guild_id: int, fortune_id: int, 
                                  is_super_rare: bool, is_chance: bool, streak: int, draw_date: str) -> None:
        """おみくじ結果をDBに保存"""
        try:
            await execute_query(
                """
                INSERT INTO user_omikuji_history (user_id, guild_id, fortune_id, drawn_date, is_super_rare, is_chance, streak_count)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                user_id, guild_id, fortune_id, draw_date, is_super_rare, is_chance, streak, fetch_type='status'
            )
        except Exception as e:
            logger.error(f"おみくじ結果保存エラー: {e}")
    
    async def save_fortune_result(self, user_id: int, guild_id: int, fortune_level: str,
                                  lucky_color: str, lucky_item: str, lucky_app: str, draw_date: str) -> None:
        """運勢結果をDBに保存"""
        try:
            await execute_query(
                """
                INSERT INTO user_fortune_history (user_id, guild_id, fortune_level, lucky_color, lucky_item, lucky_app, drawn_date)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                user_id, guild_id, fortune_level, lucky_color, lucky_item, lucky_app, draw_date, fetch_type='status'
            )
        except Exception as e:
            logger.error(f"運勢結果保存エラー: {e}")
    
    async def update_daily_stats(self, guild_id: int, stat_date: str, is_omikuji: bool = True) -> None:
        """日次統計を更新"""
        try:
            if is_omikuji:
                await execute_query(
                    """
                    INSERT INTO omikuji_daily_stats (guild_id, stat_date, omikuji_count, unique_users)
                    VALUES ($1, $2, 1, 1)
                    ON CONFLICT (guild_id, stat_date)
                    DO UPDATE SET 
                        omikuji_count = omikuji_daily_stats.omikuji_count + 1,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    guild_id, stat_date, fetch_type='status'
                )
            else:
                await execute_query(
                    """
                    INSERT INTO omikuji_daily_stats (guild_id, stat_date, fortune_count, unique_users)
                    VALUES ($1, $2, 1, 1)
                    ON CONFLICT (guild_id, stat_date)
                    DO UPDATE SET 
                        fortune_count = omikuji_daily_stats.fortune_count + 1,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    guild_id, stat_date, fetch_type='status'
                )
        except Exception as e:
            logger.error(f"日次統計更新エラー: {e}")

    async def reset_at_midnight(self) -> None:
        """日本時間の深夜0時にリセット処理を実行（DB版では不要だが互換性のため残存）"""
        while True:
            now_utc = datetime.utcnow()
            now_jst = now_utc + timedelta(hours=9)
            next_midnight_jst = datetime(now_jst.year, now_jst.month, now_jst.day) + timedelta(days=1)
            sleep_seconds = (next_midnight_jst - now_jst).total_seconds()

            await asyncio.sleep(sleep_seconds)
            
            # DB版では自動的に日付で制御されるため、特別な処理は不要
            logger.info("ホロ神社の深夜リセットが完了しました")

    @commands.hybrid_command(name="omikuji", aliases=["おみくじ", "ホロみくじ"])
    @is_guild()
    @log_commands()
    async def omikuji(self, ctx) -> None:
        """1日1回だけホロ神社でおみくじを引くことができます。"""
        logger.debug("Starting hololive omikuji command")
        await ctx.defer()

        user_id = ctx.author.id
        guild_id = ctx.guild.id
        special_user_id = settings.bot_owner_id

        now_utc = datetime.utcnow()
        now_jst = now_utc + timedelta(hours=9)
        today_jst = now_jst.date()
        today_str = today_jst.isoformat()

        logger.debug(f"User ID: {user_id}, Today JST: {today_jst}")

        # 本日のおみくじ履歴をチェック
        last_omikuji_date = await self.get_user_last_omikuji(user_id, guild_id)
        if last_omikuji_date == today_str and user_id != special_user_id:
            await ctx.send("今日はもうホロ神社でおみくじを引いています！\n日本時間24時にリセットされます。")
            logger.debug(f"User {user_id} has already drawn the omikuji today.")
            return

        # ストリーク情報を取得・更新
        streak_data = await self.get_user_streak(user_id, guild_id)
        current_streak = streak_data['streak']
        
        if streak_data['last_date']:
            last_date = datetime.fromisoformat(streak_data['last_date']).date()
            if user_id == special_user_id:
                # 特別ユーザーは連続ログインを維持
                if last_date < today_jst - timedelta(days=1):
                    current_streak = max(current_streak, 1)
            elif last_date == today_jst - timedelta(days=1):
                # 連続ログイン
                current_streak += 1
            else:
                # ストリーク途切れ
                if self.streak_reset_enabled:
                    current_streak = 1
        else:
            current_streak = 1

        # ストリーク情報を更新
        await self.update_user_streak(user_id, guild_id, current_streak, today_str)

        # みこち電脳桜神社の演出ステップ
        steps = [
            "にゃっはろ～！電脳桜神社へようこそだにぇ🌸",
            "エリート巫女みこちが式神の金時と一緒にお出迎え",
            "**みこち**「今日も良いおみくじが引けるといいにぇ～」",
            "電脳乃神が見守る中、デジタルおみくじを開く",
        ]

        # ホロライブ仕様のアイコン（元の画像を流用）
        normal_icon = "https://images.frwi.net/data/images/e5081f55-07a0-4996-9487-3b63d2fbe292.jpeg"
        special_icon = "https://images.frwi.net/data/images/3ff4aef3-e0a1-47e7-9969-cc0b0b192032.png"
        chance_icon = "https://images.frwi.net/data/images/b5972c13-9a4e-4c50-bd29-fbbe8e0f4fab.jpeg"

        # 運勢データを取得
        fortunes_data = await self.get_fortunes()
        if not fortunes_data:
            await ctx.send("申し訳ございません。ホロ神社のおみくじシステムでエラーが発生しました。")
            return

        # 重み付きランダム選択
        weights = [f['weight'] + (current_streak // 3) if f['is_special'] else f['weight'] for f in fortunes_data]
        
        selected_fortune_data = random.choices(fortunes_data, weights=weights, k=1)[0]
        fortune_name = selected_fortune_data['display_name']
        fortune_id = selected_fortune_data['id']
        
        # 特殊演出の判定
        is_super_rare = random.randint(1, 100) <= 5
        is_chance = random.randint(1, 100) <= 20
        is_rich_animation = random.randint(1, 100) <= 10
        
        if is_super_rare:
            fortune_name = "✨✨ホロ超大吉✨✨"

        embed = discord.Embed(
            title="🌸 電脳桜神社おみくじ結果 🌸",
            color=0xffd700 if is_super_rare else 0xFF69B4
        )
        embed.set_author(name=f"エリート運が{current_streak}%アップ中だにぇ！\n電脳桜神社にて...", icon_url=normal_icon)
        embed.set_thumbnail(url="https://images.frwi.net/data/images/7b54adae-c988-47f1-a090-625a7838f1c1.png")

        fm = await ctx.send(content=f"{ctx.author.mention}\nにゃっはろ～！電脳桜神社におみくじを引きに行くにぇ...", embed=None)

        description_with_steps = ""

        for i, step in enumerate(steps):
            await asyncio.sleep(2 if not is_rich_animation else 3)

            if is_chance and i == len(steps) - 2:
                embed.set_author(name=f"エリート運が{current_streak}%アップ中だにぇ！\n電脳桜神社にて...", icon_url=chance_icon)
                description_with_steps += "\n\n✨✨**エリートチャンス到来だにぇ！**✨✨"

            if is_super_rare and i == len(steps) - 1:
                description_with_steps += "\n\n🌟🌟**サイバーリーチ！**🌟🌟"

            description_with_steps += f"\n\n{step}"
            embed.description = description_with_steps
            await fm.edit(embed=embed)

        await asyncio.sleep(2 if not is_super_rare else 5)

        embed.description += f"\n\nおみくじには**{fortune_name}**と書かれていた"
        await fm.edit(embed=embed)
        
        # おみくじ結果をDBに保存
        await self.save_omikuji_result(user_id, guild_id, fortune_id, is_super_rare, is_chance, current_streak, today_str)
        await self.update_daily_stats(guild_id, today_str, is_omikuji=True)

        # ホロライブ絵文字（既存のカスタム絵文字を流用）
        holo_emoji1 = "<:omkj_iphone_dakedayo_1:1290367507575869582>"
        holo_emoji2 = "<:omkj_iphone_dakedayo_2:1290367485937451038>"
        holo_emoji3 = "<:omkj_iphone_dakedayo_3:1290367469998833727>"
        holo_emoji4 = "<a:omkj_iphone_dakedayo_4:1290367451061686363>"
        holo_emoji5 = "<:giz_server_icon:1264027561856471062>"

        emoji_list = [holo_emoji1, holo_emoji2, holo_emoji3, holo_emoji4, holo_emoji5]
        if is_super_rare:
            embed.set_author(name=f"ホロメン推し運が{current_streak}%アップ中！\n電脳桜神社にて...", icon_url=special_icon)
            await asyncio.sleep(2)
            embed.description += "\n\n✨✨「ホロの神々しい光があなたを包み込んだ！」✨✨"
            embed.set_image(url="https://images.frwi.net/data/images/a0cdbfa7-047e-43c5-93f3-f1c6478a6c64.jpeg")
            embed.color = 0xffd700
            await fm.edit(embed=embed)

            super_reactions = ["🎉", "✨", "💎", "🌟", "🔥"]

            for emoji in super_reactions:
                try:
                    await fm.add_reaction(emoji)
                except discord.HTTPException:
                    continue

            for emoji in emoji_list:
                try:
                    await fm.add_reaction(emoji)
                except discord.HTTPException:
                    continue

        elif "推し大吉" in fortune_name or "ホロ大吉" in fortune_name:
            await asyncio.sleep(1)
            embed.description += "\n\n推しメンからの特別なメッセージが届きそう..."
            await fm.edit(embed=embed)

            for emoji in emoji_list:
                try:
                    await fm.add_reaction(emoji)
                except discord.HTTPException:
                    continue

        embed.set_footer(text=
                         "電脳桜神社のおみくじをありがとうございます！また明日もお参りください！\n"
                         f"連続参拝: {current_streak}日目"
                         )
        await fm.edit(embed=embed)


    @commands.hybrid_command(name="fortune", aliases=["運勢", "ホロ運勢"])
    @is_guild()
    @log_commands()
    async def fortune(self, ctx) -> None:
        """1日1回だけホロ神社で今日の運勢を占えます。"""
        logger.debug("Starting hololive fortune command")
        await ctx.defer()

        user_id = ctx.author.id
        guild_id = ctx.guild.id
        special_user_id = settings.bot_owner_id

        now_utc = datetime.utcnow()
        now_jst = now_utc + timedelta(hours=9)
        today_jst = now_jst.date()
        today_str = today_jst.isoformat()

        logger.debug(f"User ID: {user_id}, Today JST: {today_jst}")

        # 本日の運勢履歴をチェック
        last_fortune_date = await self.get_user_last_fortune(user_id, guild_id)
        if last_fortune_date == today_str and user_id != special_user_id:
            await ctx.send("今日はもうホロ神社で運勢を占っています！\n日本時間24時にリセットされます。")
            logger.debug(f"User {user_id} has already checked their fortune today.")
            return

        # みおしゃのタロット占い演出ステップ
        steps = [
            "電脳桜神社の奥にある、みおしゃの占いの館へ向かう",
            "神秘的なタロットカードが宙に浮かんでいる",
            "**みおしゃ**「今日はどんな運命が待っているのでしょうか...」",
            "優しくタロットカードを引いてもらう",
        ]

        # タロット運勢からランダム選択
        selected_tarot = random.choice(self.TAROT_FORTUNES)
        fortune = selected_tarot["name"]
        fortune_meaning = selected_tarot["meaning"]
        tarot_color = int(selected_tarot["color"].replace("#", ""), 16)
        
        # サイバー関連のラッキーアイテム
        cyber_lucky_items = [
            "タロットカード", "水晶玉", "占い本", "美少女ゲーム", "たい焼き", "アニメグッズ",
            "ゲーミングキーボード", "VRヘッドセット", "式神お守り", "電脳アクセサリー",
            "サイバーペンダント", "デジタル数珠", "ホログラム御札"
        ]
        
        # サイバー関連のラッキーアプリ
        cyber_lucky_apps = [
            "YouTube", "Discord", "Twitter(X)", "Steam", "Spotify", "Netflix",
            "占いアプリ", "タロットアプリ", "瞑想アプリ", "アニメ配信アプリ",
            "ゲーム配信アプリ", "VR占いアプリ"
        ]
        
        lucky_color = random.choice(self.CYBER_COLORS)
        lucky_item = random.choice(cyber_lucky_items)
        lucky_app = random.choice(cyber_lucky_apps)

        embed = discord.Embed(title="✨ みおしゃのタロット占い結果 ✨", color=tarot_color)
        embed.set_author(name="みおしゃの占いの館にて...")
        embed.set_thumbnail(url="https://images.frwi.net/data/images/5d0b70e1-e16d-4e12-b399-e5dde756e6a3.png")

        fm = await ctx.send(content=f"{ctx.author.mention}\nみおしゃの占いの館で運勢を見てもらっています...", embed=None)

        description_with_steps = ""
        for step in steps:
            await asyncio.sleep(2)
            description_with_steps += f"\n\n{step}"
            embed.description = description_with_steps
            await fm.edit(embed=embed)

        await asyncio.sleep(1)
        
        # タロット占い結果の表示
        embed.description += f"\n\n🔮 引かれたタロットカード: **{fortune}**"
        embed.description += f"\n💫 カードの意味: {fortune_meaning}"
        
        embed.add_field(name="🎨 ラッキーカラー", value=lucky_color, inline=True)
        embed.add_field(name="🎁 ラッキーアイテム", value=lucky_item, inline=True) 
        embed.add_field(name="📱 ラッキーアプリ", value=lucky_app, inline=True)

        embed.set_footer(text="みおしゃ: 「素敵な一日になりますように...♪」\nまた占いに来てくださいね！")
        await fm.edit(embed=embed)
        
        # 運勢結果をDBに保存
        await self.save_fortune_result(user_id, guild_id, fortune, lucky_color, lucky_item, lucky_app, today_str)
        await self.update_daily_stats(guild_id, today_str, is_omikuji=False)

    @commands.hybrid_command(name="ranking", aliases=["ランキング", "電脳ランキング"])
    @is_guild()
    async def ranking(self, ctx) -> None:
        """電脳桜神社参拝の連続記録ランキングを表示するコマンドです。"""
        await ctx.defer()
        
        try:
            # DBから上位5名のストリーク情報を取得
            top_users = await execute_query(
                """
                SELECT user_id, current_streak, max_streak 
                FROM user_omikuji_streaks 
                WHERE guild_id = $1 AND current_streak > 0
                ORDER BY current_streak DESC, max_streak DESC 
                LIMIT 5
                """,
                ctx.guild.id, fetch_type='all'
            )
            
            e = discord.Embed(
                title="🏆 電脳桜神社 連続参拝ランキング", 
                color=0xFF69B4,
                description="みこちとホロメンたちも応援していますだにぇ！"
            )
            
            if not top_users:
                e.add_field(
                    name="まだランキングデータがありません",
                    value="電脳桜神社でおみくじを引いてランキングに参加しようだにぇ！",
                    inline=False
                )
            else:
                for rank, user_data in enumerate(top_users, start=1):
                    member = ctx.guild.get_member(user_data['user_id'])
                    if member:
                        rank_emoji = {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, "🏅")
                        e.add_field(
                            name=f"{rank_emoji} {rank}位: {member.display_name}",
                            value=f"連続参拝: {user_data['current_streak']}日\n最高記録: {user_data['max_streak']}日",
                            inline=False
                        )
            
            e.set_footer(text="毎日電脳桜神社に参拝して記録を伸ばそうだにぇ！")
            await ctx.send(embed=e)
            
        except Exception as e:
            logger.error(f"ランキング取得エラー: {e}")
            await ctx.send("申し訳ございません。ランキングの取得中にエラーが発生しました。")

    @commands.hybrid_group(name="cyber", aliases=["omkj", "holo"])
    @is_guild()
    async def cyber_group(self, ctx) -> None:
        """電脳桜神社の管理コマンドグループです。"""
        if ctx.invoked_subcommand is None:
            await ctx.send("電脳桜神社の管理コマンドです。`/cyber debug` や `/cyber add_fortune` などがありますだにぇ！")

    @cyber_group.command(name="debug")
    @is_owner()
    @is_guild()
    async def debug(self, ctx) -> None:
        """電脳桜神社のデバッグコマンドです。"""
        steps = [
            "にゃっはろ～！電脳桜神社へようこそだにぇ🌸",
            "エリート巫女みこちが式神の金時と一緒にお出迎え",
            "**みこち**「今日もデバッグで良いおみくじが引けるといいにぇ～」",
            "電脳乃神が見守る中、デバッグおみくじを開く",
        ]

        fortune = "電脳大吉!!"

        embed = discord.Embed(title="🌸 電脳桜神社デバッグ結果 🌸", color=0xFF69B4)
        embed.set_author(name="エリート運がN/A%アップ中だにぇ！\n電脳桜神社にて...")
        embed.set_thumbnail(url="https://images.frwi.net/data/images/7b54adae-c988-47f1-a090-625a7838f1c1.png")

        fm = await ctx.send(content=f"{ctx.author.mention}\nにゃっはろ～！デバッグおみくじを引きに行くにぇ...", embed=None)

        description_with_steps = ""
        for step in steps:
            await asyncio.sleep(2)
            description_with_steps += f"\n\n{step}"
            embed.description = description_with_steps
            await fm.edit(embed=embed)

        await asyncio.sleep(1)
        embed.description += f"\n\nデジタルおみくじには**{fortune}**と表示された"
        embed.set_footer(text="電脳桜神社のおみくじをありがとうございますだにぇ！\n連続参拝: N/A | デバッグモード")
        await fm.edit(embed=embed)
        
        if "電脳大吉" in fortune:
            await asyncio.sleep(1)
            embed.description += "\n\nみこちとホロメンたちからの特別な祝福が届いていますだにぇ..."
            await fm.edit(embed=embed)

    @cyber_group.command(name="add_fortune")
    @is_guild()
    @is_booster()
    async def add_fortune(self, ctx, fortune: str) -> None:
        """電脳桜神社のおみくじに新しい運勢を追加するコマンドです。"""
        await ctx.defer()
        
        try:
            # 既存の運勢をチェック
            existing = await execute_query(
                "SELECT id FROM omikuji_fortunes WHERE name = $1 OR display_name = $1",
                fortune, fetch_type='row'
            )
            
            if existing:
                await ctx.send(f"「{fortune}」はすでにホロ神社のおみくじに存在します。")
                return
            
            # 新しい運勢を追加
            await execute_query(
                """
                INSERT INTO omikuji_fortunes (name, display_name, weight, is_special, description)
                VALUES ($1, $2, 10, false, 'ホロリスが追加したカスタム運勢')
                """,
                fortune.lower().replace(' ', '_'), fortune, fetch_type='status'
            )
            
            await ctx.send(f"✨ 「{fortune}」を電脳桜神社のおみくじに追加しましただにぇ！")
            logger.info(f"User {ctx.author.id} added fortune: {fortune}")
            
        except Exception as e:
            logger.error(f"運勢追加エラー: {e}")
            await ctx.send("申し訳ございません。運勢の追加中にエラーが発生しました。")

    @cyber_group.command(name="remove_fortune")
    @is_guild()
    @is_booster()
    async def remove_fortune(self, ctx, fortune: str) -> None:
        """電脳桜神社のおみくじから運勢を削除するコマンドです。"""
        await ctx.defer()
        
        try:
            # 既存の運勢をチェック
            existing = await execute_query(
                "SELECT id FROM omikuji_fortunes WHERE name = $1 OR display_name = $1",
                fortune, fetch_type='row'
            )
            
            if not existing:
                await ctx.send(f"「{fortune}」は電脳桜神社のおみくじに存在しませんだにぇ。")
                return
            
            # 運勢を削除
            await execute_query(
                "DELETE FROM omikuji_fortunes WHERE name = $1 OR display_name = $1",
                fortune, fetch_type='status'
            )
            
            await ctx.send(f"🗑️ 「{fortune}」を電脳桜神社のおみくじから削除しましただにぇ。")
            logger.info(f"User {ctx.author.id} removed fortune: {fortune}")
            
        except Exception as e:
            logger.error(f"運勢削除エラー: {e}")
            await ctx.send("申し訳ございません。運勢の削除中にエラーが発生しました。")

    @cyber_group.command(name="toggle_streak_reset")
    @is_guild()
    @is_owner()
    async def toggle_streak_reset(self, ctx) -> None:
        """電脳桜神社の継続日数リセットを一時的に無効/有効にするコマンドです。"""
        await ctx.defer()
        self.streak_reset_enabled = not self.streak_reset_enabled
        status = "有効" if self.streak_reset_enabled else "無効"
        await ctx.send(f"電脳桜神社の継続日数リセットを{status}にしましただにぇ。")
        logger.info(f"Streak reset toggled to {status} by {ctx.author}")

    @cyber_group.command(name="list_fortunes")
    @is_guild()
    async def list_fortunes(self, ctx) -> None:
        """電脳桜神社のおみくじ運勢一覧を表示するコマンドです。"""
        await ctx.defer()
        
        try:
            fortunes = await execute_query(
                "SELECT display_name, description, is_special FROM omikuji_fortunes ORDER BY display_name",
                fetch_type='all'
            )
            
            if not fortunes:
                fortune_list = "現在、電脳桜神社には運勢が登録されていませんだにぇ。"
            else:
                fortune_lines = []
                for fortune in fortunes:
                    special_mark = "✨" if fortune[2] else "📜"
                    fortune_lines.append(f"{special_mark} {fortune[0]} - {fortune[1]}")
                fortune_list = "\n".join(fortune_lines)
            
            embed = discord.Embed(
                title="🌸 電脳桜神社 運勢一覧 🌸", 
                description=fortune_list, 
                color=0xFF69B4
            )
            embed.set_footer(text="みこちとホロメンたちが見守る電脳の運勢たちだにぇ")
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"運勢一覧取得エラー: {e}")
            await ctx.send("申し訳ございません。運勢一覧の取得中にエラーが発生しました。")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot == self.bot.user:
            return
        if message.content == "ギズみくじ":
            if message.guild is None:
                await message.channel.send("このコマンドはサーバーでのみ利用できます。")
                return
            if message.channel.id in [889075104481423461, 1096027971900428388]:
                ctx = await self.bot.get_context(message)
                await self.omikuji(ctx)

        if message.content == "運勢":
            if message.guild is None:
                await message.channel.send("このコマンドはサーバーでのみ利用できます。")
                return
            if message.channel.id in [889075104481423461, 1096027971900428388]:
                ctx = await self.bot.get_context(message)
                await self.fortune(ctx)

async def setup(bot):
    await bot.add_cog(HololiveOmikujiCog(bot))
