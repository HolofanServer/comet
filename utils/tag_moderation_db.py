"""
タグモデレーション専用データベース接続ユーティリティ

専用データベースとの接続を一貫した方法で提供するモジュールです。
"""
import logging
import os
from typing import Any, Optional

import asyncpg

logger = logging.getLogger('tag_moderation_db')

# 接続プールのキャッシュ
_tag_db_pool = None


def get_tag_database_url() -> Optional[str]:
    """タグモデレーション専用データベース接続URLを取得します"""
    db_url = os.environ.get('TAG_MODERATION_DATABASE_URL')
    if db_url:
        logger.info("TAG_MODERATION_DATABASE_URL環境変数を使用します")
        return db_url
    logger.warning("TAG_MODERATION_DATABASE_URL環境変数が設定されていません")
    return None


async def get_tag_db_pool() -> asyncpg.Pool:
    """タグモデレーション専用データベース接続プールを取得します。未初期化の場合は初期化します。"""
    global _tag_db_pool

    if _tag_db_pool is None:
        try:
            db_url = get_tag_database_url()

            if not db_url:
                logger.error("TAG_MODERATION_DATABASE_URL環境変数が設定されていません")
                raise ValueError("TAG_MODERATION_DATABASE_URL環境変数が設定されていません")

            # 接続文字列を直接使用
            _tag_db_pool = await asyncpg.create_pool(db_url)
            logger.info("タグモデレーション専用データベース接続プールを初期化しました")
        except Exception as e:
            logger.error(f"タグモデレーション専用データベース接続に失敗しました: {e}")
            raise

    return _tag_db_pool


async def close_tag_db_pool():
    """タグモデレーション専用データベース接続プールを閉じます"""
    global _tag_db_pool

    if _tag_db_pool:
        await _tag_db_pool.close()
        _tag_db_pool = None
        logger.info("タグモデレーション専用データベース接続プールを閉じました")


async def execute_tag_query(query: str, *args, fetch_type: str = 'all') -> Any:
    """
    タグモデレーション専用データベースでSQL クエリを実行して結果を返します

    Args:
        query: 実行するSQLクエリ
        *args: クエリのパラメータ
        fetch_type: 取得タイプ ('all', 'row', 'val', 'status')

    Returns:
        fetch_typeによって異なる結果を返します
    """
    pool = await get_tag_db_pool()

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
