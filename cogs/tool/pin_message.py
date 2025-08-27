import discord
from discord.ext import commands, tasks
from discord import app_commands
from discord.ui import View, Modal, LayoutView, TextDisplay, Container
from typing import Optional
from datetime import datetime
from utils.db_manager import db
from utils.logging import setup_logging
from utils.commands_help import log_commands, is_owner_app, is_guild_app

logger = setup_logging()

class ChannelStickyMessageCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.message_counters = {}  # {channel_id: count}
        self.last_sticky_times = {}  # {channel_id: datetime}
        self.last_sticky_messages = {}  # {channel_id: message_id}

    async def cog_load(self):
        """Cogが読み込まれた時の初期化処理"""
        await self.setup_database()
        self.sticky_message_checker.start()

    async def cog_unload(self):
        """Cogがアンロードされる時の処理"""
        self.sticky_message_checker.cancel()

    async def setup_database(self):
        """データベーステーブルの作成"""
        async with db.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS sticky_messages (
                    id SERIAL PRIMARY KEY,
                    guild_id BIGINT NOT NULL,
                    channel_id BIGINT NOT NULL,
                    message_content TEXT NOT NULL,
                    trigger_type VARCHAR(20) DEFAULT 'time',
                    time_interval INTEGER DEFAULT 300,
                    message_interval INTEGER DEFAULT 10,
                    is_enabled BOOLEAN DEFAULT TRUE,
                    last_message_count INTEGER DEFAULT 0,
                    last_sticky_time TIMESTAMP,
                    last_sticky_message_id BIGINT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(guild_id, channel_id)
                )
            """)
            
            # 既存のテーブルにtrigger_typeカラムを追加
            try:
                await conn.execute("ALTER TABLE sticky_messages ADD COLUMN IF NOT EXISTS trigger_type VARCHAR(20) DEFAULT 'time'")
                await conn.execute("ALTER TABLE sticky_messages ADD COLUMN IF NOT EXISTS last_message_count INTEGER DEFAULT 0")
                await conn.execute("ALTER TABLE sticky_messages ADD COLUMN IF NOT EXISTS last_sticky_time TIMESTAMP")
                await conn.execute("ALTER TABLE sticky_messages ADD COLUMN IF NOT EXISTS last_sticky_message_id BIGINT")
            except Exception as e:
                logger.info(f"カラム追加をスキップ（既に存在）: {e}")

        await self.restore_state_from_database()

    async def restore_state_from_database(self):
        """データベースから状態を復元"""
        async with db.pool.acquire() as conn:
            configs = await conn.fetch("""
                SELECT channel_id, last_message_count, last_sticky_time, last_sticky_message_id
                FROM sticky_messages 
                WHERE is_enabled = TRUE
            """)
        
        for config in configs:
            channel_id = config['channel_id']
            
            # メッセージカウンターを復元
            if config['last_message_count'] is not None:
                self.message_counters[channel_id] = config['last_message_count']
            
            # 最後の投稿時間を復元
            if config['last_sticky_time']:
                self.last_sticky_times[channel_id] = config['last_sticky_time']
            
            # 最後のメッセージIDを復元
            if config['last_sticky_message_id']:
                self.last_sticky_messages[channel_id] = config['last_sticky_message_id']
        
        logger.info(f"状態を復元しました: {len(configs)}チャンネル")

    @commands.Cog.listener()
    async def on_message(self, message):
        """メッセージが投稿された時の処理"""
        if message.author.bot:
            return
        
        if not message.guild:
            return

        channel_id = message.channel.id
        
        # メッセージカウンターを更新
        if channel_id not in self.message_counters:
            self.message_counters[channel_id] = 0
        self.message_counters[channel_id] += 1

        # データベースにカウンターを保存
        await self.update_message_count_in_db(message.guild.id, channel_id, self.message_counters[channel_id])

        # 固定メッセージの投稿条件をチェック
        await self.check_and_post_sticky_message(message.channel)

    async def update_message_count_in_db(self, guild_id, channel_id, count):
        """メッセージカウンターをデータベースに保存"""
        try:
            async with db.pool.acquire() as conn:
                await conn.execute("""
                    UPDATE sticky_messages 
                    SET last_message_count = $1, updated_at = CURRENT_TIMESTAMP
                    WHERE guild_id = $2 AND channel_id = $3
                """, count, guild_id, channel_id)
        except Exception as e:
            logger.warning(f"メッセージカウンターの保存に失敗: {e}")

    async def check_and_post_sticky_message(self, channel):
        """固定メッセージの投稿条件をチェックして投稿"""
        async with db.pool.acquire() as conn:
            config = await conn.fetchrow("""
                SELECT message_content, trigger_type, time_interval, message_interval, is_enabled
                FROM sticky_messages 
                WHERE guild_id = $1 AND channel_id = $2 AND is_enabled = TRUE
            """, channel.guild.id, channel.id)

        if not config:
            return

        channel_id = channel.id
        current_time = datetime.now()
        message_count = self.message_counters.get(channel_id, 0)
        last_sticky_time = self.last_sticky_times.get(channel_id)

        # 条件チェック
        should_post = False
        
        # メッセージ数条件
        if config['trigger_type'] == 'count' and message_count >= config['message_interval']:
            should_post = True
        
        # 時間条件
        if config['trigger_type'] == 'time' and last_sticky_time:
            time_diff = current_time - last_sticky_time
            if time_diff.total_seconds() >= config['time_interval']:
                should_post = True
        elif config['trigger_type'] == 'time' and not last_sticky_time:
            should_post = True  # 初回投稿

        if should_post:
            await self.post_sticky_message(channel, config['message_content'])

    async def post_sticky_message(self, channel, content):
        """固定メッセージを投稿"""
        try:
            # 古い固定メッセージを削除
            await self.delete_old_sticky_message(channel)
            
            # 新しい固定メッセージを投稿
            message = await channel.send(content)
            
            # 記録を更新
            channel_id = channel.id
            current_time = datetime.now()
            self.last_sticky_times[channel_id] = current_time
            self.last_sticky_messages[channel_id] = message.id
            self.message_counters[channel_id] = 0  # カウンターリセット
            
            # データベースに状態を保存
            await self.save_sticky_state_to_db(channel.guild.id, channel_id, current_time, message.id)
            
            logger.info(f"固定メッセージを投稿しました: {channel.guild.name}#{channel.name}")
            
        except discord.HTTPException as e:
            logger.error(f"固定メッセージの投稿に失敗しました: {e}")

    async def save_sticky_state_to_db(self, guild_id, channel_id, sticky_time, message_id):
        """固定メッセージの状態をデータベースに保存"""
        try:
            async with db.pool.acquire() as conn:
                await conn.execute("""
                    UPDATE sticky_messages 
                    SET last_message_count = 0, 
                        last_sticky_time = $1, 
                        last_sticky_message_id = $2,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE guild_id = $3 AND channel_id = $4
                """, sticky_time, message_id, guild_id, channel_id)
        except Exception as e:
            logger.error(f"固定メッセージ状態の保存に失敗: {e}")

    async def delete_old_sticky_message(self, channel):
        """古い固定メッセージを削除"""
        channel_id = channel.id
        old_message_id = self.last_sticky_messages.get(channel_id)
        
        if old_message_id:
            try:
                old_message = await channel.fetch_message(old_message_id)
                await old_message.delete()
                logger.info(f"古い固定メッセージを削除しました: {channel.guild.name}#{channel.name}")
            except discord.NotFound:
                pass  # メッセージが既に削除されている
            except discord.HTTPException as e:
                logger.warning(f"古い固定メッセージの削除に失敗しました: {e}")

    @tasks.loop(seconds=30)
    async def sticky_message_checker(self):
        """定期的に時間ベースの条件をチェック"""
        try:
            async with db.pool.acquire() as conn:
                configs = await conn.fetch("""
                    SELECT guild_id, channel_id, message_content, trigger_type, time_interval
                    FROM sticky_messages 
                    WHERE is_enabled = TRUE
                """)

            for config in configs:
                guild = self.bot.get_guild(config['guild_id'])
                if not guild:
                    continue
                
                channel = guild.get_channel(config['channel_id'])
                if not channel:
                    continue

                channel_id = channel.id
                last_sticky_time = self.last_sticky_times.get(channel_id)
                
                if config['trigger_type'] == 'time' and last_sticky_time:
                    time_diff = datetime.now() - last_sticky_time
                    if time_diff.total_seconds() >= config['time_interval']:
                        await self.post_sticky_message(channel, config['message_content'])

        except Exception as e:
            logger.error(f"固定メッセージチェッカーでエラーが発生しました: {e}")

    class StickyConfigPanel(LayoutView):
        """Components v2を使用した固定メッセージ設定パネル"""
        
        def __init__(self, cog, channel, config=None):
            super().__init__(timeout=300)
            self.cog = cog
            self.channel = channel
            self.config = config
            
            # 現在の設定表示
            if config:
                status_text = f"状態: {'✅ 有効' if config['is_enabled'] else '❌ 無効'}"
                trigger_text = f"トリガー: {'⏰ 時間間隔' if config['trigger_type'] == 'time' else '📊 メッセージ数'}"
                
                if config['trigger_type'] == 'time':
                    interval_text = f"間隔: {config['time_interval']}秒"
                else:
                    interval_text = f"間隔: {config['message_interval']}メッセージ"
                
                content_preview = config['message_content'][:50] + "..." if len(config['message_content']) > 50 else config['message_content']
                
                config_text = f"📌 固定メッセージ設定\n{status_text}\n{trigger_text}\n{interval_text}\n内容: {content_preview}"
            else:
                config_text = "📌 固定メッセージ設定\n❌ 設定されていません"
            
            # 現在の状況表示
            channel_id = channel.id
            current_count = self.cog.message_counters.get(channel_id, 0)
            last_time = self.cog.last_sticky_times.get(channel_id)
            
            if last_time:
                time_since = datetime.now() - last_time
                status_info = f"📊 現在の状況\n前回投稿から: {int(time_since.total_seconds())}秒経過\n投稿後メッセージ数: {current_count}"
            else:
                status_info = "📊 現在の状況\nまだ投稿されていません"
            
            # Containerを使用してTextDisplayをグループ化
            config_container = Container()
            config_container.add_item(TextDisplay(content=config_text))
            
            status_container = Container()
            status_container.add_item(TextDisplay(content=status_info))
            
            self.add_item(config_container)
            self.add_item(status_container)

    class StickyConfigButtons(View):
        """設定用のボタンパネル"""
        
        def __init__(self, cog, channel, config=None):
            super().__init__(timeout=300)
            self.cog = cog
            self.channel = channel
            self.config = config
        
        async def interaction_check(self, interaction: discord.Interaction) -> bool:
            """インタラクションの権限チェック"""
            return interaction.user.guild_permissions.administrator or interaction.user.id == interaction.client.owner_id
        
        @discord.ui.button(label="⚙️ 設定編集", style=discord.ButtonStyle.primary)
        async def edit_config_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            modal = self.cog.StickyConfigModal(self.cog, self.channel, self.config)
            await interaction.response.send_modal(modal)
        
        @discord.ui.button(label="🔄 有効/無効切替", style=discord.ButtonStyle.secondary)
        async def toggle_enabled_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if not self.config:
                await interaction.response.send_message("設定が存在しません", ephemeral=True)
                return
            
            new_status = not self.config['is_enabled']
            async with db.pool.acquire() as conn:
                await conn.execute("""
                    UPDATE sticky_messages 
                    SET is_enabled = $1, updated_at = CURRENT_TIMESTAMP
                    WHERE guild_id = $2 AND channel_id = $3
                """, new_status, interaction.guild_id, self.channel.id)
            
            status_text = "有効" if new_status else "無効"
            await interaction.response.send_message(f"固定メッセージを{status_text}にしました", ephemeral=True)
        
        @discord.ui.button(label="🗑️ 設定削除", style=discord.ButtonStyle.danger)
        async def delete_config_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if not self.config:
                await interaction.response.send_message("設定が存在しません", ephemeral=True)
                return
            
            async with db.pool.acquire() as conn:
                await conn.execute("""
                    DELETE FROM sticky_messages 
                    WHERE guild_id = $1 AND channel_id = $2
                """, interaction.guild_id, self.channel.id)
            
            # 内部状態もクリア
            channel_id = self.channel.id
            self.cog.message_counters.pop(channel_id, None)
            self.cog.last_sticky_times.pop(channel_id, None)
            self.cog.last_sticky_message_ids.pop(channel_id, None)
            
            await interaction.response.send_message("固定メッセージ設定を削除しました", ephemeral=True)
        
        @discord.ui.button(label="📤 今すぐ投稿", style=discord.ButtonStyle.success)
        async def post_now_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if not self.config or not self.config['is_enabled']:
                await interaction.response.send_message("有効な設定が存在しません", ephemeral=True)
                return
            
            await self.cog.post_sticky_message(self.channel, self.config['message_content'])
            await interaction.response.send_message("固定メッセージを投稿しました", ephemeral=True)

    class StickyConfigModal(Modal):
        """設定変更用のモーダル"""
        
        def __init__(self, cog, channel, config=None):
            super().__init__(title="固定メッセージ設定")
            self.cog = cog
            self.channel = channel
            self.config = config
            
            # 既存の設定値をデフォルトに設定
            default_content = config['message_content'] if config else ""
            default_time = str(config['time_interval']) if config else "300"
            default_count = str(config['message_interval']) if config else "10"
            default_trigger = config['trigger_type'] if config else "time"
            
            self.message_content = discord.ui.TextInput(
                label="固定メッセージの内容",
                style=discord.TextStyle.paragraph,
                default=default_content,
                max_length=2000,
                required=True
            )
            
            self.trigger_type = discord.ui.TextInput(
                label="トリガータイプ",
                style=discord.TextStyle.short,
                default=default_trigger,
                max_length=10,
                required=True
            )
            
            self.time_interval = discord.ui.TextInput(
                label="時間間隔（秒）",
                style=discord.TextStyle.short,
                default=default_time,
                max_length=10,
                required=True
            )
            
            self.message_interval = discord.ui.TextInput(
                label="メッセージ数間隔",
                style=discord.TextStyle.short,
                default=default_count,
                max_length=10,
                required=True
            )
            
            self.add_item(self.message_content)
            self.add_item(self.trigger_type)
            self.add_item(self.time_interval)
            self.add_item(self.message_interval)

        async def on_submit(self, interaction: discord.Interaction):
            try:
                time_int = int(self.time_interval.value)
                msg_int = int(self.message_interval.value)
                
                if time_int <= 0 or msg_int <= 0:
                    await interaction.response.send_message("時間間隔とメッセージ数間隔は1以上の数値を入力してください。", ephemeral=True)
                    return
                
            except ValueError:
                await interaction.response.send_message("時間間隔とメッセージ数間隔は数値で入力してください。", ephemeral=True)
                return
            
            async with db.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO sticky_messages 
                    (guild_id, channel_id, message_content, trigger_type, time_interval, message_interval, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, CURRENT_TIMESTAMP)
                    ON CONFLICT (guild_id, channel_id) 
                    DO UPDATE SET 
                        message_content = EXCLUDED.message_content,
                        trigger_type = EXCLUDED.trigger_type,
                        time_interval = EXCLUDED.time_interval,
                        message_interval = EXCLUDED.message_interval,
                        is_enabled = TRUE,
                        updated_at = CURRENT_TIMESTAMP
                """,
                    interaction.guild_id,
                    self.channel.id,
                    self.message_content.value,
                    self.trigger_type.value,
                    time_int,
                    msg_int
                )
            
            await interaction.response.send_message(
                f"設定を保存しました\n"
                f"トリガータイプ: {self.trigger_type.value}\n"
                f"時間間隔: {time_int}秒\n"
                f"メッセージ数間隔: {msg_int}メッセージ",
                ephemeral=True
            )

    @app_commands.command(name="sticky_panel", description="固定メッセージの設定パネルを表示します")
    @is_guild_app()
    @is_owner_app()
    @log_commands()
    async def sticky_panel(
        self,
        interaction: discord.Interaction,
        チャンネル: Optional[discord.TextChannel] = None
    ):
        target_channel = チャンネル or interaction.channel

        async with db.pool.acquire() as conn:
            config = await conn.fetchrow("""
                SELECT message_content, trigger_type, time_interval, message_interval, is_enabled, updated_at
                FROM sticky_messages 
                WHERE guild_id = $1 AND channel_id = $2
            """, interaction.guild_id, target_channel.id)

        # Components v2のLayoutViewを使用した設定パネル
        panel_view = self.StickyConfigPanel(self, target_channel, config)
        buttons_view = self.StickyConfigButtons(self, target_channel, config)
        
        await interaction.response.send_message(
            view=panel_view,
            ephemeral=True
        )
        await interaction.followup.send(
            view=buttons_view,
            ephemeral=True
        )

    @app_commands.command(name="sticky_set", description="固定メッセージを設定します")
    @app_commands.describe(
        メッセージ="固定メッセージの内容",
        トリガータイプ="投稿のトリガータイプ",
        時間間隔秒="時間間隔（秒）",
        メッセージ数間隔="メッセージ数間隔",
        チャンネル="対象チャンネル（省略時は現在のチャンネル）"
    )
    @app_commands.choices(トリガータイプ=[
        app_commands.Choice(name="⏰ 時間間隔", value="time"),
        app_commands.Choice(name="📊 メッセージ数", value="count")
    ])
    @is_guild_app()
    @is_owner_app()
    @log_commands()
    async def sticky_set(
        self,
        interaction: discord.Interaction,
        メッセージ: str,
        トリガータイプ: str,
        時間間隔秒: Optional[int] = 300,
        メッセージ数間隔: Optional[int] = 10,
        チャンネル: Optional[discord.TextChannel] = None
    ):
        target_channel = チャンネル or interaction.channel

        async with db.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO sticky_messages 
                (guild_id, channel_id, message_content, trigger_type, time_interval, message_interval, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, CURRENT_TIMESTAMP)
                ON CONFLICT (guild_id, channel_id) 
                DO UPDATE SET 
                    message_content = EXCLUDED.message_content,
                    trigger_type = EXCLUDED.trigger_type,
                    time_interval = EXCLUDED.time_interval,
                    message_interval = EXCLUDED.message_interval,
                    is_enabled = TRUE,
                    updated_at = CURRENT_TIMESTAMP
            """,
                interaction.guild_id,
                target_channel.id,
                メッセージ,
                トリガータイプ,
                時間間隔秒,
                メッセージ数間隔
            )

        await interaction.response.send_message(
            f"固定メッセージを設定しました\n"
            f"チャンネル: {target_channel.mention}\n"
            f"トリガータイプ: {トリガータイプ}\n"
            f"時間間隔: {時間間隔秒}秒\n"
            f"メッセージ数間隔: {メッセージ数間隔}メッセージ",
            ephemeral=True
        )

    @app_commands.command(name="sticky_disable", description="チャンネルの固定メッセージを無効にします")
    @is_guild_app()
    @is_owner_app()
    @log_commands()
    async def disable_sticky_message(
        self,
        interaction: discord.Interaction,
        チャンネル: Optional[discord.TextChannel] = None
    ):
        target_channel = チャンネル or interaction.channel

        async with db.pool.acquire() as conn:
            result = await conn.execute("""
                UPDATE sticky_messages 
                SET is_enabled = FALSE, updated_at = CURRENT_TIMESTAMP
                WHERE guild_id = $1 AND channel_id = $2
            """, interaction.guild_id, target_channel.id)

        if result == "UPDATE 0":
            await interaction.response.send_message(
                f"{target_channel.mention} に固定メッセージの設定がありません",
                ephemeral=True
            )
        else:
            # 古い固定メッセージを削除
            await self.delete_old_sticky_message(target_channel)
            
            await interaction.response.send_message(
                f"{target_channel.mention} の固定メッセージを無効にしました",
                ephemeral=True
            )

    @app_commands.command(name="sticky_status", description="チャンネルの固定メッセージ設定を確認します")
    @is_guild_app()
    @is_owner_app()
    @log_commands()
    async def sticky_status(
        self,
        interaction: discord.Interaction,
        チャンネル: Optional[discord.TextChannel] = None
    ):
        target_channel = チャンネル or interaction.channel

        async with db.pool.acquire() as conn:
            config = await conn.fetchrow("""
                SELECT message_content, trigger_type, time_interval, message_interval, is_enabled, updated_at
                FROM sticky_messages 
                WHERE guild_id = $1 AND channel_id = $2
            """, interaction.guild_id, target_channel.id)

        if not config:
            await interaction.response.send_message(
                f"{target_channel.mention} に固定メッセージの設定がありません",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"{target_channel.name} の固定メッセージ設定",
            color=discord.Color.green() if config['is_enabled'] else discord.Color.red()
        )

        embed.add_field(
            name="状態",
            value="有効" if config['is_enabled'] else "無効",
            inline=True
        )
        
        embed.add_field(
            name="トリガータイプ",
            value=config['trigger_type'],
            inline=True
        )
        
        embed.add_field(
            name="時間間隔",
            value=f"{config['time_interval']}秒",
            inline=True
        )
        
        embed.add_field(
            name="メッセージ数間隔",
            value=f"{config['message_interval']}メッセージ",
            inline=True
        )

        embed.add_field(
            name="メッセージ内容",
            value=f"```{config['message_content']}```",
            inline=False
        )

        # 現在の状況
        channel_id = target_channel.id
        current_count = self.message_counters.get(channel_id, 0)
        last_time = self.last_sticky_times.get(channel_id)
        
        if last_time:
            time_since = datetime.now() - last_time
            embed.add_field(
                name="現在の状況",
                value=f"前回投稿からの経過時間: {int(time_since.total_seconds())}秒\n"
                      f"前回投稿からのメッセージ数: {current_count}",
                inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    cog = ChannelStickyMessageCog(bot)
    await bot.add_cog(cog)
