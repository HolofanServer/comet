"""
データベース移行用の管理コマンド

JSONデータからPostgreSQLデータベースへの移行を行うコマンドを提供します。
"""
import discord
from discord.ext import commands
from discord import app_commands
import os
import json
from datetime import datetime
from dotenv import load_dotenv

from utils.logging import setup_logging
from utils.commands_help import is_owner
from utils.db_manager import db
from utils.database import get_db_pool

load_dotenv()
logger = setup_logging("D")

class DBMigrationCommands(commands.Cog):
    """データベース移行用の管理コマンド"""
    
    def __init__(self, bot):
        self.bot = bot
        self.migration_in_progress = False
    
    @commands.hybrid_command(name="migrate_db", description="JSONデータをPostgreSQLデータベースに移行します")
    @app_commands.default_permissions(administrator=True)
    @is_owner()
    async def migrate_db(self, ctx):
        """JSONデータをPostgreSQLデータベースに移行します"""
        if self.migration_in_progress:
            await ctx.send("⚠️ 移行処理が既に実行中です。完了するまでお待ちください。")
            return
        
        self.migration_in_progress = True
        
        try:
            await ctx.send("🔄 JSONデータからPostgreSQLへの移行を開始します...")
            
            # データベース接続の確認
            pool = await get_db_pool()
            if not pool:
                await ctx.send("❌ データベース接続の確立に失敗しました。環境変数を確認してください。")
                self.migration_in_progress = False
                return
                
            # データベースマネージャーの初期化
            if not db._initialized:
                await db.initialize()
                
            # バックアップの作成
            backup_dir = os.path.join(os.getcwd(), "data", "backup", f"json_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            os.makedirs(backup_dir, exist_ok=True)
            
            await ctx.send("📦 JSONデータのバックアップを作成中...")
            
            # 主要なJSONファイルをバックアップ
            json_files_to_backup = [
                ("data/analytics/oshi_roles/roles.json", "roles.json"),
                ("data/analytics/oshi_roles/users.json", "users.json"),
                ("data/analytics/oshi_roles/events.json", "events.json"),
                ("data/analytics/oshi_roles/summary.json", "summary.json"),
                ("data/config.json", "config.json"),
                ("data/role_emoji_mapping.json", "role_emoji_mapping.json"),
                ("config/bot.json", "bot.json"),
                ("config/auth.json", "auth.json"),
                ("config/members.json", "members.json")
            ]
            
            backup_count = 0
            for src_path, dst_name in json_files_to_backup:
                if os.path.exists(src_path):
                    with open(src_path, 'r', encoding='utf-8') as src_file:
                        try:
                            data = json.load(src_file)
                            
                            dst_path = os.path.join(backup_dir, dst_name)
                            with open(dst_path, 'w', encoding='utf-8') as dst_file:
                                json.dump(data, dst_file, ensure_ascii=False, indent=2)
                            backup_count += 1
                        except json.JSONDecodeError:
                            logger.warning(f"バックアップ中にJSONパースエラー: {src_path}")
            
            await ctx.send(f"✅ {backup_count}件のJSONファイルをバックアップしました: `{backup_dir}`")
            
            # 移行実行
            await ctx.send("🔄 データ移行を実行中...（これには時間がかかる場合があります）")
            success = await db.migrate_from_json()
            
            if not success:
                await ctx.send("❌ データ移行中にエラーが発生しました。ログを確認してください。")
                self.migration_in_progress = False
                return
            
            # 移行検証
            await ctx.send("🔍 移行結果を検証中...")
            verify_result = await self._verify_migration()
            
            if verify_result:
                await ctx.send("✅ データベース移行が正常に完了し、検証に合格しました！")
                await ctx.send("ℹ️ 今後はJSONファイルの代わりにデータベースからデータが読み込まれます。")
            else:
                await ctx.send("⚠️ データ移行は完了しましたが、検証で一部の不一致が見つかりました。ログを確認してください。")
            
        except Exception as e:
            logger.error(f"移行処理中にエラーが発生: {e}")
            await ctx.send(f"❌ 予期せぬエラーが発生しました: ```{str(e)}```")
        finally:
            self.migration_in_progress = False
    
    async def _verify_migration(self):
        """移行結果の検証を行います"""
        try:
            # データベース接続の確認
            if not db._initialized:
                await db.initialize()
                
            # テーブルごとのレコード数を確認
            async with db.pool.acquire() as conn:
                roles_count = await conn.fetchval("SELECT COUNT(*) FROM roles")
                users_count = await conn.fetchval("SELECT COUNT(*) FROM users")
                events_count = await conn.fetchval("SELECT COUNT(*) FROM role_events")
                user_roles_count = await conn.fetchval("SELECT COUNT(*) FROM user_roles WHERE is_active = true")
                guild_configs_count = await conn.fetchval("SELECT COUNT(*) FROM guild_configs")
                emoji_mappings_count = await conn.fetchval("SELECT COUNT(*) FROM role_emoji_mappings")
                bot_config_count = await conn.fetchval("SELECT COUNT(*) FROM bot_config")
                auth_config_count = await conn.fetchval("SELECT COUNT(*) FROM auth_config")
                members_count = await conn.fetchval("SELECT COUNT(*) FROM members")
            
            logger.info("=== 移行検証結果 ===")
            logger.info(f"ロール数: {roles_count}")
            logger.info(f"ユーザー数: {users_count}")
            logger.info(f"イベント数: {events_count}")
            logger.info(f"アクティブなロール割り当て: {user_roles_count}")
            logger.info(f"サーバー設定: {guild_configs_count}")
            logger.info(f"絵文字マッピング: {emoji_mappings_count}")
            logger.info(f"ボット設定: {bot_config_count}")
            logger.info(f"認証設定: {auth_config_count}")
            logger.info(f"メンバー情報: {members_count}")
            
            # 単純な検証: 各テーブルに少なくとも1つのレコードがあるか
            all_verified = True
            
            # 必須テーブルの検証
            if bot_config_count == 0:
                logger.warning("警告: bot_configテーブルにレコードがありません")
                all_verified = False
                
            if auth_config_count == 0:
                logger.warning("警告: auth_configテーブルにレコードがありません")
                all_verified = False
            
            # ロールベースの機能には、いくつかのレコードが必要
            if roles_count == 0 and os.path.exists("data/analytics/oshi_roles/roles.json"):
                logger.warning("警告: rolesテーブルにレコードがありません")
                all_verified = False
            
            return all_verified
            
        except Exception as e:
            logger.error(f"検証中にエラーが発生: {e}")
            return False
    
    @commands.hybrid_command(name="db_stats", description="データベースのテーブル統計を表示します")
    @app_commands.default_permissions(administrator=True)
    @is_owner()
    async def db_stats(self, ctx):
        """データベースのテーブル統計を表示します"""
        try:
            # データベース接続の確認
            if not db._initialized:
                await db.initialize()
            
            # テーブルごとのレコード数を取得
            async with db.pool.acquire() as conn:
                # 主要テーブルのカウント
                tables = [
                    "users", "roles", "user_roles", "role_events", "role_stats", 
                    "guild_configs", "custom_announcements", "role_emoji_mappings",
                    "bot_config", "auth_config", "members"
                ]
                
                results = {}
                for table in tables:
                    count = await conn.fetchval(f"SELECT COUNT(*) FROM {table}")
                    results[table] = count
            
            # 結果をEmbedで表示
            embed = discord.Embed(
                title="データベース統計",
                description="各テーブルのレコード数",
                color=discord.Color.blue()
            )
            
            for table, count in results.items():
                embed.add_field(name=table, value=str(count), inline=True)
            
            embed.set_footer(text=f"取得日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"データベース統計取得中にエラーが発生: {e}")
            await ctx.send(f"❌ エラーが発生しました: ```{str(e)}```")
    
    @commands.hybrid_command(name="test_db_connection", description="データベース接続をテストします")
    @app_commands.default_permissions(administrator=True)
    @is_owner()
    async def test_db_connection(self, ctx):
        """データベース接続をテストします"""
        try:
            await ctx.send("🔄 データベース接続をテスト中...")
            
            # DB環境変数情報を表示
            db_url = os.getenv('DATABASE_PUBLIC_URL', 'N/A')
            
            # パスワードは表示しない
            
            # 接続文字列がある場合は * で一部を隠す
            display_url = "N/A"
            if db_url != "N/A":
                # URLの構造を保持しながら重要な部分を隠す
                parts = db_url.split("://")
                if len(parts) > 1:
                    display_url = f"{parts[0]}://***:***@{parts[1].split('@')[-1]}"
                else:
                    display_url = "[設定あり - 表示を制限]"
            
            # 接続テスト
            pool = await get_db_pool()
            if pool:
                async with pool.acquire() as conn:
                    # 簡単なSQLを実行してみる
                    version = await conn.fetchval("SELECT version()")
                    db_size = await conn.fetchval("SELECT pg_database_size(current_database())/1024/1024 as size_mb")
                    
                    embed = discord.Embed(
                        title="✅ データベース接続成功",
                        description="PostgreSQLデータベースに正常に接続できました。",
                        color=discord.Color.green()
                    )
                    
                    # 接続タイプを表示
                    connection_type = "🔗 DATABASE_PUBLIC_URL" if db_url != "N/A" else "🔢 個別パラメータ"
                    embed.add_field(name="接続タイプ", value=connection_type, inline=False)
                    
                    if db_url != "N/A":
                        embed.add_field(name="DATABASE_PUBLIC_URL", value=display_url, inline=False)
                    else:
                        embed.add_field(name="接続文字列", value=db_url, inline=False)
                    
                    embed.add_field(name="PostgreSQLバージョン", value=version, inline=True)
                    embed.add_field(name="DB サイズ", value=f"{db_size:.2f} MB", inline=True)
                    
                    await ctx.send(embed=embed)
            else:
                await ctx.send("❌ データベース接続に失敗しました。環境変数を確認してください。")
        
        except Exception as e:
            logger.error(f"データベース接続テスト中にエラーが発生: {e}")
            await ctx.send(f"❌ エラーが発生しました: ```{str(e)}```")

async def setup(bot):
    await bot.add_cog(DBMigrationCommands(bot))
    logger.info("DBMigrationCommandsを読み込みました")
