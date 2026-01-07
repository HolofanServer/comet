"""
Voice API ルーター

VC録音・Voice関連機能の管理
"""
from fastapi import APIRouter, Depends, HTTPException

from api.main import verify_api_key

router = APIRouter()


@router.get("/status", dependencies=[Depends(verify_api_key)])
async def get_voice_status():
    """Voice DBの状態"""
    from cogs.voice.db import voice_db

    return {
        "enabled": voice_db._initialized if hasattr(voice_db, "_initialized") else False,
    }


@router.get("/recordings/{guild_id}", dependencies=[Depends(verify_api_key)])
async def get_recordings(guild_id: str, limit: int = 20):
    """録音一覧を取得"""
    from cogs.voice.db import voice_db

    if not voice_db._initialized:
        raise HTTPException(status_code=503, detail="Voice DB not initialized")

    async with voice_db.pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT * FROM voice_recordings
            WHERE guild_id = $1
            ORDER BY created_at DESC
            LIMIT $2
        """, int(guild_id), limit)

    return {
        "recordings": [dict(row) for row in rows],
        "count": len(rows),
    }


@router.get("/active-sessions", dependencies=[Depends(verify_api_key)])
async def get_active_sessions():
    """アクティブな録音セッション"""
    from api.main import get_bot

    bot = get_bot()
    voice_cog = bot.get_cog("VoiceRecorder")

    if not voice_cog:
        return {"sessions": [], "error": "VoiceRecorder not loaded"}

    # アクティブセッションを取得
    if hasattr(voice_cog, "_active_sessions"):
        return {"sessions": list(voice_cog._active_sessions.keys())}

    return {"sessions": []}
