"""
アチーブメント・スキルツリー・プレステージシステム管理エンジン

Discord.pyレベリングシステムのゲーミフィケーション機能を管理する
包括的なシステムマネージャー。
"""

import asyncio
import json
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from dataclasses import dataclass

from utils.database import execute_query
from utils.logging import setup_logging
from models.rank.achievements import (
    Achievement, AchievementType, AchievementRarity, AchievementCondition,
    SkillNode, SkillType, UserSkill,
    PrestigeTier, PrestigeType,
    GamificationStats
)

logger = setup_logging("ACHIEVEMENT_MANAGER")

@dataclass
class AchievementProgress:
    """アチーブメント進捗情報"""
    achievement: Achievement
    current_progress: int
    is_completed: bool
    completion_date: Optional[datetime] = None
    progress_percentage: float = 0.0

@dataclass
class SkillEffect:
    """スキル効果計算結果"""
    skill_id: str
    skill_type: SkillType
    current_level: int
    total_effect: float
    description: str

class AchievementManager:
    """アチーブメントシステム管理クラス"""
    
    def __init__(self):
        # キャッシュ管理
        self.achievement_cache: Dict[str, Achievement] = {}
        self.user_progress_cache: Dict[str, Dict[str, AchievementProgress]] = {}
        self.skill_cache: Dict[str, SkillNode] = {}
        self.user_skills_cache: Dict[str, Dict[str, UserSkill]] = {}
        self.cache_ttl = 300  # 5分間キャッシュ
        
        # 統計キャッシュ
        self.stats_cache: Dict[str, Tuple[GamificationStats, float]] = {}
        
        # プレステージキャッシュ
        self.prestige_tiers_cache: Dict[Tuple[int, str], PrestigeTier] = {}
        
    def _get_user_key(self, guild_id: int, user_id: int) -> str:
        """ユーザーキー生成"""
        return f"{guild_id}:{user_id}"
    
    async def initialize_achievements(self, force_reload: bool = False) -> bool:
        """アチーブメントシステム初期化"""
        try:
            if not force_reload and self.achievement_cache:
                return True
            
            # デフォルトアチーブメント読み込み
            await self.load_default_achievements()
            
            # デフォルトスキル読み込み  
            await self.load_default_skills()
            
            # デフォルトプレステージティア読み込み
            await self.load_default_prestige_tiers()
            
            logger.info(f"アチーブメントシステム初期化完了: "
                       f"アチーブメント {len(self.achievement_cache)}個, "
                       f"スキル {len(self.skill_cache)}個, "
                       f"プレステージティア {len(self.prestige_tiers_cache)}個")
            
            return True
            
        except Exception as e:
            logger.error(f"アチーブメントシステム初期化エラー: {e}")
            return False
    
    async def load_default_achievements(self) -> None:
        """デフォルトアチーブメント読み込み"""
        try:
            query = """
                SELECT id, name, description, type, rarity, condition_type, 
                       target_value, additional_params, xp_reward, skill_points_reward,
                       title_reward, role_reward, custom_rewards, icon, color, 
                       hidden, one_time, requires_achievements, created_at
                FROM achievements
                ORDER BY type, target_value
            """
            results = await execute_query(query)
            
            for row in results or []:
                # JSONフィールドの適切な解析
                additional_params = row.get('additional_params')
                if isinstance(additional_params, str):
                    try:
                        additional_params = json.loads(additional_params)
                    except (json.JSONDecodeError, TypeError):
                        additional_params = {}
                elif additional_params is None:
                    additional_params = {}
                
                custom_rewards = row.get('custom_rewards')
                if isinstance(custom_rewards, str):
                    try:
                        custom_rewards = json.loads(custom_rewards)
                    except (json.JSONDecodeError, TypeError):
                        custom_rewards = {}
                elif custom_rewards is None:
                    custom_rewards = {}
                
                requires_achievements = row.get('requires_achievements', [])
                if isinstance(requires_achievements, str):
                    try:
                        requires_achievements = json.loads(requires_achievements)
                    except (json.JSONDecodeError, TypeError):
                        requires_achievements = []
                
                achievement = Achievement(
                    id=row['id'],
                    name=row['name'],
                    description=row['description'],
                    type=AchievementType(row['type']),
                    rarity=AchievementRarity(row['rarity']),
                    condition={
                        'type': AchievementType(row['condition_type']),
                        'target_value': row['target_value'],
                        'current_value': 0,
                        'additional_params': additional_params,
                        'progress_percentage': 0.0,
                        'is_completed': False
                    },
                    xp_reward=row.get('xp_reward', 0),
                    skill_points_reward=row.get('skill_points_reward', 0),
                    title_reward=row.get('title_reward'),
                    role_reward=row.get('role_reward'),
                    custom_rewards=custom_rewards,
                    icon=row.get('icon'),
                    color=row.get('color'),
                    hidden=row.get('hidden', False),
                    one_time=row.get('one_time', True),
                    requires_achievements=requires_achievements,
                    created_at=row.get('created_at', datetime.now())
                )
                
                self.achievement_cache[achievement.id] = achievement
                
        except Exception as e:
            logger.error(f"デフォルトアチーブメント読み込みエラー: {e}")
    
    async def load_default_skills(self) -> None:
        """デフォルトスキル読み込み"""
        try:
            query = """
                SELECT id, name, description, type, tier, prerequisites,
                       skill_points_cost, max_level, effect_per_level,
                       icon, color, category, created_at
                FROM skill_nodes
                ORDER BY tier, category, name
            """
            results = await execute_query(query)
            
            for row in results or []:
                skill = SkillNode(
                    id=row['id'],
                    name=row['name'],
                    description=row['description'],
                    type=SkillType(row['type']),
                    tier=row['tier'],
                    prerequisites=row.get('prerequisites', []),
                    skill_points_cost=row['skill_points_cost'],
                    max_level=row.get('max_level', 1),
                    effect_per_level=row['effect_per_level'],
                    icon=row.get('icon'),
                    color=row.get('color'),
                    category=row.get('category', 'general')
                )
                
                self.skill_cache[skill.id] = skill
                
        except Exception as e:
            logger.error(f"デフォルトスキル読み込みエラー: {e}")
    
    async def load_default_prestige_tiers(self) -> None:
        """デフォルトプレステージティア読み込み"""
        try:
            query = """
                SELECT tier, name, type, required_level, required_achievements,
                       required_skill_points, benefits, reset_progress, keep_skills,
                       icon, color, badge, created_at
                FROM prestige_tiers
                ORDER BY type, tier
            """
            results = await execute_query(query)
            
            for row in results or []:
                # JSONフィールドの適切な解析
                benefits_data = row.get('benefits', {})
                if isinstance(benefits_data, str):
                    try:
                        benefits_data = json.loads(benefits_data)
                    except (json.JSONDecodeError, TypeError):
                        benefits_data = {}
                elif benefits_data is None:
                    benefits_data = {}
                
                prestige_tier = PrestigeTier(
                    tier=row['tier'],
                    name=row['name'],
                    type=PrestigeType(row['type']),
                    required_level=row['required_level'],
                    required_achievements=row.get('required_achievements', 0),
                    required_skill_points=row.get('required_skill_points', 0),
                    benefits=benefits_data,
                    reset_progress=row.get('reset_progress', True),
                    keep_skills=row.get('keep_skills', False),
                    icon=row.get('icon'),
                    color=row.get('color'),
                    badge=row.get('badge')
                )
                
                key = (prestige_tier.tier, prestige_tier.type.value)
                self.prestige_tiers_cache[key] = prestige_tier
                
        except Exception as e:
            logger.error(f"デフォルトプレステージティア読み込みエラー: {e}")
    
    async def update_achievement_progress(self, guild_id: int, user_id: int, 
                                        achievement_type: AchievementType, 
                                        increment: int = 1, 
                                        metadata: Optional[Dict[str, Any]] = None) -> List[str]:
        """アチーブメント進捗更新（新規達成したアチーブメントIDのリストを返す）"""
        newly_completed = []
        
        try:
            # 該当タイプのアチーブメントを取得
            relevant_achievements = [
                ach for ach in self.achievement_cache.values()
                if ach.type == achievement_type and not ach.hidden
            ]
            
            for achievement in relevant_achievements:
                # 現在の進捗を取得
                current_progress = await self._get_current_progress(guild_id, user_id, achievement.id)
                new_progress = current_progress + increment
                
                # 既に達成済みかチェック
                if current_progress >= achievement.condition.target_value:
                    continue
                
                # 進捗更新
                await self._update_single_achievement_progress(
                    guild_id, user_id, achievement.id, new_progress, achievement.condition.target_value
                )
                
                # 新規達成チェック
                if (current_progress < achievement.condition.target_value and 
                    new_progress >= achievement.condition.target_value):
                    newly_completed.append(achievement.id)
                    await self._complete_achievement(guild_id, user_id, achievement)
            
            # キャッシュクリア
            user_key = self._get_user_key(guild_id, user_id)
            if user_key in self.user_progress_cache:
                del self.user_progress_cache[user_key]
            
            if newly_completed:
                logger.info(f"Guild {guild_id}, User {user_id}: 新規アチーブメント達成 {len(newly_completed)}個")
            
            return newly_completed
            
        except Exception as e:
            logger.error(f"アチーブメント進捗更新エラー: {e}")
            return []
    
    async def _get_current_progress(self, guild_id: int, user_id: int, achievement_id: str) -> int:
        """現在の進捗値を取得"""
        try:
            query = """
                SELECT current_progress 
                FROM user_achievements 
                WHERE guild_id = $1 AND user_id = $2 AND achievement_id = $3
            """
            result = await execute_query(query, guild_id, user_id, achievement_id, fetch_type='row')
            return result['current_progress'] if result else 0
            
        except Exception:
            return 0
    
    async def _update_single_achievement_progress(self, guild_id: int, user_id: int,
                                                achievement_id: str, new_progress: int,
                                                target_value: int) -> None:
        """単一アチーブメントの進捗更新"""
        is_completed = new_progress >= target_value
        completion_date = datetime.now() if is_completed else None
        
        query = """
            INSERT INTO user_achievements (guild_id, user_id, achievement_id, current_progress, is_completed, completion_date)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (guild_id, user_id, achievement_id)
            DO UPDATE SET
                current_progress = EXCLUDED.current_progress,
                is_completed = EXCLUDED.is_completed,
                completion_date = CASE 
                    WHEN EXCLUDED.is_completed AND user_achievements.completion_date IS NULL 
                    THEN EXCLUDED.completion_date
                    ELSE user_achievements.completion_date
                END,
                last_updated = CURRENT_TIMESTAMP
        """
        
        await execute_query(
            query, guild_id, user_id, achievement_id, 
            new_progress, is_completed, completion_date, 
            fetch_type='status'
        )
    
    async def _complete_achievement(self, guild_id: int, user_id: int, achievement: Achievement) -> None:
        """アチーブメント達成時の処理（報酬付与等）"""
        try:
            # XP報酬付与
            if achievement.xp_reward > 0:
                # メインレベリングシステムにXPを追加
                # これは後でrank.pyとの統合時に実装
                logger.info(f"XP報酬付与: {achievement.xp_reward} XP (User: {user_id})")
            
            # スキルポイント報酬付与
            if achievement.skill_points_reward > 0:
                await self._award_skill_points(
                    guild_id, user_id, achievement.skill_points_reward, 
                    "achievement", achievement.id
                )
            
            # 統計更新
            await self._update_gamification_stats(guild_id, user_id)
            
            logger.info(f"アチーブメント達成: {achievement.name} (Guild: {guild_id}, User: {user_id})")
            
        except Exception as e:
            logger.error(f"アチーブメント達成処理エラー: {e}")
    
    async def _award_skill_points(self, guild_id: int, user_id: int, points: int, 
                                source: str, source_id: Optional[str] = None) -> None:
        """スキルポイント付与"""
        try:
            # 履歴記録
            query = """
                INSERT INTO skill_point_history (guild_id, user_id, points_gained, source, source_id, description)
                VALUES ($1, $2, $3, $4, $5, $6)
            """
            description = f"{source}によるスキルポイント獲得"
            
            await execute_query(
                query, guild_id, user_id, points, source, source_id, description,
                fetch_type='status'
            )
            
            # 統計更新
            await self._update_total_skill_points(guild_id, user_id, points)
            
        except Exception as e:
            logger.error(f"スキルポイント付与エラー: {e}")
    
    async def _update_total_skill_points(self, guild_id: int, user_id: int, points_to_add: int) -> None:
        """総スキルポイント更新"""
        try:
            query = """
                INSERT INTO gamification_stats (guild_id, user_id, total_skill_points_earned)
                VALUES ($1, $2, $3)
                ON CONFLICT (guild_id, user_id)
                DO UPDATE SET 
                    total_skill_points_earned = gamification_stats.total_skill_points_earned + EXCLUDED.total_skill_points_earned,
                    last_updated = CURRENT_TIMESTAMP
            """
            
            await execute_query(query, guild_id, user_id, points_to_add, fetch_type='status')
            
        except Exception as e:
            logger.error(f"スキルポイント統計更新エラー: {e}")
    
    async def _update_gamification_stats(self, guild_id: int, user_id: int) -> None:
        """ゲーミフィケーション統計更新"""
        try:
            # アチーブメント統計を計算
            achievement_query = """
                SELECT 
                    COUNT(*) as total_achievements,
                    COUNT(*) FILTER (WHERE is_completed = TRUE) as completed_achievements
                FROM user_achievements
                WHERE guild_id = $1 AND user_id = $2
            """
            result = await execute_query(achievement_query, guild_id, user_id, fetch_type='row')
            
            total_achievements = result['total_achievements'] if result else 0
            completed_achievements = result['completed_achievements'] if result else 0
            completion_rate = (completed_achievements / total_achievements * 100) if total_achievements > 0 else 0.0
            
            # 統計更新
            update_query = """
                INSERT INTO gamification_stats (
                    guild_id, user_id, total_achievements, completed_achievements, achievement_completion_rate
                )
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (guild_id, user_id)
                DO UPDATE SET 
                    total_achievements = EXCLUDED.total_achievements,
                    completed_achievements = EXCLUDED.completed_achievements,
                    achievement_completion_rate = EXCLUDED.achievement_completion_rate,
                    last_updated = CURRENT_TIMESTAMP
            """
            
            await execute_query(
                update_query, guild_id, user_id, total_achievements, 
                completed_achievements, completion_rate, fetch_type='status'
            )
            
        except Exception as e:
            logger.error(f"ゲーミフィケーション統計更新エラー: {e}")
    
    async def get_available_skills(self, guild_id: int, user_id: int) -> List[SkillNode]:
        """利用可能スキル一覧取得"""
        try:
            # ユーザーの習得済みスキル取得
            user_skills = await self._get_user_skills(guild_id, user_id)
            unlocked_skill_ids = set(user_skills.keys())
            
            # 利用可能スキルをフィルタ
            available_skills = []
            
            for skill in self.skill_cache.values():
                # 既に最大レベルに達している場合はスキップ
                if (skill.id in user_skills and 
                    user_skills[skill.id].current_level >= skill.max_level):
                    continue
                
                # 前提条件チェック
                if skill.prerequisites:
                    prerequisites_met = all(
                        prereq_id in unlocked_skill_ids 
                        for prereq_id in skill.prerequisites
                    )
                    if not prerequisites_met:
                        continue
                
                available_skills.append(skill)
            
            # ティアとコスト順でソート
            available_skills.sort(key=lambda s: (s.tier, s.skill_points_cost))
            
            return available_skills
            
        except Exception as e:
            logger.error(f"利用可能スキル取得エラー: {e}")
            return []
    
    async def _get_user_skills(self, guild_id: int, user_id: int) -> Dict[str, UserSkill]:
        """ユーザーの習得スキル取得"""
        user_key = self._get_user_key(guild_id, user_id)
        
        # キャッシュチェック
        if user_key in self.user_skills_cache:
            return self.user_skills_cache[user_key]
        
        try:
            query = """
                SELECT skill_id, current_level, total_invested_points, unlocked_at, last_upgraded
                FROM user_skills
                WHERE guild_id = $1 AND user_id = $2
                ORDER BY unlocked_at
            """
            results = await execute_query(query, guild_id, user_id)
            
            skills_dict = {}
            
            for row in results or []:
                user_skill = UserSkill(
                    guild_id=guild_id,
                    user_id=user_id,
                    skill_id=row['skill_id'],
                    current_level=row['current_level'],
                    total_invested_points=row['total_invested_points'],
                    unlocked_at=row['unlocked_at'],
                    last_upgraded=row['last_upgraded']
                )
                
                skills_dict[row['skill_id']] = user_skill
            
            # キャッシュに保存
            self.user_skills_cache[user_key] = skills_dict
            
            return skills_dict
            
        except Exception as e:
            logger.error(f"ユーザースキル取得エラー: {e}")
            return {}

# グローバルインスタンス
achievement_manager = AchievementManager()
