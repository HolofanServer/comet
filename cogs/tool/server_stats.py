import discord
from discord.ext import commands, tasks
import datetime

from utils.logging import setup_logging
from config.setting import get_settings
from utils.commands_help import is_guild, is_moderator, log_commands
from utils.db_manager import db

logger = setup_logging("D")
settings = get_settings()

class ServerStatsCogs(commands.Cog):
    """サーバー統計表示機能"""
    
    def __init__(self, bot):
        self.bot = bot
        self.total_ch_id = None
        self.members_ch_id = None
        self.bot_ch_id = None
        self.guild_id = settings.admin_main_guild_id
        self.last_update = datetime.datetime.now()
        self.pending_update = False
        self.update_cooldown = 60
        self.update_stats.start()
    
    async def cog_load(self):
        """Cogが読み込まれたときに設定を読み込む"""
        if not db._initialized:
            await db.initialize()
        await self.load_config()
    
    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.guild.id == self.guild_id:
            logger.debug(f"メンバー参加: {member.name}")
            await self.schedule_update()
    
    @commands.Cog.listener()
    async def on_member_remove(self, member):
        if member.guild.id == self.guild_id:
            logger.debug(f"メンバー離脱: {member.name}")
            await self.schedule_update()
            
    async def schedule_update(self):
        """更新をスケジュールします（レート制限付き）"""
        now = datetime.datetime.now()
        time_since_last = (now - self.last_update).total_seconds()
        
        if time_since_last > self.update_cooldown:
            self.last_update = now
            await self.update_stats()
            logger.debug(f"クールダウン満了後の更新実行 ({time_since_last:.1f}秒経過)")
        elif not self.pending_update:
            
            self.pending_update = True
            logger.debug(f"更新を保留しました ({time_since_last:.1f}秒/クールダウン{self.update_cooldown}秒)")
    
    async def save_config(self):
        """設定をデータベースに保存"""
        try:
            if not db._initialized:
                await db.initialize()
                
            async with db.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO server_stats (guild_id, total_ch_id, members_ch_id, bot_ch_id, updated_at)
                    VALUES ($1, $2, $3, $4, NOW())
                    ON CONFLICT (guild_id) DO UPDATE 
                    SET total_ch_id = $2, members_ch_id = $3, bot_ch_id = $4, updated_at = NOW()
                    """,
                    self.guild_id, self.total_ch_id, self.members_ch_id, self.bot_ch_id
                )
            logger.info(f"サーバー統計設定を保存しました: {self.guild_id}")
            return True
        except Exception as e:
            logger.error(f"サーバー統計設定の保存中にエラー: {e}")
            return False
    
    async def load_config(self):
        """設定をデータベースから読み込み"""
        try:
            if not db._initialized:
                await db.initialize()
                
            async with db.pool.acquire() as conn:
                config = await conn.fetchrow(
                    "SELECT total_ch_id, members_ch_id, bot_ch_id FROM server_stats WHERE guild_id = $1",
                    self.guild_id
                )
                
                if config:
                    self.total_ch_id = config['total_ch_id']
                    self.members_ch_id = config['members_ch_id']
                    self.bot_ch_id = config['bot_ch_id']
                    logger.info(f"サーバー統計設定を読み込みました: {self.guild_id}")
                    return True
                else:
                    logger.info(f"サーバー統計設定が見つかりませんでした: {self.guild_id}")
                    return False
        except Exception as e:
            logger.error(f"サーバー統計設定の読み込み中にエラー: {e}")
            return False
    
    @tasks.loop(hours=1)
    async def update_stats(self):
        """統計情報を更新"""
        await self.bot.wait_until_ready()
        
        if not all([self.total_ch_id, self.members_ch_id, self.bot_ch_id]):
            return
            
        self.pending_update = False
        logger.debug("統計情報を更新します")
            
        guild = self.bot.get_guild(self.guild_id)
        if not guild:
            logger.error("サーバーが見つかりませんでした")
            return
        
        total_members = guild.member_count
        human_members = len([m for m in guild.members if not m.bot])
        bot_members = len([m for m in guild.members if m.bot])
        
        total_ch = self.bot.get_channel(self.total_ch_id)
        members_ch = self.bot.get_channel(self.members_ch_id)
        bot_ch = self.bot.get_channel(self.bot_ch_id)
        
        try:
            if isinstance(total_ch, discord.VoiceChannel):
                await total_ch.edit(name=f"Total: {total_members}")
                logger.debug(f"全体統計チャンネルを更新: {total_members}")
                
            if isinstance(members_ch, discord.VoiceChannel):
                await members_ch.edit(name=f"Members: {human_members}")
                logger.debug(f"メンバー統計チャンネルを更新: {human_members}")
                
            if isinstance(bot_ch, discord.VoiceChannel):
                await bot_ch.edit(name=f"Bots: {bot_members}")
                logger.debug(f"ボット統計チャンネルを更新: {bot_members}")
        except Exception as e:
            logger.error(f"チャンネル名の更新中にエラー: {e}")
    
    @commands.hybrid_group(name="stats", description="サーバー統計を表示・設定します")
    @log_commands()
    @is_moderator()
    @is_guild()
    async def stats(self, ctx):
        """サーバー統計コマンドグループ"""
        if ctx.invoked_subcommand is None:
            guild = self.bot.get_guild(self.guild_id)
            if not guild:
                await ctx.send("サーバー情報の取得に失敗しました。")
                return
                
            total_members = guild.member_count
            human_members = len([m for m in guild.members if not m.bot])
            bot_members = len([m for m in guild.members if m.bot])
            
            embed = discord.Embed(title="サーバー統計情報", color=discord.Color.blue())
            embed.add_field(name="全体人数", value=f"{total_members}", inline=True)
            embed.add_field(name="メンバー数", value=f"{human_members}", inline=True)
            embed.add_field(name="ボット数", value=f"{bot_members}", inline=True)
            
            if all([self.total_ch_id, self.members_ch_id, self.bot_ch_id]):
                embed.set_footer(text="ボイスチャンネルで統計表示中")
            else:
                embed.set_footer(text="統計表示チャンネル未設定")
                
            await ctx.send(embed=embed)
    
    @stats.command(name="set", description="統計表示用のボイスチャンネルを設定します")
    @is_moderator()
    @log_commands()
    @is_guild()
    async def set_stats_ch(self, ctx,
                          total_ch: discord.VoiceChannel,
                          member_ch: discord.VoiceChannel,
                          bot_ch: discord.VoiceChannel):
        """統計表示用のボイスチャンネルを設定します"""
        self.total_ch_id = total_ch.id
        self.members_ch_id = member_ch.id
        self.bot_ch_id = bot_ch.id
        
        success = await self.save_config()
        
        if success:
            await ctx.send(f"✅ サーバー統計表示チャンネルを設定しました。1時間ごと、およびメンバーの出入り時に更新されます。更新の間隔は最短{self.update_cooldown}秒です。")
            await self.update_stats()
        else:
            await ctx.send("❌ 設定の保存に失敗しました。ログを確認してください。")

    

async def setup(bot):
    """Cogをbotに登録"""
    await bot.add_cog(ServerStatsCogs(bot))
