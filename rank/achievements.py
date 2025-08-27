"""
アチーブメント・スキルツリー・プレステージシステム コマンド

Discord.pyレベリングシステムのゲーミフィケーション機能を
ユーザーが操作するためのコマンド群を提供。
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, List

from models.rank.achievements import (
    AchievementRarity
)
from utils.rank.achievement_manager import achievement_manager, AchievementProgress
from utils.logging import setup_logging

logger = setup_logging("ACHIEVEMENTS_COG")

class AchievementsCog(commands.Cog, name="アチーブメント"):
    """アチーブメント・スキルツリー・プレステージシステム"""
    
    def __init__(self, bot):
        self.bot = bot
        self.manager = achievement_manager
    
    async def cog_load(self):
        """Cog読み込み時の初期化"""
        try:
            success = await self.manager.initialize_achievements()
            if success:
                logger.info("アチーブメントシステムCog読み込み完了")
            else:
                logger.warning("アチーブメントシステム初期化に問題が発生しました")
        except Exception as e:
            logger.error(f"アチーブメントシステムCog読み込みエラー: {e}")
    
    # === アチーブメント関連コマンド ===
    
    @app_commands.command(name="achievements", description="あなたのアチーブメント一覧を表示します")
    @app_commands.describe(
        user="他のユーザーのアチーブメントを表示（省略可）",
        filter_type="アチーブメントタイプでフィルタ（省略可）",
        show_completed="達成済みのみ表示するか"
    )
    async def achievements_command(
        self, 
        interaction: discord.Interaction, 
        user: Optional[discord.Member] = None,
        filter_type: Optional[str] = None,
        show_completed: bool = False
    ):
        """アチーブメント一覧表示"""
        try:
            await interaction.response.defer()
            
            target_user = user or interaction.user
            guild_id = interaction.guild.id
            user_id = target_user.id
            
            # アチーブメント進捗取得
            progress_dict = await self.manager.get_user_achievements(guild_id, user_id)
            
            if not progress_dict:
                embed = discord.Embed(
                    title="📋 アチーブメント一覧",
                    description="まだアチーブメントがありません。活動を始めてアチーブメントを獲得しましょう！",
                    color=0x95a5a6
                )
                embed.set_author(name=target_user.display_name, icon_url=target_user.display_avatar.url)
                await interaction.followup.send(embed=embed)
                return
            
            # フィルタリング
            filtered_progress = []
            for progress in progress_dict.values():
                if filter_type and progress.achievement.type.value != filter_type:
                    continue
                if show_completed and not progress.is_completed:
                    continue
                filtered_progress.append(progress)
            
            # ソート（完了状況 → レアリティ → 進捗率順）
            filtered_progress.sort(key=lambda p: (
                not p.is_completed,  # 達成済みを先頭に
                p.achievement.rarity.value,
                -p.progress_percentage
            ))
            
            # ページング
            per_page = 8
            pages = [filtered_progress[i:i+per_page] for i in range(0, len(filtered_progress), per_page)]
            
            if not pages:
                embed = discord.Embed(
                    title="📋 アチーブメント一覧",
                    description="指定された条件に該当するアチーブメントが見つかりませんでした。",
                    color=0x95a5a6
                )
                embed.set_author(name=target_user.display_name, icon_url=target_user.display_avatar.url)
                await interaction.followup.send(embed=embed)
                return
            
            # 最初のページを表示
            await self._send_achievement_page(interaction, pages, 0, target_user, filter_type, show_completed)
            
        except Exception as e:
            logger.error(f"アチーブメント一覧コマンドエラー: {e}")
            embed = discord.Embed(
                title="❌ エラー",
                description="アチーブメント一覧の取得中にエラーが発生しました。しばらく後にもう一度お試しください。",
                color=0xe74c3c
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    async def _send_achievement_page(self, interaction: discord.Interaction, pages: List[List[AchievementProgress]], 
                                   page_index: int, target_user: discord.Member, 
                                   filter_type: Optional[str], show_completed: bool):
        """アチーブメントページ送信"""
        page = pages[page_index]
        
        # 統計計算
        total_achievements = sum(len(p) for p in pages)
        completed_count = sum(1 for progress in page if progress.is_completed)
        
        # 埋め込み作成
        embed = discord.Embed(
            title=f"📋 アチーブメント一覧 ({page_index + 1}/{len(pages)})",
            color=0x3498db
        )
        embed.set_author(name=target_user.display_name, icon_url=target_user.display_avatar.url)
        
        # フィルタ情報
        filter_info = []
        if filter_type:
            filter_info.append(f"タイプ: {filter_type}")
        if show_completed:
            filter_info.append("達成済みのみ")
        
        if filter_info:
            embed.add_field(name="フィルタ", value=" | ".join(filter_info), inline=False)
        
        # アチーブメント表示
        for progress in page:
            achievement = progress.achievement
            
            # アイコン・ステータス
            status_icon = "✅" if progress.is_completed else "⏳"
            rarity_icon = self._get_rarity_icon(achievement.rarity)
            
            # 進捗表示
            if progress.is_completed:
                progress_text = f"**達成済み** {status_icon}"
                if progress.completion_date:
                    progress_text += f"\n📅 {progress.completion_date.strftime('%Y/%m/%d')}"
            else:
                progress_bar = self._create_progress_bar(progress.progress_percentage, length=10)
                progress_text = f"{progress_bar} {progress.progress_percentage:.1f}%\n{progress.current_progress:,}/{achievement.condition.target_value:,}"
            
            # 報酬情報
            rewards = []
            if achievement.xp_reward > 0:
                rewards.append(f"🔥 {achievement.xp_reward:,} XP")
            if achievement.skill_points_reward > 0:
                rewards.append(f"⚡ {achievement.skill_points_reward} SP")
            reward_text = " | ".join(rewards) if rewards else "報酬なし"
            
            # フィールド追加
            field_name = f"{rarity_icon} {achievement.name} {status_icon}"
            field_value = (
                f"{achievement.description}\n"
                f"**進捗:** {progress_text}\n"
                f"**報酬:** {reward_text}"
            )
            
            embed.add_field(name=field_name, value=field_value, inline=False)
        
        # フッター
        embed.set_footer(text=f"総アチーブメント: {total_achievements} | このページの達成済み: {completed_count}")
        
        # ページングビュー
        if len(pages) > 1:
            view = AchievementPaginationView(pages, page_index, target_user, filter_type, show_completed)
            await interaction.followup.send(embed=embed, view=view)
        else:
            await interaction.followup.send(embed=embed)
    
    def _get_rarity_icon(self, rarity: AchievementRarity) -> str:
        """レアリティアイコン取得"""
        icons = {
            AchievementRarity.COMMON: "⚪",
            AchievementRarity.UNCOMMON: "🟢",
            AchievementRarity.RARE: "🔵",
            AchievementRarity.EPIC: "🟣",
            AchievementRarity.LEGENDARY: "🟠",
            AchievementRarity.MYTHIC: "🔴"
        }
        return icons.get(rarity, "⚪")
    
    def _create_progress_bar(self, percentage: float, length: int = 10) -> str:
        """進捗バー作成"""
        filled = int(percentage / 100 * length)
        empty = length - filled
        return f"{'█' * filled}{'░' * empty}"
    
    # === スキルツリー関連コマンド ===
    
    @app_commands.command(name="skills", description="スキルツリーを表示・管理します")
    @app_commands.describe(
        action="実行するアクション",
        skill_id="対象のスキルID（アップグレード時）",
        user="他のユーザーのスキルを表示（表示時のみ）"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="表示", value="view"),
        app_commands.Choice(name="アップグレード", value="upgrade"),
        app_commands.Choice(name="利用可能", value="available")
    ])
    async def skills_command(
        self, 
        interaction: discord.Interaction,
        action: str = "view",
        skill_id: Optional[str] = None,
        user: Optional[discord.Member] = None
    ):
        """スキルツリーコマンド"""
        try:
            await interaction.response.defer()
            
            if action == "view":
                await self._handle_skills_view(interaction, user)
            elif action == "upgrade":
                await self._handle_skill_upgrade(interaction, skill_id)
            elif action == "available":
                await self._handle_available_skills(interaction)
            
        except Exception as e:
            logger.error(f"スキルコマンドエラー: {e}")
            embed = discord.Embed(
                title="❌ エラー",
                description="スキルコマンドの実行中にエラーが発生しました。",
                color=0xe74c3c
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    async def _handle_skills_view(self, interaction: discord.Interaction, target_user: Optional[discord.Member]):
        """スキル表示処理"""
        target_user = target_user or interaction.user
        guild_id = interaction.guild.id
        user_id = target_user.id
        
        # ユーザースキル取得
        user_skills = await self.manager._get_user_skills(guild_id, user_id)
        
        if not user_skills:
            embed = discord.Embed(
                title="🌳 スキルツリー",
                description="まだスキルを習得していません。アチーブメントを達成してスキルポイントを獲得しましょう！",
                color=0x95a5a6
            )
            embed.set_author(name=target_user.display_name, icon_url=target_user.display_avatar.url)
            await interaction.followup.send(embed=embed)
            return
        
        # スキル詳細取得
        embed = discord.Embed(
            title="🌳 習得済みスキル",
            color=0x27ae60
        )
        embed.set_author(name=target_user.display_name, icon_url=target_user.display_avatar.url)
        
        # ティア別でグループ化
        skills_by_tier = {}
        total_invested = 0
        
        for skill_id, user_skill in user_skills.items():
            skill_node = self.manager.skill_cache.get(skill_id)
            if not skill_node:
                continue
            
            tier = skill_node.tier
            if tier not in skills_by_tier:
                skills_by_tier[tier] = []
            
            # 効果計算
            total_effect = user_skill.current_level * skill_node.effect_per_level
            
            skill_info = {
                'node': skill_node,
                'user_skill': user_skill,
                'total_effect': total_effect
            }
            skills_by_tier[tier].append(skill_info)
            total_invested += user_skill.total_invested_points
        
        # ティア順で表示
        for tier in sorted(skills_by_tier.keys()):
            tier_skills = skills_by_tier[tier]
            
            tier_text = []
            for skill_info in tier_skills:
                node = skill_info['node']
                user_skill = skill_info['user_skill']
                total_effect = skill_info['total_effect']
                
                level_text = f"Lv.{user_skill.current_level}/{node.max_level}"
                effect_text = f"効果: +{total_effect:.1%}" if node.type.value.endswith('_boost') else f"効果: {total_effect:.1f}"
                
                tier_text.append(
                    f"{node.icon or '🔹'} **{node.name}** ({level_text})\n"
                    f"└ {effect_text} | 投資SP: {user_skill.total_invested_points}"
                )
            
            embed.add_field(
                name=f"📊 ティア {tier}",
                value="\n\n".join(tier_text),
                inline=False
            )
        
        # 統計情報
        embed.set_footer(text=f"総投資スキルポイント: {total_invested} | 習得スキル数: {len(user_skills)}")
        
        await interaction.followup.send(embed=embed)
    
    async def _handle_skill_upgrade(self, interaction: discord.Interaction, skill_id: Optional[str]):
        """スキルアップグレード処理"""
        if not skill_id:
            embed = discord.Embed(
                title="❌ エラー",
                description="アップグレードするスキルIDを指定してください。\n`/skills action:利用可能` でスキル一覧を確認できます。",
                color=0xe74c3c
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # スキルアップグレードロジックは後で実装
        embed = discord.Embed(
            title="🚧 開発中",
            description="スキルアップグレード機能は現在開発中です。",
            color=0xf39c12
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    async def _handle_available_skills(self, interaction: discord.Interaction):
        """利用可能スキル表示処理"""
        guild_id = interaction.guild.id
        user_id = interaction.user.id
        
        # 利用可能スキル取得
        available_skills = await self.manager.get_available_skills(guild_id, user_id)
        
        if not available_skills:
            embed = discord.Embed(
                title="🌳 利用可能スキル",
                description="現在習得可能なスキルがありません。レベルアップやアチーブメント達成でスキルポイントを獲得しましょう。",
                color=0x95a5a6
            )
            await interaction.followup.send(embed=embed)
            return
        
        # ティア別でグループ化
        skills_by_tier = {}
        for skill in available_skills:
            tier = skill.tier
            if tier not in skills_by_tier:
                skills_by_tier[tier] = []
            skills_by_tier[tier].append(skill)
        
        embed = discord.Embed(
            title="🌳 習得可能スキル",
            description="以下のスキルが習得可能です:",
            color=0x3498db
        )
        
        for tier in sorted(skills_by_tier.keys()):
            tier_skills = skills_by_tier[tier]
            
            tier_text = []
            for skill in tier_skills:
                effect_text = f"+{skill.effect_per_level:.1%}" if skill.type.value.endswith('_boost') else f"{skill.effect_per_level:.1f}"
                
                tier_text.append(
                    f"{skill.icon or '🔹'} **{skill.name}** (ID: `{skill.id}`)\n"
                    f"└ {skill.description}\n"
                    f"└ コスト: {skill.skill_points_cost}SP | 最大Lv: {skill.max_level} | 効果/Lv: {effect_text}"
                )
            
            embed.add_field(
                name=f"📊 ティア {tier}",
                value="\n\n".join(tier_text),
                inline=False
            )
        
        await interaction.followup.send(embed=embed)
    
    # === プレステージ関連コマンド ===
    
    @app_commands.command(name="prestige", description="プレステージシステムの情報を表示します")
    @app_commands.describe(
        action="実行するアクション",
        tier="プレステージティア（詳細表示時）",
        prestige_type="プレステージタイプ（詳細表示時）"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="状況確認", value="status"),
        app_commands.Choice(name="利用可能", value="available"),
        app_commands.Choice(name="詳細", value="details")
    ])
    async def prestige_command(
        self, 
        interaction: discord.Interaction,
        action: str = "status",
        tier: Optional[int] = None,
        prestige_type: Optional[str] = None
    ):
        """プレステージコマンド"""
        try:
            await interaction.response.defer()
            
            if action == "status":
                await self._handle_prestige_status(interaction)
            elif action == "available":
                await self._handle_available_prestige(interaction)
            elif action == "details":
                await self._handle_prestige_details(interaction, tier, prestige_type)
            
        except Exception as e:
            logger.error(f"プレステージコマンドエラー: {e}")
            embed = discord.Embed(
                title="❌ エラー",
                description="プレステージコマンドの実行中にエラーが発生しました。",
                color=0xe74c3c
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    async def _handle_prestige_status(self, interaction: discord.Interaction):
        """プレステージ状況確認"""
        embed = discord.Embed(
            title="👑 プレステージ状況",
            description="プレステージ機能は現在開発中です。\n\n"
                      "プレステージは高レベルに到達したプレイヤーが、\n"
                      "進捗をリセットする代わりに特別な特典を得るシステムです。",
            color=0xf39c12
        )
        await interaction.followup.send(embed=embed)
    
    async def _handle_available_prestige(self, interaction: discord.Interaction):
        """利用可能プレステージ表示"""
        embed = discord.Embed(
            title="👑 利用可能プレステージ",
            description="プレステージ機能は現在開発中です。",
            color=0xf39c12
        )
        await interaction.followup.send(embed=embed)
    
    async def _handle_prestige_details(self, interaction: discord.Interaction, tier: Optional[int], prestige_type: Optional[str]):
        """プレステージ詳細表示"""
        embed = discord.Embed(
            title="👑 プレステージ詳細",
            description="プレステージ機能は現在開発中です。",
            color=0xf39c12
        )
        await interaction.followup.send(embed=embed)

class AchievementPaginationView(discord.ui.View):
    """アチーブメントページング用ビュー"""
    
    def __init__(self, pages: List[List[AchievementProgress]], current_page: int, 
                 target_user: discord.Member, filter_type: Optional[str], show_completed: bool):
        super().__init__(timeout=300.0)
        self.pages = pages
        self.current_page = current_page
        self.target_user = target_user
        self.filter_type = filter_type
        self.show_completed = show_completed
        
        # ボタンの有効/無効設定
        self.update_buttons()
    
    def update_buttons(self):
        """ボタンの有効/無効を更新"""
        self.prev_button.disabled = self.current_page <= 0
        self.next_button.disabled = self.current_page >= len(self.pages) - 1
    
    @discord.ui.button(label="◀️", style=discord.ButtonStyle.secondary)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """前のページ"""
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            
            # 新しいページを表示
            cog = interaction.client.get_cog("アチーブメント")
            if cog:
                await cog._send_achievement_page(
                    interaction, self.pages, self.current_page, 
                    self.target_user, self.filter_type, self.show_completed
                )
    
    @discord.ui.button(label="▶️", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """次のページ"""
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
            self.update_buttons()
            
            # 新しいページを表示
            cog = interaction.client.get_cog("アチーブメント")
            if cog:
                await cog._send_achievement_page(
                    interaction, self.pages, self.current_page, 
                    self.target_user, self.filter_type, self.show_completed
                )

async def setup(bot):
    """Cog設定"""
    await bot.add_cog(AchievementsCog(bot))
