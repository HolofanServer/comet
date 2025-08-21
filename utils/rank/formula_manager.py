"""
カスタムレベル公式管理システム

Linear/Exponential/Logarithmic/Custom/Stepped公式による
柔軟なレベル計算とキャッシュ管理を提供。
"""

import time
from typing import Dict, Any, List, Tuple

from models.rank.level_formula import LevelFormula, FormulaPreset
from utils.logging import setup_logging
from utils.database import execute_query

logger = setup_logging("FORMULA_MANAGER")

class FormulaManager:
    """レベル公式管理クラス"""
    
    def __init__(self):
        """初期化"""
        # 公式キャッシュ（パフォーマンス向上）
        self.formula_cache: Dict[int, Tuple[LevelFormula, float]] = {}
        self.cache_ttl = 600  # 10分間キャッシュ
        
        # 計算結果キャッシュ
        self.calculation_cache: Dict[str, Tuple[int, float]] = {}
        self.calc_cache_ttl = 300  # 5分間キャッシュ

    async def get_guild_formula(self, guild_id: int) -> LevelFormula:
        """
        ギルドのレベル公式を取得
        
        Args:
            guild_id: DiscordサーバーID
            
        Returns:
            LevelFormula: 公式オブジェクト
        """
        current_time = time.time()
        
        # キャッシュチェック
        if guild_id in self.formula_cache:
            formula, cached_time = self.formula_cache[guild_id]
            if current_time - cached_time < self.cache_ttl:
                return formula
        
        try:
            # データベースから公式を取得
            query = """
            SELECT formula_data, formula_name, formula_type, max_level 
            FROM level_formulas 
            WHERE guild_id = $1 AND is_active = TRUE
            """
            result = await execute_query(query, guild_id)
            
            if result and len(result) > 0:
                formula_data = result[0]
                formula_json = formula_data["formula_data"]
                formula = LevelFormula.model_validate_json(formula_json)
                
                logger.info(f"Guild {guild_id}: カスタム公式 '{formula.name}' を読み込みました")
            else:
                # デフォルト公式（バランス線形）
                formula = FormulaPreset.get_balanced_linear()
                logger.info(f"Guild {guild_id}: デフォルト公式を使用します")
            
            # キャッシュに保存
            self.formula_cache[guild_id] = (formula, current_time)
            return formula
            
        except Exception as e:
            logger.error(f"Guild {guild_id}: 公式読み込みエラー {e}")
            return FormulaPreset.get_balanced_linear()

    async def set_guild_formula(
        self, 
        guild_id: int, 
        formula: LevelFormula, 
        created_by: int
    ) -> bool:
        """
        ギルドのレベル公式を設定
        
        Args:
            guild_id: DiscordサーバーID
            formula: 設定する公式
            created_by: 設定者のDiscord User ID
            
        Returns:
            bool: 設定成功フラグ
        """
        try:
            formula_json = formula.model_dump_json()
            
            query = """
            INSERT INTO level_formulas (guild_id, formula_data, formula_name, formula_type, max_level, created_by, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, NOW())
            ON CONFLICT (guild_id)
            DO UPDATE SET 
                formula_data = EXCLUDED.formula_data,
                formula_name = EXCLUDED.formula_name,
                formula_type = EXCLUDED.formula_type,
                max_level = EXCLUDED.max_level,
                updated_at = NOW()
            """
            
            await execute_query(
                query, 
                guild_id, 
                formula_json, 
                formula.name, 
                formula.formula_type.value, 
                formula.max_level, 
                created_by,
                fetch_type='status'
            )
            
            # キャッシュを無効化
            self.invalidate_cache(guild_id)
            
            logger.info(f"Guild {guild_id}: 公式 '{formula.name}' を設定しました")
            return True
            
        except Exception as e:
            logger.error(f"Guild {guild_id}: 公式設定エラー {e}")
            return False

    async def calculate_level_from_total_xp(
        self, 
        guild_id: int, 
        total_xp: int
    ) -> Tuple[int, int, int]:
        """
        累積XPからレベル・現在レベル内XP・次レベル必要XPを計算
        
        Args:
            guild_id: DiscordサーバーID
            total_xp: 累積XP
            
        Returns:
            Tuple[int, int, int]: (レベル, 現在レベル内XP, 次レベル必要XP)
        """
        formula = await self.get_guild_formula(guild_id)
        
        # キャッシュキー生成
        cache_key = f"{guild_id}_{total_xp}"
        current_time = time.time()
        
        # 計算結果キャッシュチェック
        if cache_key in self.calculation_cache:
            cached_result, cached_time = self.calculation_cache[cache_key]
            if current_time - cached_time < self.calc_cache_ttl:
                # キャッシュから結果を復元
                return self._decode_cached_result(cached_result)
        
        try:
            # レベル計算
            current_level, current_level_xp, required_for_next = formula.get_current_level_progress(total_xp)
            
            # 結果をキャッシュに保存
            encoded_result = self._encode_calculation_result(current_level, current_level_xp, required_for_next)
            self.calculation_cache[cache_key] = (encoded_result, current_time)
            
            return current_level, current_level_xp, required_for_next
            
        except Exception as e:
            logger.error(f"Guild {guild_id}: レベル計算エラー {e}")
            # フォールバック計算
            return self._fallback_level_calculation(total_xp)

    async def get_xp_required_for_level(self, guild_id: int, target_level: int) -> int:
        """
        指定レベルに必要な累積XPを取得
        
        Args:
            guild_id: DiscordサーバーID
            target_level: 目標レベル
            
        Returns:
            int: 必要累積XP
        """
        formula = await self.get_guild_formula(guild_id)
        
        try:
            return formula.calculate_required_xp(target_level)
        except Exception as e:
            logger.error(f"Guild {guild_id}: XP計算エラー {e}")
            # シンプルなフォールバック
            return target_level * 100

    async def get_available_presets(self) -> List[Dict[str, Any]]:
        """
        利用可能なプリセット公式一覧を取得
        
        Returns:
            List[Dict]: プリセット公式リスト
        """
        try:
            query = """
            SELECT preset_id, preset_name, formula_data, description, category, 
                   difficulty_level, recommended_guild_size
            FROM formula_presets 
            WHERE is_public = TRUE
            ORDER BY difficulty_level, preset_name
            """
            
            result = await execute_query(query)
            
            presets = []
            for row in result if result else []:
                # 公式データからプレビュー情報を生成
                try:
                    formula = LevelFormula.model_validate_json(row["formula_data"])
                    preview = formula.generate_preview()
                    
                    presets.append({
                        "preset_id": row["preset_id"],
                        "preset_name": row["preset_name"],
                        "description": row["description"],
                        "category": row["category"],
                        "difficulty_level": row["difficulty_level"],
                        "recommended_guild_size": row["recommended_guild_size"],
                        "preview": preview
                    })
                except Exception as parse_error:
                    logger.warning(f"プリセット解析エラー {row['preset_id']}: {parse_error}")
            
            return presets
            
        except Exception as e:
            logger.error(f"プリセット取得エラー: {e}")
            return []

    async def apply_preset_formula(
        self, 
        guild_id: int, 
        preset_id: int, 
        created_by: int
    ) -> bool:
        """
        プリセット公式をギルドに適用
        
        Args:
            guild_id: DiscordサーバーID
            preset_id: プリセットID
            created_by: 適用者のDiscord User ID
            
        Returns:
            bool: 適用成功フラグ
        """
        try:
            query = "SELECT formula_data FROM formula_presets WHERE preset_id = $1 AND is_public = TRUE"
            result = await execute_query(query, preset_id)
            
            if not result or len(result) == 0:
                logger.warning(f"プリセット {preset_id} が見つかりません")
                return False
            
            formula_json = result[0]["formula_data"]
            formula = LevelFormula.model_validate_json(formula_json)
            
            success = await self.set_guild_formula(guild_id, formula, created_by)
            
            if success:
                logger.info(f"Guild {guild_id}: プリセット {preset_id} を適用しました")
            
            return success
            
        except Exception as e:
            logger.error(f"プリセット適用エラー: {e}")
            return False

    def invalidate_cache(self, guild_id: int):
        """キャッシュを無効化"""
        # 公式キャッシュ
        if guild_id in self.formula_cache:
            del self.formula_cache[guild_id]
        
        # 計算結果キャッシュ（この guild_id に関連するもの）
        keys_to_remove = [key for key in self.calculation_cache.keys() if key.startswith(f"{guild_id}_")]
        for key in keys_to_remove:
            del self.calculation_cache[key]
        
        logger.info(f"Guild {guild_id}: 公式キャッシュを無効化しました")

    def _encode_calculation_result(self, level: int, level_xp: int, required: int) -> int:
        """計算結果をエンコード（キャッシュ効率化）"""
        # 単純なエンコーディング: level << 32 | level_xp << 16 | required
        return (level << 32) | (level_xp << 16) | required

    def _decode_cached_result(self, encoded: int) -> Tuple[int, int, int]:
        """エンコードされた結果をデコード"""
        level = (encoded >> 32) & 0xFFFFFFFF
        level_xp = (encoded >> 16) & 0xFFFF
        required = encoded & 0xFFFF
        return level, level_xp, required

    def _fallback_level_calculation(self, total_xp: int) -> Tuple[int, int, int]:
        """フォールバック用のシンプルレベル計算"""
        # 単純な線形計算
        level = max(1, total_xp // 100)
        level_start_xp = (level - 1) * 100
        current_level_xp = total_xp - level_start_xp
        required_for_next = 100 - current_level_xp
        
        return level, current_level_xp, max(0, required_for_next)

    async def cleanup_old_cache(self):
        """古いキャッシュエントリを削除"""
        current_time = time.time()
        
        # 計算結果キャッシュのクリーンアップ
        expired_keys = []
        for key, (_, cached_time) in self.calculation_cache.items():
            if current_time - cached_time > self.calc_cache_ttl * 2:  # TTLの2倍で削除
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.calculation_cache[key]
        
        if expired_keys:
            logger.info(f"期限切れキャッシュを削除: {len(expired_keys)} 件")

# モジュールレベルのインスタンス
formula_manager = FormulaManager()

async def get_guild_level_formula(guild_id: int) -> LevelFormula:
    """
    便利関数：ギルドのレベル公式を取得
    
    Args:
        guild_id: DiscordサーバーID
        
    Returns:
        LevelFormula: 公式オブジェクト
    """
    return await formula_manager.get_guild_formula(guild_id)

async def calculate_level_from_xp(guild_id: int, total_xp: int) -> Tuple[int, int, int]:
    """
    便利関数：累積XPからレベル情報を計算
    
    Args:
        guild_id: DiscordサーバーID
        total_xp: 累積XP
        
    Returns:
        Tuple[int, int, int]: (レベル, 現在レベル内XP, 次レベル必要XP)
    """
    return await formula_manager.calculate_level_from_total_xp(guild_id, total_xp)
