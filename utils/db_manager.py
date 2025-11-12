"""
データベース管理ユーティリティ

PostgreSQLデータベースとの接続および操作を管理するためのモジュールです。
JSONデータからの移行機能や、推しロールパネル機能のためのデータ操作APIを提供します。
"""
import datetime
import json
import logging
import os
import re
import uuid
from typing import Any

import asyncpg

from config.setting import get_settings

settings = get_settings()

logger = logging.getLogger('db_manager')

class DBManager:
    """PostgreSQLデータベース管理クラス"""

    def __init__(self):
        self.pool = None
        self.config = {
            'host': os.environ.get('DB_HOST', 'localhost'),
            'port': int(os.environ.get('DB_PORT', 5432)),
            'user': os.environ.get('DB_USER', 'postgres'),
            'password': os.environ.get('DB_PASSWORD', ''),
            'database': os.environ.get('DB_NAME', 'hfs_bot')
        }
        self._initialized = False

    async def initialize(self):
        """データベース接続プールを初期化します"""
        if self._initialized:
            return

        try:
            db_url = os.environ.get('DATABASE_PUBLIC_URL')
            if not db_url:
                logger.error("DATABASE_PUBLIC_URL環境変数が設定されていません")
                raise ValueError("DATABASE_PUBLIC_URL環境変数が設定されていません")

            self.pool = await asyncpg.create_pool(db_url)
            await self._setup_tables()
            self._initialized = True
            logger.info("DATABASE_PUBLIC_URLを使用してデータベース接続プールを初期化しました")
        except Exception as e:
            logger.error(f"データベース接続に失敗しました: {e}")
            raise

    async def close(self):
        """データベース接続を閉じます"""
        if self.pool:
            await self.pool.close()
            self._initialized = False
            logger.info("データベース接続プールを閉じました")

    async def _drop_all_tables(self):
        """すべてのテーブルとシーケンスを削除します（スキーマ変更時に使用）"""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("DROP TABLE IF EXISTS role_events CASCADE")
                await conn.execute("DROP TABLE IF EXISTS user_roles CASCADE")
                await conn.execute("DROP TABLE IF EXISTS role_stats CASCADE")
                await conn.execute("DROP TABLE IF EXISTS role_emoji_mappings CASCADE")
                await conn.execute("DROP TABLE IF EXISTS fan_roles CASCADE")
                await conn.execute("DROP TABLE IF EXISTS custom_announcements CASCADE")
                await conn.execute("DROP TABLE IF EXISTS guild_configs CASCADE")
                await conn.execute("DROP TABLE IF EXISTS server_stats CASCADE")
                await conn.execute("DROP TABLE IF EXISTS roles CASCADE")
                await conn.execute("DROP TABLE IF EXISTS users CASCADE")
                await conn.execute("DROP TABLE IF EXISTS bot_configs CASCADE")
                await conn.execute("DROP TABLE IF EXISTS staff_info CASCADE")

                sequences = [
                    "role_events_id_seq",
                    "user_roles_id_seq",
                    "custom_announcements_id_seq",
                    "staff_info_id_seq",
                    "server_stats_id_seq",
                    "role_emoji_mappings_id_seq"
                ]

                for seq in sequences:
                    try:
                        await conn.execute(f"DROP SEQUENCE IF EXISTS {seq} CASCADE")
                    except Exception as e:
                        logger.warning(f"シーケンス{seq}の削除中にエラー: {e}")

                logger.info("すべてのテーブルとシーケンスを削除しました")
                return True
        except Exception as e:
            logger.error(f"テーブル削除中にエラー: {e}")
            return False

    async def _setup_tables(self):
        """
        必要なテーブルをセットアップします（毎回全テーブルをCREATE TABLE IF NOT EXISTSで流す）
        """
        tables = [
            '''
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username VARCHAR(255),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
            ''',
            '''
            CREATE TABLE IF NOT EXISTS auth_config (
                id UUID PRIMARY KEY,
                label VARCHAR(100) NOT NULL,
                auth_code VARCHAR(100) NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
            ''',
            '''
            CREATE TABLE IF NOT EXISTS members (
                id BIGINT PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                role VARCHAR(100) NOT NULL,
                avatar TEXT,
                message TEXT,
                joined_at DATE,
                joined_at_jp VARCHAR(50),
                role_color VARCHAR(10),
                socials JSONB DEFAULT '{}'::jsonb,
                type VARCHAR(50) NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
            ''',
            '''
            CREATE TABLE IF NOT EXISTS server_stats (
                id SERIAL PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                total_ch_id BIGINT,
                members_ch_id BIGINT,
                bot_ch_id BIGINT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                UNIQUE(guild_id)
            )
            ''',
            '''
            CREATE TABLE IF NOT EXISTS bump_notice_settings (
                guild_id BIGINT PRIMARY KEY,
                channel_id BIGINT,
                bot_id BIGINT,
                role_id BIGINT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
            ''',
            '''
            CREATE TABLE IF NOT EXISTS member_emojis (
                emoji_id BIGINT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                url TEXT NOT NULL,
                animated BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
            ''',
            '''
            CREATE TABLE IF NOT EXISTS role_emoji_mappings (
                role_id BIGINT PRIMARY KEY,
                emoji_id BIGINT,
                emoji_name TEXT,
                animated BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
            ''',
            '''
            CREATE TABLE IF NOT EXISTS note_posts (
                id SERIAL PRIMARY KEY,
                post_id TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                link TEXT NOT NULL,
                author TEXT,
                published_at TIMESTAMP WITH TIME ZONE,
                summary TEXT,
                thumbnail_url TEXT,
                creator_icon TEXT,
                notified_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
            '''
        ]
        async with self.pool.acquire() as conn:
            for table_query in tables:
                await conn.execute(table_query)
            logger.info("必要なテーブルを確認・作成しました")

    # --- JSON移行関連のメソッド ---

    async def _clear_existing_tables(self):
        """既存のテーブルデータをクリアします"""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("DELETE FROM role_events")
                await conn.execute("DELETE FROM user_roles")
                await conn.execute("DELETE FROM role_stats")
                await conn.execute("DELETE FROM role_emoji_mappings")
                await conn.execute("DELETE FROM fan_roles")
                await conn.execute("DELETE FROM roles")
                await conn.execute("DELETE FROM users")
                logger.info("既存テーブルのデータをクリアしました")
        except Exception as e:
            logger.error(f"テーブルデータのクリア中にエラー: {e}")
            raise

    async def migrate_from_json(self):
        """JSONデータからデータベースへ移行します"""
        base_dir = os.path.join(os.getcwd(), "data", "analytics", "oshi_roles")
        data_dir = os.path.join(os.getcwd(), "data")
        config_dir = os.path.join(os.getcwd(), "config")

        if not os.path.exists(data_dir) and not os.path.exists(config_dir):
            logger.error(f"移行元ディレクトリが存在しません: {data_dir} または {config_dir}")
            return False

        if not self._initialized:
            await self.initialize()

        await self._clear_existing_tables()

        try:
            if os.path.exists(base_dir):
                roles_path = os.path.join(base_dir, "roles.json")
                users_path = os.path.join(base_dir, "users.json")
                events_path = os.path.join(base_dir, "events.json")
                summary_path = os.path.join(base_dir, "summary.json")

                if os.path.exists(roles_path):
                    await self._migrate_roles(roles_path)

                if os.path.exists(users_path):
                    await self._migrate_users(users_path)

                if os.path.exists(events_path):
                    await self._migrate_events(events_path)

                if os.path.exists(summary_path):
                    await self._migrate_summary(summary_path)

            config_path = os.path.join(data_dir, "config.json")
            if os.path.exists(config_path):
                await self._migrate_guild_configs(config_path)

            role_emoji_path = os.path.join(data_dir, "role_emoji_mapping.json")
            if os.path.exists(role_emoji_path):
                await self._migrate_role_emoji_mapping(role_emoji_path)

            member_emojis_path = os.path.join(data_dir, "m__emojis.json")
            if os.path.exists(member_emojis_path):
                await self._migrate_member_emojis(member_emojis_path)

            custom_announcements_dir = os.path.join(data_dir, "custom_announcements")
            if os.path.exists(custom_announcements_dir):
                await self._migrate_custom_announcements(custom_announcements_dir)


            bot_config_path = os.path.join(config_dir, "bot.json")
            if os.path.exists(bot_config_path):
                await self._migrate_bot_config(bot_config_path)

            auth_config_path = os.path.join(config_dir, "auth.json")
            if os.path.exists(auth_config_path):
                await self._migrate_auth_config(auth_config_path)

            members_path = os.path.join(config_dir, "members.json")
            if os.path.exists(members_path):
                await self._migrate_members(members_path)

            logger.info("JSONデータからの移行が完了しました")
            return True
        except Exception as e:
            logger.error(f"移行中にエラーが発生しました: {e}")
            return False

    async def _migrate_roles(self, file_path):
        """ロールデータの移行"""
        try:
            with open(file_path, encoding='utf-8') as f:
                roles_data = json.load(f)

            events_file = os.path.join(os.path.dirname(file_path), "events.json")
            role_id_mapping = {}

            if os.path.exists(events_file):
                with open(events_file, encoding='utf-8') as f:
                    try:
                        events_data = json.load(f)

                        for event in events_data:
                            if 'roles' in event and event['roles']:
                                for role in event['roles']:
                                    if 'id' in role and 'name' in role:
                                        role_id_mapping[role['name']] = str(role['id'])

                        logger.info(f"イベントファイルから {len(role_id_mapping)} 件のロールIDマッピングを取得しました")
                    except Exception as e:
                        logger.error(f"イベントファイルからのロールIDマッピング取得中にエラー: {e}")

            async with self.pool.acquire() as conn:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS roles (
                        role_id TEXT PRIMARY KEY,
                        role_name TEXT NOT NULL,
                        category TEXT,
                        emoji TEXT,
                        description TEXT
                    )
                """)

                migrated_count = 0
                skipped_count = 0

                for role_name, role_info in roles_data.items():
                    try:
                        role_id = role_id_mapping.get(role_name, role_name)

                        category = ''
                        if 'count' in role_info:
                            category = '推しロール'

                        await conn.execute(
                            """
                            INSERT INTO roles (role_id, role_name, category, emoji, description)
                            VALUES ($1, $2, $3, $4, $5)
                            ON CONFLICT (role_id) DO UPDATE
                            SET role_name = $2, category = $3, emoji = $4, description = $5
                            """,
                            role_id,
                            role_name,
                            category,
                            '',
                            ''
                        )
                        migrated_count += 1
                    except Exception as e:
                        logger.error(f"ロールデータの移行中にエラー (role_name: {role_name}): {e}")
                        skipped_count += 1
                        continue

                for role_name, role_id in role_id_mapping.items():
                    try:
                        await conn.execute(
                            """
                            INSERT INTO roles (role_id, role_name, category, emoji, description)
                            VALUES ($1, $2, $3, $4, $5)
                            ON CONFLICT (role_id) DO NOTHING
                            """,
                            role_id,
                            role_name,
                            '推しロール',
                            '',
                            ''
                        )
                    except Exception as e:
                        logger.error(f"イベントから取得したロールの挿入中にエラー (role_name: {role_name}): {e}")

            logger.info(f"ロールデータの移行: {len(roles_data)} 件中 {migrated_count} 件を移行、{skipped_count} 件をスキップしました")
            return True
        except Exception as e:
            logger.error(f"ロールデータ移行中にエラー: {e}")
            raise

    async def _migrate_users(self, file_path):
        """ユーザーデータの移行"""
        try:
            with open(file_path, encoding='utf-8') as f:
                users_data = json.load(f)

            async with self.pool.acquire() as conn:
                for user_id, user_info in users_data.items():
                    try:
                        user_db_id = int(user_id)
                    except ValueError:
                        logger.warning(f"整数変換できないユーザーIDをスキップしました: {user_id}")
                        continue

                    await conn.execute(
                        """
                        INSERT INTO users (user_id, username, first_seen, last_updated)
                        VALUES ($1, $2, $3, $4)
                        ON CONFLICT (user_id) DO UPDATE
                        SET username = $2, last_updated = $4
                        """,
                        user_db_id,
                        user_info.get('username', '不明'),
                        datetime.datetime.fromisoformat(user_info.get('first_seen', datetime.datetime.now().isoformat())),
                        datetime.datetime.fromisoformat(user_info.get('last_updated', datetime.datetime.now().isoformat()))
                    )

                    if 'roles' in user_info:
                        for role_data in user_info['roles']:
                            try:
                                role_id_value = role_data.get('role_id')
                                if not role_id_value:
                                    logger.warning(f"role_idが空です: ユーザーID {user_id}")
                                    continue

                                try:
                                    role_id = str(role_id_value)
                                except ValueError:
                                    logger.warning(f"整数変換できないロールIDをスキップしました: {role_id_value} (ユーザーID: {user_id})")
                                    continue

                                assigned_at = datetime.datetime.fromisoformat(role_data.get('assigned_at', datetime.datetime.now().isoformat()))
                                removed_at = None
                                is_active = True

                                if 'removed_at' in role_data and role_data['removed_at']:
                                    removed_at = datetime.datetime.fromisoformat(role_data['removed_at'])
                                    is_active = False
                            except Exception as e:
                                logger.error(f"ユーザーロールデータの処理中にエラー: {e} (ユーザーID: {user_id})")
                                continue

                            await conn.execute(
                                """
                                INSERT INTO user_roles (user_id, role_id, assigned_at, removed_at, is_active)
                                VALUES ($1, $2, $3, $4, $5)
                                ON CONFLICT (user_id, role_id, assigned_at) DO UPDATE
                                SET removed_at = $4, is_active = $5
                                """,
                                int(user_id), role_id, assigned_at, removed_at, is_active
                            )

            logger.info(f"{len(users_data)} 件のユーザーデータを移行しました")
        except Exception as e:
            logger.error(f"ユーザーデータ移行中にエラー: {e}")
            raise

    async def _migrate_events(self, file_path):
        """イベントデータの移行"""
        try:
            with open(file_path, encoding='utf-8') as f:
                events_data = json.load(f)

            migrated_count = 0
            skipped_count = 0

            async with self.pool.acquire() as conn:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS role_events (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT,
                        role_id TEXT,
                        event_type TEXT,
                        timestamp TIMESTAMP WITH TIME ZONE,
                        interaction_id TEXT
                    )
                """)

                for event in events_data:
                    try:
                        try:
                            user_id = int(event.get('user_id'))
                        except (ValueError, TypeError):
                            logger.warning(f"無効なユーザーIDをスキップしました: {event.get('user_id')}")
                            skipped_count += 1
                            continue

                        timestamp_str = event.get('timestamp')
                        if timestamp_str:
                            timestamp = None
                            date_formats = [
                                "%Y-%m-%d %H:%M:%S",
                                "%Y-%m-%dT%H:%M:%S",
                                "%Y-%m-%d",
                            ]

                            for date_format in date_formats:
                                try:
                                    timestamp = datetime.datetime.strptime(timestamp_str, date_format)
                                    break
                                except ValueError:
                                    continue

                            if timestamp is None:
                                timestamp = datetime.datetime.now()
                                logger.warning(f"日付形式を解析できないため現在日時を使用: {timestamp_str}")
                        else:
                            timestamp = datetime.datetime.now()

                        event_type = event.get('event_type', 'unknown')

                        roles = event.get('roles', [])
                        if roles:
                            for role in roles:
                                try:
                                    role_id = str(role.get('id'))

                                    role_exists = await conn.fetchval(
                                        "SELECT EXISTS(SELECT 1 FROM roles WHERE role_id = $1)",
                                        role_id
                                    )

                                    if not role_exists:
                                        await conn.execute(
                                            """
                                            INSERT INTO roles (role_id, role_name, category, emoji, description)
                                            VALUES ($1, $2, $3, $4, $5)
                                            """,
                                            role_id,
                                            role.get('name', '不明'),
                                            event.get('category', ''),
                                            '',
                                            ''
                                        )

                                    await conn.execute(
                                        """
                                        INSERT INTO role_events (user_id, role_id, event_type, timestamp, interaction_id)
                                        VALUES ($1, $2, $3, $4, $5)
                                        """,
                                        user_id,
                                        role_id,
                                        event_type,
                                        timestamp,
                                        event.get('interaction_id', '')
                                    )
                                    migrated_count += 1
                                except Exception as e:
                                    logger.warning(f"イベント処理中にエラー: {e}, ロール: {role}")
                                    skipped_count += 1
                        else:
                            try:
                                if 'role_id' in event:
                                    role_id = str(event.get('role_id'))

                                    role_exists = await conn.fetchval(
                                        "SELECT EXISTS(SELECT 1 FROM roles WHERE role_id = $1)",
                                        role_id
                                    )

                                    if not role_exists:
                                        await conn.execute(
                                            """
                                            INSERT INTO roles (role_id, role_name, category, emoji, description)
                                            VALUES ($1, $2, $3, $4, $5)
                                            """,
                                            role_id,
                                            event.get('role_name', '不明'),
                                            event.get('category', ''),
                                            '',
                                            ''
                                        )

                                    await conn.execute(
                                        """
                                        INSERT INTO role_events (user_id, role_id, event_type, timestamp, interaction_id)
                                        VALUES ($1, $2, $3, $4, $5)
                                        """,
                                        user_id,
                                        role_id,
                                        event_type,
                                        timestamp,
                                        event.get('interaction_id', '')
                                    )
                                    migrated_count += 1
                                else:
                                    logger.warning(f"role_idが見つからないイベントをスキップ: {event}")
                                    skipped_count += 1
                            except Exception as e:
                                logger.warning(f"イベント処理中にエラー: {e}, イベント: {event}")
                                skipped_count += 1
                    except Exception as e:
                        logger.error(f"イベントデータ処理中の予期しないエラー: {e} - イベント: {event}")
                        skipped_count += 1
                        continue

            logger.info(f"{len(events_data)} 件のイベントデータから {migrated_count} 件を移行しました。{skipped_count} 件をスキップしました。")
            return True
        except Exception as e:
            logger.error(f"イベントデータ移行中にエラー: {e}")
            raise

    async def _migrate_summary(self, file_path):
        """統計サマリーデータの移行"""
        try:
            with open(file_path, encoding='utf-8') as f:
                summary_data = json.load(f)

            if 'daily_stats' in summary_data:
                async with self.pool.acquire() as conn:
                    for date_str, roles_stats in summary_data['daily_stats'].items():
                        date_obj = datetime.date.fromisoformat(date_str)

                        for role_id, stats in roles_stats.items():
                            await conn.execute(
                                """
                                INSERT INTO role_stats (role_id, date, total_count, daily_adds, daily_removes)
                                VALUES ($1, $2, $3, $4, $5)
                                ON CONFLICT (role_id, date) DO UPDATE
                                SET total_count = $3, daily_adds = $4, daily_removes = $5
                                """,
                                str(role_id),
                                date_obj,
                                stats.get('total', 0),
                                stats.get('adds', 0),
                                stats.get('removes', 0)
                            )

            logger.info("統計サマリーデータを移行しました")
        except Exception as e:
            logger.error(f"統計データ移行中にエラー: {e}")
            raise

    async def _migrate_guild_configs(self, file_path):
        """サーバー設定データの移行"""
        try:
            with open(file_path, encoding='utf-8') as f:
                config_data = json.load(f)

            async with self.pool.acquire() as conn:
                for guild_id, config in config_data.items():
                    welcome_channel_id = config.get('welcome_channel')

                    await conn.execute(
                        """
                        INSERT INTO guild_configs (guild_id, welcome_channel_id, config_json)
                        VALUES ($1, $2, $3)
                        ON CONFLICT (guild_id) DO UPDATE
                        SET welcome_channel_id = $2, config_json = $3, updated_at = NOW()
                        """,
                        int(guild_id),
                        welcome_channel_id,
                        json.dumps(config)
                    )

            logger.info(f"{len(config_data)}件のサーバー設定データを移行しました")
            return True
        except Exception as e:
            logger.error(f"サーバー設定データ移行中にエラー: {e}")
            raise

    async def _migrate_role_emoji_mapping(self, file_path):
        """ロール絵文字マッピングデータの移行"""
        try:
            with open(file_path, encoding='utf-8') as f:
                mapping_data = json.load(f)

            async with self.pool.acquire() as conn:
                for role_id, emoji_data in mapping_data.items():
                    # 絵文字データの解析
                    emoji_id = None
                    emoji_name = None
                    emoji_json = None

                    if isinstance(emoji_data, dict):
                        emoji_id = emoji_data.get('id')
                        emoji_name = emoji_data.get('name')
                        emoji_json = json.dumps(emoji_data)
                    elif isinstance(emoji_data, str):
                        emoji_name = emoji_data
                        emoji_match = re.search(r'<:[^:]+:([0-9]+)>', emoji_data)
                        if emoji_match:
                            emoji_id = emoji_match.group(1)

                    guild_id = settings.admin_main_guild_id

                    await conn.execute(
                        """
                        INSERT INTO role_emoji_mappings (role_id, emoji_id, emoji_name, emoji_data, guild_id)
                        VALUES ($1, $2, $3, $4, $5)
                        ON CONFLICT (role_id, guild_id) DO UPDATE
                        SET emoji_id = $2, emoji_name = $3, emoji_data = $4, updated_at = NOW()
                        """,
                        str(role_id),
                        emoji_id,
                        emoji_name,
                        emoji_json,
                        guild_id
                    )

            logger.info(f"{len(mapping_data)}件のロール絵文字マッピングデータを移行しました")
            return True
        except Exception as e:
            logger.error(f"ロール絵文字マッピングデータ移行中にエラー: {e}")
            raise

    async def _migrate_custom_announcements(self, directory_path):
        """カスタムアナウンステンプレートの移行"""
        try:
            # JSONファイルを検索
            json_files = [f for f in os.listdir(directory_path) if f.endswith('.json')]

            if not json_files:
                logger.info("カスタムアナウンステンプレートのJSONファイルが見つかりませんでした")
                return False

            template_count = 0
            async with self.pool.acquire() as conn:
                for json_file in json_files:
                    file_path = os.path.join(directory_path, json_file)
                    with open(file_path, encoding='utf-8') as f:
                        templates = json.load(f)

                    # ファイル名からギルドIDを抽出（例: announcements_1234567890.json）
                    guild_match = re.search(r'(\d+)', json_file)
                    guild_id = int(guild_match.group(1)) if guild_match else 1092138492173242430

                    for template_name, template_content in templates.items():
                        await conn.execute(
                            """
                            INSERT INTO custom_announcements (template_name, template_content, guild_id)
                            VALUES ($1, $2, $3)
                            ON CONFLICT (guild_id, template_name) DO UPDATE
                            SET template_content = $2, updated_at = NOW()
                            """,
                            template_name,
                            template_content,
                            guild_id
                        )
                        template_count += 1

            logger.info(f"{template_count}件のカスタムアナウンステンプレートを移行しました")
            return True
        except Exception as e:
            logger.error(f"カスタムアナウンスデータ移行中にエラー: {e}")
            raise

    async def _migrate_bot_config(self, file_path):
        """ボット設定ファイル(bot.json)の移行"""
        try:
            # JSONファイルを読み込み
            with open(file_path, encoding='utf-8') as f:
                bot_config = json.load(f)

            # データベースに保存
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO bot_config (name, version, owner, prefix, updated_at)
                    VALUES ($1, $2, $3, $4, NOW())
                    ON CONFLICT (id) DO UPDATE
                    SET name = $1, version = $2, owner = $3, prefix = $4, updated_at = NOW()
                    """,
                    bot_config.get('name', 'HFS Manager'),
                    bot_config.get('version', '0.1.0'),
                    bot_config.get('owner', 'FreeWiFi7749'),
                    bot_config.get('prefix', 'hfs-hp/')
                )

            logger.info(f"ボット設定をデータベースに移行しました: {file_path}")
            return True
        except Exception as e:
            logger.error(f"ボット設定移行中にエラー: {e}")
            raise

    async def _migrate_auth_config(self, file_path):
        """認証設定ファイル(auth.json)の移行"""
        try:
            # JSONファイルを読み込み
            with open(file_path, encoding='utf-8') as f:
                auth_config = json.load(f)

            # データベースに保存
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO auth_config (id, label, auth_code, updated_at)
                    VALUES ($1, $2, $3, NOW())
                    ON CONFLICT (id) DO UPDATE
                    SET label = $2, auth_code = $3, updated_at = NOW()
                    """,
                    auth_config.get('id', str(uuid.uuid4())),
                    auth_config.get('label', 'HFS_Manager'),
                    auth_config.get('auth_code', '')
                )

            logger.info(f"認証設定をデータベースに移行しました: {file_path}")
            return True
        except Exception as e:
            logger.error(f"認証設定移行中にエラー: {e}")
            raise

    async def _migrate_members(self, file_path):
        """メンバー情報ファイル(members.json)の移行"""
        try:
            # JSONファイルを読み込み
            with open(file_path, encoding='utf-8') as f:
                members_data = json.load(f)

            total_count = 0

            # データベースに保存
            async with self.pool.acquire() as conn:
                # スタッフメンバーの移行
                if 'staff' in members_data:
                    for member in members_data['staff']:
                        try:
                            # 日付処理
                            joined_at = None
                            joined_at_str = member.get('joinedAt')

                            if joined_at_str:
                                # 複数の日付形式を試す
                                date_formats = [
                                    "%Y-%m-%d %H:%M:%S",
                                    "%Y-%m-%dT%H:%M:%S",
                                    "%Y-%m-%d",
                                ]

                                for date_format in date_formats:
                                    try:
                                        joined_at = datetime.datetime.strptime(joined_at_str, date_format)
                                        break
                                    except ValueError:
                                        continue

                            await conn.execute(
                                """
                                INSERT INTO members (
                                    id, name, role, avatar, message, joined_at, joined_at_jp,
                                    role_color, socials, type, updated_at
                                )
                                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, NOW())
                                ON CONFLICT (id) DO UPDATE
                                SET name = $2, role = $3, avatar = $4, message = $5,
                                    joined_at = $6, joined_at_jp = $7, role_color = $8,
                                    socials = $9, type = $10, updated_at = NOW()
                                """,
                                int(member.get('id', 0)),
                                member.get('name', ''),
                                member.get('role', 'Staff'),
                                member.get('avatar', ''),
                                member.get('message', ''),
                                joined_at,
                                member.get('joinedAtJp', ''),
                                member.get('roleColor', '#ffffff'),
                                json.dumps(member.get('socials', {})),
                                'staff'
                            )
                            total_count += 1
                        except Exception as e:
                            logger.error(f"メンバー情報処理中にエラー: {e} - メンバー: {member}")

                # specialThanksメンバーの移行
                if 'specialThanks' in members_data:
                    for member in members_data['specialThanks']:
                        try:
                            # 日付処理
                            joined_at = None
                            joined_at_str = member.get('joinedAt')

                            if joined_at_str:
                                # 複数の日付形式を試す
                                date_formats = [
                                    "%Y-%m-%d %H:%M:%S",
                                    "%Y-%m-%dT%H:%M:%S",
                                    "%Y-%m-%d",
                                ]

                                for date_format in date_formats:
                                    try:
                                        joined_at = datetime.datetime.strptime(joined_at_str, date_format)
                                        break
                                    except ValueError:
                                        continue

                            await conn.execute(
                                """
                                INSERT INTO members (
                                    id, name, role, avatar, message, joined_at, joined_at_jp,
                                    role_color, socials, type, updated_at
                                )
                                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, NOW())
                                ON CONFLICT (id) DO UPDATE
                                SET name = $2, role = $3, avatar = $4, message = $5,
                                    joined_at = $6, joined_at_jp = $7, role_color = $8,
                                    socials = $9, type = $10, updated_at = NOW()
                                """,
                                int(member.get('id', 0)),
                                member.get('name', ''),
                                member.get('role', '常連'),
                                member.get('avatar', ''),
                                member.get('message', ''),
                                joined_at,
                                member.get('joinedAtJp', ''),
                                member.get('roleColor', '#ffffff'),
                                json.dumps(member.get('socials', {})),
                                'specialThanks'
                            )
                            total_count += 1
                        except Exception as e:
                            logger.error(f"メンバー情報処理中にエラー: {e} - メンバー: {member}")

                # testersメンバーの移行
                if 'testers' in members_data:
                    for member in members_data['testers']:
                        try:
                            # 日付処理
                            joined_at = None
                            joined_at_str = member.get('joinedAt')

                            if joined_at_str:
                                # 複数の日付形式を試す
                                date_formats = [
                                    "%Y-%m-%d %H:%M:%S",
                                    "%Y-%m-%dT%H:%M:%S",
                                    "%Y-%m-%d",
                                ]

                                for date_format in date_formats:
                                    try:
                                        joined_at = datetime.datetime.strptime(joined_at_str, date_format)
                                        break
                                    except ValueError:
                                        continue

                            await conn.execute(
                                """
                                INSERT INTO members (
                                    id, name, role, avatar, message, joined_at, joined_at_jp,
                                    role_color, socials, type, updated_at
                                )
                                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, NOW())
                                ON CONFLICT (id) DO UPDATE
                                SET name = $2, role = $3, avatar = $4, message = $5,
                                    joined_at = $6, joined_at_jp = $7, role_color = $8,
                                    socials = $9, type = $10, updated_at = NOW()
                                """,
                                int(member.get('id', 0)),
                                member.get('name', ''),
                                member.get('role', 'テスター'),
                                member.get('avatar', ''),
                                member.get('message', ''),
                                joined_at,
                                member.get('joinedAtJp', ''),
                                member.get('roleColor', '#ffffff'),
                                json.dumps(member.get('socials', {})),
                                'testers'
                            )
                            total_count += 1
                        except Exception as e:
                            logger.error(f"メンバー情報処理中にエラー: {e} - メンバー: {member}")

            logger.info(f"{total_count}件のメンバー情報をデータベースに移行しました: {file_path}")
            return True
        except Exception as e:
            logger.error(f"メンバー情報移行中にエラー: {e}")
            raise

    # --- role_emoji_mapping API ---
    async def get_role_emoji_mapping_dict(self) -> dict[str, str]:
        """role_emoji_mappings テーブルを dict で取得"""
        if not self._initialized:
            await self.initialize()
        mapping: dict[str, str] = {}
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT role_id, emoji_id, emoji_name, animated FROM role_emoji_mappings")
            for r in rows:
                mapping[str(r["role_id"])] = {
                    "emoji_id": r["emoji_id"],
                    "emoji_name": r["emoji_name"],
                    "animated": r["animated"]
                }
        return mapping

    async def upsert_role_emoji_mapping_dict(self, mapping: dict[str, dict[str, str]], guild_id: int):
        """辞書をテーブルに upsert"""
        if not self._initialized:
            await self.initialize()
        async with self.pool.acquire() as conn:
            for role_id, emoji in mapping.items():
                await conn.execute(
                    """
                    INSERT INTO role_emoji_mappings (role_id, guild_id, emoji_id, emoji_name, animated)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (role_id, guild_id) DO UPDATE
                    SET emoji_id = $3, emoji_name = $4, animated = $5, updated_at = NOW()
                    """,
                    str(role_id), guild_id, emoji.get("emoji_id"), emoji.get("emoji_name"), emoji.get("animated", False)
                )

    async def _migrate_member_emojis(self, file_path):
        """m__emojis.json を member_emojis テーブルに移行"""
        try:
            with open(file_path, encoding='utf-8') as f:
                emojis_data = json.load(f)

            async with self.pool.acquire() as conn:
                migrated = 0
                for item in emojis_data:
                    try:
                        emoji_id = int(item.get('id'))
                        name = item.get('name', '')
                        url = item.get('url', '')
                        animated = bool(item.get('animated', False))
                        await conn.execute(
                            """
                            INSERT INTO member_emojis (emoji_id, name, url, animated)
                            VALUES ($1, $2, $3, $4)
                            ON CONFLICT (emoji_id) DO UPDATE
                            SET name = $2, url = $3, animated = $4, updated_at = NOW()
                            """,
                            emoji_id, name, url, animated
                        )
                        migrated += 1
                    except Exception as e:
                        logger.error(f"member_emojis 移行中にエラー: {e}")
                        continue
            logger.info(f"member_emojis: {migrated} 件を移行しました")
            return True
        except Exception as e:
            logger.error(f"m__emojis.json からの移行に失敗: {e}")
            return False

    # --- 推しロール操作用API ---

    async def get_user_roles(self, user_id: int) -> list[dict[str, Any]]:
        """ユーザーの現在のロール一覧を取得します"""
        try:
            async with self.pool.acquire() as conn:
                records = await conn.fetch(
                    """
                    SELECT r.role_id, r.role_name, r.category, r.emoji,
                           ur.assigned_at
                    FROM roles r
                    JOIN user_roles ur ON r.role_id = ur.role_id
                    WHERE ur.user_id = $1 AND ur.is_active = true
                    ORDER BY ur.assigned_at DESC
                    """,
                    user_id
                )

                result = []
                for record in records:
                    result.append({
                        'role_id': record['role_id'],
                        'role_name': record['role_name'],
                        'category': record['category'],
                        'emoji': record['emoji'],
                        'assigned_at': record['assigned_at'].isoformat()
                    })

                return result
        except Exception as e:
            logger.error(f"ユーザーのロール取得中にエラー: {e}")
            return []

    async def add_role_to_user(self, user_id: int, role_id, username: str = None, interaction_id: str = None):
        """ユーザーにロールを追加し、イベントを記録します"""
        try:
            if not self._initialized:
                await self.initialize()

            # role_idを文字列に変換して一貫性を確保
            role_id_str = str(role_id)

            async with self.pool.acquire() as conn:
                # ユーザーが存在するか確認し、存在しなければ作成
                user_exists = await conn.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM users WHERE user_id = $1)",
                    user_id
                )

                if not user_exists:
                    await conn.execute(
                        "INSERT INTO users (user_id, username) VALUES ($1, $2)",
                        user_id, username or '不明'
                    )

                # ロールが存在するか確認
                role_exists = await conn.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM roles WHERE role_id = $1)",
                    role_id_str
                )

                if not role_exists:
                    logger.warning(f"存在しないロールID: {role_id_str}")
                    return False

                # 既に有効なロールがあるか確認
                active_role = await conn.fetchval(
                    """SELECT id FROM user_roles
                    WHERE user_id = $1 AND role_id = $2 AND is_active = true""",
                    user_id, role_id_str
                )

                if active_role:
                    logger.info(f"ユーザー {user_id} は既にロール {role_id_str} を持っています")
                    return False

                # 新しいロール割り当てを作成
                now = datetime.datetime.now()
                await conn.execute(
                    """INSERT INTO user_roles (user_id, role_id, assigned_at, is_active)
                    VALUES ($1, $2, $3, true)""",
                    user_id, role_id_str, now
                )

                # イベントを記録
                await conn.execute(
                    """INSERT INTO role_events (user_id, role_id, event_type, timestamp, interaction_id)
                    VALUES ($1, $2, $3, $4, $5)""",
                    user_id, role_id_str, 'add', now, interaction_id or ''
                )

                return True

        except Exception as e:
            logger.error(f"ロール追加中にエラー: {e}")
            return False

    async def remove_role_from_user(self, user_id: int, role_id, interaction_id: str = None) -> bool:
        """ユーザーからロールを削除し、イベントを記録します"""
        try:
            now = datetime.datetime.now()

            async with self.pool.acquire() as conn:
                # トランザクション開始
                async with conn.transaction():
                    # 現在のアクティブなロールを取得
                    user_role = await conn.fetchrow(
                        """
                        SELECT id, assigned_at FROM user_roles
                        WHERE user_id = $1 AND role_id = $2 AND is_active = true
                        """,
                        user_id, role_id
                    )

                    # アクティブなロールがあれば削除
                    if user_role:
                        # ロールの非アクティブ化
                        await conn.execute(
                            """
                            UPDATE user_roles
                            SET is_active = false, removed_at = $3
                            WHERE id = $1
                            """,
                            user_role['id'], now
                        )

                        # イベントの記録
                        await conn.execute(
                            """
                            INSERT INTO role_events (user_id, role_id, event_type, timestamp, interaction_id)
                            VALUES ($1, $2, 'remove', $3, $4)
                            """,
                            user_id, str(role_id), now, interaction_id
                        )

                        # 統計の更新
                        today = now.date()
                        await conn.execute(
                            """
                            INSERT INTO role_stats (role_id, date, total_count, daily_removes)
                            VALUES ($1, $2, (
                                SELECT COUNT(*) FROM user_roles
                                WHERE role_id = $1 AND is_active = true
                            ), 1)
                            ON CONFLICT (role_id, date) DO UPDATE
                            SET total_count = (
                                SELECT COUNT(*) FROM user_roles
                                WHERE role_id = $1 AND is_active = true
                            ),
                            daily_removes = role_stats.daily_removes + 1
                            """,
                            role_id, today
                        )

                    return True
        except Exception as e:
            logger.error(f"ロール削除中にエラー: {e}")
            return False

    # --- 統計情報取得用API ---

    async def get_role_statistics(self, days: int = 30) -> dict[str, Any]:
        """ロールの統計情報を取得します"""
        try:
            end_date = datetime.date.today()
            start_date = end_date - datetime.timedelta(days=days)

            async with self.pool.acquire() as conn:
                # アクティブなロール数の合計
                total_roles = await conn.fetchval(
                    """
                    SELECT COUNT(*) FROM user_roles WHERE is_active = true
                    """
                )

                # ロールごとの統計
                role_stats = await conn.fetch(
                    """
                    SELECT r.role_id, r.role_name, r.emoji,
                           COUNT(ur.id) AS active_count,
                           MAX(rs.daily_adds) AS max_daily_adds,
                           SUM(rs.daily_adds) AS total_adds,
                           SUM(rs.daily_removes) AS total_removes
                    FROM roles r
                    LEFT JOIN user_roles ur ON r.role_id = ur.role_id AND ur.is_active = true
                    LEFT JOIN role_stats rs ON r.role_id = rs.role_id
                                          AND rs.date BETWEEN $1 AND $2
                    GROUP BY r.role_id, r.role_name, r.emoji
                    ORDER BY active_count DESC
                    """,
                    start_date, end_date
                )

                # 日別データ
                daily_data = await conn.fetch(
                    """
                    SELECT date, SUM(daily_adds) AS total_adds, SUM(daily_removes) AS total_removes
                    FROM role_stats
                    WHERE date BETWEEN $1 AND $2
                    GROUP BY date
                    ORDER BY date
                    """,
                    start_date, end_date
                )

                return {
                    'total_active_roles': total_roles,
                    'period': {
                        'start': start_date.isoformat(),
                        'end': end_date.isoformat(),
                        'days': days
                    },
                    'roles': [dict(r) for r in role_stats],
                    'daily': [dict(d) for d in daily_data]
                }
        except Exception as e:
            logger.error(f"統計情報取得中にエラー: {e}")
            return {}

    async def get_bump_notice_settings(self, guild_id: int):
        """
        bump notice用設定（チャンネル/BOT/ロールID）を取得
        Returns: dict or None
        """
        if not self.pool:
            await self.initialize()
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT channel_id, bot_id, role_id FROM bump_notice_settings WHERE guild_id = $1
            """, guild_id)
            if row:
                return dict(row)
            return None

    async def set_bump_notice_settings(self, guild_id: int, channel_id: int = None, bot_id: int = None, role_id: int = None):
        """
        bump notice用設定を保存/更新
        指定された値のみ更新（Noneは変更しない）
        """
        if not self.pool:
            await self.initialize()
        async with self.pool.acquire() as conn:
            # 既存取得
            row = await conn.fetchrow("SELECT * FROM bump_notice_settings WHERE guild_id = $1", guild_id)
            new_channel_id = channel_id if channel_id is not None else (row["channel_id"] if row else None)
            new_bot_id = bot_id if bot_id is not None else (row["bot_id"] if row else None)
            new_role_id = role_id if role_id is not None else (row["role_id"] if row else None)
            await conn.execute("""
                INSERT INTO bump_notice_settings (guild_id, channel_id, bot_id, role_id, updated_at)
                VALUES ($1, $2, $3, $4, NOW())
                ON CONFLICT (guild_id) DO UPDATE SET channel_id = $2, bot_id = $3, role_id = $4, updated_at = NOW()
            """, guild_id, new_channel_id, new_bot_id, new_role_id)

# シングルトンインスタンス
db = DBManager()
