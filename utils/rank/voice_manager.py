"""
音声チャンネルXP・複数トラックシステム　コアエンジン

音声活動の追跡、XP計算、セッション管理を行う
リアルタイム音声XPシステムのメインエンジン。
"""

import uuid
import time
import asyncio
from typing import Dict, Optional, Tuple, Set
from datetime import datetime
from dataclasses import dataclass

from models.rank.voice_activity import (
    VoiceConfig, VoiceSession, VoiceActivityType,
    VoiceTrackType, VoiceChannelConfig, VoicePresets
)
from utils.logging import setup_logging
from utils.database import execute_query

logger = setup_logging("VOICE_MANAGER")

@dataclass
class ActiveSession:
    """アクティブセッション用の軽量データクラス"""
    session_id: str
    guild_id: int
    user_id: int
    channel_id: int
    start_time: datetime
    current_activity: VoiceActivityType
    last_activity_time: datetime
    
    # 累積時間（秒）
    speaking_seconds: int = 0
    listening_seconds: int = 0
    afk_seconds: int = 0
    
    # セッション情報
    current_participants: int = 1
    pending_xp: int = 0
    last_xp_calculation: datetime = None
    
    def __post_init__(self):
        if self.last_xp_calculation is None:
            self.last_xp_calculation = self.start_time

class VoiceManager:
    """音声チャンネルXPシステム管理クラス"""
    
    def __init__(self):
        # アクティブセッション管理
        self.active_sessions: Dict[str, ActiveSession] = {}
        self.guild_configs: Dict[int, Tuple[VoiceConfig, float]] = {}
        self.config_cache_ttl = 300  # 5分間キャッシュ
        
        # XP計算タスク管理
        self.xp_calculation_tasks: Dict[int, asyncio.Task] = {}
        
        # 参加者数トラッキング
        self.channel_participants: Dict[str, Set[int]] = {}
    
    def _get_user_key(self, guild_id: int, user_id: int) -> str:
        return f"{guild_id}:{user_id}"
    
    def _get_channel_key(self, guild_id: int, channel_id: int) -> str:
        return f"{guild_id}:{channel_id}"
    
    async def get_guild_voice_config(self, guild_id: int) -> VoiceConfig:
        """ギルドの音声XP設定を取得（キャッシュ対応）"""
        current_time = time.time()
        
        # キャッシュチェック
        if guild_id in self.guild_configs:
            config, cached_time = self.guild_configs[guild_id]
            if current_time - cached_time < self.config_cache_ttl:
                return config
        
        try:
            query = "SELECT config_data FROM voice_configs WHERE guild_id = $1"
            result = await execute_query(query, guild_id, fetch_type='row')
            
            if result and result["config_data"]:
                config = VoiceConfig.model_validate_json(result["config_data"])
            else:
                config = VoicePresets.get_balanced()
                await self.save_guild_voice_config(guild_id, config, save_to_db=True)
            
            self.guild_configs[guild_id] = (config, current_time)
            return config
            
        except Exception as e:
            logger.error(f"Guild {guild_id}: 音声XP設定読み込みエラー {e}")
            return VoicePresets.get_balanced()
    
    async def save_guild_voice_config(self, guild_id: int, config: VoiceConfig, updated_by: Optional[int] = None, save_to_db: bool = True) -> bool:
        """ギルドの音声XP設定を保存"""
        try:
            if save_to_db:
                config_json = config.model_dump_json()
                
                query = """
                INSERT INTO voice_configs (guild_id, config_data, voice_xp_enabled, global_voice_multiplier, daily_voice_xp_limit, updated_by, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, NOW())
                ON CONFLICT (guild_id)
                DO UPDATE SET 
                    config_data = EXCLUDED.config_data,
                    voice_xp_enabled = EXCLUDED.voice_xp_enabled,
                    updated_at = NOW()
                """
                
                await execute_query(
                    query, guild_id, config_json, config.voice_xp_enabled, 
                    config.global_voice_multiplier, config.daily_voice_xp_limit, 
                    updated_by, fetch_type='status'
                )
            
            current_time = time.time()
            self.guild_configs[guild_id] = (config, current_time)
            return True
            
        except Exception as e:
            logger.error(f"Guild {guild_id}: 音声XP設定保存エラー {e}")
            return False
    
    async def start_voice_session(self, guild_id: int, user_id: int, channel_id: int, initial_activity: VoiceActivityType = VoiceActivityType.LISTENING) -> str:
        """音声セッションを開始"""
        try:
            config = await self.get_guild_voice_config(guild_id)
            
            if not config.voice_xp_enabled:
                return None
            
            if channel_id in config.excluded_channel_ids or user_id in config.excluded_user_ids:
                return None
            
            user_key = self._get_user_key(guild_id, user_id)
            
            # 既存セッションを終了
            if user_key in self.active_sessions:
                await self.end_voice_session(guild_id, user_id, force_end=True)
            
            # 新しいセッション作成
            session_id = str(uuid.uuid4())
            current_time = datetime.now()
            
            active_session = ActiveSession(
                session_id=session_id, guild_id=guild_id, user_id=user_id, 
                channel_id=channel_id, start_time=current_time,
                current_activity=initial_activity, last_activity_time=current_time
            )
            
            self.active_sessions[user_key] = active_session
            
            # 参加者数更新
            channel_key = self._get_channel_key(guild_id, channel_id)
            if channel_key not in self.channel_participants:
                self.channel_participants[channel_key] = set()
            self.channel_participants[channel_key].add(user_id)
            active_session.current_participants = len(self.channel_participants[channel_key])
            
            # データベースに初期セッション記録を作成
            await self._create_session_in_db(active_session, config)
            
            # XP計算タスクを開始
            await self._ensure_xp_calculation_task(guild_id, config)
            
            logger.info(f"Guild {guild_id}, User {user_id}: 音声セッション開始")
            return session_id
            
        except Exception as e:
            logger.error(f"Guild {guild_id}, User {user_id}: セッション開始エラー {e}")
            return None
    
    async def end_voice_session(self, guild_id: int, user_id: int, force_end: bool = False) -> Optional[VoiceSession]:
        """音声セッションを終了"""
        try:
            user_key = self._get_user_key(guild_id, user_id)
            
            if user_key not in self.active_sessions:
                return None
            
            active_session = self.active_sessions[user_key]
            current_time = datetime.now()
            
            # 最終XP計算
            await self._calculate_session_xp(active_session, current_time)
            
            # セッション時間計算
            duration_seconds = int((current_time - active_session.start_time).total_seconds())
            
            # 最小セッション時間チェック
            config = await self.get_guild_voice_config(guild_id)
            if duration_seconds < config.min_voice_session_seconds and not force_end:
                del self.active_sessions[user_key]
                self._remove_user_from_channel(guild_id, active_session.channel_id, user_id)
                return None
            
            # VoiceSessionオブジェクト作成
            completed_session = VoiceSession(
                guild_id=guild_id, user_id=user_id, channel_id=active_session.channel_id,
                session_id=active_session.session_id, start_time=active_session.start_time,
                end_time=current_time, duration_seconds=duration_seconds,
                total_speaking_seconds=active_session.speaking_seconds,
                total_listening_seconds=active_session.listening_seconds,
                total_afk_seconds=active_session.afk_seconds,
                base_xp_earned=active_session.pending_xp,
                total_xp_earned=active_session.pending_xp,
                peak_participants=active_session.current_participants,
                track_type=self._get_channel_track_type(config, active_session.channel_id),
                is_completed=True
            )
            
            # データベースでセッション完了
            await self._complete_session_in_db(completed_session)
            
            # アクティブセッションから削除
            del self.active_sessions[user_key]
            self._remove_user_from_channel(guild_id, active_session.channel_id, user_id)
            
            logger.info(f"Guild {guild_id}, User {user_id}: 音声セッション終了 (時間: {duration_seconds}s, XP: {completed_session.total_xp_earned})")
            return completed_session
            
        except Exception as e:
            logger.error(f"Guild {guild_id}, User {user_id}: セッション終了エラー {e}")
            return None
    
    async def update_voice_activity(self, guild_id: int, user_id: int, new_activity: VoiceActivityType, speaking: bool = False):
        """ユーザーの音声活動状態を更新"""
        try:
            user_key = self._get_user_key(guild_id, user_id)
            
            if user_key not in self.active_sessions:
                return
            
            active_session = self.active_sessions[user_key]
            current_time = datetime.now()
            
            # 前回からの経過時間計算
            time_diff = (current_time - active_session.last_activity_time).total_seconds()
            
            # 前の活動状態の時間を累積
            if active_session.current_activity == VoiceActivityType.SPEAKING:
                active_session.speaking_seconds += int(time_diff)
            elif active_session.current_activity == VoiceActivityType.LISTENING:
                active_session.listening_seconds += int(time_diff)
            elif active_session.current_activity == VoiceActivityType.AFK:
                active_session.afk_seconds += int(time_diff)
            
            # 状態更新
            active_session.current_activity = new_activity
            active_session.last_activity_time = current_time
            
        except Exception as e:
            logger.error(f"Guild {guild_id}, User {user_id}: 活動状態更新エラー {e}")
    
    async def _calculate_session_xp(self, active_session: ActiveSession, current_time: datetime):
        """セッションのXPを計算して加算"""
        try:
            config = await self.get_guild_voice_config(active_session.guild_id)
            
            # 前回計算からの経過時間
            time_since_last = (current_time - active_session.last_xp_calculation).total_seconds()
            
            if time_since_last < config.xp_calculation_interval:
                return
            
            # チャンネル設定取得
            channel_config = config.get_channel_config(active_session.channel_id)
            
            # 基本XP計算（分単位）
            minutes_elapsed = time_since_last / 60.0
            base_xp = int(channel_config.base_xp_per_minute * minutes_elapsed)
            
            # 活動倍率適用
            activity_multiplier = config.get_activity_multiplier(active_session.channel_id, active_session.current_activity)
            
            # 参加者数ボーナス
            participant_multiplier = self._get_participant_multiplier(active_session.current_participants, channel_config)
            
            # 時間帯倍率
            time_multiplier = self._get_time_multiplier(current_time, channel_config)
            
            # トラック倍率
            track_type = self._get_channel_track_type(config, active_session.channel_id)
            track_multiplier = config.tracks[track_type].global_multiplier if track_type in config.tracks else 1.0
            
            # 最終XP計算
            total_multiplier = activity_multiplier * participant_multiplier * time_multiplier * track_multiplier * config.global_voice_multiplier
            calculated_xp = int(base_xp * total_multiplier)
            
            # 上限チェック
            max_xp_per_calculation = int((channel_config.max_xp_per_hour * time_since_last) / 3600)
            calculated_xp = min(calculated_xp, max_xp_per_calculation)
            
            # XP加算
            if calculated_xp > 0:
                active_session.pending_xp += calculated_xp
            
            # 計算時間更新
            active_session.last_xp_calculation = current_time
            
        except Exception as e:
            logger.error(f"XP計算エラー: {e}")
    
    def _get_participant_multiplier(self, participant_count: int, channel_config: VoiceChannelConfig) -> float:
        """参加者数に基づく倍率を取得"""
        if participant_count == 1:
            return channel_config.participant_bonus.get("solo", 0.5)
        elif 2 <= participant_count <= 4:
            return channel_config.participant_bonus.get("small", 1.0)
        elif 5 <= participant_count <= 8:
            return channel_config.participant_bonus.get("medium", 1.3)
        elif 9 <= participant_count <= 15:
            return channel_config.participant_bonus.get("large", 1.5)
        else:
            return channel_config.participant_bonus.get("huge", 1.2)
    
    def _get_time_multiplier(self, current_time: datetime, channel_config: VoiceChannelConfig) -> float:
        """時間帯に基づく倍率を取得"""
        hour = current_time.hour
        
        if 6 <= hour < 12:
            return channel_config.time_multipliers.get("morning", 1.0)
        elif 12 <= hour < 18:
            return channel_config.time_multipliers.get("afternoon", 1.2)
        elif 18 <= hour < 22:
            return channel_config.time_multipliers.get("evening", 1.5)
        else:
            return channel_config.time_multipliers.get("night", 0.8)
    
    def _get_channel_track_type(self, config: VoiceConfig, channel_id: int) -> VoiceTrackType:
        """チャンネルのトラックタイプを取得"""
        if channel_id in config.channels:
            return VoiceTrackType(config.channels[channel_id].track_type)
        return VoiceTrackType.GENERAL
    
    def _remove_user_from_channel(self, guild_id: int, channel_id: int, user_id: int):
        """チャンネルから参加者を削除"""
        channel_key = self._get_channel_key(guild_id, channel_id)
        if channel_key in self.channel_participants:
            self.channel_participants[channel_key].discard(user_id)
            if not self.channel_participants[channel_key]:
                del self.channel_participants[channel_key]
    
    async def _create_session_in_db(self, active_session: ActiveSession, config: VoiceConfig):
        """データベースにセッション記録を作成"""
        try:
            track_type = self._get_channel_track_type(config, active_session.channel_id)
            
            query = """
            INSERT INTO voice_sessions (session_id, guild_id, user_id, channel_id, start_time, track_type, peak_participants, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
            """
            
            await execute_query(query, active_session.session_id, active_session.guild_id, active_session.user_id,
                               active_session.channel_id, active_session.start_time, track_type.value, 
                               active_session.current_participants, fetch_type='status')
            
        except Exception as e:
            logger.error(f"セッション作成エラー: {e}")
    
    async def _complete_session_in_db(self, completed_session: VoiceSession):
        """データベースでセッションを完了"""
        try:
            query = """
            UPDATE voice_sessions SET end_time = $1, duration_seconds = $2, total_speaking_seconds = $3, 
                   total_listening_seconds = $4, total_afk_seconds = $5, base_xp_earned = $6, 
                   total_xp_earned = $7, peak_participants = $8, is_completed = TRUE
            WHERE session_id = $9
            """
            
            await execute_query(query, completed_session.end_time, completed_session.duration_seconds,
                               completed_session.total_speaking_seconds, completed_session.total_listening_seconds,
                               completed_session.total_afk_seconds, completed_session.base_xp_earned,
                               completed_session.total_xp_earned, completed_session.peak_participants,
                               completed_session.session_id, fetch_type='status')
            
        except Exception as e:
            logger.error(f"セッション完了エラー: {e}")
    
    async def _ensure_xp_calculation_task(self, guild_id: int, config: VoiceConfig):
        """XP計算タスクが動作していることを確認"""
        if guild_id in self.xp_calculation_tasks:
            task = self.xp_calculation_tasks[guild_id]
            if not task.done():
                return
        
        # 新しいタスクを開始
        task = asyncio.create_task(self._xp_calculation_loop(guild_id, config.xp_calculation_interval))
        self.xp_calculation_tasks[guild_id] = task
    
    async def _xp_calculation_loop(self, guild_id: int, interval_seconds: int):
        """XP計算ループ（バックグラウンドタスク）"""
        try:
            while True:
                await asyncio.sleep(interval_seconds)
                
                # このギルドのアクティブセッションに対してXP計算
                current_time = datetime.now()
                guild_sessions = [session for session in self.active_sessions.values() if session.guild_id == guild_id]
                
                if not guild_sessions:
                    break
                
                for session in guild_sessions:
                    await self._calculate_session_xp(session, current_time)
                    
        except Exception as e:
            logger.error(f"XP計算ループエラー: {e}")
        finally:
            if guild_id in self.xp_calculation_tasks:
                del self.xp_calculation_tasks[guild_id]

# モジュールレベルのインスタンス
voice_manager = VoiceManager()
