# エラーハンドリング

## C.O.M.E.T.について

**C.O.M.E.T.**の名前は以下の頭文字から構成されています：

- **C**ommunity of
- **O**shilove
- **M**oderation &
- **E**njoyment
- **T**ogether

HFS - ホロライブ非公式ファンサーバーのコミュニティを支える、推し愛とモデレーション、そして楽しさを一緒に提供するボットです。

## 概要

COMETボットのエラーハンドリングシステムは、包括的なエラー捕捉、分類、報告、復旧機能を提供します。ユーザーエクスペリエンスを損なうことなく、システムの安定性と信頼性を確保します。

## エラーハンドリングアーキテクチャ

```
┌─────────────────────────────────────────────────────────────┐
│                エラーハンドリングアーキテクチャ               │
├─────────────────────────────────────────────────────────────┤
│  エラー検出層 (Error Detection)                              │
│  ├── グローバルエラーハンドラー                              │
│  ├── Cogレベルエラーハンドラー                               │
│  ├── コマンドレベルエラーハンドラー                          │
│  └── 例外監視システム                                        │
├─────────────────────────────────────────────────────────────┤
│  エラー分類層 (Error Classification)                        │
│  ├── システムエラー                                          │
│  ├── ユーザーエラー                                          │
│  ├── 外部サービスエラー                                      │
│  └── 設定エラー                                              │
├─────────────────────────────────────────────────────────────┤
│  エラー処理層 (Error Processing)                            │
│  ├── エラー分析                                              │
│  ├── コンテキスト収集                                        │
│  ├── 重要度判定                                              │
│  └── 復旧戦略決定                                            │
├─────────────────────────────────────────────────────────────┤
│  エラー報告層 (Error Reporting)                             │
│  ├── ユーザー通知                                            │
│  ├── 管理者アラート                                          │
│  ├── ログ記録                                                │
│  └── 外部監視システム連携                                    │
├─────────────────────────────────────────────────────────────┤
│  エラー復旧層 (Error Recovery)                              │
│  ├── 自動復旧                                                │
│  ├── フォールバック処理                                      │
│  ├── 部分機能停止                                            │
│  └── 手動介入要求                                            │
└─────────────────────────────────────────────────────────────┘
```

## グローバルエラーハンドラー

### 1. メインボットエラーハンドラー

**場所**: [`main.py:143-176`](../main.py)

```python
class MyBot(commands.AutoShardedBot):
    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        """コマンドエラーのグローバルハンドリング"""
        if hasattr(ctx, 'handled') and ctx.handled:
            return
        
        # エラーコンテキストの収集
        error_context = {
            "command": {
                "name": ctx.command.name if ctx.command else "unknown",
                "content": ctx.message.content,
                "cog": ctx.cog.__class__.__name__ if ctx.cog else None
            },
            "user": {
                "id": ctx.author.id,
                "name": str(ctx.author),
                "bot": ctx.author.bot
            },
            "channel": {
                "id": ctx.channel.id,
                "name": getattr(ctx.channel, 'name', 'DM'),
                "type": str(ctx.channel.type)
            }
        }
        
        if ctx.guild:
            error_context["guild"] = {
                "id": ctx.guild.id,
                "name": ctx.guild.name,
                "member_count": ctx.guild.member_count
            }
        
        # エラーハンドリング
        handled = await handle_command_error(ctx, error, self.ERROR_LOG_CHANNEL_ID, error_context)
        if handled:
            ctx.handled = True
    
    @commands.Cog.listener()
    async def on_application_command_error(self, interaction: discord.Interaction, error: commands.CommandError) -> None:
        """アプリケーションコマンドエラーのハンドリング"""
        error_context = {
            "command": {
                "name": interaction.command.name if interaction.command else "unknown",
                "type": "application_command"
            },
            "user": {
                "id": interaction.user.id,
                "name": str(interaction.user)
            },
            "guild": {
                "id": interaction.guild.id,
                "name": interaction.guild.name
            } if interaction.guild else None
        }
        
        await handle_application_command_error(interaction, error, error_context)
```

### 2. エラーハンドリング関数

**場所**: [`utils/error.py`](../utils/error.py)

```python
import discord
from discord.ext import commands
import traceback
import logging
from datetime import datetime
from typing import Dict, Any, Optional, Union
import pytz

logger = logging.getLogger(__name__)

async def handle_command_error(
    ctx: commands.Context, 
    error: commands.CommandError, 
    error_channel_id: int,
    context: Dict[str, Any] = None
) -> bool:
    """コマンドエラーの統合ハンドリング"""
    
    error_info = ErrorAnalyzer.analyze_error(error, context)
    
    # ユーザーへの応答
    user_message = await _generate_user_message(error_info)
    if user_message:
        try:
            await ctx.send(user_message, ephemeral=True)
        except discord.HTTPException:
            pass  # メッセージ送信に失敗しても続行
    
    # ログ記録
    await _log_error(error_info, ctx)
    
    # 管理者通知（重要なエラーのみ）
    if error_info.severity in ['HIGH', 'CRITICAL']:
        await _notify_administrators(error_info, error_channel_id, ctx)
    
    # 自動復旧の試行
    if error_info.recoverable:
        recovery_success = await _attempt_recovery(error_info, ctx)
        if recovery_success:
            logger.info(f"Error recovery successful for {error_info.error_type}")
    
    return True

async def handle_application_command_error(
    interaction: discord.Interaction,
    error: commands.CommandError,
    context: Dict[str, Any] = None
) -> bool:
    """アプリケーションコマンドエラーのハンドリング"""
    
    error_info = ErrorAnalyzer.analyze_error(error, context)
    
    # ユーザーへの応答
    user_message = await _generate_user_message(error_info)
    if user_message:
        try:
            if interaction.response.is_done():
                await interaction.followup.send(user_message, ephemeral=True)
            else:
                await interaction.response.send_message(user_message, ephemeral=True)
        except discord.HTTPException:
            pass
    
    # ログ記録
    await _log_interaction_error(error_info, interaction)
    
    return True
```

## エラー分析システム

### 1. エラー分析器

```python
from enum import Enum
from dataclasses import dataclass
from typing import List, Optional

class ErrorSeverity(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class ErrorCategory(Enum):
    USER_ERROR = "USER_ERROR"
    SYSTEM_ERROR = "SYSTEM_ERROR"
    EXTERNAL_ERROR = "EXTERNAL_ERROR"
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"
    PERMISSION_ERROR = "PERMISSION_ERROR"

@dataclass
class ErrorInfo:
    error_type: str
    error_message: str
    category: ErrorCategory
    severity: ErrorSeverity
    recoverable: bool
    user_friendly_message: str
    technical_details: Dict[str, Any]
    suggested_actions: List[str]
    context: Dict[str, Any]

class ErrorAnalyzer:
    @staticmethod
    def analyze_error(error: Exception, context: Dict[str, Any] = None) -> ErrorInfo:
        """エラーの詳細分析"""
        error_type = type(error).__name__
        error_message = str(error)
        
        # エラータイプ別の分析
        if isinstance(error, commands.CommandNotFound):
            return ErrorInfo(
                error_type=error_type,
                error_message=error_message,
                category=ErrorCategory.USER_ERROR,
                severity=ErrorSeverity.LOW,
                recoverable=True,
                user_friendly_message="そのコマンドは存在しません。`/help`で利用可能なコマンドを確認してください。",
                technical_details={"command": error_message},
                suggested_actions=["コマンド名を確認", "ヘルプコマンドを使用"],
                context=context or {}
            )
        
        elif isinstance(error, commands.MissingRequiredArgument):
            return ErrorInfo(
                error_type=error_type,
                error_message=error_message,
                category=ErrorCategory.USER_ERROR,
                severity=ErrorSeverity.LOW,
                recoverable=True,
                user_friendly_message=f"必須パラメータ `{error.param.name}` が不足しています。",
                technical_details={"missing_param": error.param.name},
                suggested_actions=["コマンドの使用方法を確認", "必要なパラメータを追加"],
                context=context or {}
            )
        
        elif isinstance(error, commands.MissingPermissions):
            return ErrorInfo(
                error_type=error_type,
                error_message=error_message,
                category=ErrorCategory.PERMISSION_ERROR,
                severity=ErrorSeverity.MEDIUM,
                recoverable=False,
                user_friendly_message="このコマンドを実行する権限がありません。",
                technical_details={"missing_permissions": error.missing_permissions},
                suggested_actions=["管理者に権限を確認", "適切なロールを取得"],
                context=context or {}
            )
        
        elif isinstance(error, commands.BotMissingPermissions):
            return ErrorInfo(
                error_type=error_type,
                error_message=error_message,
                category=ErrorCategory.CONFIGURATION_ERROR,
                severity=ErrorSeverity.HIGH,
                recoverable=True,
                user_friendly_message="ボットに必要な権限がありません。管理者にお問い合わせください。",
                technical_details={"missing_permissions": error.missing_permissions},
                suggested_actions=["ボット権限を確認", "管理者に連絡"],
                context=context or {}
            )
        
        elif isinstance(error, commands.CommandOnCooldown):
            return ErrorInfo(
                error_type=error_type,
                error_message=error_message,
                category=ErrorCategory.USER_ERROR,
                severity=ErrorSeverity.LOW,
                recoverable=True,
                user_friendly_message=f"コマンドはクールダウン中です。{error.retry_after:.1f}秒後に再試行してください。",
                technical_details={"retry_after": error.retry_after, "cooldown_type": str(error.cooldown.type)},
                suggested_actions=["しばらく待ってから再試行"],
                context=context or {}
            )
        
        elif isinstance(error, discord.HTTPException):
            return ErrorInfo(
                error_type=error_type,
                error_message=error_message,
                category=ErrorCategory.EXTERNAL_ERROR,
                severity=ErrorSeverity.HIGH,
                recoverable=True,
                user_friendly_message="Discord APIでエラーが発生しました。しばらく待ってから再試行してください。",
                technical_details={"status": error.status, "code": error.code},
                suggested_actions=["しばらく待ってから再試行", "管理者に報告"],
                context=context or {}
            )
        
        elif isinstance(error, discord.Forbidden):
            return ErrorInfo(
                error_type=error_type,
                error_message=error_message,
                category=ErrorCategory.PERMISSION_ERROR,
                severity=ErrorSeverity.HIGH,
                recoverable=False,
                user_friendly_message="ボットにこの操作を実行する権限がありません。",
                technical_details={"discord_error": str(error)},
                suggested_actions=["ボット権限を確認", "管理者に連絡"],
                context=context or {}
            )
        
        else:
            # 未知のエラー
            return ErrorInfo(
                error_type=error_type,
                error_message=error_message,
                category=ErrorCategory.SYSTEM_ERROR,
                severity=ErrorSeverity.CRITICAL,
                recoverable=False,
                user_friendly_message="予期しないエラーが発生しました。管理者に報告してください。",
                technical_details={
                    "traceback": traceback.format_exc(),
                    "error_args": getattr(error, 'args', [])
                },
                suggested_actions=["管理者に報告", "しばらく待ってから再試行"],
                context=context or {}
            )
```

### 2. エラー復旧システム

```python
class ErrorRecoveryManager:
    def __init__(self, bot):
        self.bot = bot
        self.recovery_strategies = {
            'commands.BotMissingPermissions': self._recover_missing_permissions,
            'discord.HTTPException': self._recover_http_exception,
            'commands.CommandOnCooldown': self._recover_cooldown,
            'ConnectionError': self._recover_connection_error
        }
    
    async def attempt_recovery(self, error_info: ErrorInfo, ctx: commands.Context) -> bool:
        """エラー復旧の試行"""
        recovery_strategy = self.recovery_strategies.get(error_info.error_type)
        
        if recovery_strategy:
            try:
                return await recovery_strategy(error_info, ctx)
            except Exception as e:
                logger.error(f"Recovery attempt failed: {e}")
                return False
        
        return False
    
    async def _recover_missing_permissions(self, error_info: ErrorInfo, ctx: commands.Context) -> bool:
        """権限不足エラーの復旧"""
        missing_perms = error_info.technical_details.get('missing_permissions', [])
        
        # 管理者に権限付与を要求
        admin_channel = self.bot.get_channel(self.bot.ERROR_LOG_CHANNEL_ID)
        if admin_channel:
            embed = discord.Embed(
                title="🔧 権限不足エラー - 自動復旧要求",
                description=f"ボットに以下の権限が必要です：\n{', '.join(missing_perms)}",
                color=0xFF9900
            )
            embed.add_field(name="サーバー", value=ctx.guild.name, inline=True)
            embed.add_field(name="チャンネル", value=ctx.channel.mention, inline=True)
            embed.add_field(name="コマンド", value=ctx.command.name, inline=True)
            
            await admin_channel.send(embed=embed)
        
        return False  # 手動介入が必要
    
    async def _recover_http_exception(self, error_info: ErrorInfo, ctx: commands.Context) -> bool:
        """HTTP例外の復旧"""
        status = error_info.technical_details.get('status')
        
        if status == 429:  # Rate Limited
            # レート制限の場合は待機
            await asyncio.sleep(5)
            return True
        elif status in [500, 502, 503, 504]:  # Server errors
            # サーバーエラーの場合は短時間待機後に再試行
            await asyncio.sleep(2)
            return True
        
        return False
    
    async def _recover_cooldown(self, error_info: ErrorInfo, ctx: commands.Context) -> bool:
        """クールダウンエラーの復旧"""
        # クールダウンは自然回復を待つ
        return False
    
    async def _recover_connection_error(self, error_info: ErrorInfo, ctx: commands.Context) -> bool:
        """接続エラーの復旧"""
        # 接続の再確立を試行
        try:
            if self.bot.is_closed():
                await self.bot.connect(reconnect=True)
                return True
        except Exception:
            pass
        
        return False
```

## エラー通知システム

### 1. 管理者通知

```python
async def _notify_administrators(error_info: ErrorInfo, error_channel_id: int, ctx: commands.Context) -> None:
    """管理者への通知"""
    try:
        channel = ctx.bot.get_channel(error_channel_id)
        if not channel:
            return
        
        embed = discord.Embed(
            title=f"🚨 {error_info.severity} エラー発生",
            description=error_info.error_message,
            color=_get_color_for_severity(error_info.severity),
            timestamp=datetime.now(pytz.timezone('Asia/Tokyo'))
        )
        
        embed.add_field(
            name="エラータイプ",
            value=error_info.error_type,
            inline=True
        )
        
        embed.add_field(
            name="カテゴリ",
            value=error_info.category.value,
            inline=True
        )
        
        embed.add_field(
            name="復旧可能",
            value="✅ はい" if error_info.recoverable else "❌ いいえ",
            inline=True
        )
        
        if error_info.context:
            context_text = ""
            if "command" in error_info.context:
                context_text += f"コマンド: {error_info.context['command']['name']}\n"
            if "user" in error_info.context:
                context_text += f"ユーザー: {error_info.context['user']['name']} ({error_info.context['user']['id']})\n"
            if "guild" in error_info.context:
                context_text += f"サーバー: {error_info.context['guild']['name']} ({error_info.context['guild']['id']})\n"
            
            if context_text:
                embed.add_field(name="コンテキスト", value=context_text, inline=False)
        
        if error_info.suggested_actions:
            actions_text = "\n".join([f"• {action}" for action in error_info.suggested_actions])
            embed.add_field(name="推奨アクション", value=actions_text, inline=False)
        
        if error_info.technical_details:
            details_text = "```json\n" + json.dumps(error_info.technical_details, indent=2, ensure_ascii=False) + "\n```"
            if len(details_text) > 1024:
                details_text = details_text[:1020] + "...\n```"
            embed.add_field(name="技術的詳細", value=details_text, inline=False)
        
        await channel.send(embed=embed)
        
    except Exception as e:
        logger.error(f"Failed to notify administrators: {e}")

def _get_color_for_severity(severity: ErrorSeverity) -> int:
    """重要度に応じた色を取得"""
    colors = {
        ErrorSeverity.LOW: 0x808080,      # グレー
        ErrorSeverity.MEDIUM: 0xFF9900,   # オレンジ
        ErrorSeverity.HIGH: 0xFF0000,     # 赤
        ErrorSeverity.CRITICAL: 0x990000  # 暗赤
    }
    return colors.get(severity, 0x000000)
```

### 2. ユーザーメッセージ生成

```python
async def _generate_user_message(error_info: ErrorInfo) -> Optional[str]:
    """ユーザー向けメッセージの生成"""
    if error_info.category == ErrorCategory.USER_ERROR and error_info.severity == ErrorSeverity.LOW:
        return error_info.user_friendly_message
    elif error_info.category == ErrorCategory.PERMISSION_ERROR:
        return f"❌ {error_info.user_friendly_message}"
    elif error_info.severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
        return f"⚠️ {error_info.user_friendly_message}\n\nエラーID: {_generate_error_id()}"
    else:
        return error_info.user_friendly_message

def _generate_error_id() -> str:
    """エラーIDの生成"""
    import uuid
    return str(uuid.uuid4())[:8].upper()
```

## ログ記録

### 1. エラーログ記録

```python
async def _log_error(error_info: ErrorInfo, ctx: commands.Context) -> None:
    """エラーログの記録"""
    log_data = {
        "timestamp": datetime.now(pytz.timezone('Asia/Tokyo')).isoformat(),
        "error_type": error_info.error_type,
        "error_message": error_info.error_message,
        "category": error_info.category.value,
        "severity": error_info.severity.value,
        "recoverable": error_info.recoverable,
        "context": error_info.context,
        "technical_details": error_info.technical_details,
        "suggested_actions": error_info.suggested_actions,
        "command_info": {
            "name": ctx.command.name if ctx.command else None,
            "cog": ctx.cog.__class__.__name__ if ctx.cog else None,
            "content": ctx.message.content
        },
        "user_info": {
            "id": ctx.author.id,
            "name": str(ctx.author),
            "bot": ctx.author.bot
        },
        "guild_info": {
            "id": ctx.guild.id,
            "name": ctx.guild.name,
            "member_count": ctx.guild.member_count
        } if ctx.guild else None,
        "channel_info": {
            "id": ctx.channel.id,
            "name": getattr(ctx.channel, 'name', 'DM'),
            "type": str(ctx.channel.type)
        }
    }
    
    logger.error(f"Command error occurred: {error_info.error_type}", extra={"error_data": log_data})

async def _log_interaction_error(error_info: ErrorInfo, interaction: discord.Interaction) -> None:
    """インタラクションエラーログの記録"""
    log_data = {
        "timestamp": datetime.now(pytz.timezone('Asia/Tokyo')).isoformat(),
        "error_type": error_info.error_type,
        "error_message": error_info.error_message,
        "category": error_info.category.value,
        "severity": error_info.severity.value,
        "context": error_info.context,
        "interaction_info": {
            "command_name": interaction.command.name if interaction.command else None,
            "command_type": "application_command",
            "user_id": interaction.user.id,
            "user_name": str(interaction.user),
            "guild_id": interaction.guild.id if interaction.guild else None,
            "guild_name": interaction.guild.name if interaction.guild else None,
            "channel_id": interaction.channel.id if interaction.channel else None
        }
    }
    
    logger.error(f"Application command error occurred: {error_info.error_type}", extra={"error_data": log_data})
```

## エラー統計とレポート

### 1. エラー統計収集

```python
class ErrorStatistics:
    def __init__(self, db_service):
        self.db_service = db_service
    
    async def record_error(self, error_info: ErrorInfo, context: Dict[str, Any]) -> None:
        """エラー統計の記録"""
        query = """
        INSERT INTO error_statistics (
            timestamp, error_type, category, severity, 
            recoverable, command_name, user_id, guild_id, 
            created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        await self.db_service.execute_query(
            query,
            (
                datetime.now().isoformat(),
                error_info.error_type,
                error_info.category.value,
                error_info.severity.value,
                error_info.recoverable,
                context.get("command", {}).get("name"),
                context.get("user", {}).get("id"),
                context.get("guild", {}).get("id"),
                datetime.now().isoformat()
            )
        )
    
    async def get_error_trends(self, days: int = 7) -> Dict[str, Any]:
        """エラートレンドの取得"""
        query = """
        SELECT 
            DATE(timestamp) as date,
            error_type,
            category,
            severity,
            COUNT(*) as count
        FROM error_statistics 
        WHERE timestamp > datetime('now', '-{} days')
        GROUP BY DATE(timestamp), error_type, category, severity
        ORDER BY date DESC, count DESC
        """.format(days)
        
        results = await self.db_service.fetch_all(query, ())
        
        trends = {
            "daily_counts": {},
            "error_types": {},
            "categories": {},
            "severities": {}
        }
        
        for row in results:
            date = row["date"]
            if date not in trends["daily_counts"]:
                trends["daily_counts"][date] = 0
            trends["daily_counts"][date] += row["count"]
            
            error_type = row["error_type"]
            if error_type not in trends["error_types"]:
                trends["error_types"][error_type] = 0
            trends["error_types"][error_type] += row["count"]
            
            category = row["category"]
            if category not in trends["categories"]:
                trends["categories"][category] = 0
            trends["categories"][category] += row["count"]
            
            severity = row["severity"]
            if severity not in trends["severities"]:
                trends["severities"][severity] = 0
            trends["severities"][severity] += row["count"]
        
        return trends
    
    async def get_top_error_sources(self, limit: int = 10) -> List[Dict[str, Any]]:
        """主要エラー源の取得"""
        query = """
        SELECT 
            command_name,
            error_type,
            COUNT(*) as error_count,
            MAX(timestamp) as last_occurrence
        FROM error_statistics 
        WHERE timestamp > datetime('now', '-7 days')
        GROUP BY command_name, error_type
        ORDER BY error_count DESC
        LIMIT ?
        """
        
        return await self.db_service.fetch_all(query, (limit,))
```

## Cogレベルエラーハンドリング

### 1. Cogエラーハンドラーテンプレート

```python
class ExampleCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.error_stats = ErrorStatistics(bot.db_service)
    
    @commands.command()
    async def example_command(self, ctx):
        try:
            # コマンドロジック
            pass
        except SpecificException as e:
            # 特定の例外の処理
            await self._handle_specific_error(ctx, e)
        except Exception as e:
            # 予期しない例外
            await self._handle_unexpected_error(ctx, e)
    
    async def _handle_specific_error(self, ctx: commands.Context, error: Exception) -> None:
        """特定エラーの処理"""
        error_info = ErrorInfo(
            error_type=type(error).__name__,
            error_message=str(error),
            category=ErrorCategory.USER_ERROR,
            severity=ErrorSeverity.LOW,
            recoverable=True,
            user_friendly_message="操作を完了できませんでした。入力を確認してください。",
            technical_details={"error_details": str(error)},
            suggested_actions=["入力を確認", "再試行"],
            context={"command": ctx.command.name, "user": ctx.author.id}
        )
        
        await ctx.send(error_info.user_friendly_message)
        await self.error_stats.record_error(error_info, {"command": {"name": ctx.command.name}})
    
    async def _handle_unexpected_error(self, ctx: commands.Context, error: Exception) -> None:
        """予期しないエラーの処理"""
        error_id = _generate_error_id()
        
        await ctx.send(f"予期しないエラーが発生しました。エラーID: {error_id}")
        
        # 詳細ログ
        logger.error(
            f"Unexpected error in {ctx.command.name}",
            extra={
                "error_id": error_id,
                "error": str(error),
                "traceback": traceback.format_exc(),
                "command": ctx.command.name,
                "user": ctx.author.id,
                "guild": ctx.guild.id if ctx.guild else None
            }
        )
    
    @example_command.error
    async def example_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        """コマンド固有のエラーハンドラー"""
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"必須パラメータ `{error.param.name}` が不足しています。")
            ctx.handled = True
        elif isinstance(error, commands.BadArgument):
            await ctx.send("パラメータの形式が正しくありません。")
            ctx.handled = True
        # その他のエラーはグローバルハンドラーに委譲
```

## パフォーマンス監視

### 1. エラー率監視

```python
class ErrorRateMonitor:
    def __init__(self, threshold: float = 0.05):
        self.threshold = threshold  # 5%
        self.error_count = 0
        self.total_count = 0
        self.window_start = time.time()
        self.window_duration = 300  # 5分
    
    def record_command(self, success: bool) -> None:
        """コマンド実行結果の記録"""
        current_time = time.time()
        
        # ウィンドウのリセット
        if current_time - self.window_start > self.window_duration:
            self.error_count = 0
            self.total_count = 0
            self.window_start = current_time
        
        self.total_count += 1
        if not success:
            self.error_count += 1
    
    def get_error_rate(self) -> float:
        """現在のエラー率を取得"""
        if self.total_count == 0:
            return 0.0
        return self.error_count / self.total_count
    
    def is_error_rate_high(self) -> bool:
        """エラー率が閾値を超えているかチェック"""
        return self.get_error_rate() > self.threshold and self.total_count >= 10
```

---

## 関連ドキュメント

- [メインボットクラス](01-main-bot-class.md)
- [ログシステム](03-logging-system.md)
- [認証システム](02-authentication-system.md)
- [アプリケーション起動フロー](../01-architecture/02-application-startup-flow.md)
