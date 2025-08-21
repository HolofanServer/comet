"""
カスタムレベル計算公式システム用Pydanticモデル

Linear/Exponential/Logarithmic/Custom公式による
柔軟なレベル進行システムの設定データモデル。
"""

from pydantic import BaseModel, Field, field_validator
from typing import Dict, List, Optional, Any
from enum import Enum
import math

class FormulaType(str, Enum):
    """レベル公式のタイプ"""
    LINEAR = "linear"           # 線形増加
    EXPONENTIAL = "exponential" # 指数増加  
    LOGARITHMIC = "logarithmic" # 対数増加
    CUSTOM = "custom"           # カスタム公式
    STEPPED = "stepped"         # 段階的（レベル範囲ごとに異なる式）

class LinearFormula(BaseModel):
    """線形公式: xp_required = base + (level * multiplier)"""
    base_xp: int = Field(default=100, ge=1, le=100000, description="基本必要XP")
    level_multiplier: int = Field(default=50, ge=1, le=10000, description="レベル毎増加XP")
    
    def calculate_required_xp(self, level: int) -> int:
        """指定レベルに必要な累積XP"""
        if level <= 1:
            return 0
        # 累積XP = Σ(base + i * multiplier) for i in range(1, level)
        return sum(self.base_xp + i * self.level_multiplier for i in range(1, level))

class ExponentialFormula(BaseModel):
    """指数公式: xp_required = base * (growth_rate ^ level)"""
    base_xp: int = Field(default=100, ge=1, le=10000, description="基本必要XP")
    growth_rate: float = Field(default=1.2, ge=1.001, le=3.0, description="成長率")
    max_level_xp: int = Field(default=1000000, ge=1000, description="単レベル最大XP上限")
    
    def calculate_required_xp(self, level: int) -> int:
        """指定レベルに必要な累積XP"""
        if level <= 1:
            return 0
        
        total_xp = 0
        for i in range(1, level):
            level_xp = min(
                int(self.base_xp * (self.growth_rate ** i)), 
                self.max_level_xp
            )
            total_xp += level_xp
        return total_xp

class LogarithmicFormula(BaseModel):
    """対数公式: xp_required = base * log(level * log_base)"""
    base_xp: int = Field(default=100, ge=1, le=10000, description="基本必要XP")
    log_base: float = Field(default=2.0, ge=1.1, le=10.0, description="対数底")
    scale_factor: float = Field(default=1.5, ge=0.1, le=10.0, description="スケール係数")
    
    def calculate_required_xp(self, level: int) -> int:
        """指定レベルに必要な累積XP"""
        if level <= 1:
            return 0
        
        total_xp = 0
        for i in range(1, level):
            level_xp = int(
                self.base_xp * self.scale_factor * math.log(i * self.log_base)
            )
            total_xp += max(level_xp, 1)  # 最低1XP
        return total_xp

class CustomFormula(BaseModel):
    """カスタム公式: xp_required = base * (level ^ power) + (level * linear) + constant"""
    base_xp: int = Field(default=50, ge=1, le=10000, description="基本XP")
    power: float = Field(default=1.5, ge=0.5, le=5.0, description="べき乗")
    linear_factor: int = Field(default=25, ge=0, le=1000, description="線形係数")
    constant: int = Field(default=0, ge=0, le=1000, description="定数項")
    
    # 特殊調整
    milestone_bonuses: Dict[int, int] = Field(
        default_factory=dict,
        description="マイルストーンレベルでのボーナスXP"
    )
    
    def calculate_required_xp(self, level: int) -> int:
        """指定レベルに必要な累積XP"""
        if level <= 1:
            return 0
        
        total_xp = 0
        for i in range(1, level):
            # 基本公式
            level_xp = int(
                self.base_xp * (i ** self.power) + 
                (i * self.linear_factor) + 
                self.constant
            )
            
            # マイルストーンボーナス
            if i in self.milestone_bonuses:
                level_xp += self.milestone_bonuses[i]
            
            total_xp += max(level_xp, 1)
        return total_xp

class SteppedFormula(BaseModel):
    """段階式公式: レベル範囲ごとに異なる公式を適用"""
    
    class LevelRange(BaseModel):
        min_level: int = Field(ge=1, description="範囲開始レベル")
        max_level: Optional[int] = Field(default=None, description="範囲終了レベル（Noneで無制限）")
        base_xp: int = Field(ge=1, description="この範囲の基本XP")
        multiplier: float = Field(default=1.0, ge=0.1, le=10.0, description="この範囲の倍率")
    
    level_ranges: List[LevelRange] = Field(description="レベル範囲のリスト")
    
    def calculate_required_xp(self, level: int) -> int:
        """指定レベルに必要な累積XP"""
        if level <= 1:
            return 0
        
        total_xp = 0
        for i in range(1, level):
            # 該当する範囲を検索
            level_xp = 100  # デフォルト値
            
            for range_config in self.level_ranges:
                if range_config.min_level <= i and \
                   (range_config.max_level is None or i <= range_config.max_level):
                    level_xp = int(range_config.base_xp * range_config.multiplier)
                    break
            
            total_xp += level_xp
        return total_xp
    
    @field_validator('level_ranges')
    @classmethod
    def validate_ranges(cls, v):
        if not v:
            raise ValueError('少なくとも1つのレベル範囲が必要です')
        
        # 範囲の重複チェック
        sorted_ranges = sorted(v, key=lambda x: x.min_level)
        for i in range(len(sorted_ranges) - 1):
            current = sorted_ranges[i]
            next_range = sorted_ranges[i + 1]
            
            if current.max_level and current.max_level >= next_range.min_level:
                raise ValueError(f'レベル範囲が重複しています: {current.min_level}-{current.max_level} と {next_range.min_level}-{next_range.max_level}')
        
        return v

class LevelFormula(BaseModel):
    """統合レベル計算公式"""
    
    # 基本設定
    formula_type: FormulaType = Field(description="公式タイプ")
    name: str = Field(max_length=100, description="公式名")
    description: Optional[str] = Field(default=None, max_length=500, description="説明")
    
    # 公式定義（タイプに応じて1つのみ設定）
    linear: Optional[LinearFormula] = Field(default=None)
    exponential: Optional[ExponentialFormula] = Field(default=None)
    logarithmic: Optional[LogarithmicFormula] = Field(default=None)
    custom: Optional[CustomFormula] = Field(default=None)
    stepped: Optional[SteppedFormula] = Field(default=None)
    
    # 制限設定
    max_level: int = Field(default=100, ge=1, le=1000, description="最大レベル")
    
    # 表示設定
    preview_levels: List[int] = Field(
        default_factory=lambda: [5, 10, 25, 50, 100],
        description="プレビュー表示するレベル"
    )
    
    @field_validator('linear', 'exponential', 'logarithmic', 'custom', 'stepped')
    @classmethod
    def validate_formula_match(cls, v, info):
        """公式タイプと設定の一致を検証"""
        if hasattr(info, 'data') and 'formula_type' in info.data:
            formula_type = info.data['formula_type']
            field_name = info.field_name
            
            # 対応するタイプの場合は必須、それ以外はNone
            if formula_type.value == field_name and v is None:
                raise ValueError(f'{formula_type}タイプには{field_name}設定が必要です')
            elif formula_type.value != field_name and v is not None:
                raise ValueError(f'{formula_type}タイプでは{field_name}設定は使用できません')
        
        return v
    
    def calculate_required_xp(self, target_level: int) -> int:
        """指定レベルに必要な累積XP"""
        if target_level <= 1:
            return 0
        
        if target_level > self.max_level:
            target_level = self.max_level
        
        formula_map = {
            FormulaType.LINEAR: self.linear,
            FormulaType.EXPONENTIAL: self.exponential,
            FormulaType.LOGARITHMIC: self.logarithmic,
            FormulaType.CUSTOM: self.custom,
            FormulaType.STEPPED: self.stepped
        }
        
        formula = formula_map.get(self.formula_type)
        if not formula:
            raise ValueError(f'公式タイプ {self.formula_type} の設定が見つかりません')
        
        return formula.calculate_required_xp(target_level)
    
    def get_level_from_total_xp(self, total_xp: int) -> int:
        """累積XPからレベルを逆算"""
        if total_xp <= 0:
            return 1
        
        # 二分探索でレベルを特定
        low, high = 1, self.max_level
        result_level = 1
        
        while low <= high:
            mid = (low + high) // 2
            required_xp = self.calculate_required_xp(mid)
            
            if required_xp <= total_xp:
                result_level = mid
                low = mid + 1
            else:
                high = mid - 1
        
        return result_level
    
    def get_current_level_progress(self, total_xp: int) -> tuple[int, int, int]:
        """現在レベル、現在レベル内XP、次レベル必要XPを取得"""
        current_level = self.get_level_from_total_xp(total_xp)
        
        if current_level >= self.max_level:
            current_level_start = self.calculate_required_xp(self.max_level)
            return self.max_level, total_xp - current_level_start, 0
        
        current_level_start = self.calculate_required_xp(current_level)
        next_level_start = self.calculate_required_xp(current_level + 1)
        
        current_level_xp = total_xp - current_level_start
        required_for_next = next_level_start - total_xp
        
        return current_level, current_level_xp, required_for_next
    
    def generate_preview(self) -> Dict[str, Any]:
        """公式のプレビューデータを生成"""
        preview_data = {
            "formula_type": self.formula_type,
            "name": self.name,
            "description": self.description,
            "levels": []
        }
        
        for level in self.preview_levels:
            if level <= self.max_level:
                required_xp = self.calculate_required_xp(level)
                preview_data["levels"].append({
                    "level": level,
                    "total_xp_required": required_xp,
                    "level_xp_required": required_xp - self.calculate_required_xp(level - 1) if level > 1 else 0
                })
        
        return preview_data

class FormulaPreset(BaseModel):
    """プリセット公式定義"""
    
    @classmethod
    def get_balanced_linear(cls) -> LevelFormula:
        """バランス型線形公式"""
        return LevelFormula(
            formula_type=FormulaType.LINEAR,
            name="バランス線形",
            description="一定ペースでレベルアップ。初心者に優しい設計",
            linear=LinearFormula(base_xp=100, level_multiplier=50),
            max_level=100
        )
    
    @classmethod
    def get_competitive_exponential(cls) -> LevelFormula:
        """競争型指数公式"""
        return LevelFormula(
            formula_type=FormulaType.EXPONENTIAL,
            name="競争型指数",
            description="高レベルほど大幅にXP必要。長期コミット型",
            exponential=ExponentialFormula(base_xp=80, growth_rate=1.15),
            max_level=200
        )
    
    @classmethod
    def get_casual_logarithmic(cls) -> LevelFormula:
        """カジュアル型対数公式"""
        return LevelFormula(
            formula_type=FormulaType.LOGARITHMIC,
            name="カジュアル対数",
            description="高レベルでも比較的上がりやすい。ライト層向け",
            logarithmic=LogarithmicFormula(base_xp=120, log_base=1.8, scale_factor=1.3),
            max_level=150
        )
