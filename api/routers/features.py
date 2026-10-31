"""
Features API ルーター

Bot機能の詳細設定（おみくじ、Giveaway、リアクション等）
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from api.main import get_bot, verify_api_key
from utils.database import get_db_pool

router = APIRouter()


async def safe_fetchval(conn, query: str, default=0):
    """テーブルが存在しない場合にデフォルト値を返す"""
    try:
        result = await conn.fetchval(query)
        return result if result is not None else default
    except Exception:
        return default


async def safe_fetch(conn, query: str, *args):
    """テーブルが存在しない場合に空リストを返す"""
    try:
        return await conn.fetch(query, *args)
    except Exception:
        return []


# ========== おみくじ ==========

@router.get("/omikuji/stats", dependencies=[Depends(verify_api_key)])
async def get_omikuji_stats():
    """おみくじ統計"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        total = await safe_fetchval(conn, "SELECT COUNT(*) FROM omikuji_results")
        today = await safe_fetchval(conn, """
            SELECT COUNT(*) FROM omikuji_results
            WHERE created_at::date = CURRENT_DATE
        """)
    return {"total": total, "today": today}


# ========== Giveaway ==========

@router.get("/giveaway/active", dependencies=[Depends(verify_api_key)])
async def get_active_giveaways():
    """アクティブなGiveaway一覧"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await safe_fetch(conn, """
            SELECT * FROM giveaways
            WHERE ended = false
            ORDER BY end_time ASC
        """)
    return {"giveaways": [dict(row) for row in rows], "count": len(rows)}


@router.get("/giveaway/history", dependencies=[Depends(verify_api_key)])
async def get_giveaway_history(limit: int = 10):
    """Giveaway履歴"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await safe_fetch(conn, """
            SELECT * FROM giveaways
            WHERE ended = true
            ORDER BY end_time DESC
            LIMIT $1
        """, limit)
    return {"giveaways": [dict(row) for row in rows]}


# ========== 自動リアクション ==========

@router.get("/auto-reaction/config", dependencies=[Depends(verify_api_key)])
async def get_auto_reaction_config():
    """自動リアクション設定"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await safe_fetch(conn, "SELECT * FROM auto_reactions ORDER BY created_at DESC")
    return {"reactions": [dict(row) for row in rows]}


class AutoReactionCreate(BaseModel):
    channel_id: str
    emoji: str
    match_pattern: str | None = None


@router.post("/auto-reaction/add", dependencies=[Depends(verify_api_key)])
async def add_auto_reaction(data: AutoReactionCreate):
    """自動リアクション追加"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO auto_reactions (channel_id, emoji, match_pattern)
            VALUES ($1, $2, $3)
        """, int(data.channel_id), data.emoji, data.match_pattern)
    return {"success": True}


# ========== スティッキーメッセージ ==========

@router.get("/sticky/list", dependencies=[Depends(verify_api_key)])
async def get_sticky_messages():
    """スティッキーメッセージ一覧"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await safe_fetch(conn, "SELECT * FROM sticky_messages ORDER BY created_at DESC")
    return {"messages": [dict(row) for row in rows]}


# ========== 推しロールパネル ==========

@router.get("/oshi-panel/stats", dependencies=[Depends(verify_api_key)])
async def get_oshi_panel_stats():
    """推しロールパネル統計"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        panels = await safe_fetchval(conn, "SELECT COUNT(*) FROM oshi_role_panels")
        assignments = await safe_fetchval(conn, "SELECT COUNT(*) FROM oshi_role_assignments")
    return {"panels": panels, "total_assignments": assignments}


# ========== バナー同期 ==========

@router.get("/banner/status", dependencies=[Depends(verify_api_key)])
async def get_banner_status():
    """バナー同期状態"""
    bot = get_bot()
    cog = bot.get_cog("BannerSync")
    if not cog:
        return {"enabled": False}
    return {
        "enabled": True,
        "is_running": cog.sync_banner.is_running() if hasattr(cog, "sync_banner") else False,
    }


# ========== VC通知 ==========

@router.get("/vc-notification/config", dependencies=[Depends(verify_api_key)])
async def get_vc_notification_config():
    """VC通知設定"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM vc_notification_config LIMIT 1")
    if not row:
        return {"configured": False}
    return {"configured": True, **dict(row)}


# ========== 国別ウェルカム ==========

@router.get("/welcome/stats", dependencies=[Depends(verify_api_key)])
async def get_welcome_stats():
    """ウェルカムメッセージ統計"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        total = await safe_fetchval(conn, "SELECT COUNT(*) FROM welcome_messages_sent")
        recent = await safe_fetchval(conn, """
            SELECT COUNT(*) FROM welcome_messages_sent
            WHERE sent_at > NOW() - INTERVAL '7 days'
        """)
    return {"total_sent": total, "last_7_days": recent}


# ========== タグモデレーション ==========

@router.get("/tag-moderation/stats", dependencies=[Depends(verify_api_key)])
async def get_tag_moderation_stats():
    """タグモデレーション統計"""
    bot = get_bot()
    cog = bot.get_cog("TagModerationCog")
    if not cog:
        return {"enabled": False}
    return {"enabled": True}


# ========== 画像検知 (AUS) ==========

@router.get("/image-detection/stats", dependencies=[Depends(verify_api_key)])
async def get_image_detection_stats():
    """画像検知統計"""
    bot = get_bot()
    aus_cog = bot.get_cog("ImageDetection")
    if not aus_cog:
        return {"enabled": False}
    return {"enabled": True}


# ========== レポート ==========

@router.get("/report/stats", dependencies=[Depends(verify_api_key)])
async def get_report_stats():
    """レポート統計"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        total = await safe_fetchval(conn, "SELECT COUNT(*) FROM reports")
        pending = await safe_fetchval(conn, "SELECT COUNT(*) FROM reports WHERE status = 'pending'")
        resolved = await safe_fetchval(conn, "SELECT COUNT(*) FROM reports WHERE status = 'resolved'")
    return {"total": total, "pending": pending, "resolved": resolved}


@router.get("/report/users", dependencies=[Depends(verify_api_key)])
async def get_user_reports():
    """ユーザーレポート一覧"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await safe_fetch(conn, """
            SELECT * FROM reports
            WHERE target_type = 'user'
            ORDER BY created_at DESC
            LIMIT 50
        """)
    return {"reports": [dict(row) for row in rows]}


@router.get("/report/messages", dependencies=[Depends(verify_api_key)])
async def get_message_reports():
    """メッセージレポート一覧"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await safe_fetch(conn, """
            SELECT * FROM reports
            WHERE target_type = 'message'
            ORDER BY created_at DESC
            LIMIT 50
        """)
    return {"reports": [dict(row) for row in rows]}


# ========== AUS (無断転載検知) ==========

@router.get("/aus/artists", dependencies=[Depends(verify_api_key)])
async def get_aus_artists():
    """認証済み絵師一覧"""
    from cogs.aus.database import DatabaseManager
    db = DatabaseManager()
    try:
        await db.initialize()
        artists = await db.get_all_verified_artists()
        return {"artists": artists}
    except Exception:
        return {"artists": []}
    finally:
        await db.close()


@router.get("/aus/tickets", dependencies=[Depends(verify_api_key)])
async def get_aus_tickets():
    """認証申請チケット一覧"""
    from cogs.aus.database import DatabaseManager
    db = DatabaseManager()
    try:
        await db.initialize()
        tickets = await db.get_all_pending_tickets()
        return {"tickets": tickets}
    except Exception:
        return {"tickets": []}
    finally:
        await db.close()


@router.get("/aus/stats", dependencies=[Depends(verify_api_key)])
async def get_aus_stats():
    """AUS統計"""
    from cogs.aus.database import DatabaseManager
    db = DatabaseManager()
    try:
        await db.initialize()
        artists = await db.get_all_verified_artists()
        stats = await db.get_ticket_stats()
        return {
            "verified_artists": len(artists),
            "pending_tickets": stats.get("pending", 0),
            "approved_tickets": stats.get("approved", 0),
            "rejected_tickets": stats.get("rejected", 0),
        }
    except Exception:
        return {"verified_artists": 0, "pending_tickets": 0, "approved_tickets": 0, "rejected_tickets": 0}
    finally:
        await db.close()


# ========== Note通知 ==========

@router.get("/note/notifications", dependencies=[Depends(verify_api_key)])
async def get_note_notifications():
    """Note通知設定一覧"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await safe_fetch(conn, "SELECT * FROM note_notifications ORDER BY created_at DESC")
    return {"notifications": [dict(row) for row in rows]}


@router.get("/note/stats", dependencies=[Depends(verify_api_key)])
async def get_note_stats():
    """Note通知統計"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        total = await safe_fetchval(conn, "SELECT COUNT(*) FROM note_notifications")
        enabled = await safe_fetchval(conn, "SELECT COUNT(*) FROM note_notifications WHERE enabled = true")
        channels = await safe_fetchval(conn, "SELECT COUNT(DISTINCT channel_id) FROM note_notifications")
    return {"total_notifications": total, "enabled": enabled, "channels": channels}


# ========== ホームページ連携 ==========

@router.get("/homepage/staff", dependencies=[Depends(verify_api_key)])
async def get_homepage_staff():
    """スタッフ一覧"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await safe_fetch(conn, "SELECT * FROM staff_members ORDER BY added_at DESC")
    return {"staff": [dict(row) for row in rows]}


@router.get("/homepage/member-cards", dependencies=[Depends(verify_api_key)])
async def get_member_cards():
    """メンバーカード一覧"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await safe_fetch(conn, "SELECT * FROM member_cards ORDER BY created_at DESC LIMIT 50")
    return {"cards": [dict(row) for row in rows]}


@router.get("/homepage/stats", dependencies=[Depends(verify_api_key)])
async def get_homepage_stats():
    """ホームページ連携統計"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        staff = await safe_fetchval(conn, "SELECT COUNT(*) FROM staff_members")
        cards = await safe_fetchval(conn, "SELECT COUNT(*) FROM member_cards")
    return {"staff_count": staff, "member_cards": cards}


# ========== Giveaway (拡張) ==========

@router.get("/giveaways", dependencies=[Depends(verify_api_key)])
async def get_all_giveaways():
    """全Giveaway一覧"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await safe_fetch(conn, """
            SELECT g.*,
                   (SELECT COUNT(*) FROM giveaway_entries WHERE giveaway_id = g.id) as participants_count
            FROM giveaways g
            ORDER BY g.end_time DESC
            LIMIT 50
        """)
    return {"giveaways": [dict(row) for row in rows]}


@router.get("/giveaways/stats", dependencies=[Depends(verify_api_key)])
async def get_giveaway_stats():
    """Giveaway統計"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        total = await safe_fetchval(conn, "SELECT COUNT(*) FROM giveaways")
        active = await safe_fetchval(conn, "SELECT COUNT(*) FROM giveaways WHERE ended = false")
        participants = await safe_fetchval(conn, "SELECT COUNT(*) FROM giveaway_entries")
    return {"total": total, "active": active, "total_participants": participants}


# ========== 自動リアクション (拡張) ==========

@router.get("/auto-reactions", dependencies=[Depends(verify_api_key)])
async def get_all_auto_reactions():
    """自動リアクション一覧"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await safe_fetch(conn, "SELECT * FROM auto_reactions ORDER BY created_at DESC")
    return {"reactions": [dict(row) for row in rows]}
