"""
レベリングシステムのAI設定管理コマンド群

自然言語による設定変更、設定の確認・編集・エクスポート等の
管理者向けコマンドを提供。
"""

import discord
from discord.ext import commands
from discord import app_commands

from typing import Optional, Dict, Any
from datetime import datetime

from utils.logging import setup_logging
from utils.commands_help import is_guild, log_commands
from utils.database import execute_query
from utils.rank.ai_config import parse_config_natural_language, explain_config_japanese
from models.rank.level_config import LevelConfig
from config.setting import get_settings

logger = setup_logging("RANK_CONFIG")
settings = get_settings()

class RankConfigCog(commands.Cog):
    """レベリングシステムのAI設定管理"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @app_commands.command(
        name="level-config-parse",
        description="自然言語でレベリング設定を変更（AI解析）"
    )
    @app_commands.describe(
        setting="設定内容を自然言語で記述（例：#qa は平日20-24時XP2倍、スパム語は無効）",
        confirm="設定を即座に適用するかどうか（デフォルト：プレビューのみ）"
    )
    @is_guild()
    @log_commands()
    async def config_parse(
        self, 
        interaction: discord.Interaction, 
        setting: str,
        confirm: bool = False
    ):
        """自然言語設定の解析・適用"""
        
        # 管理者権限チェック
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "❌ **エラー**\nこのコマンドはサーバー管理権限が必要です。",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(thinking=True)
        
        try:
            # サーバーコンテキスト収集
            context = await self._gather_server_context(interaction.guild)
            
            # AI解析
            result = await parse_config_natural_language(setting, context=context)
            
            if not result.success:
                embed = discord.Embed(
                    title="❌ 設定解析エラー",
                    description=f"**エラー内容:**\n{result.error_message}",
                    color=discord.Color.red()
                )
                embed.add_field(
                    name="入力内容",
                    value=f"```\n{result.original_input[:500]}\n```",
                    inline=False
                )
                embed.add_field(
                    name="💡 改善提案",
                    value="• より具体的にチャンネル名やロール名を指定してください\n"
                          "• 時刻は「20:00-24:00」形式で指定してください\n"
                          "• 倍率は「2倍」「0.5倍」などで指定してください",
                    inline=False
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # 設定説明生成
            explanation = await explain_config_japanese(result.config)
            
            # プレビューEmbed作成
            embed = discord.Embed(
                title="🤖 AI設定解析結果",
                description=f"**信頼度:** {result.confidence:.1%}\n\n**解析された設定:**",
                color=discord.Color.green()
            )
            
            # 説明を追加
            if explanation:
                embed.add_field(
                    name="📋 設定内容",
                    value=explanation[:1000] + ("..." if len(explanation) > 1000 else ""),
                    inline=False
                )
            
            # JSON設定（折りたたみ）
            config_json = result.config.model_dump_json(indent=2, ensure_ascii=False)
            if len(config_json) <= 1000:
                embed.add_field(
                    name="🔧 JSON設定",
                    value=f"```json\n{config_json}\n```",
                    inline=False
                )
            else:
                embed.add_field(
                    name="🔧 JSON設定",
                    value="```json\n" + config_json[:900] + "\n...\n```",
                    inline=False
                )
            
            # 適用の確認
            if not confirm:
                embed.add_field(
                    name="⚠️ 確認",
                    value="**この設定はまだ適用されていません。**\n"
                          "`confirm=True` を追加して再実行すると適用されます。",
                    inline=False
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                # データベースに保存
                await self._save_level_config(interaction.guild_id, result.config)
                
                embed.add_field(
                    name="✅ 適用完了",
                    value="設定がサーバーに適用されました！",
                    inline=False
                )
                await interaction.followup.send(embed=embed)
                
                logger.info(f"Guild {interaction.guild_id}: AI設定適用完了")
                
        except Exception as e:
            logger.error(f"設定解析エラー: {e}")
            await interaction.followup.send(
                f"❌ **予期しないエラー**\n処理中に問題が発生しました: {str(e)}",
                ephemeral=True
            )
    
    @app_commands.command(
        name="level-config-show",
        description="現在のレベリング設定を表示"
    )
    @is_guild()
    @log_commands()
    async def config_show(self, interaction: discord.Interaction):
        """現在の設定を表示"""
        
        await interaction.response.defer()
        
        try:
            # 現在の設定を取得
            config = await self._load_level_config(interaction.guild_id)
            
            if not config:
                embed = discord.Embed(
                    title="📋 レベリング設定",
                    description="❌ **設定が見つかりません**\n\nデフォルト設定が使用されています。\n"
                               "`/level-config-parse` コマンドで設定を作成してください。",
                    color=discord.Color.orange()
                )
                await interaction.followup.send(embed=embed)
                return
            
            # AI説明生成
            explanation = await explain_config_japanese(config)
            
            embed = discord.Embed(
                title="📋 現在のレベリング設定",
                description="",
                color=discord.Color.blue()
            )
            
            # 基本情報
            embed.add_field(
                name="⚙️ 基本設定",
                value=f"**基本XP:** {config.base_xp}\n"
                      f"**クールダウン:** {config.base_cooldown}秒\n"
                      f"**全体倍率:** {config.global_multiplier}x\n"
                      f"**有効状態:** {'✅ 有効' if config.enabled else '❌ 無効'}",
                inline=True
            )
            
            # チャンネル設定
            if config.channels:
                channel_info = []
                for ch in config.channels[:5]:  # 最大5個まで表示
                    name = ch.channel_name or f"<#{ch.channel_id}>"
                    channel_info.append(f"• {name}: {ch.multiplier}x")
                if len(config.channels) > 5:
                    channel_info.append(f"... 他{len(config.channels)-5}個")
                
                embed.add_field(
                    name="📺 チャンネル設定",
                    value="\n".join(channel_info),
                    inline=True
                )
            
            # 時間帯設定
            if config.time_windows:
                time_info = []
                for tw in config.time_windows[:3]:  # 最大3個まで表示
                    days = tw.day if isinstance(tw.day, str) else ", ".join(tw.day)
                    time_info.append(f"• {days} {tw.start_time}-{tw.end_time}: {tw.multiplier}x")
                if len(config.time_windows) > 3:
                    time_info.append(f"... 他{len(config.time_windows)-3}個")
                
                embed.add_field(
                    name="⏰ 時間帯設定",
                    value="\n".join(time_info),
                    inline=False
                )
            
            # AI説明
            if explanation:
                embed.add_field(
                    name="💬 AI説明",
                    value=explanation[:500] + ("..." if len(explanation) > 500 else ""),
                    inline=False
                )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"設定表示エラー: {e}")
            await interaction.followup.send(
                f"❌ **エラー**\n設定の表示に失敗しました: {str(e)}",
                ephemeral=True
            )
    
    @app_commands.command(
        name="level-config-export",
        description="設定をJSONファイルでエクスポート"
    )
    @is_guild()
    @log_commands()
    async def config_export(self, interaction: discord.Interaction):
        """設定をJSONでエクスポート"""
        
        # 管理者権限チェック  
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "❌ **エラー**\nこのコマンドはサーバー管理権限が必要です。",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            config = await self._load_level_config(interaction.guild_id)
            
            if not config:
                await interaction.followup.send(
                    "❌ **エラー**\n設定が見つかりません。",
                    ephemeral=True
                )
                return
            
            # JSON作成
            config_json = config.model_dump_json(indent=2, ensure_ascii=False)
            
            # ファイル作成
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"level_config_{interaction.guild.name}_{timestamp}.json"
            
            file = discord.File(
                fp=discord.utils._BytesLikeObject(config_json.encode('utf-8')),
                filename=filename
            )
            
            embed = discord.Embed(
                title="📤 設定エクスポート",
                description=f"**ファイル名:** `{filename}`\n"
                           f"**サイズ:** {len(config_json)} bytes",
                color=discord.Color.green()
            )
            
            await interaction.followup.send(
                embed=embed,
                file=file,
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"設定エクスポートエラー: {e}")
            await interaction.followup.send(
                f"❌ **エラー**\nエクスポートに失敗しました: {str(e)}",
                ephemeral=True
            )
    
    @app_commands.command(
        name="level-config-reset",
        description="レベリング設定をリセット"
    )
    @app_commands.describe(confirm="本当にリセットするか確認")
    @is_guild()
    @log_commands()
    async def config_reset(self, interaction: discord.Interaction, confirm: bool = False):
        """設定リセット"""
        
        # 管理者権限チェック
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "❌ **エラー**\nこのコマンドはサーバー管理権限が必要です。",
                ephemeral=True
            )
            return
        
        if not confirm:
            embed = discord.Embed(
                title="⚠️ 設定リセット確認",
                description="**この操作により以下が削除されます：**\n"
                           "• すべてのチャンネル別設定\n"
                           "• すべてのロール別設定\n"
                           "• すべての時間帯設定\n"
                           "• カスタムスパムフィルタ\n\n"
                           "**実行するには `confirm=True` を追加してください。**",
                color=discord.Color.orange()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        await interaction.response.defer()
        
        try:
            # データベースから削除
            await self._delete_level_config(interaction.guild_id)
            
            embed = discord.Embed(
                title="✅ 設定リセット完了",
                description="レベリング設定が初期状態にリセットされました。\n"
                           "デフォルト設定が適用されています。",
                color=discord.Color.green()
            )
            
            await interaction.followup.send(embed=embed)
            logger.info(f"Guild {interaction.guild_id}: 設定リセット完了")
            
        except Exception as e:
            logger.error(f"設定リセットエラー: {e}")
            await interaction.followup.send(
                f"❌ **エラー**\nリセットに失敗しました: {str(e)}",
                ephemeral=True
            )
    
    async def _gather_server_context(self, guild: discord.Guild) -> Dict[str, Any]:
        """サーバーのコンテキスト情報を収集"""
        context = {}
        
        try:
            # チャンネル情報
            channels = []
            for channel in guild.text_channels:
                channels.append(f"#{channel.name}")
            context["channels"] = channels[:20]  # 最大20個
            
            # ロール情報
            roles = []
            for role in guild.roles:
                if role.name != "@everyone":
                    roles.append(role.name)
            context["roles"] = roles[:20]  # 最大20個
            
        except Exception as e:
            logger.warning(f"コンテキスト収集エラー: {e}")
        
        return context
    
    async def _save_level_config(self, guild_id: int, config: LevelConfig):
        """設定をデータベースに保存"""
        config_json = config.model_dump_json()
        
        query = """
        INSERT INTO level_configs (guild_id, config_data, updated_at)
        VALUES ($1, $2, NOW())
        ON CONFLICT (guild_id)
        DO UPDATE SET 
            config_data = EXCLUDED.config_data,
            updated_at = NOW()
        """
        
        await execute_query(query, guild_id, config_json)
    
    async def _load_level_config(self, guild_id: int) -> Optional[LevelConfig]:
        """データベースから設定を読み込み"""
        query = "SELECT config_data FROM level_configs WHERE guild_id = $1"
        result = await execute_query(query, guild_id)
        
        if result and len(result) > 0:
            config_json = result[0]["config_data"]
            return LevelConfig.model_validate_json(config_json)
        
        return None
    
    async def _delete_level_config(self, guild_id: int):
        """設定を削除"""
        query = "DELETE FROM level_configs WHERE guild_id = $1"
        await execute_query(query, guild_id)

async def setup(bot):
    await bot.add_cog(RankConfigCog(bot))
