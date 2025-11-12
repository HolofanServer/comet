# 監視Cogs

## C.O.M.E.T.について

**C.O.M.E.T.**の名前は以下の頭文字から構成されています：

- **C**ommunity of
- **O**shilove
- **M**oderation &
- **E**njoyment
- **T**ogether

HFS - ホロライブ非公式ファンサーバーのコミュニティを支える、推し愛とモデレーション、そして楽しさを一緒に提供するボットです。

## 概要

監視Cogsは、システムの健全性監視、外部サービス監視、パフォーマンス追跡機能を提供します。UptimeKuma統合、リアルタイム監視、アラート機能を含み、システムの安定性と可用性を確保します。

## Cogs構成

### 1. ステータス監視 (`status.py`)

**目的**: UptimeKumaとの統合によるシステム監視

**主要機能**:
- UptimeKuma API統合
- サービス状態の監視
- ダウンタイム通知
- パフォーマンスメトリクス収集
- 監視ダッシュボード

**場所**: [`cogs/uptimekuma/status.py`](../cogs/uptimekuma/status.py)

#### 実装詳細

```python
import aiohttp
import asyncio
from datetime import datetime, timedelta
import pytz
from typing import Dict, List, Optional, Any
import json

class UptimeKumaStatusCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.uptime_kuma_url = os.getenv("UPTIME_KUMA_URL")
        self.api_key = os.getenv("UPTIME_KUMA_API_KEY")
        self.monitoring_enabled = bool(self.uptime_kuma_url and self.api_key)
        
        # 監視設定
        self.check_interval = 60  # 1分間隔
        self.alert_channels = {}  # guild_id -> channel_id
        self.service_status_cache = {}
        self.last_status_check = None
        
        # バックグラウンドタスク
        if self.monitoring_enabled:
            self.monitoring_task = self.bot.loop.create_task(self.monitoring_loop())
        else:
            logger.warning("UptimeKuma monitoring disabled: missing configuration")

    def cog_unload(self):
        """Cogアンロード時のクリーンアップ"""
        if hasattr(self, 'monitoring_task'):
            self.monitoring_task.cancel()

    async def monitoring_loop(self):
        """監視ループ"""
        await self.bot.wait_until_ready()
        
        while not self.bot.is_closed():
            try:
                await self.check_all_services()
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Monitoring loop error: {e}")
                await asyncio.sleep(60)  # エラー時は1分待機

    async def check_all_services(self):
        """全サービスの状態チェック"""
        try:
            services = await self.get_monitored_services()
            
            for service in services:
                await self.check_service_status(service)
                
            self.last_status_check = datetime.now(pytz.UTC)
            
        except Exception as e:
            logger.error(f"Failed to check services: {e}")

    async def get_monitored_services(self) -> List[Dict[str, Any]]:
        """監視対象サービスの取得"""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"Authorization": f"Bearer {self.api_key}"}
                
                async with session.get(
                    f"{self.uptime_kuma_url}/api/monitors",
                    headers=headers,
                    timeout=30
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("monitors", [])
                    else:
                        logger.error(f"Failed to fetch monitors: HTTP {response.status}")
                        return []
                        
        except Exception as e:
            logger.error(f"Error fetching monitored services: {e}")
            return []

    async def check_service_status(self, service: Dict[str, Any]):
        """個別サービスの状態チェック"""
        service_id = service.get("id")
        service_name = service.get("name", "Unknown")
        
        try:
            # サービスの詳細状態を取得
            status_data = await self.get_service_details(service_id)
            
            if not status_data:
                return
            
            current_status = status_data.get("status")
            previous_status = self.service_status_cache.get(service_id, {}).get("status")
            
            # 状態変化の検出
            if previous_status and current_status != previous_status:
                await self.handle_status_change(service, previous_status, current_status, status_data)
            
            # キャッシュの更新
            self.service_status_cache[service_id] = {
                "status": current_status,
                "last_check": datetime.now(pytz.UTC),
                "response_time": status_data.get("response_time"),
                "uptime": status_data.get("uptime")
            }
            
        except Exception as e:
            logger.error(f"Error checking service {service_name}: {e}")

    async def get_service_details(self, service_id: int) -> Optional[Dict[str, Any]]:
        """サービス詳細情報の取得"""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"Authorization": f"Bearer {self.api_key}"}
                
                async with session.get(
                    f"{self.uptime_kuma_url}/api/monitors/{service_id}",
                    headers=headers,
                    timeout=30
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        logger.error(f"Failed to fetch service details: HTTP {response.status}")
                        return None
                        
        except Exception as e:
            logger.error(f"Error fetching service details: {e}")
            return None

    async def handle_status_change(
        self, 
        service: Dict[str, Any], 
        previous_status: str, 
        current_status: str,
        status_data: Dict[str, Any]
    ):
        """サービス状態変化の処理"""
        service_name = service.get("name", "Unknown")
        service_url = service.get("url", "")
        
        # 状態変化の種類を判定
        if current_status == "up" and previous_status == "down":
            # 復旧
            await self.send_recovery_alert(service_name, service_url, status_data)
        elif current_status == "down" and previous_status == "up":
            # ダウン
            await self.send_downtime_alert(service_name, service_url, status_data)
        elif current_status == "warning":
            # 警告状態
            await self.send_warning_alert(service_name, service_url, status_data)

    async def send_downtime_alert(self, service_name: str, service_url: str, status_data: Dict[str, Any]):
        """ダウンタイムアラートの送信"""
        embed = discord.Embed(
            title="🔴 サービスダウン検出",
            description=f"**{service_name}** がダウンしています。",
            color=0xFF0000,
            timestamp=datetime.now(pytz.UTC)
        )
        
        if service_url:
            embed.add_field(name="URL", value=service_url, inline=False)
        
        error_message = status_data.get("error_message", "不明なエラー")
        embed.add_field(name="エラー", value=error_message, inline=False)
        
        last_check = status_data.get("last_check")
        if last_check:
            embed.add_field(name="最終チェック", value=last_check, inline=True)
        
        embed.set_footer(text="UptimeKuma監視システム")
        
        await self.send_alert_to_channels(embed)

    async def send_recovery_alert(self, service_name: str, service_url: str, status_data: Dict[str, Any]):
        """復旧アラートの送信"""
        embed = discord.Embed(
            title="✅ サービス復旧",
            description=f"**{service_name}** が復旧しました。",
            color=0x00FF00,
            timestamp=datetime.now(pytz.UTC)
        )
        
        if service_url:
            embed.add_field(name="URL", value=service_url, inline=False)
        
        response_time = status_data.get("response_time")
        if response_time:
            embed.add_field(name="応答時間", value=f"{response_time}ms", inline=True)
        
        uptime = status_data.get("uptime")
        if uptime:
            embed.add_field(name="稼働率", value=f"{uptime:.2f}%", inline=True)
        
        embed.set_footer(text="UptimeKuma監視システム")
        
        await self.send_alert_to_channels(embed)

    async def send_warning_alert(self, service_name: str, service_url: str, status_data: Dict[str, Any]):
        """警告アラートの送信"""
        embed = discord.Embed(
            title="⚠️ サービス警告",
            description=f"**{service_name}** で問題が検出されました。",
            color=0xFF9900,
            timestamp=datetime.now(pytz.UTC)
        )
        
        if service_url:
            embed.add_field(name="URL", value=service_url, inline=False)
        
        response_time = status_data.get("response_time")
        if response_time:
            embed.add_field(name="応答時間", value=f"{response_time}ms", inline=True)
        
        warning_message = status_data.get("warning_message", "応答時間が遅延しています")
        embed.add_field(name="警告内容", value=warning_message, inline=False)
        
        embed.set_footer(text="UptimeKuma監視システム")
        
        await self.send_alert_to_channels(embed)

    async def send_alert_to_channels(self, embed: discord.Embed):
        """全アラートチャンネルにアラートを送信"""
        for guild_id, channel_id in self.alert_channels.items():
            try:
                channel = self.bot.get_channel(channel_id)
                if channel:
                    await channel.send(embed=embed)
            except Exception as e:
                logger.error(f"Failed to send alert to channel {channel_id}: {e}")

    @app_commands.command(name="monitoring_setup", description="監視システムの設定")
    @app_commands.describe(channel="アラートを送信するチャンネル")
    async def setup_monitoring(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """監視システムの設定"""
        
        # 権限チェック
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("この機能を使用する権限がありません。", ephemeral=True)
            return
        
        if not self.monitoring_enabled:
            await interaction.response.send_message(
                "監視システムが無効です。UptimeKuma設定を確認してください。", 
                ephemeral=True
            )
            return
        
        # アラートチャンネルの設定
        self.alert_channels[interaction.guild.id] = channel.id
        await self.save_monitoring_config(interaction.guild.id, channel.id)
        
        embed = discord.Embed(
            title="✅ 監視システム設定完了",
            description="監視システムが正常に設定されました。",
            color=0x00FF00
        )
        embed.add_field(name="アラートチャンネル", value=channel.mention, inline=True)
        embed.add_field(name="チェック間隔", value=f"{self.check_interval}秒", inline=True)
        embed.add_field(name="UptimeKuma URL", value=self.uptime_kuma_url, inline=False)
        
        await interaction.response.send_message(embed=embed)

    async def save_monitoring_config(self, guild_id: int, channel_id: int):
        """監視設定の保存"""
        try:
            query = """
            INSERT OR REPLACE INTO monitoring_config (
                guild_id, alert_channel_id, check_interval, 
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?)
            """
            
            now = datetime.now().isoformat()
            await self.bot.db_service.execute_query(
                query,
                (guild_id, channel_id, self.check_interval, now, now)
            )
        except Exception as e:
            logger.error(f"Failed to save monitoring config: {e}")

    @app_commands.command(name="status_dashboard", description="サービス状態ダッシュボード")
    async def show_status_dashboard(self, interaction: discord.Interaction):
        """サービス状態ダッシュボードの表示"""
        
        if not self.monitoring_enabled:
            await interaction.response.send_message(
                "監視システムが無効です。", 
                ephemeral=True
            )
            return
        
        await interaction.response.defer()
        
        try:
            services = await self.get_monitored_services()
            
            if not services:
                await interaction.followup.send("監視対象サービスがありません。")
                return
            
            embed = discord.Embed(
                title="📊 サービス状態ダッシュボード",
                description="現在の全サービス状態",
                color=0x0099FF,
                timestamp=datetime.now(pytz.UTC)
            )
            
            # サービス状態の集計
            status_counts = {"up": 0, "down": 0, "warning": 0, "unknown": 0}
            
            for service in services[:10]:  # 最大10サービス表示
                service_id = service.get("id")
                service_name = service.get("name", "Unknown")
                
                cached_status = self.service_status_cache.get(service_id, {})
                status = cached_status.get("status", "unknown")
                response_time = cached_status.get("response_time")
                
                status_counts[status] = status_counts.get(status, 0) + 1
                
                # ステータス絵文字
                status_emoji = {
                    "up": "🟢",
                    "down": "🔴", 
                    "warning": "🟡",
                    "unknown": "⚪"
                }.get(status, "⚪")
                
                field_value = f"{status_emoji} {status.upper()}"
                if response_time:
                    field_value += f" ({response_time}ms)"
                
                embed.add_field(name=service_name, value=field_value, inline=True)
            
            # サマリー情報
            total_services = len(services)
            uptime_percentage = (status_counts["up"] / total_services * 100) if total_services > 0 else 0
            
            summary = f"稼働中: {status_counts['up']}/{total_services} ({uptime_percentage:.1f}%)"
            if status_counts["down"] > 0:
                summary += f"\n🔴 ダウン: {status_counts['down']}"
            if status_counts["warning"] > 0:
                summary += f"\n🟡 警告: {status_counts['warning']}"
            
            embed.add_field(name="📈 サマリー", value=summary, inline=False)
            
            # 最終チェック時刻
            if self.last_status_check:
                jst_time = self.last_status_check.astimezone(pytz.timezone('Asia/Tokyo'))
                embed.set_footer(text=f"最終チェック: {jst_time.strftime('%Y-%m-%d %H:%M:%S JST')}")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Failed to show status dashboard: {e}")
            await interaction.followup.send("ダッシュボードの表示に失敗しました。")

    @app_commands.command(name="service_details", description="特定サービスの詳細情報")
    @app_commands.describe(service_name="詳細を表示するサービス名")
    async def show_service_details(self, interaction: discord.Interaction, service_name: str):
        """特定サービスの詳細情報表示"""
        
        if not self.monitoring_enabled:
            await interaction.response.send_message("監視システムが無効です。", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        try:
            services = await self.get_monitored_services()
            
            # サービス検索
            target_service = None
            for service in services:
                if service.get("name", "").lower() == service_name.lower():
                    target_service = service
                    break
            
            if not target_service:
                await interaction.followup.send(f"サービス「{service_name}」が見つかりません。")
                return
            
            # 詳細情報の取得
            service_id = target_service.get("id")
            details = await self.get_service_details(service_id)
            
            if not details:
                await interaction.followup.send("サービス詳細の取得に失敗しました。")
                return
            
            embed = discord.Embed(
                title=f"🔍 {target_service.get('name', 'Unknown')} - 詳細情報",
                color=0x0099FF,
                timestamp=datetime.now(pytz.UTC)
            )
            
            # 基本情報
            embed.add_field(name="URL", value=target_service.get("url", "N/A"), inline=False)
            embed.add_field(name="タイプ", value=target_service.get("type", "N/A"), inline=True)
            embed.add_field(name="間隔", value=f"{target_service.get('interval', 'N/A')}秒", inline=True)
            
            # 現在の状態
            cached_status = self.service_status_cache.get(service_id, {})
            status = cached_status.get("status", "unknown")
            status_emoji = {
                "up": "🟢",
                "down": "🔴",
                "warning": "🟡", 
                "unknown": "⚪"
            }.get(status, "⚪")
            
            embed.add_field(name="現在の状態", value=f"{status_emoji} {status.upper()}", inline=True)
            
            # パフォーマンス情報
            response_time = cached_status.get("response_time")
            if response_time:
                embed.add_field(name="応答時間", value=f"{response_time}ms", inline=True)
            
            uptime = cached_status.get("uptime")
            if uptime:
                embed.add_field(name="稼働率", value=f"{uptime:.2f}%", inline=True)
            
            # 最終チェック
            last_check = cached_status.get("last_check")
            if last_check:
                jst_time = last_check.astimezone(pytz.timezone('Asia/Tokyo'))
                embed.add_field(name="最終チェック", value=jst_time.strftime('%Y-%m-%d %H:%M:%S JST'), inline=True)
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Failed to show service details: {e}")
            await interaction.followup.send("サービス詳細の表示に失敗しました。")

    @app_commands.command(name="monitoring_stats", description="監視統計情報")
    async def show_monitoring_stats(self, interaction: discord.Interaction):
        """監視統計情報の表示"""
        
        if not self.monitoring_enabled:
            await interaction.response.send_message("監視システムが無効です。", ephemeral=True)
            return
        
        try:
            # 統計データの取得
            stats = await self.get_monitoring_statistics()
            
            embed = discord.Embed(
                title="📈 監視統計情報",
                description="過去24時間の監視統計",
                color=0x0099FF,
                timestamp=datetime.now(pytz.UTC)
            )
            
            embed.add_field(name="総監視サービス数", value=stats.get("total_services", 0), inline=True)
            embed.add_field(name="稼働中サービス", value=stats.get("services_up", 0), inline=True)
            embed.add_field(name="ダウンサービス", value=stats.get("services_down", 0), inline=True)
            
            embed.add_field(name="総チェック回数", value=stats.get("total_checks", 0), inline=True)
            embed.add_field(name="平均応答時間", value=f"{stats.get('avg_response_time', 0):.1f}ms", inline=True)
            embed.add_field(name="全体稼働率", value=f"{stats.get('overall_uptime', 0):.2f}%", inline=True)
            
            # インシデント情報
            incidents = stats.get("recent_incidents", [])
            if incidents:
                incident_text = "\n".join([
                    f"• {incident['service']} - {incident['type']} ({incident['time']})"
                    for incident in incidents[:5]
                ])
                embed.add_field(name="最近のインシデント", value=incident_text, inline=False)
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            logger.error(f"Failed to show monitoring stats: {e}")
            await interaction.response.send_message("統計情報の表示に失敗しました。", ephemeral=True)

    async def get_monitoring_statistics(self) -> Dict[str, Any]:
        """監視統計の取得"""
        try:
            # UptimeKuma APIから統計データを取得
            # 実装は具体的なAPI仕様に依存
            return {
                "total_services": len(self.service_status_cache),
                "services_up": sum(1 for status in self.service_status_cache.values() if status.get("status") == "up"),
                "services_down": sum(1 for status in self.service_status_cache.values() if status.get("status") == "down"),
                "total_checks": 0,
                "avg_response_time": 0,
                "overall_uptime": 0,
                "recent_incidents": []
            }
        except Exception as e:
            logger.error(f"Failed to get monitoring statistics: {e}")
            return {}

    async def load_monitoring_configs(self):
        """監視設定の読み込み"""
        try:
            query = "SELECT guild_id, alert_channel_id FROM monitoring_config"
            results = await self.bot.db_service.fetch_all(query, ())
            
            for row in results:
                self.alert_channels[row['guild_id']] = row['alert_channel_id']
                
        except Exception as e:
            logger.error(f"Failed to load monitoring configs: {e}")
```

## システム監視機能

### 1. ボットパフォーマンス監視

```python
class BotPerformanceMonitor:
    def __init__(self, bot):
        self.bot = bot
        self.metrics = {
            "command_count": 0,
            "error_count": 0,
            "response_times": [],
            "memory_usage": [],
            "cpu_usage": []
        }
        
        # パフォーマンス監視タスク
        self.performance_task = bot.loop.create_task(self.performance_monitoring_loop())

    async def performance_monitoring_loop(self):
        """パフォーマンス監視ループ"""
        while not self.bot.is_closed():
            try:
                await self.collect_performance_metrics()
                await asyncio.sleep(300)  # 5分間隔
            except Exception as e:
                logger.error(f"Performance monitoring error: {e}")
                await asyncio.sleep(60)

    async def collect_performance_metrics(self):
        """パフォーマンスメトリクスの収集"""
        import psutil
        
        # メモリ使用量
        process = psutil.Process()
        memory_mb = process.memory_info().rss / 1024 / 1024
        self.metrics["memory_usage"].append(memory_mb)
        
        # CPU使用率
        cpu_percent = process.cpu_percent()
        self.metrics["cpu_usage"].append(cpu_percent)
        
        # 古いデータの削除（過去1時間分のみ保持）
        max_entries = 12  # 5分間隔で1時間分
        for key in ["memory_usage", "cpu_usage", "response_times"]:
            if len(self.metrics[key]) > max_entries:
                self.metrics[key] = self.metrics[key][-max_entries:]

    def record_command_execution(self, response_time: float, success: bool):
        """コマンド実行の記録"""
        self.metrics["command_count"] += 1
        if not success:
            self.metrics["error_count"] += 1
        
        self.metrics["response_times"].append(response_time)

    def get_performance_summary(self) -> Dict[str, Any]:
        """パフォーマンスサマリーの取得"""
        return {
            "total_commands": self.metrics["command_count"],
            "total_errors": self.metrics["error_count"],
            "error_rate": self.metrics["error_count"] / max(self.metrics["command_count"], 1),
            "avg_response_time": sum(self.metrics["response_times"]) / max(len(self.metrics["response_times"]), 1),
            "current_memory_mb": self.metrics["memory_usage"][-1] if self.metrics["memory_usage"] else 0,
            "current_cpu_percent": self.metrics["cpu_usage"][-1] if self.metrics["cpu_usage"] else 0,
            "guild_count": len(self.bot.guilds),
            "user_count": sum(guild.member_count for guild in self.bot.guilds)
        }
```

### 2. アラート管理システム

```python
class AlertManager:
    def __init__(self, bot):
        self.bot = bot
        self.alert_rules = {}
        self.alert_history = []
        self.cooldown_periods = {}  # アラートのクールダウン管理

    def add_alert_rule(self, rule_name: str, condition: callable, cooldown: int = 300):
        """アラートルールの追加"""
        self.alert_rules[rule_name] = {
            "condition": condition,
            "cooldown": cooldown,
            "last_triggered": None
        }

    async def check_alert_conditions(self, metrics: Dict[str, Any]):
        """アラート条件のチェック"""
        current_time = datetime.now()
        
        for rule_name, rule in self.alert_rules.items():
            try:
                # 条件チェック
                if rule["condition"](metrics):
                    # クールダウンチェック
                    last_triggered = rule.get("last_triggered")
                    if last_triggered:
                        time_diff = (current_time - last_triggered).total_seconds()
                        if time_diff < rule["cooldown"]:
                            continue  # クールダウン中
                    
                    # アラート送信
                    await self.send_alert(rule_name, metrics)
                    rule["last_triggered"] = current_time
                    
            except Exception as e:
                logger.error(f"Error checking alert rule {rule_name}: {e}")

    async def send_alert(self, rule_name: str, metrics: Dict[str, Any]):
        """アラートの送信"""
        alert_data = {
            "rule": rule_name,
            "timestamp": datetime.now(),
            "metrics": metrics,
            "severity": self.get_alert_severity(rule_name, metrics)
        }
        
        self.alert_history.append(alert_data)
        
        # アラート通知の送信
        embed = self.create_alert_embed(alert_data)
        await self.send_alert_to_channels(embed)

    def get_alert_severity(self, rule_name: str, metrics: Dict[str, Any]) -> str:
        """アラートの重要度判定"""
        severity_rules = {
            "high_memory_usage": "HIGH",
            "high_cpu_usage": "MEDIUM",
            "high_error_rate": "HIGH",
            "service_down": "CRITICAL",
            "slow_response": "MEDIUM"
        }
        return severity_rules.get(rule_name, "LOW")

    def create_alert_embed(self, alert_data: Dict[str, Any]) -> discord.Embed:
        """アラート埋め込みの作成"""
        severity = alert_data["severity"]
        color_map = {
            "LOW": 0x808080,
            "MEDIUM": 0xFF9900,
            "HIGH": 0xFF0000,
            "CRITICAL": 0x990000
        }
        
        embed = discord.Embed(
            title=f"🚨 {severity} アラート",
            description=f"ルール: {alert_data['rule']}",
            color=color_map.get(severity, 0x808080),
            timestamp=alert_data["timestamp"]
        )
        
        # メトリクス情報の追加
        metrics = alert_data["metrics"]
        for key, value in metrics.items():
            if isinstance(value, (int, float)):
                embed.add_field(name=key, value=f"{value:.2f}", inline=True)
        
        return embed
```

## データベース設計

### 監視関連テーブル

```sql
-- 監視設定テーブル
CREATE TABLE monitoring_config (
    guild_id INTEGER PRIMARY KEY,
    alert_channel_id INTEGER NOT NULL,
    check_interval INTEGER DEFAULT 60,
    uptime_kuma_url TEXT,
    api_key_hash TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- サービス状態履歴テーブル
CREATE TABLE service_status_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service_id INTEGER NOT NULL,
    service_name TEXT NOT NULL,
    status TEXT NOT NULL,
    response_time INTEGER,
    error_message TEXT,
    checked_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- アラート履歴テーブル
CREATE TABLE alert_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_name TEXT NOT NULL,
    severity TEXT NOT NULL,
    message TEXT,
    metrics_data TEXT,
    triggered_at TIMESTAMP NOT NULL,
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- パフォーマンスメトリクステーブル
CREATE TABLE performance_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    metric_type TEXT NOT NULL,
    metric_value REAL NOT NULL,
    recorded_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 関連ドキュメント

- [Cogsアーキテクチャ](01-cogs-architecture.md)
- [ログシステム](../02-core/03-logging-system.md)
- [エラーハンドリング](../02-core/04-error-handling.md)
- [外部API統合](../04-utilities/02-api-integration.md)
