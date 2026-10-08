"""
AUS (Art Unauthorized-repost Shield) API ルーター

無断転載検知システムの管理
"""
from fastapi import APIRouter, Depends, HTTPException

from api.main import verify_api_key

router = APIRouter()


@router.get("/status", dependencies=[Depends(verify_api_key)])
async def get_aus_status():
    """AUSシステムの状態"""
    from cogs.aus import aus_db

    if not aus_db._initialized:
        return {"enabled": False, "error": "AUS DB not initialized"}

    return {"enabled": True}


@router.get("/stats/{guild_id}", dependencies=[Depends(verify_api_key)])
async def get_aus_stats(guild_id: str):
    """AUS統計を取得"""
    from cogs.aus import aus_db

    if not aus_db._initialized:
        raise HTTPException(status_code=503, detail="AUS DB not initialized")

    async with aus_db.pool.acquire() as conn:
        # 検知数
        total_detections = await conn.fetchval("""
            SELECT COUNT(*) FROM aus_detections WHERE guild_id = $1
        """, int(guild_id))

        # 登録作品数
        registered_works = await conn.fetchval("""
            SELECT COUNT(*) FROM aus_registered_works WHERE guild_id = $1
        """, int(guild_id))

    return {
        "total_detections": total_detections or 0,
        "registered_works": registered_works or 0,
    }


@router.get("/config/{guild_id}", dependencies=[Depends(verify_api_key)])
async def get_aus_config(guild_id: str):
    """AUS設定を取得"""
    from cogs.aus import aus_db

    if not aus_db._initialized:
        raise HTTPException(status_code=503, detail="AUS DB not initialized")

    async with aus_db.pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT * FROM aus_config WHERE guild_id = $1
        """, int(guild_id))

    if not row:
        return {"configured": False}

    return {
        "configured": True,
        "enabled": row.get("is_enabled", True),
        "alert_channel_id": str(row["alert_channel_id"]) if row.get("alert_channel_id") else None,
        "excluded_channels": [str(c) for c in (row.get("excluded_channels") or [])],
    }


@router.get("/detections/{guild_id}", dependencies=[Depends(verify_api_key)])
async def get_recent_detections(guild_id: str, limit: int = 20):
    """最近の検知一覧"""
    from cogs.aus import aus_db

    if not aus_db._initialized:
        raise HTTPException(status_code=503, detail="AUS DB not initialized")

    async with aus_db.pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT * FROM aus_detections
            WHERE guild_id = $1
            ORDER BY detected_at DESC
            LIMIT $2
        """, int(guild_id), limit)

    return {
        "detections": [dict(row) for row in rows],
        "count": len(rows),
    }
