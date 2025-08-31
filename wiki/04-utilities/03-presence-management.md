# プレゼンス管理

## C.O.M.E.T.について

**C.O.M.E.T.**の名前は以下の頭文字から構成されています：

- **C**ommunity of
- **O**shilove
- **M**oderation &
- **E**njoyment
- **T**ogether

HFS - ホロライブ非公式ファンサーバーのコミュニティを支える、推し愛とモデレーション、そして楽しさを一緒に提供するボットです。

## 概要

COMETボットのプレゼンス管理システムは、ボットのステータス、アクティビティ、オンライン状態を動的に管理します。システム状態の反映、カスタムメッセージの表示、スケジュール管理機能を提供し、ユーザーにボットの状態を分かりやすく伝えます。

## プレゼンス管理アーキテクチャ

```
┌─────────────────────────────────────────────────────────────┐
│                プレゼンス管理アーキテクチャ                   │
├─────────────────────────────────────────────────────────────┤
│  プレゼンス制御層 (Presence Control)                        │
│  ├── ステータス管理                                          │
│  ├── アクティビティ管理                                      │
│  ├── スケジューラー                                          │
│  └── 動的更新システム                                        │
├─────────────────────────────────────────────────────────────┤
│  状態監視層 (State Monitoring)                              │
│  ├── システム状態監視                                        │
│  ├── パフォーマンス監視                                      │
│  ├── エラー状態検出                                          │
│  └── 外部サービス状態                                        │
├─────────────────────────────────────────────────────────────┤
│  メッセージ管理層 (Message Management)                      │
│  ├── 定型メッセージ                                          │
│  ├── カスタムメッセージ                                      │
│  ├── 多言語対応                                              │
│  └── テンプレートシステム                                    │
├─────────────────────────────────────────────────────────────┤
│  表示層 (Display Layer)                                     │
│  ├── Discord ステータス                                     │
│  ├── アクティビティ表示                                      │
│  ├── カスタムステータス                                      │
│  └── リッチプレゼンス                                        │
└─────────────────────────────────────────────────────────────┘
```

## プレゼンス管理システム

### 1. 基本プレゼンス管理

```python
import discord
import asyncio
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class PresenceType(Enum):
    PLAYING = discord.ActivityType.playing
    STREAMING = discord.ActivityType.streaming
    LISTENING = discord.ActivityType.listening
    WATCHING = discord.ActivityType.watching
    CUSTOM = discord.ActivityType.custom
    COMPETING = discord.ActivityType.competing

class PresenceStatus(Enum):
    ONLINE = discord.Status.online
    IDLE = discord.Status.idle
    DND = discord.Status.dnd
    INVISIBLE = discord.Status.invisible

class PresenceManager:
    def __init__(self, bot):
        self.bot = bot
        self.current_presence = None
        self.presence_queue = []
        self.auto_rotation_enabled = True
        self.rotation_interval = 300  # 5分
        self.last_update = None
        
        # プレゼンステンプレート
        self.presence_templates = {
            "default": [
                {"type": PresenceType.WATCHING, "name": "HFS コミュニティ", "status": PresenceStatus.ONLINE},
                {"type": PresenceType.LISTENING, "name": "ホロライブ音楽", "status": PresenceStatus.ONLINE},
                {"type": PresenceType.PLAYING, "name": "推し活サポート", "status": PresenceStatus.ONLINE},
                {"type": PresenceType.WATCHING, "name": "配信アーカイブ", "status": PresenceStatus.ONLINE},
            ],
            "maintenance": [
                {"type": PresenceType.PLAYING, "name": "メンテナンス中...", "status": PresenceStatus.DND},
                {"type": PresenceType.WATCHING, "name": "システム更新", "status": PresenceStatus.DND},
            ],
            "error": [
                {"type": PresenceType.PLAYING, "name": "エラー復旧中", "status": PresenceStatus.IDLE},
                {"type": PresenceType.WATCHING, "name": "システム診断", "status": PresenceStatus.IDLE},
            ],
            "celebration": [
                {"type": PresenceType.PLAYING, "name": "🎉 記念日", "status": PresenceStatus.ONLINE},
                {"type": PresenceType.WATCHING, "name": "🎊 特別配信", "status": PresenceStatus.ONLINE},
            ]
        }
        
        # 動的プレゼンス情報
        self.dynamic_info = {
            "guild_count": 0,
            "user_count": 0,
            "uptime": None,
            "version": "2.1.0"
        }
        
        # プレゼンス更新タスク
        self.presence_task = None
    
    async def start_presence_management(self):
        """プレゼンス管理の開始"""
        if self.presence_task is None or self.presence_task.done():
            self.presence_task = self.bot.loop.create_task(self.presence_update_loop())
            logger.info("Presence management started")
    
    async def stop_presence_management(self):
        """プレゼンス管理の停止"""
        if self.presence_task and not self.presence_task.done():
            self.presence_task.cancel()
            logger.info("Presence management stopped")
    
    async def presence_update_loop(self):
        """プレゼンス更新ループ"""
        await self.bot.wait_until_ready()
        
        while not self.bot.is_closed():
            try:
                if self.auto_rotation_enabled:
                    await self.rotate_presence()
                
                await asyncio.sleep(self.rotation_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Presence update loop error: {e}")
                await asyncio.sleep(60)
    
    async def rotate_presence(self):
        """プレゼンスのローテーション"""
        try:
            # 現在のシステム状態に基づいてテンプレートを選択
            template_name = self.get_current_template()
            templates = self.presence_templates.get(template_name, self.presence_templates["default"])
            
            # ランダムにプレゼンスを選択
            presence_config = random.choice(templates)
            
            # 動的情報を含むプレゼンスを生成
            dynamic_presence = await self.generate_dynamic_presence(presence_config)
            
            await self.set_presence(dynamic_presence)
            
        except Exception as e:
            logger.error(f"Failed to rotate presence: {e}")
    
    def get_current_template(self) -> str:
        """現在のシステム状態に基づいてテンプレートを決定"""
        # システム状態の確認
        if self.is_maintenance_mode():
            return "maintenance"
        elif self.has_critical_errors():
            return "error"
        elif self.is_special_event():
            return "celebration"
        else:
            return "default"
    
    def is_maintenance_mode(self) -> bool:
        """メンテナンスモードかどうかを確認"""
        # 実装は具体的な条件に依存
        return False
    
    def has_critical_errors(self) -> bool:
        """重大なエラーがあるかどうかを確認"""
        # エラー監視システムとの連携
        return False
    
    def is_special_event(self) -> bool:
        """特別なイベント期間かどうかを確認"""
        # 記念日やイベントの確認
        now = datetime.now()
        # 例: ホロライブ記念日など
        return False
    
    async def generate_dynamic_presence(self, base_config: Dict) -> Dict:
        """動的情報を含むプレゼンスの生成"""
        # 動的情報の更新
        await self.update_dynamic_info()
        
        presence_name = base_config["name"]
        
        # 動的プレースホルダーの置換
        presence_name = presence_name.replace("{guild_count}", str(self.dynamic_info["guild_count"]))
        presence_name = presence_name.replace("{user_count}", str(self.dynamic_info["user_count"]))
        presence_name = presence_name.replace("{version}", self.dynamic_info["version"])
        
        # アップタイムの表示
        if "{uptime}" in presence_name and self.dynamic_info["uptime"]:
            uptime_str = self.format_uptime(self.dynamic_info["uptime"])
            presence_name = presence_name.replace("{uptime}", uptime_str)
        
        return {
            "type": base_config["type"],
            "name": presence_name,
            "status": base_config["status"]
        }
    
    async def update_dynamic_info(self):
        """動的情報の更新"""
        try:
            self.dynamic_info["guild_count"] = len(self.bot.guilds)
            self.dynamic_info["user_count"] = sum(guild.member_count for guild in self.bot.guilds)
            
            # アップタイムの計算
            if hasattr(self.bot, 'start_time'):
                self.dynamic_info["uptime"] = datetime.now() - self.bot.start_time
                
        except Exception as e:
            logger.error(f"Failed to update dynamic info: {e}")
    
    def format_uptime(self, uptime: timedelta) -> str:
        """アップタイムのフォーマット"""
        days = uptime.days
        hours, remainder = divmod(uptime.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        
        if days > 0:
            return f"{days}d {hours}h"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"
    
    async def set_presence(self, presence_config: Dict):
        """プレゼンスの設定"""
        try:
            activity_type = presence_config["type"].value
            activity_name = presence_config["name"]
            status = presence_config["status"].value
            
            # アクティビティの作成
            if activity_type == discord.ActivityType.streaming:
                activity = discord.Streaming(
                    name=activity_name,
                    url="https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # ダミーURL
                )
            else:
                activity = discord.Activity(
                    type=activity_type,
                    name=activity_name
                )
            
            # プレゼンスの更新
            await self.bot.change_presence(status=status, activity=activity)
            
            self.current_presence = presence_config
            self.last_update = datetime.now()
            
            logger.debug(f"Presence updated: {activity_name} ({status.name})")
            
        except Exception as e:
            logger.error(f"Failed to set presence: {e}")
    
    async def set_custom_presence(self, activity_type: PresenceType, name: str, status: PresenceStatus = PresenceStatus.ONLINE, duration: int = None):
        """カスタムプレゼンスの設定"""
        presence_config = {
            "type": activity_type,
            "name": name,
            "status": status
        }
        
        await self.set_presence(presence_config)
        
        # 一時的なプレゼンスの場合、指定時間後に元に戻す
        if duration:
            await asyncio.sleep(duration)
            await self.rotate_presence()
    
    def add_custom_template(self, template_name: str, presences: List[Dict]):
        """カスタムテンプレートの追加"""
        self.presence_templates[template_name] = presences
        logger.info(f"Added custom presence template: {template_name}")
    
    def remove_template(self, template_name: str):
        """テンプレートの削除"""
        if template_name in self.presence_templates and template_name != "default":
            del self.presence_templates[template_name]
            logger.info(f"Removed presence template: {template_name}")
    
    def set_rotation_interval(self, seconds: int):
        """ローテーション間隔の設定"""
        self.rotation_interval = max(60, seconds)  # 最小1分
        logger.info(f"Presence rotation interval set to {self.rotation_interval} seconds")
    
    def enable_auto_rotation(self):
        """自動ローテーションの有効化"""
        self.auto_rotation_enabled = True
        logger.info("Auto presence rotation enabled")
    
    def disable_auto_rotation(self):
        """自動ローテーションの無効化"""
        self.auto_rotation_enabled = False
        logger.info("Auto presence rotation disabled")
    
    def get_current_presence_info(self) -> Dict:
        """現在のプレゼンス情報を取得"""
        return {
            "current_presence": self.current_presence,
            "last_update": self.last_update,
            "auto_rotation": self.auto_rotation_enabled,
            "rotation_interval": self.rotation_interval,
            "dynamic_info": self.dynamic_info
        }
```

### 2. イベント連動プレゼンス

```python
class EventDrivenPresence:
    def __init__(self, presence_manager: PresenceManager):
        self.presence_manager = presence_manager
        self.event_handlers = {}
        self.temporary_presences = {}
    
    def register_event_handler(self, event_name: str, handler: callable):
        """イベントハンドラーの登録"""
        if event_name not in self.event_handlers:
            self.event_handlers[event_name] = []
        self.event_handlers[event_name].append(handler)
    
    async def handle_event(self, event_name: str, event_data: Dict = None):
        """イベントの処理"""
        if event_name in self.event_handlers:
            for handler in self.event_handlers[event_name]:
                try:
                    await handler(event_data or {})
                except Exception as e:
                    logger.error(f"Event handler error for {event_name}: {e}")
    
    async def on_command_executed(self, event_data: Dict):
        """コマンド実行時のプレゼンス更新"""
        command_name = event_data.get("command_name")
        user_count = event_data.get("user_count", 0)
        
        if command_name:
            temp_presence = {
                "type": PresenceType.PLAYING,
                "name": f"/{command_name} コマンド実行中",
                "status": PresenceStatus.ONLINE
            }
            
            await self.presence_manager.set_custom_presence(
                temp_presence["type"],
                temp_presence["name"],
                temp_presence["status"],
                duration=30  # 30秒間表示
            )
    
    async def on_error_occurred(self, event_data: Dict):
        """エラー発生時のプレゼンス更新"""
        error_severity = event_data.get("severity", "LOW")
        
        if error_severity in ["HIGH", "CRITICAL"]:
            error_presence = {
                "type": PresenceType.PLAYING,
                "name": "⚠️ システム問題を調査中",
                "status": PresenceStatus.IDLE
            }
            
            await self.presence_manager.set_custom_presence(
                error_presence["type"],
                error_presence["name"],
                error_presence["status"],
                duration=600  # 10分間表示
            )
    
    async def on_maintenance_start(self, event_data: Dict):
        """メンテナンス開始時のプレゼンス更新"""
        maintenance_presence = {
            "type": PresenceType.PLAYING,
            "name": "🔧 メンテナンス中",
            "status": PresenceStatus.DND
        }
        
        # メンテナンス中は自動ローテーションを無効化
        self.presence_manager.disable_auto_rotation()
        
        await self.presence_manager.set_custom_presence(
            maintenance_presence["type"],
            maintenance_presence["name"],
            maintenance_presence["status"]
        )
    
    async def on_maintenance_end(self, event_data: Dict):
        """メンテナンス終了時のプレゼンス更新"""
        # 自動ローテーションを再開
        self.presence_manager.enable_auto_rotation()
        
        completion_presence = {
            "type": PresenceType.PLAYING,
            "name": "✅ メンテナンス完了",
            "status": PresenceStatus.ONLINE
        }
        
        await self.presence_manager.set_custom_presence(
            completion_presence["type"],
            completion_presence["name"],
            completion_presence["status"],
            duration=120  # 2分間表示
        )
    
    async def on_special_event(self, event_data: Dict):
        """特別イベント時のプレゼンス更新"""
        event_name = event_data.get("event_name", "特別イベント")
        event_emoji = event_data.get("emoji", "🎉")
        
        event_presence = {
            "type": PresenceType.PLAYING,
            "name": f"{event_emoji} {event_name}",
            "status": PresenceStatus.ONLINE
        }
        
        await self.presence_manager.set_custom_presence(
            event_presence["type"],
            event_presence["name"],
            event_presence["status"],
            duration=3600  # 1時間表示
        )
```

### 3. スケジュール管理

```python
from datetime import time
import calendar

class PresenceScheduler:
    def __init__(self, presence_manager: PresenceManager):
        self.presence_manager = presence_manager
        self.schedules = {}
        self.timezone = "Asia/Tokyo"
    
    def add_schedule(self, schedule_name: str, schedule_config: Dict):
        """スケジュールの追加"""
        self.schedules[schedule_name] = schedule_config
        logger.info(f"Added presence schedule: {schedule_name}")
    
    def remove_schedule(self, schedule_name: str):
        """スケジュールの削除"""
        if schedule_name in self.schedules:
            del self.schedules[schedule_name]
            logger.info(f"Removed presence schedule: {schedule_name}")
    
    async def check_schedules(self):
        """スケジュールのチェック"""
        import pytz
        
        now = datetime.now(pytz.timezone(self.timezone))
        current_time = now.time()
        current_weekday = now.weekday()
        
        for schedule_name, config in self.schedules.items():
            if self.should_activate_schedule(config, current_time, current_weekday):
                await self.activate_schedule(schedule_name, config)
    
    def should_activate_schedule(self, config: Dict, current_time: time, current_weekday: int) -> bool:
        """スケジュールを有効化すべきかチェック"""
        # 時間チェック
        start_time = config.get("start_time")
        end_time = config.get("end_time")
        
        if start_time and end_time:
            if not (start_time <= current_time <= end_time):
                return False
        
        # 曜日チェック
        weekdays = config.get("weekdays")
        if weekdays and current_weekday not in weekdays:
            return False
        
        # 日付チェック
        specific_dates = config.get("specific_dates")
        if specific_dates:
            current_date = datetime.now().date()
            if current_date not in specific_dates:
                return False
        
        return True
    
    async def activate_schedule(self, schedule_name: str, config: Dict):
        """スケジュールの有効化"""
        presence_config = config.get("presence")
        if presence_config:
            await self.presence_manager.set_custom_presence(
                presence_config["type"],
                presence_config["name"],
                presence_config["status"],
                duration=config.get("duration")
            )
            
            logger.info(f"Activated scheduled presence: {schedule_name}")

# スケジュール設定例
def setup_default_schedules(scheduler: PresenceScheduler):
    """デフォルトスケジュールの設定"""
    
    # 平日の朝の挨拶
    scheduler.add_schedule("morning_greeting", {
        "start_time": time(8, 0),
        "end_time": time(9, 0),
        "weekdays": [0, 1, 2, 3, 4],  # 月-金
        "presence": {
            "type": PresenceType.PLAYING,
            "name": "🌅 おはようございます！",
            "status": PresenceStatus.ONLINE
        },
        "duration": 3600  # 1時間
    })
    
    # 深夜のメンテナンス時間
    scheduler.add_schedule("night_maintenance", {
        "start_time": time(2, 0),
        "end_time": time(4, 0),
        "presence": {
            "type": PresenceType.PLAYING,
            "name": "🌙 深夜メンテナンス",
            "status": PresenceStatus.IDLE
        }
    })
    
    # 週末の特別メッセージ
    scheduler.add_schedule("weekend_message", {
        "weekdays": [5, 6],  # 土日
        "presence": {
            "type": PresenceType.PLAYING,
            "name": "🎮 週末を楽しもう！",
            "status": PresenceStatus.ONLINE
        }
    })
```

### 4. プレゼンス統計

```python
class PresenceStatistics:
    def __init__(self):
        self.presence_history = []
        self.activity_counts = {}
        self.status_duration = {}
        self.last_reset = datetime.now()
    
    def record_presence_change(self, old_presence: Dict, new_presence: Dict):
        """プレゼンス変更の記録"""
        timestamp = datetime.now()
        
        change_record = {
            "timestamp": timestamp,
            "old_presence": old_presence,
            "new_presence": new_presence
        }
        
        self.presence_history.append(change_record)
        
        # 統計の更新
        self.update_statistics(new_presence, timestamp)
        
        # 履歴の制限（最新100件のみ保持）
        if len(self.presence_history) > 100:
            self.presence_history = self.presence_history[-100:]
    
    def update_statistics(self, presence: Dict, timestamp: datetime):
        """統計の更新"""
        activity_name = presence.get("name", "Unknown")
        status = presence.get("status", PresenceStatus.ONLINE).name
        
        # アクティビティカウント
        if activity_name not in self.activity_counts:
            self.activity_counts[activity_name] = 0
        self.activity_counts[activity_name] += 1
        
        # ステータス継続時間
        if status not in self.status_duration:
            self.status_duration[status] = timedelta()
    
    def get_statistics_summary(self) -> Dict:
        """統計サマリーの取得"""
        total_changes = len(self.presence_history)
        
        # 最も使用されたアクティビティ
        most_used_activity = max(self.activity_counts.items(), key=lambda x: x[1]) if self.activity_counts else ("None", 0)
        
        # 平均変更間隔
        if len(self.presence_history) > 1:
            time_diffs = []
            for i in range(1, len(self.presence_history)):
                diff = self.presence_history[i]["timestamp"] - self.presence_history[i-1]["timestamp"]
                time_diffs.append(diff.total_seconds())
            
            avg_interval = sum(time_diffs) / len(time_diffs)
        else:
            avg_interval = 0
        
        return {
            "total_changes": total_changes,
            "most_used_activity": most_used_activity,
            "average_change_interval": avg_interval,
            "activity_counts": dict(sorted(self.activity_counts.items(), key=lambda x: x[1], reverse=True)),
            "status_duration": self.status_duration,
            "period_start": self.last_reset,
            "period_end": datetime.now()
        }
    
    def reset_statistics(self):
        """統計のリセット"""
        self.presence_history.clear()
        self.activity_counts.clear()
        self.status_duration.clear()
        self.last_reset = datetime.now()
        logger.info("Presence statistics reset")
```

## 管理コマンド

### 1. プレゼンス管理コマンド

```python
class PresenceCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.presence_manager = PresenceManager(bot)
        self.event_presence = EventDrivenPresence(self.presence_manager)
        self.scheduler = PresenceScheduler(self.presence_manager)
        self.statistics = PresenceStatistics()
    
    @app_commands.command(name="presence_set", description="プレゼンスを設定")
    @app_commands.describe(
        activity_type="アクティビティタイプ",
        name="表示名",
        status="ステータス",
        duration="表示時間（秒）"
    )
    async def set_presence(
        self, 
        interaction: discord.Interaction, 
        activity_type: str,
        name: str,
        status: str = "online",
        duration: int = None
    ):
        """プレゼンスの手動設定"""
        
        # 権限チェック
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("この機能を使用する権限がありません。", ephemeral=True)
            return
        
        try:
            # タイプとステータスの変換
            presence_type = PresenceType[activity_type.upper()]
            presence_status = PresenceStatus[status.upper()]
            
            await self.presence_manager.set_custom_presence(
                presence_type, name, presence_status, duration
            )
            
            embed = discord.Embed(
                title="✅ プレゼンス設定完了",
                description=f"プレゼンスが設定されました。",
                color=0x00FF00
            )
            embed.add_field(name="タイプ", value=activity_type, inline=True)
            embed.add_field(name="表示名", value=name, inline=True)
            embed.add_field(name="ステータス", value=status, inline=True)
            
            if duration:
                embed.add_field(name="表示時間", value=f"{duration}秒", inline=True)
            
            await interaction.response.send_message(embed=embed)
            
        except KeyError as e:
            await interaction.response.send_message(f"無効な値です: {e}", ephemeral=True)
        except Exception as e:
            logger.error(f"Failed to set presence: {e}")
            await interaction.response.send_message("プレゼンスの設定に失敗しました。", ephemeral=True)
    
    @app_commands.command(name="presence_status", description="現在のプレゼンス状態を表示")
    async def show_presence_status(self, interaction: discord.Interaction):
        """プレゼンス状態の表示"""
        
        info = self.presence_manager.get_current_presence_info()
        
        embed = discord.Embed(
            title="📊 プレゼンス状態",
            color=0x0099FF
        )
        
        current = info.get("current_presence")
        if current:
            embed.add_field(name="現在のアクティビティ", value=current["name"], inline=False)
            embed.add_field(name="タイプ", value=current["type"].name, inline=True)
            embed.add_field(name="ステータス", value=current["status"].name, inline=True)
        
        embed.add_field(name="自動ローテーション", value="有効" if info["auto_rotation"] else "無効", inline=True)
        embed.add_field(name="ローテーション間隔", value=f"{info['rotation_interval']}秒", inline=True)
        
        if info.get("last_update"):
            embed.add_field(name="最終更新", value=info["last_update"].strftime("%Y-%m-%d %H:%M:%S"), inline=True)
        
        # 動的情報
        dynamic = info.get("dynamic_info", {})
        embed.add_field(name="サーバー数", value=dynamic.get("guild_count", 0), inline=True)
        embed.add_field(name="ユーザー数", value=dynamic.get("user_count", 0), inline=True)
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="presence_rotation", description="自動ローテーションの制御")
    @app_commands.describe(
        action="アクション（enable/disable）",
        interval="ローテーション間隔（秒）"
    )
    async def control_rotation(
        self, 
        interaction: discord.Interaction, 
        action: str,
        interval: int = None
    ):
        """自動ローテーションの制御"""
        
        # 権限チェック
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("この機能を使用する権限がありません。", ephemeral=True)
            return
        
        if action.lower() == "enable":
            self.presence_manager.enable_auto_rotation()
            if interval:
                self.presence_manager.set_rotation_interval(interval)
            
            embed = discord.Embed(
                title="✅ 自動ローテーション有効化",
                description="プレゼンスの自動ローテーションが有効になりました。",
                color=0x00FF00
            )
            
        elif action.lower() == "disable":
            self.presence_manager.disable_auto_rotation()
            
            embed = discord.Embed(
                title="⏸️ 自動ローテーション無効化",
                description="プレゼンスの自動ローテーションが無効になりました。",
                color=0xFF9900
            )
            
        else:
            await interaction.response.send_message("無効なアクションです。'enable' または 'disable' を指定してください。", ephemeral=True)
            return
        
        if interval:
            embed.add_field(name="ローテーション間隔", value=f"{interval}秒", inline=True)
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="presence_stats", description="プレゼンス統計を表示")
    async def show_presence_statistics(self, interaction: discord.Interaction):
        """プレゼンス統計の表示"""
        
        stats = self.statistics.get_statistics_summary()
        
        embed = discord.Embed(
            title="📈 プレゼンス統計",
            description=f"期間: {stats['period_start'].strftime('%Y-%m-%d')} - {stats['period_end'].strftime('%Y-%m-%d')}",
            color=0x0099FF
        )
        
        embed.add_field(name="総変更回数", value=stats["total_changes"], inline=True)
        embed.add_field(name="平均変更間隔", value=f"{stats['average_change_interval']:.1f}秒", inline=True)
        
        # 最も使用されたアクティビティ
        most_used = stats["most_used_activity"]
        embed.add_field(name="最多使用アクティビティ", value=f"{most_used[0]} ({most_used[1]}回)", inline=False)
        
        # トップ5アクティビティ
        top_activities = list(stats["activity_counts"].items())[:5]
        if top_activities:
            activities_text = "\n".join([f"{i+1}. {name}: {count}回" for i, (name, count) in enumerate(top_activities)])
            embed.add_field(name="使用頻度トップ5", value=activities_text, inline=False)
        
        await interaction.response.send_message(embed=embed)
```

---

## 関連ドキュメント

- [メインボットクラス](../02-core/01-main-bot-class.md)
- [ログシステム](../02-core/03-logging-system.md)
- [エラーハンドリング](../02-core/04-error-handling.md)
- [監視Cogs](../03-cogs/08-monitoring-cogs.md)
