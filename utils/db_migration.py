"""
データベース移行ユーティリティ

JSONからPostgreSQLへのデータ移行を実行するためのコマンドラインスクリプトです。
"""
import asyncio
import os
import json
import logging
import argparse
import datetime

from utils.db_manager import db

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f"db_migration_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    ]
)
logger = logging.getLogger('db_migration')


async def verify_migration():
    """移行後のデータ検証を行います"""
    try:
        # データベース接続の確認
        if not db._initialized:
            await db.initialize()
            
        # ロール数の確認
        async with db.pool.acquire() as conn:
            roles_count = await conn.fetchval("SELECT COUNT(*) FROM roles")
            users_count = await conn.fetchval("SELECT COUNT(*) FROM users")
            events_count = await conn.fetchval("SELECT COUNT(*) FROM role_events")
            user_roles_count = await conn.fetchval("SELECT COUNT(*) FROM user_roles WHERE is_active = true")
        
        # JSONファイルの数との比較
        base_dir = os.path.join(os.getcwd(), "data", "analytics", "oshi_roles")
        
        # ロールJSON
        roles_json_path = os.path.join(base_dir, "roles.json")
        roles_json_count = 0
        if os.path.exists(roles_json_path):
            with open(roles_json_path, 'r', encoding='utf-8') as f:
                roles_json_count = len(json.load(f))
        
        # イベントJSON
        events_json_path = os.path.join(base_dir, "events.json")
        events_json_count = 0
        if os.path.exists(events_json_path):
            with open(events_json_path, 'r', encoding='utf-8') as f:
                events_json_count = len(json.load(f))
        
        # ユーザーJSON
        users_json_path = os.path.join(base_dir, "users.json")
        users_json_count = 0
        active_roles_json_count = 0
        if os.path.exists(users_json_path):
            with open(users_json_path, 'r', encoding='utf-8') as f:
                users_data = json.load(f)
                users_json_count = len(users_data)
                
                # アクティブなロールを数える
                for user_id, user_info in users_data.items():
                    if 'roles' in user_info:
                        for role in user_info['roles']:
                            if not role.get('removed_at'):
                                active_roles_json_count += 1
        
        # 結果を表示
        logger.info("=== 移行検証結果 ===")
        logger.info(f"ロール数: DB={roles_count}, JSON={roles_json_count}")
        logger.info(f"ユーザー数: DB={users_count}, JSON={users_json_count}")
        logger.info(f"イベント数: DB={events_count}, JSON={events_json_count}")
        logger.info(f"アクティブなロール割り当て: DB={user_roles_count}, JSON={active_roles_json_count}")
        
        if roles_count < roles_json_count:
            logger.warning(f"警告: DBのロール数がJSONより少ないです: {roles_count} < {roles_json_count}")
        if users_count < users_json_count:
            logger.warning(f"警告: DBのユーザー数がJSONより少ないです: {users_count} < {users_json_count}")
        if events_count < events_json_count:
            logger.warning(f"警告: DBのイベント数がJSONより少ないです: {events_count} < {events_json_count}")
        if user_roles_count < active_roles_json_count:
            logger.warning(f"警告: DBのアクティブなロール割り当て数がJSONより少ないです: {user_roles_count} < {active_roles_json_count}")
        
        if (roles_count >= roles_json_count and 
            users_count >= users_json_count and 
            events_count >= events_json_count and
            user_roles_count >= active_roles_json_count):
            logger.info("検証成功: すべてのデータが正しく移行されています")
            return True
        else:
            logger.error("検証失敗: 一部のデータが正しく移行されていない可能性があります")
            return False
    except Exception as e:
        logger.error(f"検証中にエラーが発生しました: {e}")
        return False


async def create_backup():
    """JSON形式のバックアップを作成します"""
    try:
        backup_dir = os.path.join(os.getcwd(), "data", "backup", f"json_backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}")
        os.makedirs(backup_dir, exist_ok=True)
        
        # 元のJSONファイルをコピー
        base_dir = os.path.join(os.getcwd(), "data", "analytics", "oshi_roles")
        json_files = ["roles.json", "users.json", "events.json", "summary.json"]
        
        for file_name in json_files:
            src_path = os.path.join(base_dir, file_name)
            if os.path.exists(src_path):
                with open(src_path, 'r', encoding='utf-8') as src_file:
                    data = json.load(src_file)
                
                dst_path = os.path.join(backup_dir, file_name)
                with open(dst_path, 'w', encoding='utf-8') as dst_file:
                    json.dump(data, dst_file, ensure_ascii=False, indent=2)
        
        logger.info(f"バックアップを作成しました: {backup_dir}")
        return backup_dir
    except Exception as e:
        logger.error(f"バックアップ作成中にエラーが発生しました: {e}")
        return None


async def main():
    """メイン実行関数"""
    parser = argparse.ArgumentParser(description='JSONからPostgreSQLへのデータ移行')
    parser.add_argument('--verify-only', action='store_true', help='検証のみ実行し、移行は行いません')
    parser.add_argument('--backup', action='store_true', help='移行前にJSONデータのバックアップを作成します')
    parser.add_argument('--skip-verification', action='store_true', help='移行後の検証をスキップします')
    args = parser.parse_args()
    
    try:
        # データベース初期化
        await db.initialize()
        logger.info("データベース接続を初期化しました")
        
        # バックアップ作成
        if args.backup:
            backup_path = await create_backup()
            if not backup_path:
                logger.error("バックアップの作成に失敗しました。処理を中止します。")
                return 1
        
        # 検証のみモードの場合
        if args.verify_only:
            logger.info("検証のみモードで実行します")
            success = await verify_migration()
            return 0 if success else 1
        
        # 移行実行
        logger.info("JSONデータからPostgreSQLへの移行を開始します...")
        success = await db.migrate_from_json()
        
        if not success:
            logger.error("移行に失敗しました")
            return 1
        
        logger.info("移行が完了しました")
        
        # 検証実行
        if not args.skip_verification:
            logger.info("移行結果の検証を開始します...")
            verify_success = await verify_migration()
            if not verify_success:
                logger.warning("移行の検証に失敗しました。データを確認してください。")
                return 1
        
        logger.info("データベース移行処理が正常に完了しました")
        return 0
    except Exception as e:
        logger.error(f"予期せぬエラーが発生しました: {e}")
        return 1
    finally:
        # データベース接続を閉じる
        await db.close()
        logger.info("データベース接続を閉じました")


if __name__ == "__main__":
    # スクリプト単独実行時のエントリーポイント
    exit_code = asyncio.run(main())
    exit(exit_code)
