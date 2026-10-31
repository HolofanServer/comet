"""
Checkpoint API ルーター

ログ収集・統計機能の管理
"""
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query

from api.main import verify_api_key
from cogs.cp.db import checkpoint_db

router = APIRouter()


@router.get("/status", dependencies=[Depends(verify_api_key)])
async def get_cp_status():
    """Checkpoint DBの状態"""
    return {"enabled": checkpoint_db._initialized}


@router.get("/config/{guild_id}", dependencies=[Depends(verify_api_key)])
async def get_cp_config(guild_id: str):
    """Checkpoint設定を取得"""
    if not checkpoint_db._initialized:
        raise HTTPException(status_code=503, detail="Checkpoint DB not initialized")

    async with checkpoint_db.pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM cp_config WHERE guild_id = $1",
            int(guild_id)
        )

    if not row:
        return {"configured": False, "is_enabled": True}

    return {
        "configured": True,
        "is_enabled": row.get("is_enabled", True),
        "excluded_channels": [str(c) for c in (row.get("excluded_channels") or [])],
    }


@router.get("/stats/{guild_id}", dependencies=[Depends(verify_api_key)])
async def get_guild_stats(guild_id: str, days: int = Query(default=7, ge=1, le=30)):
    """サーバー統計を取得"""
    if not checkpoint_db._initialized:
        raise HTTPException(status_code=503, detail="Checkpoint DB not initialized")

    start_date = date.today() - timedelta(days=days)

    async with checkpoint_db.pool.acquire() as conn:
        # メッセージ数
        messages = await conn.fetchval("""
            SELECT COUNT(*) FROM cp_message_logs
            WHERE guild_id = $1 AND created_at >= $2
        """, int(guild_id), start_date)

        # アクティブユーザー数
        active_users = await conn.fetchval("""
            SELECT COUNT(DISTINCT user_id) FROM cp_daily_stats
            WHERE guild_id = $1 AND stat_date >= $2
        """, int(guild_id), start_date)

        # リアクション数
        reactions = await conn.fetchval("""
            SELECT COUNT(*) FROM cp_reaction_logs
            WHERE guild_id = $1 AND created_at >= $2
        """, int(guild_id), start_date)

        # VC時間（秒）
        vc_seconds = await conn.fetchval("""
            SELECT COALESCE(SUM(vc_seconds), 0) FROM cp_daily_stats
            WHERE guild_id = $1 AND stat_date >= $2
        """, int(guild_id), start_date)

    return {
        "period_days": days,
        "messages": messages or 0,
        "active_users": active_users or 0,
        "reactions": reactions or 0,
        "vc_hours": round((vc_seconds or 0) / 3600, 1),
    }


@router.get("/user/{guild_id}/{user_id}/stats", dependencies=[Depends(verify_api_key)])
async def get_user_stats(guild_id: str, user_id: str, days: int = Query(default=30, ge=1, le=90)):
    """ユーザー統計を取得"""
    if not checkpoint_db._initialized:
        raise HTTPException(status_code=503, detail="Checkpoint DB not initialized")

    stats = await checkpoint_db.get_daily_stats(int(user_id), int(guild_id), days)

    return {
        "user_id": user_id,
        "period_days": days,
        "stats": [
            {
                "date": s.stat_date,
                "messages": s.message_count,
                "reactions": s.reaction_count,
                "vc_seconds": s.vc_seconds,
                "mentions_sent": s.mention_sent_count,
                "mentions_received": s.mention_received_count,
            }
            for s in stats
        ],
    }


@router.get("/top-users/{guild_id}", dependencies=[Depends(verify_api_key)])
async def get_top_users(guild_id: str, days: int = Query(default=7, ge=1, le=30), limit: int = Query(default=10, ge=1, le=50)):
    """アクティブユーザーランキング"""
    if not checkpoint_db._initialized:
        raise HTTPException(status_code=503, detail="Checkpoint DB not initialized")

    start_date = date.today() - timedelta(days=days)

    async with checkpoint_db.pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT user_id, SUM(message_count) as total_messages
            FROM cp_daily_stats
            WHERE guild_id = $1 AND stat_date >= $2
            GROUP BY user_id
            ORDER BY total_messages DESC
            LIMIT $3
        """, int(guild_id), start_date, limit)

    return {
        "top_users": [
            {"user_id": str(row["user_id"]), "messages": row["total_messages"]}
            for row in rows
        ],
    }
