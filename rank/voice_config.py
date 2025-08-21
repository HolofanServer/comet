"""
音声チャンネルXP・複数トラックシステム管理コマンド群

音声XP設定の管理、チャンネル設定、統計表示、プリセット適用など
管理者・ユーザー向けの包括的な音声XPシステム管理UI。
"""

import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional, Literal
from datetime import datetime, timedelta

from utils.logging import setup_logging
from utils.commands_help import is_guild, log_commands
from utils.rank.voice_manager import voice_manager
from models.rank.voice_activity import (
    VoiceConfig, VoiceTrackType, VoiceActivityType, 
    VoiceChannelConfig, VoicePresets
)
from config.setting import get_settings

logger = setup_logging("VOICE_CONFIG")
settings = get_settings()

class VoiceConfigCog(commands.Cog):
    """音声XPシステム管理"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @app_commands.command(
        name="voice-config-show",
        description="現在の音声XP設定を表示"
    )
    @is_guild()
    @log_commands()
    async def voice_config_show(self, interaction: discord.Interaction):
        """現在の音声XP設定を表示"""
        
        await interaction.response.defer()
        
        try:
            config = await voice_manager.get_guild_voice_config(interaction.guild_id)
            
            embed = discord.Embed(
                title="🎤 音声XP設定",
                description=f"**音声XP:** {'✅ 有効' if config.voice_xp_enabled else '❌ 無効'}",
                color=discord.Color.blue() if config.voice_xp_enabled else discord.Color.red()
            )
            
            # 基本設定
            embed.add_field(
                name="⚙️ 基本設定",
                value=f"**グローバル倍率:** {config.global_voice_multiplier}x\n"
                      f"**日次XP上限:** {config.daily_voice_xp_limit:,} XP\n"
                      f"**AFK判定時間:** {config.afk_detection_minutes} 分\n"
                      f"**XP計算間隔:** {config.xp_calculation_interval} 秒",
                inline=False
            )
            
            # トラック設定
            if config.tracks:
                track_info = []
                for track_type, track_config in list(config.tracks.items())[:4]:  # 最大4つまで表示
                    status = "✅" if track_config.is_active else "❌"
                    track_info.append(
                        f"{status} **{track_config.track_name}** ({track_config.global_multiplier}x)"
                    )
                
                embed.add_field(
                    name="🎯 音声トラック",
                    value="\n".join(track_info) if track_info else "設定なし",
                    inline=False
                )
            
            # チャンネル設定数
            embed.add_field(
                name="📊 統計",
                value=f"**設定済みチャンネル:** {len(config.channels)} 個\n"
                      f"**除外チャンネル:** {len(config.excluded_channel_ids)} 個\n"
                      f"**除外ユーザー:** {len(config.excluded_user_ids)} 人",
                inline=True
            )
            
            # 制限設定
            embed.add_field(
                name="🚫 制限設定",
                value=f"**最小セッション:** {config.min_voice_session_seconds} 秒\n"
                      f"**発言検出窓:** {config.speaking_detection_window} 秒\n"
                      f"**ボットチャンネル除外:** {'はい' if config.exclude_bot_channels else 'いいえ'}",
                inline=True
            )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"音声設定表示エラー: {e}")
            await interaction.followup.send(
                f"❌ **エラー**\n音声XP設定の表示に失敗しました: {str(e)}",
                ephemeral=True
            )
    
    @app_commands.command(
        name="voice-config-preset",
        description="音声XP設定プリセットを適用"
    )
    @app_commands.describe(
        preset="適用するプリセット",
        confirm="適用を確認するかどうか"
    )
    @is_guild()
    @log_commands()
    async def voice_config_preset(
        self, 
        interaction: discord.Interaction, 
        preset: Literal["balanced", "high_reward", "casual"],
        confirm: bool = False
    ):
        """音声XP設定プリセットを適用"""
        
        # 管理者権限チェック
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "❌ **エラー**\nこのコマンドはサーバー管理権限が必要です。",
                ephemeral=True
            )
            return
        
        await interaction.response.defer()
        
        try:
            # プリセット取得
            preset_configs = {
                "balanced": ("バランス型", VoicePresets.get_balanced()),
                "high_reward": ("高報酬型", VoicePresets.get_high_reward()),
                "casual": ("カジュアル型", VoicePresets.get_casual())
            }
            
            if preset not in preset_configs:
                await interaction.followup.send(
                    "❌ **エラー**\n無効なプリセットです。",
                    ephemeral=True
                )
                return
            
            preset_name, config = preset_configs[preset]
            
            if not confirm:
                # 確認画面
                embed = discord.Embed(
                    title="⚠️ 音声XP設定変更の確認",
                    description=f"**{preset_name}** プリセットを適用しようとしています。",
                    color=discord.Color.orange()
                )
                
                embed.add_field(
                    name="📋 プリセット詳細",
                    value=f"**グローバル倍率:** {config.global_voice_multiplier}x\n"
                          f"**日次XP上限:** {config.daily_voice_xp_limit:,} XP\n"
                          f"**AFK判定時間:** {config.afk_detection_minutes} 分\n"
                          f"**XP計算間隔:** {config.xp_calculation_interval} 秒",
                    inline=False
                )
                
                embed.add_field(
                    name="⚠️ 注意",
                    value="**この操作により既存の音声XP設定が変更されます。**\n"
                          "既存のチャンネル設定は保持されますが、基本設定が上書きされます。\n\n"
                          "`confirm=True` を追加して再実行してください。",
                    inline=False
                )
                
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # プリセット適用
            success = await voice_manager.save_guild_voice_config(
                interaction.guild_id,
                config,
                interaction.user.id
            )
            
            if success:
                embed = discord.Embed(
                    title="✅ 音声XP設定変更完了",
                    description=f"**{preset_name}** プリセットを適用しました！",
                    color=discord.Color.green()
                )
                
                embed.add_field(
                    name="🔄 変更内容",
                    value=f"**プリセット:** {preset_name}\n"
                          f"**グローバル倍率:** {config.global_voice_multiplier}x\n"
                          f"**日次XP上限:** {config.daily_voice_xp_limit:,} XP",
                    inline=False
                )
                
                embed.add_field(
                    name="💡 確認",
                    value="`/voice-config-show` で新しい設定を確認できます。",
                    inline=False
                )
                
                await interaction.followup.send(embed=embed)
                logger.info(f"Guild {interaction.guild_id}: 音声XPプリセット {preset} 適用完了 by {interaction.user.id}")
            else:
                await interaction.followup.send(
                    "❌ **エラー**\nプリセットの適用に失敗しました。",
                    ephemeral=True
                )
            
        except Exception as e:
            logger.error(f"プリセット適用エラー: {e}")
            await interaction.followup.send(
                f"❌ **エラー**\nプリセットの適用中にエラーが発生しました: {str(e)}",
                ephemeral=True
            )
    
    @app_commands.command(
        name="voice-config-channel",
        description="音声チャンネルの設定を変更"
    )
    @app_commands.describe(
        channel="設定するチャンネル",
        track_type="トラックタイプ",
        base_xp_per_minute="分あたり基本XP",
        enabled="チャンネルを有効にするか"
    )
    @is_guild()
    @log_commands()
    async def voice_config_channel(
        self,
        interaction: discord.Interaction,
        channel: discord.VoiceChannel,
        track_type: Optional[Literal["general", "study", "gaming", "music", "event"]] = None,
        base_xp_per_minute: Optional[int] = None,
        enabled: Optional[bool] = None
    ):
        """音声チャンネルの設定を変更"""
        
        # 管理者権限チェック
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "❌ **エラー**\nこのコマンドはサーバー管理権限が必要です。",
                ephemeral=True
            )
            return
        
        await interaction.response.defer()
        
        try:
            config = await voice_manager.get_guild_voice_config(interaction.guild_id)
            
            # チャンネル設定を取得または作成
            channel_config = config.get_channel_config(channel.id)
            channel_config.channel_name = channel.name
            
            # 設定更新
            changes = []
            
            if track_type is not None:
                try:
                    new_track_type = VoiceTrackType(track_type)
                    channel_config.track_type = new_track_type
                    changes.append(f"トラック: {track_type}")
                except ValueError:
                    await interaction.followup.send(
                        f"❌ **エラー**\n無効なトラックタイプです: {track_type}",
                        ephemeral=True
                    )
                    return
            
            if base_xp_per_minute is not None:
                if 1 <= base_xp_per_minute <= 100:
                    channel_config.base_xp_per_minute = base_xp_per_minute
                    changes.append(f"基本XP: {base_xp_per_minute}/分")
                else:
                    await interaction.followup.send(
                        "❌ **エラー**\n基本XPは1-100の範囲で指定してください。",
                        ephemeral=True
                    )
                    return
            
            if enabled is not None:
                channel_config.is_enabled = enabled
                changes.append(f"有効: {'はい' if enabled else 'いいえ'}")
            
            if not changes:
                await interaction.followup.send(
                    "❌ **エラー**\n変更する項目を指定してください。",
                    ephemeral=True
                )
                return
            
            # 設定を保存
            config.channels[channel.id] = channel_config
            success = await voice_manager.save_guild_voice_config(
                interaction.guild_id,
                config,
                interaction.user.id
            )
            
            if success:
                embed = discord.Embed(
                    title="✅ チャンネル設定更新完了",
                    description=f"**{channel.name}** の設定を更新しました！",
                    color=discord.Color.green()
                )
                
                embed.add_field(
                    name="🔄 変更内容",
                    value="\n".join(changes),
                    inline=False
                )
                
                embed.add_field(
                    name="📊 現在の設定",
                    value=f"**トラック:** {channel_config.track_type.value}\n"
                          f"**基本XP:** {channel_config.base_xp_per_minute}/分\n"
                          f"**有効:** {'はい' if channel_config.is_enabled else 'いいえ'}",
                    inline=False
                )
                
                await interaction.followup.send(embed=embed)
                logger.info(f"Guild {interaction.guild_id}: チャンネル {channel.id} 設定更新")
            else:
                await interaction.followup.send(
                    "❌ **エラー**\nチャンネル設定の更新に失敗しました。",
                    ephemeral=True
                )
            
        except Exception as e:
            logger.error(f"チャンネル設定更新エラー: {e}")
            await interaction.followup.send(
                f"❌ **エラー**\nチャンネル設定の更新中にエラーが発生しました: {str(e)}",
                ephemeral=True
            )
    
    @app_commands.command(
        name="voice-config-toggle",
        description="音声XPシステムの有効/無効を切り替え"
    )
    @app_commands.describe(
        enabled="音声XPを有効にするかどうか"
    )
    @is_guild()
    @log_commands()
    async def voice_config_toggle(
        self,
        interaction: discord.Interaction,
        enabled: bool
    ):
        """音声XPシステムの有効/無効を切り替え"""
        
        # 管理者権限チェック
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "❌ **エラー**\nこのコマンドはサーバー管理権限が必要です。",
                ephemeral=True
            )
            return
        
        await interaction.response.defer()
        
        try:
            config = await voice_manager.get_guild_voice_config(interaction.guild_id)
            
            if config.voice_xp_enabled == enabled:
                status = "有効" if enabled else "無効"
                await interaction.followup.send(
                    f"ℹ️ **情報**\n音声XPシステムは既に{status}になっています。",
                    ephemeral=True
                )
                return
            
            config.voice_xp_enabled = enabled
            
            success = await voice_manager.save_guild_voice_config(
                interaction.guild_id,
                config,
                interaction.user.id
            )
            
            if success:
                status = "有効化" if enabled else "無効化"
                icon = "✅" if enabled else "❌"
                color = discord.Color.green() if enabled else discord.Color.red()
                
                embed = discord.Embed(
                    title=f"{icon} 音声XPシステム{status}完了",
                    description=f"音声XPシステムを{status}しました。",
                    color=color
                )
                
                if enabled:
                    embed.add_field(
                        name="🎤 音声XP有効",
                        value="ユーザーが音声チャンネルに参加すると、時間に応じてXPが付与されます。",
                        inline=False
                    )
                else:
                    embed.add_field(
                        name="⏸️ 音声XP無効",
                        value="音声チャンネル滞在によるXP付与が停止されました。\n"
                              "既存の音声統計データは保持されます。",
                        inline=False
                    )
                
                await interaction.followup.send(embed=embed)
                logger.info(f"Guild {interaction.guild_id}: 音声XP {status} by {interaction.user.id}")
            else:
                await interaction.followup.send(
                    "❌ **エラー**\n設定の変更に失敗しました。",
                    ephemeral=True
                )
            
        except Exception as e:
            logger.error(f"音声XP切り替えエラー: {e}")
            await interaction.followup.send(
                f"❌ **エラー**\n設定の変更中にエラーが発生しました: {str(e)}",
                ephemeral=True
            )
    
    @app_commands.command(
        name="voice-config-multiplier",
        description="音声XPの倍率を設定"
    )
    @app_commands.describe(
        multiplier="グローバル倍率（0.1-10.0）"
    )
    @is_guild()
    @log_commands()
    async def voice_config_multiplier(
        self,
        interaction: discord.Interaction,
        multiplier: float
    ):
        """音声XPの倍率を設定"""
        
        # 管理者権限チェック
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "❌ **エラー**\nこのコマンドはサーバー管理権限が必要です。",
                ephemeral=True
            )
            return
        
        await interaction.response.defer()
        
        try:
            # バリデーション
            if not (0.1 <= multiplier <= 10.0):
                await interaction.followup.send(
                    "❌ **エラー**\n倍率は0.1-10.0の範囲で指定してください。",
                    ephemeral=True
                )
                return
            
            config = await voice_manager.get_guild_voice_config(interaction.guild_id)
            old_multiplier = config.global_voice_multiplier
            config.global_voice_multiplier = multiplier
            
            success = await voice_manager.save_guild_voice_config(
                interaction.guild_id,
                config,
                interaction.user.id
            )
            
            if success:
                embed = discord.Embed(
                    title="✅ 音声XP倍率更新完了",
                    description=f"グローバル倍率を **{old_multiplier}x** から **{multiplier}x** に変更しました。",
                    color=discord.Color.green()
                )
                
                if multiplier > old_multiplier:
                    embed.add_field(
                        name="📈 倍率アップ",
                        value=f"音声XPが **{(multiplier/old_multiplier):.1f}倍** 獲得しやすくなりました。",
                        inline=False
                    )
                elif multiplier < old_multiplier:
                    embed.add_field(
                        name="📉 倍率ダウン",
                        value=f"音声XPが **{(old_multiplier/multiplier):.1f}倍** 獲得しにくくなりました。",
                        inline=False
                    )
                
                await interaction.followup.send(embed=embed)
                logger.info(f"Guild {interaction.guild_id}: 音声XP倍率変更 {old_multiplier} -> {multiplier}")
            else:
                await interaction.followup.send(
                    "❌ **エラー**\n倍率の変更に失敗しました。",
                    ephemeral=True
                )
            
        except Exception as e:
            logger.error(f"音声XP倍率変更エラー: {e}")
            await interaction.followup.send(
                f"❌ **エラー**\n倍率の変更中にエラーが発生しました: {str(e)}",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(VoiceConfigCog(bot))
