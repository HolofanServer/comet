"""
Manage API ルーター

匿名DM、警告システム等の管理機能
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from api.main import verify_api_key
from utils.database import get_db_pool

router = APIRouter()


async def safe_fetch(conn, query: str, *args):
    """テーブルが存在しない場合に空リストを返す"""
    try:
        return await conn.fetch(query, *args)
    except Exception:
        return []


async def safe_fetchrow(conn, query: str, *args):
    """テーブルが存在しない場合にNoneを返す"""
    try:
        return await conn.fetchrow(query, *args)
    except Exception:
        return None


# ========== 匿名DM ==========

@router.get("/anon-dm/sessions/{guild_id}", dependencies=[Depends(verify_api_key)])
async def get_anon_dm_sessions(guild_id: str):
    """アクティブな匿名DMセッション一覧"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await safe_fetch(conn, """
            SELECT * FROM anon_dm_sessions
            WHERE guild_id = $1 AND status = 'active'
            ORDER BY created_at DESC
        """, int(guild_id))
    return {
        "sessions": [dict(row) for row in rows],
        "count": len(rows),
    }


@router.get("/anon-dm/config/{guild_id}", dependencies=[Depends(verify_api_key)])
async def get_anon_dm_config(guild_id: str):
    """匿名DM設定を取得"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await safe_fetchrow(conn, """
            SELECT * FROM anon_dm_categories WHERE guild_id = $1
        """, int(guild_id))
    if not row:
        return {"configured": False}
    return {
        "configured": True,
        "category_id": str(row["category_id"]) if row.get("category_id") else None,
        "log_channel_id": str(row["log_channel_id"]) if row.get("log_channel_id") else None,
    }


# ========== 警告システム ==========

@router.get("/warning/config/{guild_id}", dependencies=[Depends(verify_api_key)])
async def get_warning_config(guild_id: str):
    """警告システム設定を取得"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await safe_fetchrow(conn, """
            SELECT * FROM user_warning_config WHERE guild_id = $1
        """, int(guild_id))
    if not row:
        return {"configured": False, "watched_users": [], "excluded_channels": []}
    return {
        "configured": True,
        "warning_channel_id": str(row["warning_channel_id"]) if row.get("warning_channel_id") else None,
        "watched_users": [str(u) for u in (row.get("watched_users") or [])],
        "excluded_channels": [str(c) for c in (row.get("excluded_channels") or [])],
    }


class WatchedUserUpdate(BaseModel):
    user_id: str
    action: str  # "add" or "remove"


@router.post("/warning/watched-users/{guild_id}", dependencies=[Depends(verify_api_key)])
async def update_watched_users(guild_id: str, data: WatchedUserUpdate):
    """監視対象ユーザーを追加/削除"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        if data.action == "add":
            await conn.execute("""
                UPDATE user_warning_config
                SET watched_users = array_append(watched_users, $2::BIGINT)
                WHERE guild_id = $1 AND NOT ($2::BIGINT = ANY(watched_users))
            """, int(guild_id), int(data.user_id))
        elif data.action == "remove":
            await conn.execute("""
                UPDATE user_warning_config
                SET watched_users = array_remove(watched_users, $2::BIGINT)
                WHERE guild_id = $1
            """, int(guild_id), int(data.user_id))
    return {"success": True}
