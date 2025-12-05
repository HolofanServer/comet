from datetime import datetime, timedelta

import discord
from discord.ext import commands

from utils.db_manager import db
from utils.logging import setup_logging

logger = setup_logging()


class TimeoutView(discord.ui.View):
    """タイムアウトボタン付きのビュー"""

#     def __init__(self, target_user: discord.Member, timeout: float = 3600.0):
#         super().__init__(timeout=timeout)
#         self.target_user = target_user

#     @discord.ui.button(label="1週間タイムアウト", style=discord.ButtonStyle.red, emoji="⏰")
#     async def timeout_user(self, interaction: discord.Interaction, button: discord.ui.Button):
#         """タイムアウトボタンの処理"""
#         try:
#             # モデレーター権限をチェック
#             if not interaction.user.guild_permissions.moderate_members:
#                 await interaction.response.send_message(
#                     "❌ この操作を実行する権限がありません。",
#                     ephemeral=True
#                 )
#                 return

#             # ボットに必要な権限があるかチェック
#             bot_member = interaction.guild.get_member(interaction.client.user.id)
#             if not bot_member.guild_permissions.moderate_members:
#                 await interaction.response.send_message(
#                     "❌ ボットにタイムアウト権限がありません。",
#                     ephemeral=True
#                 )
#                 return

#             # 既にタイムアウト中かチェック
#             if self.target_user.is_timed_out():
#                 await interaction.response.send_message(
#                     f"⚠️ {self.target_user.mention} は既にタイムアウト中です。",
#                     ephemeral=True
#                 )
#                 return

#             # タイムアウト期間を計算（1週間）
#             timeout_until = discord.utils.utcnow() + timedelta(weeks=1)

#             # タイムアウトを適用
#             await self.target_user.timeout(
#                 timeout_until,
#                 reason=f"モデレーター {interaction.user} による手動タイムアウト"
#             )

#             await interaction.response.send_message(
#                 f"✅ {self.target_user.mention} に1週間のタイムアウトを適用しました。",
#                 ephemeral=True
#             )

#             # ボタンを無効化
#             button.disabled = True
#             button.label = "タイムアウト済み"
#             await interaction.edit_original_response(view=self)

#             logger.info(f"{interaction.user} が {self.target_user} に1週間のタイムアウトを適用しました")

#         except discord.Forbidden:
#             await interaction.response.send_message(
#                 f"❌ {self.target_user.mention} にタイムアウトを適用する権限がありません。",
#                 ephemeral=True
#             )
#         except Exception as e:
#             logger.error(f"タイムアウト適用エラー: {e}")
#             await interaction.response.send_message(
#                 "❌ タイムアウトの適用中にエラーが発生しました。",
#                 ephemeral=True
#             )


# class UserWarningSystem(commands.Cog):
#     """特定ユーザーの監視と警告システム"""

#     def __init__(self, bot: commands.Bot):
#         self.bot = bot
#         # キャッシュ用（DBから読み込み）
#         self.monitored_users: dict[int, set[int]] = {}  # guild_id -> user_ids
#         self.warning_channel_ids: dict[int, int] = {}  # guild_id -> channel_id
#         self.excluded_channels: dict[int, set[int]] = {}  # guild_id -> channel_ids

#     async def cog_load(self):
#         """Cog読み込み時の初期化"""
#         await self._create_tables()
#         await self._load_data_from_db()
#         logger.info("UserWarningSystem Cogが読み込まれました")

#     async def _create_tables(self):
#         """必要なテーブルを作成"""
#         try:
#             async with db.pool.acquire() as conn:
#                 # 監視対象ユーザーテーブル
#                 await conn.execute("""
#                     CREATE TABLE IF NOT EXISTS monitored_users (
#                         id SERIAL PRIMARY KEY,
#                         guild_id BIGINT NOT NULL,
#                         user_id BIGINT NOT NULL,
#                         added_by BIGINT NOT NULL,
#                         added_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
#                         reason TEXT,
#                         UNIQUE(guild_id, user_id)
#                     )
#                 """)

#                 # 除外チャンネルテーブル
#                 await conn.execute("""
#                     CREATE TABLE IF NOT EXISTS excluded_channels (
#                         id SERIAL PRIMARY KEY,
#                         guild_id BIGINT NOT NULL,
#                         channel_id BIGINT NOT NULL,
#                         added_by BIGINT NOT NULL,
#                         added_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
#                         reason TEXT,
#                         UNIQUE(guild_id, channel_id)
#                     )
#                 """)

#                 # 警告システム設定テーブル
#                 await conn.execute("""
#                     CREATE TABLE IF NOT EXISTS warning_system_config (
#                         id SERIAL PRIMARY KEY,
#                         guild_id BIGINT NOT NULL UNIQUE,
#                         warning_channel_id BIGINT,
#                         is_enabled BOOLEAN DEFAULT TRUE,
#                         updated_by BIGINT NOT NULL,
#                         updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
#                     )
#                 """)

#                 # 警告ログテーブル
#                 await conn.execute("""
#                     CREATE TABLE IF NOT EXISTS warning_logs (
#                         id SERIAL PRIMARY KEY,
#                         guild_id BIGINT NOT NULL,
#                         user_id BIGINT NOT NULL,
#                         channel_id BIGINT NOT NULL,
#                         message_content TEXT,
#                         warning_channel_id BIGINT,
#                         moderator_id BIGINT,
#                         timeout_applied BOOLEAN DEFAULT FALSE,
#                         timeout_applied_by BIGINT,
#                         timeout_applied_at TIMESTAMP WITH TIME ZONE,
#                         created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
#                     )
#                 """)

#             logger.info("警告システムのテーブル作成完了")
#         except Exception as e:
#             logger.error(f"テーブル作成エラー: {e}")

#     async def _load_data_from_db(self):
#         """データベースからデータを読み込み"""
#         try:
#             async with db.pool.acquire() as conn:
#                 # 監視対象ユーザーを読み込み
#                 monitored_data = await conn.fetch("SELECT guild_id, user_id FROM monitored_users")
#                 for row in monitored_data:
#                     guild_id = row['guild_id']
#                     if guild_id not in self.monitored_users:
#                         self.monitored_users[guild_id] = set()
#                     self.monitored_users[guild_id].add(row['user_id'])

#                 # 除外チャンネルを読み込み
#                 excluded_data = await conn.fetch("SELECT guild_id, channel_id FROM excluded_channels")
#                 for row in excluded_data:
#                     guild_id = row['guild_id']
#                     if guild_id not in self.excluded_channels:
#                         self.excluded_channels[guild_id] = set()
#                     self.excluded_channels[guild_id].add(row['channel_id'])

#                 # 警告チャンネル設定を読み込み
#                 config_data = await conn.fetch("SELECT guild_id, warning_channel_id FROM warning_system_config WHERE is_enabled = TRUE")
#                 for row in config_data:
#                     if row['warning_channel_id']:
#                         self.warning_channel_ids[row['guild_id']] = row['warning_channel_id']

#             logger.info(f"警告システムデータ読み込み完了: 監視ユーザー {sum(len(users) for users in self.monitored_users.values())}人, 除外チャンネル {sum(len(channels) for channels in self.excluded_channels.values())}個")
#         except Exception as e:
#             logger.error(f"データ読み込みエラー: {e}")

#     @commands.Cog.listener()
#     async def on_message(self, message: discord.Message):
#         """メッセージ監視イベント"""
#         # ボット自身のメッセージは無視
#         if message.author.bot:
#             return

#         guild_id = message.guild.id if message.guild else None
#         if not guild_id:
#             return

#         # 監視対象ユーザーかチェック
#         guild_monitored = self.monitored_users.get(guild_id, set())
#         logger.info(f"監視対象ユーザーチェック: ユーザーID {message.author.id}, 監視対象: {guild_monitored}")

#         if message.author.id not in guild_monitored:
#             return

#         logger.info(f"監視対象ユーザー {message.author} からのメッセージを検出")

#         # 警告チャンネルが設定されていない場合は無視
#         warning_channel_id = self.warning_channel_ids.get(guild_id)
#         logger.info(f"警告チャンネルID: {warning_channel_id}")

#         if not warning_channel_id:
#             logger.warning(f"警告チャンネルが設定されていません (Guild: {guild_id})")
#             return

#         # 除外チャンネルかチェック
#         guild_excluded = self.excluded_channels.get(guild_id, set())
#         if message.channel.id in guild_excluded:
#             logger.info(f"除外チャンネル {message.channel.name} のメッセージのため削除をスキップ")
#             await self._send_warning_in_exclude_channel(message, warning_channel_id)
#             return

#         logger.info(f"通常の警告処理を開始: {message.author} in {message.channel.name}")

#         # 警告を送信
#         await self._send_warning(message, warning_channel_id)

#         # 元のメッセージを自動削除
#         await self._delete_original_message(message)

#         # ログを記録
#         await self._log_warning(message, warning_channel_id)

#     async def _send_warning(self, message: discord.Message, warning_channel_id: int):
#         """警告メッセージを送信"""
#         try:
#             warning_channel = self.bot.get_channel(warning_channel_id)
#             if not warning_channel:
#                 logger.error(f"警告チャンネル（ID: {warning_channel_id}）が見つかりません")
#                 return

#             # 警告用のEmbed作成
#             embed = discord.Embed(
#                 title="⚠️ 監視対象ユーザーからのメッセージ",
#                 color=discord.Color.red(),
#                 timestamp=datetime.now()
#             )

#             embed.add_field(
#                 name="ユーザー",
#                 value=f"{message.author.mention} ({message.author})",
#                 inline=False
#             )

#             embed.add_field(
#                 name="チャンネル",
#                 value=f"{message.channel.mention} ({message.channel.name})",
#                 inline=False
#             )

#             # メッセージ内容（長すぎる場合は切り詰め）
#             content = message.content[:1000] + "..." if len(message.content) > 1000 else message.content
#             embed.add_field(
#                 name="メッセージ内容",
#                 value=content or "*メッセージ内容なし（添付ファイルのみ）*",
#                 inline=False
#             )

#             # 添付ファイルがある場合
#             if message.attachments:
#                 attachment_list = "\n".join([f"• {att.filename}" for att in message.attachments])
#                 embed.add_field(
#                     name="添付ファイル",
#                     value=attachment_list,
#                     inline=False
#                 )

#             embed.add_field(
#                 name="メッセージリンク",
#                 value=f"[メッセージに移動]({message.jump_url})",
#                 inline=False
#             )

#             embed.set_footer(text=f"ユーザーID: {message.author.id}")

#             # タイムアウトボタン付きビューを作成
#             view = TimeoutView(message.author, timeout=3600)  # 1時間でタイムアウト

#             # 警告メッセージを送信
#             await warning_channel.send(embed=embed, view=view)

#             logger.info(f"監視対象ユーザー {message.author} からのメッセージに対して警告を送信しました")

#         except Exception as e:
#             logger.error(f"警告メッセージ送信エラー: {e}")

#     async def _send_warning_in_exclude_channel(self, message: discord.Message, warning_channel_id: int):
#         """除外チャンネル用の警告メッセージを送信"""
#         try:
#             warning_channel = self.bot.get_channel(warning_channel_id)
#             if not warning_channel:
#                 logger.error(f"警告チャンネル（ID: {warning_channel_id}）が見つかりません")
#                 return

#             # 警告用のEmbed作成
#             embed = discord.Embed(
#                 title="⚠️ 除外チャンネル内で監視対象ユーザーからのメッセージ",
#                 color=discord.Color.red(),
#                 timestamp=datetime.now()
#             )

#             embed.add_field(
#                 name="ユーザー",
#                 value=f"{message.author.mention} ({message.author})",
#                 inline=False
#             )

#             embed.add_field(
#                 name="チャンネル",
#                 value=f"{message.channel.mention} ({message.channel.name})",
#                 inline=False
#             )

#             # メッセージ内容（長すぎる場合は切り詰め）
#             content = message.content[:1000] + "..." if len(message.content) > 1000 else message.content
#             embed.add_field(
#                 name="メッセージ内容",
#                 value=content or "*メッセージ内容なし（添付ファイルのみ）*",
#                 inline=False
#             )

#             # 添付ファイルがある場合
#             if message.attachments:
#                 attachment_list = "\n".join([f"• {att.filename}" for att in message.attachments])
#                 embed.add_field(
#                     name="添付ファイル",
#                     value=attachment_list,
#                     inline=False
#                 )

#             embed.add_field(
#                 name="メッセージリンク",
#                 value=f"[メッセージに移動]({message.jump_url})",
#                 inline=False
#             )

#             embed.set_footer(text=f"ユーザーID: {message.author.id}")

#             # タイムアウトボタン付きビューを作成
#             view = TimeoutView(message.author, timeout=3600)  # 1時間でタイムアウト

#             # 警告メッセージを送信
#             await warning_channel.send(embed=embed, view=view)

#             logger.info(f"監視対象ユーザー {message.author} からのメッセージに対して警告を送信しました")

#         except Exception as e:
#             logger.error(f"警告メッセージ送信エラー: {e}")

#     async def _delete_original_message(self, message: discord.Message):
#         """元のメッセージを削除"""
#         try:
#             logger.info(f"メッセージ削除を試行: {message.author} のメッセージ (ID: {message.id})")

#             # ボットの権限をチェック
#             bot_member = message.guild.get_member(self.bot.user.id)
#             if not bot_member:
#                 logger.error("ボットのメンバー情報を取得できません")
#                 return

#             channel_perms = message.channel.permissions_for(bot_member)
#             logger.info(f"ボットの権限 - manage_messages: {channel_perms.manage_messages}, read_messages: {channel_perms.read_messages}")

#             if not channel_perms.manage_messages:
#                 logger.error(f"チャンネル {message.channel.name} でメッセージ管理権限がありません")
#                 return

#             await message.delete()
#             logger.info(f"監視対象ユーザー {message.author} のメッセージを削除しました")

#         except discord.NotFound:
#             logger.warning(f"削除対象のメッセージが見つかりません (ID: {message.id})")
#         except discord.Forbidden:
#             logger.error(f"メッセージ削除権限がありません - チャンネル: {message.channel.name}")
#         except discord.HTTPException as e:
#             logger.error(f"Discord API エラー: {e}")
#         except Exception as e:
#             logger.error(f"メッセージ削除エラー: {e}")

#     async def _log_warning(self, message: discord.Message, warning_channel_id: int):
#         """警告をデータベースに記録"""
#         try:
#             async with db.pool.acquire() as conn:
#                 await conn.execute("""
#                     INSERT INTO warning_logs
#                     (guild_id, user_id, channel_id, message_content, warning_channel_id, created_at)
#                     VALUES ($1, $2, $3, $4, $5, $6)
#                 """, message.guild.id, message.author.id, message.channel.id,
#                     message.content[:1000], warning_channel_id, datetime.now())
#         except Exception as e:
#             logger.error(f"警告ログ記録エラー: {e}")


#     @commands.hybrid_group(name="warning", aliases=["warn"])
#     @commands.has_permissions(moderate_members=True)
#     async def warning_group(self, ctx: commands.Context):
#         """警告システム管理コマンドグループ"""
#         if ctx.invoked_subcommand is None:
#             embed = discord.Embed(
#                 title="警告システム管理",
#                 description="利用可能なコマンド:",
#                 color=discord.Color.blue()
#             )
#             embed.add_field(
#                 name="`warning add <ユーザー> [理由]`",
#                 value="監視対象ユーザーを追加（理由は任意）",
#                 inline=False
#             )
#             embed.add_field(
#                 name="`warning remove <ユーザー>`",
#                 value="監視対象ユーザーを削除",
#                 inline=False
#             )
#             embed.add_field(
#                 name="`warning list`",
#                 value="監視対象ユーザー一覧を表示",
#                 inline=False
#             )
#             embed.add_field(
#                 name="`warning channel <チャンネル>`",
#                 value="警告送信先チャンネルを設定",
#                 inline=False
#             )
#             embed.add_field(
#                 name="`warning exclude <チャンネル> [理由]`",
#                 value="除外チャンネルを追加（理由は任意）",
#                 inline=False
#             )
#             embed.add_field(
#                 name="`warning unexclude <チャンネル>`",
#                 value="除外チャンネルから削除",
#                 inline=False
#             )
#             embed.add_field(
#                 name="`warning status [ユーザー]`",
#                 value="設定状況またはユーザー詳細を表示",
#                 inline=False
#             )
#             embed.add_field(
#                 name="`warning setup <警告チャンネル> <監視ユーザー> <理由> [除外チャンネル]`",
#                 value="一括設定（除外チャンネルは任意）",
#                 inline=False
#             )
#             await ctx.send(embed=embed)

#     @warning_group.command(name="setup")
#     @commands.has_permissions(moderate_members=True)
#     async def setup_warning_system(self, ctx: commands.Context, warning_channel: discord.TextChannel, user: discord.User, reason: str, exclude_channel: discord.TextChannel = None):
#         """一括設定コマンド: 警告チャンネル、監視ユーザー、理由、除外チャンネル"""
#         try:
#             guild_id = ctx.guild.id

#             # 1. 警告チャンネル設定
#             async with db.pool.acquire() as conn:
#                 await conn.execute("""
#                     INSERT INTO warning_system_config (guild_id, warning_channel_id, updated_by)
#                     VALUES ($1, $2, $3)
#                     ON CONFLICT (guild_id)
#                     DO UPDATE SET warning_channel_id = $2, updated_by = $3, updated_at = CURRENT_TIMESTAMP
#                 """, guild_id, warning_channel.id, ctx.author.id)

#             self.warning_channel_ids[guild_id] = warning_channel.id

#             # 2. 監視対象ユーザー追加
#             async with db.pool.acquire() as conn:
#                 await conn.execute("""
#                     INSERT INTO monitored_users (guild_id, user_id, added_by, reason)
#                     VALUES ($1, $2, $3, $4)
#                     ON CONFLICT (guild_id, user_id) DO UPDATE SET reason = $4, added_by = $3
#                 """, guild_id, user.id, ctx.author.id, reason)

#             if guild_id not in self.monitored_users:
#                 self.monitored_users[guild_id] = set()
#             self.monitored_users[guild_id].add(user.id)

#             # 3. 除外チャンネル追加（指定されている場合）
#             exclude_text = ""
#             if exclude_channel:
#                 async with db.pool.acquire() as conn:
#                     await conn.execute("""
#                         INSERT INTO excluded_channels (guild_id, channel_id, added_by, reason)
#                         VALUES ($1, $2, $3, $4)
#                         ON CONFLICT (guild_id, channel_id) DO NOTHING
#                     """, guild_id, exclude_channel.id, ctx.author.id, "一括設定で追加")

#                 if guild_id not in self.excluded_channels:
#                     self.excluded_channels[guild_id] = set()
#                 self.excluded_channels[guild_id].add(exclude_channel.id)
#                 exclude_text = f"\n📝 除外チャンネル: {exclude_channel.mention}"

#             # 成功メッセージ
#             embed = discord.Embed(
#                 title="✅ 警告システム一括設定完了",
#                 color=discord.Color.green()
#             )
#             embed.add_field(
#                 name="設定内容",
#                 value=f"🚨 警告チャンネル: {warning_channel.mention}\n👤 監視対象ユーザー: {user.mention}\n📋 理由: {reason}{exclude_text}",
#                 inline=False
#             )

#             await ctx.send(embed=embed)
#             logger.info(f"警告システム一括設定完了 - Guild: {guild_id}, User: {user.id}, Channel: {warning_channel.id}")

#         except Exception as e:
#             await ctx.send(f"❌ エラーが発生しました: {e}")
#             logger.error(f"一括設定エラー: {e}")

#     @warning_group.command(name="add")
#     @commands.has_permissions(moderate_members=True)
#     async def add_monitored_user(self, ctx: commands.Context, user: discord.User, *, reason: str):
#         """監視対象ユーザーを追加"""
#         try:
#             guild_id = ctx.guild.id
#             guild_monitored = self.monitored_users.get(guild_id, set())

#             if user.id in guild_monitored:
#                 await ctx.send(f"❌ {user.mention} は既に監視対象に登録されています。")
#                 return

#             # データベースに追加
#             async with db.pool.acquire() as conn:
#                 await conn.execute("""
#                     INSERT INTO monitored_users (guild_id, user_id, added_by, reason)
#                     VALUES ($1, $2, $3, $4)
#                     ON CONFLICT (guild_id, user_id) DO NOTHING
#                 """, guild_id, user.id, ctx.author.id, reason)

#             # キャッシュを更新
#             if guild_id not in self.monitored_users:
#                 self.monitored_users[guild_id] = set()
#             self.monitored_users[guild_id].add(user.id)

#             await ctx.send(f"✅ {user.mention} を監視対象に追加しました (理由: {reason})。")
#             logger.info(f"監視対象ユーザーを追加: {user} (ID: {user.id}) in guild {guild_id}")

#         except Exception as e:
#             await ctx.send(f"❌ エラーが発生しました: {e}")
#             logger.error(f"監視対象ユーザー追加エラー: {e}")

#     @warning_group.command(name="remove")
#     @commands.has_permissions(moderate_members=True)
#     async def remove_monitored_user(self, ctx: commands.Context, user: discord.User):
#         """監視対象ユーザーを削除"""
#         try:
#             if user.id not in self.monitored_users:
#                 await ctx.send("❌ 指定されたユーザーは監視対象に登録されていません。")
#                 return

#             self.monitored_users.remove(user.id)

#             try:
#                 await ctx.send(f"✅ {user.mention} を監視対象から削除しました。")
#             except discord.NotFound:
#                 await ctx.send(f"✅ ユーザーID `{user.id}` を監視対象から削除しました。")

#             logger.info(f"監視対象ユーザーを削除: ID {user.id}")

#         except Exception as e:
#             await ctx.send(f"❌ エラーが発生しました: {e}")
#             logger.error(f"監視対象ユーザー削除エラー: {e}")

#     @warning_group.command(name="list")
#     @commands.has_permissions(moderate_members=True)
#     async def list_monitored_users(self, ctx: commands.Context):
#         """監視対象ユーザー一覧を表示"""
#         if not self.monitored_users:
#             await ctx.send("📝 現在監視対象のユーザーはいません。")
#             return

#         embed = discord.Embed(
#             title="監視対象ユーザー一覧",
#             color=discord.Color.blue()
#         )

#         user_list = []
#         for user_id in self.monitored_users:
#             try:
#                 user = await self.bot.fetch_user(user_id)
#                 user_list.append(f"• {user.mention} ({user}) - ID: `{user_id}`")
#             except discord.NotFound:
#                 user_list.append(f"• 不明なユーザー - ID: `{user_id}`")

#         embed.description = "\n".join(user_list)
#         await ctx.send(embed=embed)

#     @warning_group.command(name="channel")
#     @commands.has_permissions(moderate_members=True)
#     async def set_warning_channel(self, ctx: commands.Context, channel: discord.TextChannel):
#         """警告送信先チャンネルを設定"""
#         try:
#             guild_id = ctx.guild.id

#             # データベースに保存
#             async with db.pool.acquire() as conn:
#                 await conn.execute("""
#                     INSERT INTO warning_system_config (guild_id, warning_channel_id, updated_by)
#                     VALUES ($1, $2, $3)
#                     ON CONFLICT (guild_id)
#                     DO UPDATE SET warning_channel_id = $2, updated_by = $3, updated_at = CURRENT_TIMESTAMP
#                 """, guild_id, channel.id, ctx.author.id)

#             # キャッシュを更新
#             self.warning_channel_ids[guild_id] = channel.id

#             await ctx.send(f"✅ 警告送信先チャンネルを {channel.mention} に設定しました。")
#             logger.info(f"警告送信先チャンネルを設定: {channel.name} (ID: {channel.id}) in guild {guild_id}")

#         except Exception as e:
#             await ctx.send(f"❌ エラーが発生しました: {e}")
#             logger.error(f"警告チャンネル設定エラー: {e}")

#     @warning_group.command(name="exclude")
#     @commands.has_permissions(moderate_members=True)
#     async def add_excluded_channel(self, ctx: commands.Context, channel: discord.TextChannel, *, reason: str = None):
#         """除外チャンネルを追加（メッセージを削除しない）"""
#         try:
#             guild_id = ctx.guild.id
#             guild_excluded = self.excluded_channels.get(guild_id, set())

#             if channel.id in guild_excluded:
#                 await ctx.send(f"❌ {channel.mention} は既に除外チャンネルに登録されています。")
#                 return

#             # データベースに追加
#             async with db.pool.acquire() as conn:
#                 await conn.execute("""
#                     INSERT INTO excluded_channels (guild_id, channel_id, added_by, reason)
#                     VALUES ($1, $2, $3, $4)
#                     ON CONFLICT (guild_id, channel_id) DO NOTHING
#                 """, guild_id, channel.id, ctx.author.id, reason)

#             # キャッシュを更新
#             if guild_id not in self.excluded_channels:
#                 self.excluded_channels[guild_id] = set()
#             self.excluded_channels[guild_id].add(channel.id)

#             reason_text = f" (理由: {reason})" if reason else ""
#             await ctx.send(f"✅ {channel.mention} を除外チャンネルに追加しました{reason_text}。このチャンネルでのメッセージは削除されません。")
#             logger.info(f"除外チャンネルを追加: {channel.name} (ID: {channel.id}) in guild {guild_id}")

#         except Exception as e:
#             await ctx.send(f"❌ エラーが発生しました: {e}")
#             logger.error(f"除外チャンネル追加エラー: {e}")

#     @warning_group.command(name="unexclude")
#     @commands.has_permissions(moderate_members=True)
#     async def remove_excluded_channel(self, ctx: commands.Context, channel: discord.TextChannel):
#         """除外チャンネルから削除"""
#         try:
#             guild_id = ctx.guild.id
#             guild_excluded = self.excluded_channels.get(guild_id, set())

#             if channel.id not in guild_excluded:
#                 await ctx.send("❌ 指定されたチャンネルは除外チャンネルに登録されていません。")
#                 return

#             # データベースから削除
#             async with db.pool.acquire() as conn:
#                 await conn.execute("""
#                     DELETE FROM excluded_channels
#                     WHERE guild_id = $1 AND channel_id = $2
#                 """, guild_id, channel.id)

#             # キャッシュを更新
#             self.excluded_channels[guild_id].discard(channel.id)

#             await ctx.send(f"✅ {channel.mention} を除外チャンネルから削除しました。")
#             logger.info(f"除外チャンネルを削除: ID {channel.id} in guild {guild_id}")

#         except Exception as e:
#             await ctx.send(f"❌ エラーが発生しました: {e}")
#             logger.error(f"除外チャンネル削除エラー: {e}")

#     @warning_group.command(name="status")
#     @commands.has_permissions(moderate_members=True)
#     async def show_status(self, ctx: commands.Context, user: discord.User = None):
#         """設定状況またはユーザー詳細を表示"""
#         guild_id = ctx.guild.id

#         if user:
#             # 特定ユーザーの詳細表示
#             await self._show_user_status(ctx, user, guild_id)
#         else:
#             # 全体の設定状況表示
#             await self._show_general_status(ctx, guild_id)

#     async def _show_general_status(self, ctx: commands.Context, guild_id: int):
#         """全体の設定状況を表示"""
#         embed = discord.Embed(
#             title="警告システム設定状況",
#             color=discord.Color.green()
#         )

#         # 監視対象ユーザー数
#         guild_monitored = self.monitored_users.get(guild_id, set())
#         embed.add_field(
#             name="監視対象ユーザー数",
#             value=f"{len(guild_monitored)}人",
#             inline=True
#         )

#         # 警告送信先チャンネル
#         warning_channel_id = self.warning_channel_ids.get(guild_id)
#         if warning_channel_id:
#             channel = self.bot.get_channel(warning_channel_id)
#             channel_info = channel.mention if channel else f"ID: {warning_channel_id} (チャンネルが見つかりません)"
#         else:
#             channel_info = "未設定"

#         embed.add_field(
#             name="警告送信先チャンネル",
#             value=channel_info,
#             inline=True
#         )

#         # 除外チャンネル数
#         guild_excluded = self.excluded_channels.get(guild_id, set())
#         embed.add_field(
#             name="除外チャンネル数",
#             value=f"{len(guild_excluded)}個",
#             inline=True
#         )

#         await ctx.send(embed=embed)

#     async def _show_user_status(self, ctx: commands.Context, user: discord.User, guild_id: int):
#         """特定ユーザーの詳細を表示"""
#         # ユーザー情報を取得
#         async with db.pool.acquire() as conn:
#             user_data = await conn.fetchrow("""
#                 SELECT added_by, added_at, reason
#                 FROM monitored_users
#                 WHERE guild_id = $1 AND user_id = $2
#             """, guild_id, user.id)

#         if not user_data:
#             await ctx.send(f"❌ {user.mention} は監視対象に登録されていません。")
#             return

#         # 警告ログを取得
#         async with db.pool.acquire() as conn:
#             warning_logs = await conn.fetch("""
#                 SELECT created_at, channel_id, timeout_applied, timeout_applied_by
#                 FROM warning_logs
#                 WHERE guild_id = $1 AND user_id = $2
#                 ORDER BY created_at DESC
#                 LIMIT 10
#             """, guild_id, user.id)

#         embed = discord.Embed(
#             title=f"ユーザー詳細: {user.display_name}",
#             color=discord.Color.orange()
#         )
#         # 基本情報
#         try:
#             added_by = await self.bot.fetch_user(user_data['added_by'])
#             added_by_name = added_by.display_name
#         except Exception:
#             added_by_name = f"ID: {user_data['added_by']}"

#         embed.add_field(
#             name="登録情報",
#             value=f"追加者: {added_by_name}\n追加日: {user_data['added_at'].strftime('%Y-%m-%d %H:%M')}\n理由: {user_data['reason'] or 'なし'}",
#             inline=False
#         )

#         if warning_logs:
#             log_text = []
#             for log in warning_logs[:5]:
#                 channel = self.bot.get_channel(log['channel_id'])
#                 channel_name = channel.name if channel else f"ID:{log['channel_id']}"
#                 timeout_text = " (タイムアウト適用)" if log['timeout_applied'] else ""
#                 log_text.append(f"• {log['created_at'].strftime('%m/%d %H:%M')} - #{channel_name}{timeout_text}")

#             embed.add_field(
#                 name=f"警告履歴 (最新5件 / 全{len(warning_logs)}件)",
#                 value="\n".join(log_text),
#                 inline=False
#             )
#         else:
#             embed.add_field(
#                 name="警告履歴",
#                 value="なし",
#                 inline=False
#             )

#         await ctx.send(embed=embed)

#     async def _get_monitored_users_autocomplete(self, interaction: discord.Interaction, current: str):
#         """監視対象ユーザーのオートコンプリート"""
#         guild_id = interaction.guild.id
#         guild_monitored = self.monitored_users.get(guild_id, set())

#         choices = []
#         for user_id in guild_monitored:
#             try:
#                 user = await self.bot.fetch_user(user_id)
#                 if current.lower() in user.display_name.lower() or current in str(user_id):
#                     choices.append(discord.app_commands.Choice(
#                         name=f"{user.display_name} ({user_id})",
#                         value=str(user_id)
#                     ))
#                 if len(choices) >= 25:
#                     break
#             except Exception:
#                 continue

#         return choices


async def setup(bot: commands.Bot):
    """Cog setup関数"""
    await bot.add_cog(UserWarningSystem(bot))
