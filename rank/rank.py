import discord
from discord.ext import commands
from discord import app_commands
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import aiohttp
import asyncio
import random
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timedelta

from utils.logging import setup_logging
from utils.commands_help import is_guild, log_commands
from utils.database import execute_query
from config.setting import get_settings
from models.rank.level_config import LevelConfig
from models.rank.achievements import AchievementType
from utils.rank.quality_analyzer import analyze_message_quality
from utils.rank.formula_manager import formula_manager, calculate_level_from_xp
from utils.rank.achievement_manager import achievement_manager

logger = setup_logging("D")
settings = get_settings()


class RankCardGenerator:
    """美しいランクカード画像を生成するクラス"""
    
    def __init__(self, cache_dir: str = "cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.fonts = self._load_fonts()
        
    def _load_fonts(self) -> Dict[str, ImageFont.FreeTypeFont]:
        """フォントを事前読み込み"""
        fonts = {}
        font_configs = [
            ("large", 54),      # ユーザー名用（大きめ）
            ("medium", 36),     # レベル・統計用（中くらい）
            ("small", 28),      # XP数値用（小中）
            ("tiny", 22)        # 小さな詳細用（小）
        ]
        
        # 試行するフォントパス（優先順位順）
        font_candidates = [
            "resource/font/NotoSansJP-VariableFont_wght.ttf",  # 既存の日本語フォント
            "/System/Library/Fonts/Hiragino Sans GB.ttc",     # macOS日本語
            "/System/Library/Fonts/Arial.ttf",                # macOS英語
            "arial.ttf",                                       # 汎用
            "helvetica.ttf",                                   # 汎用
        ]
        
        for name, size in font_configs:
            font_loaded = False
            
            # 優先順位でフォントを試行
            for font_path in font_candidates:
                try:
                    if Path(font_path).exists():
                        fonts[name] = ImageFont.truetype(str(Path(font_path).resolve()), size)
                        logger.info(f"フォント読み込み成功: {name} = {font_path} ({size}px)")
                        font_loaded = True
                        break
                    else:
                        # パスが存在しない場合はスキップ
                        continue
                except Exception as e:
                    # このフォントでエラーが出た場合は次を試行
                    logger.debug(f"フォント試行失敗: {font_path} - {e}")
                    continue
            
            # 全てのフォントで失敗した場合の最終フォールバック
            if not font_loaded:
                try:
                    # PIL内蔵のデフォルトフォントを直接的にサイズ指定で作成
                    fonts[name] = ImageFont.load_default()
                    logger.warning(f"全フォント読み込み失敗、デフォルトフォントを使用: {name} ({size}px指定だが反映されない可能性)")
                except Exception as e:
                    # 緊急フォールバック
                    fonts[name] = ImageFont.load_default()
                    logger.error(f"デフォルトフォント読み込みも失敗: {name} - {e}")
        
        return fonts
    
    def get_cache_key(self, user_id: int, level: int, xp: int, rank: int, 
                     username: str, avatar_url: str) -> str:
        """キャッシュキーを生成"""
        data = f"{user_id}-{level}-{xp}-{rank}-{username}-{hash(avatar_url)}"
        return hashlib.md5(data.encode()).hexdigest()
    
    async def get_cached_card(self, cache_key: str) -> Optional[bytes]:
        """キャッシュから画像を取得"""
        cache_file = self.cache_dir / f"{cache_key}.png"
        if cache_file.exists():
            # キャッシュの有効期限チェック（1時間）
            cache_time = datetime.fromtimestamp(cache_file.stat().st_mtime)
            if datetime.now() - cache_time < timedelta(hours=1):
                return cache_file.read_bytes()
        return None
    
    async def cache_card(self, cache_key: str, image_data: bytes):
        """画像をキャッシュに保存"""
        cache_file = self.cache_dir / f"{cache_key}.png"
        cache_file.write_bytes(image_data)
    
    async def download_avatar(self, session: aiohttp.ClientSession, 
                            avatar_url: str, size: int = 150) -> Image.Image:
        """アバター画像をダウンロードして処理"""
        try:
            async with session.get(avatar_url) as resp:
                if resp.status == 200:
                    avatar_data = await resp.read()
                    avatar = Image.open(BytesIO(avatar_data))
                else:
                    avatar = self._create_default_avatar(size)
        except Exception as e:
            logger.warning(f"アバターダウンロードエラー: {e}")
            avatar = self._create_default_avatar(size)
        
        # 円形アバターに変換
        avatar = avatar.convert("RGBA")
        avatar = avatar.resize((size, size), Image.LANCZOS)
        
        # 円形マスクを作成
        mask = Image.new("L", (size, size), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, size, size), fill=255)
        
        # マスクを適用
        avatar.putalpha(mask)
        return avatar
    
    def _create_default_avatar(self, size: int) -> Image.Image:
        """デフォルトアバターを作成"""
        avatar = Image.new("RGBA", (size, size), (114, 137, 218, 255))
        draw = ImageDraw.Draw(avatar)
        
        # 簡単な人型アイコンを描画
        center_x, center_y = size // 2, size // 2
        # 頭部
        draw.ellipse([center_x-15, center_y-25, center_x+15, center_y-5], 
                    fill=(255, 255, 255, 200))
        # 体部
        draw.ellipse([center_x-20, center_y-5, center_x+20, center_y+25], 
                    fill=(255, 255, 255, 200))
        
        return avatar
    
    def create_gradient_background(self, width: int, height: int, 
                                 start_color: Tuple[int, int, int] = (114, 72, 180), 
                                 end_color: Tuple[int, int, int] = (236, 150, 180)) -> Image.Image:
        """グラデーション背景を作成"""
        gradient = Image.new("RGB", (width, height))
        draw = ImageDraw.Draw(gradient)
        
        for y in range(height):
            # カスタム色でのグラデーション
            ratio = y / height
            r = int(start_color[0] + (end_color[0] - start_color[0]) * ratio)
            g = int(start_color[1] + (end_color[1] - start_color[1]) * ratio)
            b = int(start_color[2] + (end_color[2] - start_color[2]) * ratio)
            
            draw.line([(0, y), (width, y)], fill=(r, g, b))
        
        return gradient.convert("RGBA")
    
    async def generate_rank_card(self, user_data: Dict[str, Any]) -> BytesIO:
        """ランクカード画像を生成（非同期）"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._generate_rank_card_sync, user_data)
    
    def _generate_rank_card_sync(self, user_data: Dict[str, Any]) -> BytesIO:
        """ランクカード画像を生成（同期版） - 美しいデザイン仕様対応"""
        width, height = 1000, 350
        
        # 背景画像の読み込み
        try:
            background_path = Path("resource/images/rank-bg.png")
            if background_path.exists():
                card = Image.open(background_path).convert("RGBA")
                card = card.resize((width, height), Image.LANCZOS)
            else:
                # フォールバック: グラデーション背景
                card = self.create_gradient_background(width, height, (139, 92, 246), (236, 72, 153))
                card = card.convert("RGBA")
        except Exception as e:
            logger.warning(f"背景画像読み込みエラー: {e}")
            card = self.create_gradient_background(width, height, (139, 92, 246), (236, 72, 153))
            card = card.convert("RGBA")
        
        draw = ImageDraw.Draw(card)
        
        # アバター部分の処理（左側、250x250px）
        avatar_size = 250
        avatar_x, avatar_y = 40, 40
        
        if 'avatar' in user_data:
            avatar = user_data['avatar']
            
            # 装飾リング（金色/オレンジ）
            ring_size = avatar_size + 10
            ring_x, ring_y = avatar_x - 5, avatar_y - 5
            
            # 外側リング
            draw.ellipse([ring_x, ring_y, ring_x + ring_size, ring_y + ring_size], 
                        outline=(245, 158, 11, 255), width=4)
            
            # 内側微光効果
            draw.ellipse([ring_x + 2, ring_y + 2, ring_x + ring_size - 2, ring_y + ring_size - 2], 
                        outline=(255, 255, 255, 100), width=1)
            
            # アバター配置
            card.paste(avatar, (avatar_x, avatar_y), avatar)
        
        # レベル表示（アバター下部）
        level_text = f"Lv. {user_data['level']}"
        level_bbox = draw.textbbox((0, 0), level_text, font=self.fonts['medium'])
        level_width = level_bbox[2] - level_bbox[0]
        level_x = avatar_x + (avatar_size - level_width) // 2
        draw.text((level_x, avatar_y + avatar_size + 10), level_text, 
                 font=self.fonts['medium'], fill=(255, 255, 255), 
                 stroke_width=1, stroke_fill=(0, 0, 0))
        
        # ユーザー情報エリア（右側）
        info_start_x = 320
        
        # ユーザー名（大きく、ボールド）
        username = user_data['username'][:20]
        draw.text((info_start_x, 60), username, font=self.fonts['large'], 
                 fill=(255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0))
        
        # 統計情報エリア
        stats_y = 130
        
        # Rank表示（左側）
        rank_text = f"Rank #{user_data['rank']:,}"
        draw.text((info_start_x, stats_y), rank_text, 
                 font=self.fonts['medium'], fill=(245, 158, 11), 
                 stroke_width=1, stroke_fill=(0, 0, 0))
        
        # Total XP表示（右側）
        total_text = f"Total {user_data['total_xp']:,}"
        total_bbox = draw.textbbox((0, 0), total_text, font=self.fonts['medium'])
        total_width = total_bbox[2] - total_bbox[0]
        draw.text((width - total_width - 50, stats_y), total_text, 
                 font=self.fonts['medium'], fill=(229, 231, 235), 
                 stroke_width=1, stroke_fill=(0, 0, 0))
        
        # プログレスバー（美しいデザイン）
        bar_width = 600
        bar_height = 25
        bar_x = info_start_x
        bar_y = stats_y + 40
        
        # プログレスバー背景（角丸）
        bar_bg = Image.new("RGBA", (bar_width, bar_height), (47, 49, 54, 255))
        
        # 進捗部分のグラデーション
        if user_data['required_level_xp'] > 0:
            progress = min(user_data['current_level_xp'] / user_data['required_level_xp'], 1.0)
            progress_width = int(bar_width * progress)
            if progress_width > 0:
                # 青から緑へのグラデーション
                progress_gradient = self.create_gradient_background(
                    progress_width, bar_height, (16, 185, 129), (59, 130, 246)
                )
                bar_bg.paste(progress_gradient, (0, 0))
        
        # 角丸マスク
        mask = Image.new("L", (bar_width, bar_height), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle([0, 0, bar_width, bar_height], 
                                   radius=bar_height//2, fill=255)
        bar_bg.putalpha(mask)
        
        # プログレスバーを貼り付け
        card.paste(bar_bg, (bar_x, bar_y), bar_bg)
        
        # XP数値表示（プログレスバー上に中央配置）
        xp_text = f"{user_data['current_level_xp']:,} / {user_data['required_level_xp']:,}"
        xp_bbox = draw.textbbox((0, 0), xp_text, font=self.fonts['small'])
        xp_width = xp_bbox[2] - xp_bbox[0]
        xp_x = bar_x + (bar_width - xp_width) // 2
        draw.text((xp_x, bar_y + 30), xp_text, 
                 font=self.fonts['small'], fill=(200, 200, 200))
        
        # 美しいドロップシャドウ効果を追加
        shadow_offset = 2
        for text_info in [
            (username, (info_start_x - shadow_offset, 60 + shadow_offset), self.fonts['large']),
            (rank_text, (info_start_x - shadow_offset, stats_y + shadow_offset), self.fonts['medium']),
            (total_text, (width - total_width - 50 - shadow_offset, stats_y + shadow_offset), self.fonts['medium'])
        ]:
            text, pos, font = text_info
            draw.text(pos, text, font=font, fill=(0, 0, 0, 128))
        
        # 画像をバイナリに変換
        buffer = BytesIO()
        card.save(buffer, format='PNG', optimize=True, quality=95)
        buffer.seek(0)
        return buffer


class LevelDatabase:
    """レベリングシステムのデータベースクラス"""
    
    def __init__(self):
        pass
    
    async def initialize(self):
        """データベース初期化"""
        # メインテーブル作成
        await execute_query('''
            CREATE TABLE IF NOT EXISTS leaderboard (
                guild_id BIGINT NOT NULL,
                member_id BIGINT NOT NULL,
                member_name TEXT NOT NULL,
                member_level INTEGER NOT NULL DEFAULT 1,
                member_xp INTEGER NOT NULL DEFAULT 0,
                member_total_xp INTEGER NOT NULL DEFAULT 0,
                last_message_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (guild_id, member_id)
            )
        ''', fetch_type='status')
        
        # ロール報酬テーブル
        await execute_query('''
            CREATE TABLE IF NOT EXISTS role_rewards (
                guild_id BIGINT NOT NULL,
                role_id BIGINT NOT NULL,
                level_requirement INTEGER NOT NULL,
                role_name TEXT,
                PRIMARY KEY (guild_id, role_id)
            )
        ''', fetch_type='status')
        
        # インデックス作成
        await execute_query('''
            CREATE INDEX IF NOT EXISTS idx_leaderboard_guild_xp 
            ON leaderboard(guild_id, member_total_xp DESC)
        ''', fetch_type='status')
        
        logger.info("レベリングシステムのテーブルが初期化されました")
    
    async def calculate_level(self, guild_id: int, total_xp: int) -> int:
        """総XPからレベルを計算（カスタム公式対応）"""
        if total_xp <= 0:
            return 1
        try:
            level, _, _ = await calculate_level_from_xp(guild_id, total_xp)
            return level
        except Exception as e:
            logger.error(f"レベル計算エラー: {e}")
            # フォールバック：従来の計算式
            return int(0.04 * (total_xp ** 0.5)) + 1
    
    async def get_xp_for_level(self, guild_id: int, level: int) -> int:
        """指定レベルに必要な総XPを計算（カスタム公式対応）"""
        if level <= 1:
            return 0
        try:
            return await formula_manager.get_xp_required_for_level(guild_id, level)
        except Exception as e:
            logger.error(f"XP計算エラー: {e}")
            # フォールバック：従来の計算式
            return int(((level - 1) / 0.04) ** 2)
    
    async def get_current_level_xp(self, guild_id: int, total_xp: int) -> Tuple[int, int]:
        """現在のレベル内XPと次レベルまでの必要XPを計算（カスタム公式対応）"""
        try:
            # calculate_level_from_xpは(レベル, 現在レベル内XP, 次レベル必要XP)を返す
            level_info = await calculate_level_from_xp(guild_id, total_xp)
            if len(level_info) == 3:
                level, current_level_xp, required_xp = level_info
                return current_level_xp, required_xp
            else:
                # 予期しない戻り値の場合はフォールバックを使用
                raise ValueError(f"予期しない戻り値: {level_info}")
        except Exception as e:
            logger.error(f"レベル内XP計算エラー: {e}")
            # フォールバック：従来の計算
            level = int(0.04 * (total_xp ** 0.5)) + 1
            current_level_start_xp = int(((level - 1) / 0.04) ** 2)
            next_level_xp = int(((level) / 0.04) ** 2)
            current_level_xp = total_xp - current_level_start_xp
            required_xp = next_level_xp - current_level_start_xp
            return current_level_xp, required_xp
    
    async def get_or_create_member(self, guild_id: int, member_id: int, 
                                  member_name: str) -> Dict[str, Any]:
        """メンバー情報を取得または作成"""
        result = await execute_query(
            "SELECT * FROM leaderboard WHERE guild_id = $1 AND member_id = $2",
            guild_id, member_id, fetch_type='row'
        )
        
        if result:
            return dict(result)
        else:
            await execute_query(
                "INSERT INTO leaderboard (guild_id, member_id, member_name) VALUES ($1, $2, $3)",
                guild_id, member_id, member_name, fetch_type='status'
            )
            return {
                'guild_id': guild_id,
                'member_id': member_id,
                'member_name': member_name,
                'member_level': 1,
                'member_xp': 0,
                'member_total_xp': 0
            }
    
    async def add_xp(self, guild_id: int, member_id: int, member_name: str, 
                    xp_gain: int) -> Tuple[bool, int]:
        """XPを追加し、レベルアップをチェック（カスタム公式対応）"""
        try:
            member_data = await self.get_or_create_member(guild_id, member_id, member_name)
            
            old_level = member_data['member_level']
            new_total_xp = member_data['member_total_xp'] + xp_gain
            new_level = await self.calculate_level(guild_id, new_total_xp)
            
            current_level_xp, required_xp = await self.get_current_level_xp(guild_id, new_total_xp)
            
            await execute_query('''
                UPDATE leaderboard 
                SET member_xp = $1, member_total_xp = $2, member_level = $3, 
                    last_message_time = CURRENT_TIMESTAMP
                WHERE guild_id = $4 AND member_id = $5
            ''', current_level_xp, new_total_xp, new_level, guild_id, member_id, fetch_type='status')
            
            level_up = new_level > old_level
            return level_up, new_level
            
        except Exception as e:
            logger.error(f"XP追加エラー (Guild: {guild_id}, Member: {member_id}): {e}")
            # フォールバック: 最低限の処理を実行
            return False, member_data.get('member_level', 1) if 'member_data' in locals() else 1
    
    async def get_member_rank(self, guild_id: int, member_id: int) -> int:
        """メンバーのランクを取得"""
        result = await execute_query('''
            SELECT COUNT(*) + 1 as rank
            FROM leaderboard l2 
            WHERE l2.guild_id = $1 
            AND l2.member_total_xp > (
                SELECT member_total_xp 
                FROM leaderboard 
                WHERE guild_id = $1 AND member_id = $2
            )
        ''', guild_id, member_id, fetch_type='row')
        
        return result['rank'] if result else 1
    
    async def get_leaderboard(self, guild_id: int, limit: int = 10, 
                            offset: int = 0) -> List[Dict[str, Any]]:
        """リーダーボードを取得"""
        result = await execute_query('''
            SELECT member_id, member_name, member_level, member_total_xp,
                   ROW_NUMBER() OVER (ORDER BY member_total_xp DESC, member_level DESC) as rank
            FROM leaderboard 
            WHERE guild_id = $1
            ORDER BY member_total_xp DESC, member_level DESC
            LIMIT $2 OFFSET $3
        ''', guild_id, limit, offset, fetch_type='all')
        
        return [dict(row) for row in result] if result else []


class LevelingSystem(commands.Cog, name="レベリング"):
    """Discord.py レベリングシステム（AI設定対応）"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = LevelDatabase()
        self.rank_generator = RankCardGenerator()
        self.xp_cooldowns: Dict[str, float] = {}
        self.achievement_manager = achievement_manager
        
        # デフォルト設定（AI設定がない場合のフォールバック）
        self.default_config = LevelConfig(
            base_xp=15,
            base_cooldown=60,
            global_multiplier=1.0
        )
        
        # 設定キャッシュ（パフォーマンス向上のため）
        self.config_cache: Dict[int, Tuple[LevelConfig, float]] = {}
        self.cache_ttl = 300  # 5分間キャッシュ
        
        # スパム防止
        self.message_cache: Dict[str, List[Tuple[str, float]]] = {}
    
    async def cog_load(self):
        """Cog読み込み時の処理"""
        await self.db.initialize()
        logger.info("レベリングシステム（AI設定対応）が正常に読み込まれました")
    
    async def get_guild_config(self, guild_id: int) -> LevelConfig:
        """ギルドのAI設定を取得（キャッシュ対応）"""
        import time
        current_time = time.time()
        
        # キャッシュチェック
        if guild_id in self.config_cache:
            config, cached_time = self.config_cache[guild_id]
            if current_time - cached_time < self.cache_ttl:
                return config
        
        # データベースから設定を読み込み
        try:
            query = "SELECT config_data FROM level_configs WHERE guild_id = $1"
            result = await execute_query(query, guild_id)
            
            if result and len(result) > 0:
                config_json = result[0]["config_data"]
                config = LevelConfig.model_validate_json(config_json)
                logger.info(f"Guild {guild_id}: AI設定を読み込みました")
            else:
                config = self.default_config
                logger.info(f"Guild {guild_id}: デフォルト設定を使用します")
            
            # キャッシュに保存
            self.config_cache[guild_id] = (config, current_time)
            return config
            
        except Exception as e:
            logger.error(f"Guild {guild_id}: 設定読み込みエラー {e}")
            return self.default_config
    
    def invalidate_config_cache(self, guild_id: int):
        """設定キャッシュを無効化"""
        if guild_id in self.config_cache:
            del self.config_cache[guild_id]
            logger.info(f"Guild {guild_id}: 設定キャッシュを無効化しました")
    
    async def calculate_xp_gain(self, guild_id: int, channel_id: int, user_roles: List[int], 
                              message_content: str, current_time: float, 
                              enable_quality_analysis: bool = True) -> Tuple[int, int, Optional[float]]:
        """AI設定＋品質分析に基づいてXP付与量・クールダウン・品質倍率を計算"""
        config = await self.get_guild_config(guild_id)
        
        if not config.enabled:
            return 0, config.base_cooldown
        
        # メッセージ長を計算
        message_length = len(message_content)
        
        # ベースXP
        base_xp = config.base_xp
        
        # チャンネル倍率
        channel_multiplier = 1.0
        for channel_config in config.channels:
            if (channel_config.channel_id and str(channel_id) == channel_config.channel_id) or \
               (channel_config.channel_name and str(channel_id) in [str(ch.id) for ch in self.bot.get_all_channels() if ch.name == channel_config.channel_name]):
                channel_multiplier = channel_config.multiplier
                if channel_config.base_xp:
                    base_xp = channel_config.base_xp
                break
        
        # ロール倍率・ボーナス
        role_multiplier = 1.0
        role_bonus = 0
        for role_config in config.roles:
            if role_config.role_id and int(role_config.role_id) in user_roles:
                role_multiplier = max(role_multiplier, role_config.multiplier)
                role_bonus = max(role_bonus, role_config.bonus_xp)
        
        # 時間帯倍率
        time_multiplier = self._get_time_multiplier(config, current_time)
        
        # AI品質分析による倍率
        quality_multiplier = 1.0
        message_length = len(message_content)
        
        if enable_quality_analysis and message_length >= 10:
            try:
                # チャンネル名を取得
                channel = self.bot.get_channel(channel_id)
                channel_name = channel.name if channel else None
                
                # AI品質分析実行
                quality_result = await analyze_message_quality(
                    message_content, 
                    channel_name=channel_name,
                    guild_context=f"Guild ID: {guild_id}"
                )
                
                if quality_result.success and quality_result.analysis:
                    quality_multiplier = quality_result.analysis.xp_multiplier
                    logger.info(f"品質分析完了 - カテゴリ: {quality_result.analysis.category}, "
                               f"品質倍率: {quality_multiplier:.2f}, "
                               f"総合スコア: {quality_result.analysis.quality_scores.overall:.2f}")
                else:
                    logger.warning(f"品質分析失敗: {quality_result.error_message}")
                    
            except Exception as e:
                logger.error(f"品質分析エラー: {e}")
                # エラー時はデフォルト値を使用
        
        # メッセージ長ボーナス（基本実装）
        length_multiplier = 1.0
        if message_length > 100:
            length_multiplier = 1.1
        elif message_length > 50:
            length_multiplier = 1.05
        
        # 最終XP計算（品質分析倍率を含む）
        final_xp = int(
            base_xp * 
            config.global_multiplier * 
            channel_multiplier * 
            role_multiplier * 
            time_multiplier * 
            length_multiplier * 
            quality_multiplier
        ) + role_bonus
        
        # クールダウン（チャンネル固有またはデフォルト）
        cooldown = config.base_cooldown
        for channel_config in config.channels:
            if (channel_config.channel_id and str(channel_id) == channel_config.channel_id) and \
               channel_config.cooldown_seconds:
                cooldown = channel_config.cooldown_seconds
                break
        
        return max(final_xp, 0), cooldown, quality_multiplier
    
    def _get_time_multiplier(self, config: LevelConfig, current_time: float) -> float:
        """現在時刻に基づく倍率を計算"""
        from datetime import datetime, timezone
        
        now = datetime.fromtimestamp(current_time, tz=timezone.utc)
        current_day = now.strftime('%A').lower()  # monday, tuesday, etc.
        current_time_str = now.strftime('%H:%M')
        
        # 曜日マッピング
        weekday_mapping = {
            'weekday': ['monday', 'tuesday', 'wednesday', 'thursday', 'friday'],
            'weekend': ['saturday', 'sunday']
        }
        
        for time_window in config.time_windows:
            # 曜日チェック
            target_days = []
            if isinstance(time_window.day, list):
                target_days = time_window.day
            else:
                day = time_window.day
                if day in weekday_mapping:
                    target_days = weekday_mapping[day]
                else:
                    target_days = [day]
            
            if current_day not in target_days:
                continue
            
            # 時間チェック（簡易実装）
            if time_window.start_time <= current_time_str <= time_window.end_time:
                return time_window.multiplier
        
        return 1.0
    
    def cog_check(self, ctx):
        """Cog全体のチェック"""
        return ctx.guild is not None
    
    async def is_spam(self, guild_id: int, user_id: int, message_content: str) -> bool:
        """AI設定に基づくスパムメッセージチェック"""
        config = await self.get_guild_config(guild_id)
        spam_filter = config.spam_filter
        
        current_time = asyncio.get_event_loop().time()
        user_key = str(user_id)
        
        # メッセージ長チェック
        if len(message_content) < spam_filter.min_length or \
           len(message_content) > spam_filter.max_length:
            return True
        
        # 禁止単語チェック
        message_lower = message_content.lower()
        for banned_word in spam_filter.banned_words:
            if banned_word.lower() in message_lower:
                logger.info(f"User {user_id}: 禁止単語検出 '{banned_word}'")
                return True
        
        # メッセージキャッシュ管理
        if user_key not in self.message_cache:
            self.message_cache[user_key] = []
        
        # 古いメッセージを削除（30秒ウィンドウ）
        window = 30
        self.message_cache[user_key] = [
            (msg, timestamp) for msg, timestamp in self.message_cache[user_key]
            if current_time - timestamp < window
        ]
        
        # 繰り返しメッセージチェック
        recent_messages = [msg for msg, _ in self.message_cache[user_key]]
        if len(recent_messages) >= 3:
            # 類似性チェック（簡易実装）
            last_messages = recent_messages[-3:]
            unique_ratio = len(set(last_messages)) / len(last_messages)
            if unique_ratio <= spam_filter.repetition_threshold:
                logger.info(f"User {user_id}: 繰り返しメッセージ検出")
                return True
        
        # 短時間大量投稿チェック（5メッセージ/30秒）
        if len(self.message_cache[user_key]) >= 5:
            logger.info(f"User {user_id}: 短時間大量投稿検出")
            return True
        
        # メッセージをキャッシュに追加
        self.message_cache[user_key].append((message_content[:100], current_time))
        
        return False
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """AI設定対応メッセージイベントリスナー"""
        if message.author.bot or not message.guild:
            return
        
        try:
            current_time = asyncio.get_event_loop().time()
            
            # AI設定ベースのスパムチェック
            if await self.is_spam(message.guild.id, message.author.id, message.content):
                return
            
            # ユーザーロール取得
            user_roles = [role.id for role in message.author.roles]
            
            # AI設定に基づくXP計算
            xp_gain, cooldown = await self.calculate_xp_gain(
                message.guild.id, 
                message.channel.id, 
                user_roles,
                message.content,
                current_time
            )
            
            # XP付与が無効な場合はスキップ
            if xp_gain <= 0:
                return
            
            # クールダウンチェック（動的設定対応）
            user_key = f"{message.author.id}_{message.guild.id}"
            
            if user_key in self.xp_cooldowns:
                time_since_last = current_time - self.xp_cooldowns[user_key]
                if time_since_last < cooldown:
                    return
            
            # XP付与実行
            self.xp_cooldowns[user_key] = current_time
            
            level_up, new_level = await self.db.add_xp(
                message.guild.id, message.author.id, message.author.display_name, xp_gain
            )
            
            # アチーブメント進捗更新（メッセージ送信・XP獲得・レベルアップ関連）
            await self._update_achievement_progress(
                message.guild.id, message.author.id, 
                xp_gain, new_level if level_up else None,
                message_content=message.content
            )
            
            # レベルアップ処理
            if level_up:
                await self.handle_level_up(message.author, new_level, message.channel)
                logger.info(f"Guild {message.guild.id}, User {message.author.id}: "
                           f"レベルアップ {new_level} (XP: {xp_gain})")
            else:
                logger.debug(f"Guild {message.guild.id}, User {message.author.id}: "
                            f"XP付与 {xp_gain}")
        
        except Exception as e:
            logger.error(f"メッセージ処理エラー (Guild: {message.guild.id}): {e}")
            # エラー時はデフォルト動作を実行
            try:
                xp_gain = random.randint(10, 20)  # フォールバック値
                level_up, new_level = await self.db.add_xp(
                    message.guild.id, message.author.id, message.author.display_name, xp_gain
                )
                logger.info(f"Guild {message.guild.id}, User {message.author.id}: "
                           f"フォールバックXP付与 {xp_gain}")
            except Exception as fallback_error:
                logger.error(f"フォールバック処理エラー: {fallback_error}")
    
    async def handle_level_up(self, member: discord.Member, new_level: int, 
                            channel: discord.TextChannel):
        """レベルアップ処理"""
        # アチーブメント新規達成チェック
        newly_completed = await self.achievement_manager.update_achievement_progress(
            member.guild.id, member.id, AchievementType.LEVEL, 0  # レベル系は絶対値で判定
        )
        
        embed = discord.Embed(
            title="🎉 レベルアップ！",
            description=f"{member.mention} がレベル **{new_level}** に到達しました！",
            color=discord.Color.green()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="新しいレベル", value=str(new_level), inline=True)
        
        # 新規アチーブメント達成があればメッセージに追加
        if newly_completed:
            achievement_names = []
            for ach_id in newly_completed:
                ach = self.achievement_manager.achievement_cache.get(ach_id)
                if ach:
                    achievement_names.append(f"🏆 {ach.name}")
            
            if achievement_names:
                embed.add_field(
                    name="🎊 新アチーブメント達成！",
                    value="\n".join(achievement_names),
                    inline=False
                )
        
        try:
            await channel.send(embed=embed)
            
            # ロール報酬チェック
            await self.check_role_rewards(member, new_level)
        
        except discord.HTTPException as e:
            logger.warning(f"レベルアップメッセージ送信エラー: {e}")
    
    async def check_role_rewards(self, member: discord.Member, level: int):
        """ロール報酬チェック（基本実装）"""
        # 簡単な実装例
        role_rewards = {
            5: "Bronze Member",
            10: "Silver Member",
            20: "Gold Member",
            50: "Platinum Member"
        }
        
        if level in role_rewards:
            role_name = role_rewards[level]
            role = discord.utils.get(member.guild.roles, name=role_name)
            
            if role:
                try:
                    await member.add_roles(role, reason=f"レベル {level} 到達報酬")
                except discord.HTTPException:
                    pass
    
    @commands.hybrid_command(name="rank", description="ランク情報を表示します")
    @app_commands.describe(user="確認するユーザー（省略可）")
    @is_guild()
    @log_commands()
    async def rank(self, ctx: commands.Context, user: Optional[discord.Member] = None):
        """ランクコマンド"""
        try:
            await ctx.defer()
            
            target = user or ctx.author
            
            # データベースからユーザー情報取得
            member_data = await self.db.get_or_create_member(
                ctx.guild.id, target.id, target.display_name
            )
            
            if member_data['member_total_xp'] == 0:
                embed = discord.Embed(
                    title="📊 データなし",
                    description=f"{target.mention} はまだメッセージを投稿していないか、XPを獲得していません！\n\n💬 **チャットでメッセージを送信してXPを獲得しましょう！**",
                    color=discord.Color.orange()
                )
                embed.add_field(
                    name="💡 ヒント",
                    value="メッセージを投稿するとXPを獲得できます。\n詳細は `/help rank` をご確認ください。",
                    inline=False
                )
                await ctx.send(embed=embed, ephemeral=True)
                return
                
        except Exception as db_error:
            logger.error(f"ランクコマンド - データベースエラー (Guild: {ctx.guild.id}): {db_error}")
            embed = discord.Embed(
                title="❌ エラーが発生しました",
                description="申し訳ございません。データベースの接続に問題があります。\n少し時間をおいて再度お試しください。",
                color=discord.Color.red()
            )
            embed.add_field(
                name="🔧 問題が続く場合",
                value="サーバー管理者にお知らせください。",
                inline=False
            )
            await ctx.send(embed=embed, ephemeral=True)
            return
        
        try:
            # ランク取得
            rank = await self.db.get_member_rank(ctx.guild.id, target.id)
            
            # 現在レベル内XP計算
            current_level_xp, required_level_xp = await self.db.get_current_level_xp(
                ctx.guild.id, member_data['member_total_xp']
            )
            
            # 画像生成用データ準備
            user_data = {
                'username': target.display_name,
                'level': member_data['member_level'],
                'rank': rank,
                'current_level_xp': current_level_xp,
                'required_level_xp': required_level_xp,
                'total_xp': member_data['member_total_xp']
            }
            
            # キャッシュキー生成
            cache_key = self.rank_generator.get_cache_key(
                target.id, member_data['member_level'], current_level_xp, rank,
                target.display_name, str(target.display_avatar.url)
            )
            
            # キャッシュチェック
            cached_image = await self.rank_generator.get_cached_card(cache_key)
            if cached_image:
                file = discord.File(BytesIO(cached_image), filename="rank.png")
                await ctx.send(file=file)
                return
                
        except Exception as calc_error:
            logger.error(f"ランク計算エラー (Guild: {ctx.guild.id}): {calc_error}")
            # フォールバック: シンプルなテキスト表示
            embed = discord.Embed(
                title="❌ 計算エラー",
                description="データの計算中にエラーが発生しました。基本情報のみ表示します。",
                color=discord.Color.red()
            )
            embed.add_field(name="レベル", value=str(member_data.get('member_level', '不明')), inline=True)
            embed.add_field(name="総XP", value=f"{member_data.get('member_total_xp', 0):,}", inline=True)
            embed.set_thumbnail(url=target.display_avatar.url)
            await ctx.send(embed=embed, ephemeral=True)
            return
        
        # 「生成中」メッセージを改善
        progress_embed = discord.Embed(
            title="🎨 ランクカード生成中...",
            description="🔄 アバターをダウンロード中...",
            color=discord.Color.blue()
        )
        thinking_msg = await ctx.send(embed=progress_embed)
        
        try:
            # アバターダウンロード
            async with aiohttp.ClientSession() as session:
                # 進捗更新
                progress_embed.description = "🎨 ランクカードを描画中..."
                await thinking_msg.edit(embed=progress_embed)
                
                avatar = await self.rank_generator.download_avatar(
                    session, str(target.display_avatar.url)
                )
                user_data['avatar'] = avatar
            
            # ランクカード生成
            card_buffer = await self.rank_generator.generate_rank_card(user_data)
            
            # キャッシュに保存
            await self.rank_generator.cache_card(cache_key, card_buffer.getvalue())
            
            # 最終進捗更新
            progress_embed.description = "✅ 完成！ランクカードを表示します。"
            progress_embed.color = discord.Color.green()
            await thinking_msg.edit(embed=progress_embed)
            
            # ファイル送信
            card_buffer.seek(0)
            file = discord.File(card_buffer, filename=f"{target.display_name}_rank.png")
            
            # 元のメッセージを編集
            await thinking_msg.edit(content="", embed=None, attachments=[file])
        
        except Exception as e:
            logger.error(f"ランクカード生成エラー: {e}")
            
            # エラー時の改善されたフォールバック表示
            error_embed = discord.Embed(
                title=f"📈 {target.display_name} のランク情報",
                description="🎨 **画像生成に失敗しましたが、データをテキストで表示します。**",
                color=discord.Color.gold()
            )
            
            # メイン統計
            stats_text = f"""
            **レベル:** {member_data['member_level']:,} 🎆
            **ランク:** #{rank:,} 🏆
            **現在XP:** {current_level_xp:,} / {required_level_xp:,}
            **総XP:** {member_data['member_total_xp']:,} ⭐
            """
            error_embed.add_field(name="📊 ステータス", value=stats_text, inline=False)
            
            # 進捗バー
            progress_percent = (current_level_xp / required_level_xp) * 100 if required_level_xp > 0 else 100
            progress_filled = int(progress_percent / 5)
            progress_bar = "🟦" * progress_filled + "⬜" * (20 - progress_filled)
            
            error_embed.add_field(
                name=f"🔄 レベル進捗 ({progress_percent:.1f}%)",
                value=progress_bar,
                inline=False
            )
            
            # 次レベルまでの情報
            remaining_xp = required_level_xp - current_level_xp
            if remaining_xp > 0:
                error_embed.add_field(
                    name=f"🎯 次レベルまであと {remaining_xp:,} XP",
                    value=f"レベル {member_data['member_level'] + 1} まであと少し！",
                    inline=False
                )
            
            error_embed.set_thumbnail(url=target.display_avatar.url)
            error_embed.set_footer(
                text="🛠️ 画像生成機能は一時的に使用できません | データは正常です",
                icon_url="https://cdn.discordapp.com/emojis/1234567890123456789.png"  # オプション
            )
            
            await thinking_msg.edit(content="", embed=error_embed)
    
    @commands.hybrid_command(name="leaderboard", aliases=["lb", "top"], 
                           description="サーバーリーダーボードを表示")
    @app_commands.describe(page="ページ番号（デフォルト: 1）")
    @is_guild()
    @log_commands()
    async def leaderboard(self, ctx: commands.Context, page: int = 1):
        """リーダーボードコマンド"""
        try:
            await ctx.defer()
            
            if page < 1:
                page = 1
                
            # ページ範囲の妥当性チェック
            if page > 100:  # 最大100ページに制限
                embed = discord.Embed(
                    title="❌ ページ番号エラー",
                    description="ページ番号は1から100までの範囲で指定してください。",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed, ephemeral=True)
                return
            
            offset = (page - 1) * 10
            leaderboard_data = await self.db.get_leaderboard(ctx.guild.id, 10, offset)
            
            if not leaderboard_data:
                if page == 1:
                    # 1ページ目でデータがない場合
                    embed = discord.Embed(
                        title="📊 空のリーダーボード",
                        description="🎯 **まだ誰もXPを獲得していません！**\n\n💬 チャットでメッセージを送信して、サーバーで最初のランクを獲得しましょう！",
                        color=discord.Color.orange()
                    )
                    embed.add_field(
                        name="🚀 始め方",
                        value="メッセージを投稿するとXPを獲得できます。\n活動的なメンバーがリーダーボードに表示されます！",
                        inline=False
                    )
                else:
                    # 指定されたページにデータがない場合
                    embed = discord.Embed(
                        title="📄 ページが見つかりません",
                        description=f"ページ {page} にはデータがありません。\n\n🔙 `/leaderboard 1` でリーダーボードの最初のページを確認してください。",
                        color=discord.Color.orange()
                    )
                await ctx.send(embed=embed)
                return
                
        except Exception as db_error:
            logger.error(f"リーダーボードコマンド - データベースエラー (Guild: {ctx.guild.id}): {db_error}")
            embed = discord.Embed(
                title="❌ データ取得エラー",
                description="申し訳ございません。リーダーボードデータの取得中にエラーが発生しました。\n少し時間をおいて再度お試しください。",
                color=discord.Color.red()
            )
            embed.add_field(
                name="🔧 問題が続く場合",
                value="サーバー管理者にお知らせください。",
                inline=False
            )
            await ctx.send(embed=embed, ephemeral=True)
            return
        
        embed = discord.Embed(
            title=f"🏆 {ctx.guild.name} リーダーボード - ページ {page}",
            color=discord.Color.gold()
        )
        
        for data in leaderboard_data:
            user = self.bot.get_user(data['member_id'])
            username = user.display_name if user else data['member_name']
            
            medal = ""
            rank = data['rank']
            if rank == 1:
                medal = "🥇 "
            elif rank == 2:
                medal = "🥈 "
            elif rank == 3:
                medal = "🥉 "
            
            embed.add_field(
                name=f"{medal}#{rank} {username}",
                value=f"レベル {data['member_level']} • {data['member_total_xp']:,} XP",
                inline=False
            )
        
        embed.set_footer(text=f"ページ {page} • 毎日メッセージを送信してXPを獲得しよう！")
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="givexp", description="管理者用: ユーザーにXPを付与")
    @app_commands.describe(
        user="XPを付与するユーザー",
        amount="付与するXP量"
    )
    @commands.has_permissions(administrator=True)
    @is_guild()
    @log_commands()
    async def give_xp(self, ctx: commands.Context, user: discord.Member, amount: int):
        """XP付与コマンド（管理者限定）"""
        await ctx.defer()
        
        if amount <= 0:
            await ctx.send("❌ XP量は正の数である必要があります。", ephemeral=True)
            return
        
        try:
            level_up, new_level = await self.db.add_xp(
                ctx.guild.id, user.id, user.display_name, amount
            )
            
            embed = discord.Embed(
                title="✅ XP付与完了",
                description=f"{user.mention} に {amount:,} XP を付与しました",
                color=discord.Color.green()
            )
            
            if level_up:
                embed.add_field(
                    name="🎉 レベルアップ！", 
                    value=f"新しいレベル: {new_level}",
                    inline=False
                )
            
            await ctx.send(embed=embed)
            
            if level_up:
                await self.handle_level_up(user, new_level, ctx.channel)
        
        except Exception as e:
            logger.error(f"XP付与エラー: {e}")
            await ctx.send("❌ XP付与中にエラーが発生しました。", ephemeral=True)
    
    @commands.hybrid_command(name="resetxp", description="管理者用: ユーザーのXPをリセット")
    @app_commands.describe(user="XPをリセットするユーザー")
    @commands.has_permissions(administrator=True)
    @is_guild()
    @log_commands()
    async def reset_xp(self, ctx: commands.Context, user: discord.Member):
        """XPリセットコマンド（管理者限定）"""
        await ctx.defer()
        
        try:
            await execute_query('''
                UPDATE leaderboard 
                SET member_level = 1, member_xp = 0, member_total_xp = 0
                WHERE guild_id = $1 AND member_id = $2
            ''', ctx.guild.id, user.id, fetch_type='status')
            
            embed = discord.Embed(
                title="✅ XPリセット完了",
                description=f"{user.mention} のXPをリセットしました",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)
        
        except Exception as e:
            logger.error(f"XPリセットエラー: {e}")
            await ctx.send("❌ XPリセット中にエラーが発生しました。", ephemeral=True)
    
    @commands.hybrid_command(name="levelstats", description="レベリングシステムの統計を表示")
    @is_guild()
    @log_commands()  
    async def level_stats(self, ctx: commands.Context):
        """レベリングシステム統計コマンド"""
        await ctx.defer()
        
        try:
            # 統計データ取得
            stats = await execute_query('''
                SELECT 
                    COUNT(*) as total_users,
                    SUM(member_total_xp) as total_xp,
                    AVG(member_level) as avg_level,
                    MAX(member_level) as max_level
                FROM leaderboard 
                WHERE guild_id = $1
            ''', ctx.guild.id, fetch_type='row')
            
            # トップユーザー取得
            top_user = await execute_query('''
                SELECT member_name, member_level, member_total_xp
                FROM leaderboard 
                WHERE guild_id = $1
                ORDER BY member_total_xp DESC 
                LIMIT 1
            ''', ctx.guild.id, fetch_type='row')
            
            embed = discord.Embed(
                title=f"📊 {ctx.guild.name} レベリング統計",
                color=discord.Color.blue()
            )
            
            if stats and stats['total_users'] > 0:
                embed.add_field(
                    name="総ユーザー数", 
                    value=f"{stats['total_users']:,}", 
                    inline=True
                )
                embed.add_field(
                    name="総XP", 
                    value=f"{stats['total_xp']:,}" if stats['total_xp'] else "0", 
                    inline=True
                )
                embed.add_field(
                    name="平均レベル", 
                    value=f"{stats['avg_level']:.1f}" if stats['avg_level'] else "1.0", 
                    inline=True
                )
                embed.add_field(
                    name="最高レベル", 
                    value=f"{stats['max_level']}" if stats['max_level'] else "1", 
                    inline=True
                )
                
                if top_user:
                    embed.add_field(
                        name="トップユーザー",
                        value=f"{top_user['member_name']}\nレベル {top_user['member_level']} ({top_user['member_total_xp']:,} XP)",
                        inline=False
                    )
            else:
                embed.description = "まだ誰もXPを獲得していません！"
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"統計取得エラー: {e}")
            await ctx.send("❌ 統計の取得中にエラーが発生しました。", ephemeral=True)
    
    # アチーブメント進捗更新メソッド（新規追加）
    async def _update_achievement_progress(self, guild_id: int, user_id: int, 
                                         xp_gained: int, new_level: Optional[int] = None,
                                         message_content: Optional[str] = None):
        """アチーブメント進捗更新統合メソッド"""
        try:
            # 各種アチーブメントタイプの進捗を並行更新
            update_tasks = []
            
            # メッセージ数アチーブメント
            if message_content:
                update_tasks.append(
                    self.achievement_manager.update_achievement_progress(
                        guild_id, user_id, AchievementType.MESSAGE_COUNT, 1
                    )
                )
            
            # XP総計アチーブメント
            if xp_gained > 0:
                # 現在の総XPを取得
                member_data = await self.db.get_or_create_member(guild_id, user_id, "")
                total_xp = member_data.get('member_total_xp', 0)
                
                update_tasks.append(
                    self.achievement_manager.update_achievement_progress(
                        guild_id, user_id, AchievementType.XP_TOTAL, total_xp
                    )
                )
            
            # レベルアチーブメント（レベルアップ時のみ）
            if new_level:
                update_tasks.append(
                    self.achievement_manager.update_achievement_progress(
                        guild_id, user_id, AchievementType.LEVEL, new_level
                    )
                )
            
            # 全ての更新を並行実行
            if update_tasks:
                results = await asyncio.gather(*update_tasks, return_exceptions=True)
                
                # 新規達成アチーブメントをまとめて記録
                newly_completed = []
                for result in results:
                    if isinstance(result, list):
                        newly_completed.extend(result)
                
                if newly_completed:
                    logger.info(f"Guild {guild_id}, User {user_id}: 新規アチーブメント達成 {len(newly_completed)}個")
                    
        except Exception as e:
            logger.error(f"アチーブメント進捗更新エラー: {e}")
    
    # エラーハンドリング
    async def cog_command_error(self, ctx: commands.Context, error: commands.CommandError):
        """Cogレベルの改善されたエラーハンドラー"""
        if isinstance(error, commands.MissingPermissions):
            # 権限エラーの詳細対応
            missing_perms = ", ".join(error.missing_permissions)
            
            if ctx.command.name in ['givexp', 'resetxp']:
                embed = discord.Embed(
                    title="🚫 管理者権限が必要です",
                    description=f"🔒 **`{ctx.command.name}`** コマンドは管理者のみ実行できます。\n\nこのコマンドはXPシステムに影響するため、サーバー管理者のみが使用できます。",
                    color=discord.Color.red()
                )
                embed.add_field(
                    name="📝 必要な権限",
                    value=f"『**{missing_perms}**』",
                    inline=True
                )
                embed.add_field(
                    name="🙋 管理者の方へ",
                    value="これらのコマンドでXPを付与・リセットできます。",
                    inline=True
                )
            else:
                embed = discord.Embed(
                    title="❓ 権限が不足です",
                    description=f"このコマンドを実行するためには **{missing_perms}** 権限が必要です。",
                    color=discord.Color.orange()
                )
                embed.add_field(
                    name="🔧 解決方法",
                    value="サーバー管理者に権限の付与を依頼してください。",
                    inline=False
                )
            
            await ctx.send(embed=embed, ephemeral=True)
            
        elif isinstance(error, commands.BotMissingPermissions):
            # Botの権限不足
            embed = discord.Embed(
                title="🤖 Botの権限が不足です",
                description="Botがこのコマンドを実行するために必要な権限がありません。\nサーバー管理者にBotの権限設定を確認してもらってください。",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed, ephemeral=True)
            
        elif isinstance(error, commands.CommandOnCooldown):
            # クールダウンエラー
            remaining = round(error.retry_after, 1)
            embed = discord.Embed(
                title="⏰ クールダウン中です",
                description=f"あと **{remaining}秒** 待ってから再度お試しください。",
                color=discord.Color.yellow()
            )
            await ctx.send(embed=embed, ephemeral=True)
            
        else:
            logger.error(f"コマンドエラー: {ctx.command.name if ctx.command else 'Unknown'} - {error}")
            embed = discord.Embed(
                title="❌ 予期しないエラーが発生しました",
                description="申し訳ございません。コマンドの実行中にエラーが発生しました。\n少し時間をおいて再度お試しください。",
                color=discord.Color.red()
            )
            embed.add_field(
                name="🔧 問題が続く場合",
                value="サーバー管理者にお知らせください。\nエラーの詳細はログに記録されます。",
                inline=False
            )
            await ctx.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(LevelingSystem(bot))
