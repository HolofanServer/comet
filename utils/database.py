"""
データベース接続ユーティリティ

PostgreSQLデータベースとの接続を一貫した方法で提供するモジュールです。
"""
import os
import logging
from typing import Dict, Any, Optional
import asyncpg

logger = logging.getLogger('database')

# 接続設定のキャッシュ
_db_config = None
_db_pool = None

def get_database_url() -> Optional[str]:
    """データベース接続URLを取得します"""
    # DATABASE_PUBLIC_URLを優先的に使用
    db_url = os.environ.get('DATABASE_PUBLIC_URL')
    if db_url:
        logger.info("DATABASE_PUBLIC_URL環境変数を使用します")
        return db_url
    return None

def get_db_config() -> Dict[str, Any]:
    """データベース接続設定を取得します"""
    global _db_config
    
    if _db_config is None:
        # Railway環境変数を使用
        if os.environ.get('RAILWAY_ENVIRONMENT'):
            # Railway環境での接続情報
            _db_config = {
                'host': os.environ.get('PGHOST', ''),
                'port': int(os.environ.get('PGPORT', 5432)),
                'user': os.environ.get('PGUSER', ''),
                'password': os.environ.get('PGPASSWORD', ''),
                'database': os.environ.get('PGDATABASE', '')
            }
            logger.info("Railway環境の接続設定を使用します")
        else:
            # ローカル開発環境での接続情報
            _db_config = {
                'host': os.environ.get('DB_HOST', 'localhost'),
                'port': int(os.environ.get('DB_PORT', 5432)),
                'user': os.environ.get('DB_USER', 'postgres'),
                'password': os.environ.get('DB_PASSWORD', ''),
                'database': os.environ.get('DB_NAME', 'hfs_bot')
            }
            logger.info("ローカル環境の接続設定を使用します")
    
    return _db_config

async def get_db_pool() -> asyncpg.Pool:
    """データベース接続プールを取得します。未初期化の場合は初期化します。"""
    global _db_pool
    
    if _db_pool is None:
        try:
            # DATABASE_PUBLIC_URLのみを使用
            db_url = os.environ.get('DATABASE_PUBLIC_URL')
            
            if not db_url:
                logger.error("DATABASE_PUBLIC_URL環境変数が設定されていません")
                raise ValueError("DATABASE_PUBLIC_URL環境変数が設定されていません")
                
            # 接続文字列を直接使用
            _db_pool = await asyncpg.create_pool(db_url)
            logger.info("DATABASE_PUBLIC_URLを使用してデータベース接続プールを初期化しました")
        except Exception as e:
            logger.error(f"データベース接続に失敗しました: {e}")
            raise
    
    return _db_pool

async def close_db_pool():
    """データベース接続プールを閉じます"""
    global _db_pool
    
    if _db_pool:
        await _db_pool.close()
        _db_pool = None
        logger.info("データベース接続プールを閉じました")

async def execute_query(query: str, *args, fetch_type: str = 'all') -> Any:
    """
    SQL クエリを実行して結果を返します
    
    Args:
        query: 実行するSQLクエリ
        *args: クエリのパラメータ
        fetch_type: 取得タイプ ('all', 'row', 'val', 'status')
    
    Returns:
        fetch_typeによって異なる結果を返します
    """
    pool = await get_db_pool()
    
    try:
        async with pool.acquire() as conn:
            if fetch_type == 'all':
                return await conn.fetch(query, *args)
            elif fetch_type == 'row':
                return await conn.fetchrow(query, *args)
            elif fetch_type == 'val':
                return await conn.fetchval(query, *args)
            elif fetch_type == 'status':
                return await conn.execute(query, *args)
            else:
                raise ValueError(f"未対応の fetch_type: {fetch_type}")
    except Exception as e:
        logger.error(f"クエリ実行中にエラー: {e}")
        logger.error(f"クエリ: {query}")
        raise
