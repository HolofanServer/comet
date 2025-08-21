"""
カスタムレベル公式管理コマンド群

Linear/Exponential/Logarithmic/Custom/Stepped公式による
柔軟なレベル進行システムの管理者向けコマンドを提供。
"""

import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional

from utils.logging import setup_logging
from utils.commands_help import is_guild, log_commands
from utils.rank.formula_manager import formula_manager
from models.rank.level_formula import LevelFormula, FormulaType
from config.setting import get_settings

logger = setup_logging("FORMULA_CONFIG")
settings = get_settings()

class FormulaConfigCog(commands.Cog):
    """カスタムレベル公式管理システム"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @app_commands.command(
        name="level-formula-show",
        description="現在のレベル計算公式を表示"
    )
    @is_guild()
    @log_commands()
    async def formula_show(self, interaction: discord.Interaction):
        """現在のレベル公式を表示"""
        
        await interaction.response.defer()
        
        try:
            formula = await formula_manager.get_guild_formula(interaction.guild_id)
            preview = formula.generate_preview()
            
            embed = discord.Embed(
                title="📊 現在のレベル計算公式",
                description=f"**公式名:** {formula.name}\n**タイプ:** {formula.formula_type.value.title()}",
                color=discord.Color.blue()
            )
            
            if formula.description:
                embed.add_field(
                    name="📝 説明",
                    value=formula.description,
                    inline=False
                )
            
            # 基本設定
            embed.add_field(
                name="⚙️ 設定",
                value=f"**最大レベル:** {formula.max_level}",
                inline=True
            )
            
            # プレビューレベル表示
            if preview["levels"]:
                level_info = []
                for level_data in preview["levels"][:5]:  # 最大5レベルまで表示
                    level = level_data["level"]
                    total_xp = level_data["total_xp_required"]
                    level_xp = level_data["level_xp_required"]
                    
                    level_info.append(f"**Lv.{level}:** {total_xp:,} XP ({level_xp:,} XP)")
                
                embed.add_field(
                    name="📈 レベル別必要XP",
                    value="\n".join(level_info),
                    inline=False
                )
            
            # 公式の詳細パラメータ
            if formula.formula_type == FormulaType.LINEAR and formula.linear:
                embed.add_field(
                    name="📐 線形公式パラメータ",
                    value=f"基本XP: {formula.linear.base_xp}\n倍率: {formula.linear.level_multiplier}",
                    inline=True
                )
            elif formula.formula_type == FormulaType.EXPONENTIAL and formula.exponential:
                embed.add_field(
                    name="📈 指数公式パラメータ",
                    value=f"基本XP: {formula.exponential.base_xp}\n成長率: {formula.exponential.growth_rate}",
                    inline=True
                )
            elif formula.formula_type == FormulaType.LOGARITHMIC and formula.logarithmic:
                embed.add_field(
                    name="📊 対数公式パラメータ",
                    value=f"基本XP: {formula.logarithmic.base_xp}\n対数底: {formula.logarithmic.log_base}",
                    inline=True
                )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"公式表示エラー: {e}")
            await interaction.followup.send(
                f"❌ **エラー**\n公式の表示に失敗しました: {str(e)}",
                ephemeral=True
            )
    
    @app_commands.command(
        name="level-formula-presets",
        description="利用可能なプリセット公式一覧を表示"
    )
    @is_guild()
    @log_commands()
    async def formula_presets(self, interaction: discord.Interaction):
        """プリセット公式一覧を表示"""
        
        await interaction.response.defer()
        
        try:
            presets = await formula_manager.get_available_presets()
            
            if not presets:
                embed = discord.Embed(
                    title="📋 プリセット公式",
                    description="利用可能なプリセット公式が見つかりません。",
                    color=discord.Color.orange()
                )
                await interaction.followup.send(embed=embed)
                return
            
            # 難易度別にグループ化
            difficulty_names = {1: "初心者", 2: "簡単", 3: "普通", 4: "難しい", 5: "上級者"}
            
            embed = discord.Embed(
                title="📋 利用可能なプリセット公式",
                description="以下のプリセット公式から選択できます：",
                color=discord.Color.green()
            )
            
            for preset in presets[:8]:  # 最大8個まで表示
                difficulty = difficulty_names.get(preset["difficulty_level"], "不明")
                preview_levels = preset["preview"]["levels"][:3]  # 最初の3レベル
                
                preview_text = "、".join([
                    f"Lv.{data['level']}: {data['total_xp_required']:,}XP"
                    for data in preview_levels
                ])
                
                embed.add_field(
                    name=f"🔧 {preset['preset_name']} (ID: {preset['preset_id']})",
                    value=f"**難易度:** {difficulty}\n"
                          f"**説明:** {preset['description']}\n"
                          f"**プレビュー:** {preview_text}",
                    inline=False
                )
            
            embed.add_field(
                name="💡 使用方法",
                value="`/level-formula-apply preset_id:<ID>` でプリセットを適用できます",
                inline=False
            )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"プリセット表示エラー: {e}")
            await interaction.followup.send(
                f"❌ **エラー**\nプリセットの表示に失敗しました: {str(e)}",
                ephemeral=True
            )
    
    @app_commands.command(
        name="level-formula-apply",
        description="プリセット公式を適用"
    )
    @app_commands.describe(
        preset_id="適用するプリセットのID",
        confirm="適用を確認するかどうか"
    )
    @is_guild()
    @log_commands()
    async def formula_apply(
        self, 
        interaction: discord.Interaction, 
        preset_id: int,
        confirm: bool = False
    ):
        """プリセット公式を適用"""
        
        # 管理者権限チェック
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "❌ **エラー**\nこのコマンドはサーバー管理権限が必要です。",
                ephemeral=True
            )
            return
        
        await interaction.response.defer()
        
        try:
            # プリセット情報を取得
            presets = await formula_manager.get_available_presets()
            target_preset = next((p for p in presets if p["preset_id"] == preset_id), None)
            
            if not target_preset:
                await interaction.followup.send(
                    f"❌ **エラー**\nプリセットID {preset_id} が見つかりません。\n"
                    "`/level-formula-presets` でプリセット一覧を確認してください。",
                    ephemeral=True
                )
                return
            
            if not confirm:
                # 確認画面
                embed = discord.Embed(
                    title="⚠️ レベル公式変更の確認",
                    description=f"**{target_preset['preset_name']}** を適用しようとしています。",
                    color=discord.Color.orange()
                )
                
                embed.add_field(
                    name="📝 説明",
                    value=target_preset["description"],
                    inline=False
                )
                
                embed.add_field(
                    name="🎯 難易度",
                    value=f"レベル {target_preset['difficulty_level']}/5",
                    inline=True
                )
                
                # プレビュー表示
                preview_levels = target_preset["preview"]["levels"][:4]
                preview_text = "\n".join([
                    f"**Lv.{data['level']}:** {data['total_xp_required']:,} XP"
                    for data in preview_levels
                ])
                
                embed.add_field(
                    name="📈 XP必要量プレビュー",
                    value=preview_text,
                    inline=False
                )
                
                embed.add_field(
                    name="⚠️ 注意",
                    value="**この操作により既存のレベル公式が変更されます。**\n"
                          "ユーザーのレベル計算に影響する可能性があります。\n\n"
                          "`confirm=True` を追加して再実行してください。",
                    inline=False
                )
                
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # プリセット適用
            success = await formula_manager.apply_preset_formula(
                interaction.guild_id, 
                preset_id, 
                interaction.user.id
            )
            
            if success:
                embed = discord.Embed(
                    title="✅ レベル公式変更完了",
                    description=f"**{target_preset['preset_name']}** を適用しました！",
                    color=discord.Color.green()
                )
                
                embed.add_field(
                    name="🔄 変更内容",
                    value=f"**公式:** {target_preset['preset_name']}\n"
                          f"**タイプ:** {target_preset['preview']['formula_type'].title()}\n"
                          f"**説明:** {target_preset['description']}",
                    inline=False
                )
                
                embed.add_field(
                    name="💡 確認",
                    value="`/level-formula-show` で新しい公式を確認できます。",
                    inline=False
                )
                
                await interaction.followup.send(embed=embed)
                logger.info(f"Guild {interaction.guild_id}: プリセット {preset_id} 適用完了 by {interaction.user.id}")
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
        name="level-formula-test",
        description="指定XPでレベル計算をテスト"
    )
    @app_commands.describe(
        total_xp="テストするXP量",
        target_level="逆算テスト用の目標レベル（オプション）"
    )
    @is_guild()
    @log_commands()
    async def formula_test(
        self, 
        interaction: discord.Interaction, 
        total_xp: Optional[int] = None,
        target_level: Optional[int] = None
    ):
        """レベル計算をテスト"""
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            if total_xp is None and target_level is None:
                await interaction.followup.send(
                    "❌ **エラー**\n`total_xp` または `target_level` のどちらかを指定してください。",
                    ephemeral=True
                )
                return
            
            formula = await formula_manager.get_guild_formula(interaction.guild_id)
            
            embed = discord.Embed(
                title="🧪 レベル公式テスト結果",
                description=f"**現在の公式:** {formula.name} ({formula.formula_type.value})",
                color=discord.Color.blue()
            )
            
            if total_xp is not None:
                # XPからレベルを計算
                level, level_xp, required = await formula_manager.calculate_level_from_total_xp(
                    interaction.guild_id, total_xp
                )
                
                embed.add_field(
                    name="📊 XP → レベル計算",
                    value=f"**入力XP:** {total_xp:,}\n"
                          f"**現在レベル:** {level}\n"
                          f"**レベル内XP:** {level_xp:,}\n"
                          f"**次レベルまで:** {required:,} XP",
                    inline=False
                )
            
            if target_level is not None:
                # レベルから必要XPを計算
                required_xp = await formula_manager.get_xp_required_for_level(
                    interaction.guild_id, target_level
                )
                
                embed.add_field(
                    name="🎯 レベル → XP計算",
                    value=f"**目標レベル:** {target_level}\n"
                          f"**必要累積XP:** {required_xp:,}",
                    inline=False
                )
                
                # 前レベルとの差分も表示
                if target_level > 1:
                    prev_xp = await formula_manager.get_xp_required_for_level(
                        interaction.guild_id, target_level - 1
                    )
                    diff_xp = required_xp - prev_xp
                    
                    embed.add_field(
                        name="📈 レベルアップ必要XP",
                        value=f"**Lv.{target_level-1} → Lv.{target_level}:** {diff_xp:,} XP",
                        inline=True
                    )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"公式テストエラー: {e}")
            await interaction.followup.send(
                f"❌ **エラー**\nテスト計算に失敗しました: {str(e)}",
                ephemeral=True
            )
    
    @app_commands.command(
        name="level-formula-create",
        description="カスタム線形公式を作成"
    )
    @app_commands.describe(
        name="公式名",
        base_xp="基本必要XP",
        multiplier="レベル毎増加XP",
        max_level="最大レベル",
        description="公式の説明（オプション）"
    )
    @is_guild()
    @log_commands()
    async def formula_create_linear(
        self, 
        interaction: discord.Interaction,
        name: str,
        base_xp: int,
        multiplier: int,
        max_level: int = 100,
        description: Optional[str] = None
    ):
        """カスタム線形公式を作成"""
        
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
            if not (1 <= base_xp <= 10000):
                await interaction.followup.send(
                    "❌ **エラー**\n基本XPは1-10000の範囲で指定してください。",
                    ephemeral=True
                )
                return
            
            if not (1 <= multiplier <= 1000):
                await interaction.followup.send(
                    "❌ **エラー**\n倍率は1-1000の範囲で指定してください。",
                    ephemeral=True
                )
                return
            
            if not (10 <= max_level <= 500):
                await interaction.followup.send(
                    "❌ **エラー**\n最大レベルは10-500の範囲で指定してください。",
                    ephemeral=True
                )
                return
            
            # カスタム公式作成
            from models.level_formula import LinearFormula
            
            linear_formula = LinearFormula(
                base_xp=base_xp,
                level_multiplier=multiplier
            )
            
            custom_formula = LevelFormula(
                formula_type=FormulaType.LINEAR,
                name=name[:50],  # 名前は50文字まで
                description=description[:200] if description else f"カスタム線形公式 (基本:{base_xp}, 倍率:{multiplier})",
                linear=linear_formula,
                max_level=max_level
            )
            
            # 公式を保存
            success = await formula_manager.set_guild_formula(
                interaction.guild_id,
                custom_formula,
                interaction.user.id
            )
            
            if success:
                # プレビュー生成
                preview = custom_formula.generate_preview()
                
                embed = discord.Embed(
                    title="✅ カスタム公式作成完了",
                    description=f"**{name}** を作成・適用しました！",
                    color=discord.Color.green()
                )
                
                embed.add_field(
                    name="⚙️ 設定",
                    value=f"**タイプ:** 線形公式\n"
                          f"**基本XP:** {base_xp}\n"
                          f"**レベル毎増加:** {multiplier}\n"
                          f"**最大レベル:** {max_level}",
                    inline=False
                )
                
                # プレビュー表示
                if preview["levels"]:
                    preview_text = "\n".join([
                        f"**Lv.{data['level']}:** {data['total_xp_required']:,} XP"
                        for data in preview["levels"][:4]
                    ])
                    
                    embed.add_field(
                        name="📈 XP必要量プレビュー",
                        value=preview_text,
                        inline=False
                    )
                
                await interaction.followup.send(embed=embed)
                logger.info(f"Guild {interaction.guild_id}: カスタム公式 '{name}' 作成完了")
            else:
                await interaction.followup.send(
                    "❌ **エラー**\nカスタム公式の作成に失敗しました。",
                    ephemeral=True
                )
            
        except Exception as e:
            logger.error(f"カスタム公式作成エラー: {e}")
            await interaction.followup.send(
                f"❌ **エラー**\nカスタム公式の作成中にエラーが発生しました: {str(e)}",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(FormulaConfigCog(bot))
