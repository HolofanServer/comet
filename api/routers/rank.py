"""
Rank API ルーター
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from api.main import get_bot, verify_api_key
from cogs.rank.models import rank_db

router = APIRouter()


# ========== モデル ==========

class RankConfigUpdate(BaseModel):
    """Rank設定更新リクエスト"""
    message_xp: int | None = None
    omikuji_xp: int | None = None
    vc_xp_per_10min: int | None = None
    message_cooldown_seconds: int | None = None
    is_enabled: bool | None = None
    streak_bonus_enabled: bool | None = None
    quality_bonus_enabled: bool | None = None


class ChannelMultiplierUpdate(BaseModel):
    """チャンネル倍率更新"""
    channel_id: str
    multiplier: float


class GlobalMultiplierUpdate(BaseModel):
    """グローバル倍率更新"""
    multiplier: float


class XPUpdate(BaseModel):
    """XP更新"""
    user_id: str
    yearly_xp: int | None = None
    lifetime_xp: int | None = None


# ========== エンドポイント ==========

@router.get("/config/{guild_id}", dependencies=[Depends(verify_api_key)])
async def get_config(guild_id: str):
    """Rank設定を取得"""
    config = await rank_db.get_config(int(guild_id))
    return {
        "guild_id": str(config.guild_id),
        "message_xp": config.message_xp,
        "message_cooldown_seconds": config.message_cooldown_seconds,
        "omikuji_xp": config.omikuji_xp,
        "vc_xp_per_10min": config.vc_xp_per_10min,
        "regular_xp_threshold": config.regular_xp_threshold,
        "regular_days_threshold": config.regular_days_threshold,
        "regular_role_id": str(config.regular_role_id) if config.regular_role_id else None,
        "excluded_channels": [str(c) for c in (config.excluded_channels or [])],
        "excluded_roles": [str(r) for r in (config.excluded_roles or [])],
        "is_enabled": config.is_enabled,
        "streak_bonus_enabled": config.streak_bonus_enabled,
        "quality_bonus_enabled": config.quality_bonus_enabled,
        "channel_multipliers": config.channel_multipliers,
        "global_multiplier": config.global_multiplier,
    }


@router.patch("/config/{guild_id}", dependencies=[Depends(verify_api_key)])
async def update_config(guild_id: str, update: RankConfigUpdate):
    """Rank設定を更新"""
    updates = {k: v for k, v in update.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")

    success = await rank_db.update_xp_settings(
        int(guild_id),
        message_xp=updates.get("message_xp"),
        omikuji_xp=updates.get("omikuji_xp"),
        vc_xp=updates.get("vc_xp_per_10min"),
        cooldown=updates.get("message_cooldown_seconds"),
    )
    return {"success": success}


@router.post("/config/{guild_id}/channel-multiplier", dependencies=[Depends(verify_api_key)])
async def set_channel_multiplier(guild_id: str, data: ChannelMultiplierUpdate):
    """チャンネル倍率を設定"""
    if data.multiplier < 0.5 or data.multiplier > 3.0:
        raise HTTPException(status_code=400, detail="Multiplier must be between 0.5 and 3.0")

    success = await rank_db.update_channel_multiplier(
        int(guild_id), int(data.channel_id), data.multiplier
    )
    return {"success": success}


@router.post("/config/{guild_id}/global-multiplier", dependencies=[Depends(verify_api_key)])
async def set_global_multiplier(guild_id: str, data: GlobalMultiplierUpdate):
    """グローバル倍率を設定（イベント用）"""
    if data.multiplier < 1.0 or data.multiplier > 5.0:
        raise HTTPException(status_code=400, detail="Multiplier must be between 1.0 and 5.0")

    success = await rank_db.update_global_multiplier(int(guild_id), data.multiplier)
    return {"success": success}


@router.get("/rankings/{guild_id}", dependencies=[Depends(verify_api_key)])
async def get_rankings(
    guild_id: str,
    limit: int = Query(default=10, ge=1, le=100),
    order_by: str = Query(default="yearly_xp"),
):
    """ランキングを取得"""
    if order_by not in ("yearly_xp", "lifetime_xp", "active_days"):
        order_by = "yearly_xp"

    rankings = await rank_db.get_rankings(int(guild_id), limit, order_by)

    # ユーザー名を取得
    bot = get_bot()
    result = []
    for user in rankings:
        username = f"User#{user.user_id}"
        try:
            discord_user = await bot.fetch_user(user.user_id)
            username = discord_user.display_name
        except Exception:
            pass

        result.append({
            "user_id": str(user.user_id),
            "username": username,
            "yearly_xp": user.yearly_xp,
            "lifetime_xp": user.lifetime_xp,
            "current_level": user.current_level,
            "active_days": user.active_days,
            "current_streak": user.current_streak,
            "is_regular": user.is_regular,
        })

    return {"rankings": result}


@router.get("/user/{guild_id}/{user_id}", dependencies=[Depends(verify_api_key)])
async def get_user(guild_id: str, user_id: str):
    """ユーザー情報を取得"""
    user = await rank_db.get_user(int(user_id), int(guild_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    rank = await rank_db.get_user_rank(int(user_id), int(guild_id))

    return {
        "user_id": str(user.user_id),
        "guild_id": str(user.guild_id),
        "yearly_xp": user.yearly_xp,
        "lifetime_xp": user.lifetime_xp,
        "current_level": user.current_level,
        "active_days": user.active_days,
        "current_streak": user.current_streak,
        "is_regular": user.is_regular,
        "rank": rank,
    }


@router.patch("/user/{guild_id}/{user_id}/xp", dependencies=[Depends(verify_api_key)])
async def update_user_xp(guild_id: str, user_id: str, data: XPUpdate):
    """ユーザーのXPを更新"""
    success = await rank_db.set_xp(
        int(user_id), int(guild_id),
        yearly_xp=data.yearly_xp,
        lifetime_xp=data.lifetime_xp,
    )
    return {"success": success}


@router.post("/user/{guild_id}/{user_id}/reset", dependencies=[Depends(verify_api_key)])
async def reset_user(guild_id: str, user_id: str):
    """ユーザーをリセット"""
    success = await rank_db.reset_user(int(user_id), int(guild_id))
    return {"success": success}


@router.get("/stats/{guild_id}", dependencies=[Depends(verify_api_key)])
async def get_stats(guild_id: str):
    """Rank統計を取得"""
    from cogs.cp.db import checkpoint_db

    total_users = 0
    active_today = 0

    if checkpoint_db._initialized:
        async with checkpoint_db.pool.acquire() as conn:
            total_users = await conn.fetchval(
                "SELECT COUNT(*) FROM rank_users WHERE guild_id = $1",
                int(guild_id)
            )
            active_today = await conn.fetchval(
                "SELECT COUNT(*) FROM rank_users WHERE guild_id = $1 AND last_active_date = CURRENT_DATE",
                int(guild_id)
            )

    return {
        "total_users": total_users or 0,
        "active_today": active_today or 0,
    }
