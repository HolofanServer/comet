"""
HFS Bot 管理API

ダッシュボードからBotの全機能を管理するためのFastAPI
"""
import os
import secrets
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader

from config.setting import get_settings
from utils.logging import setup_logging

logger = setup_logging(__name__)
settings = get_settings()

# APIキー認証
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str = Security(API_KEY_HEADER)):
    """APIキーを検証（タイミング攻撃対策済み）"""
    expected_key = os.environ.get("DASHBOARD_API_KEY")
    if not expected_key:
        raise HTTPException(status_code=500, detail="API key not configured")
    if not api_key:
        raise HTTPException(status_code=401, detail="API key required")
    # タイミング攻撃を防ぐため、secrets.compare_digestを使用
    if not secrets.compare_digest(api_key.encode('utf-8'), expected_key.encode('utf-8')):
        raise HTTPException(status_code=401, detail="Invalid API key")
    return api_key


# Botインスタンスへの参照（main.pyから設定される）
_bot = None

def set_bot(bot):
    """Botインスタンスを設定"""
    global _bot
    _bot = bot

def get_bot():
    """Botインスタンスを取得"""
    if _bot is None:
        raise HTTPException(status_code=503, detail="Bot not ready")
    return _bot


@asynccontextmanager
async def lifespan(app: FastAPI):
    """APIライフサイクル"""
    logger.info("🚀 管理API起動")
    yield
    logger.info("🛑 管理API停止")


# FastAPIアプリ
app = FastAPI(
    title="C.O.M.E.T 管理API",
    description="ダッシュボードからBotの全機能を管理",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.api_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ========== ヘルスチェック ==========

@app.get("/health")
async def health_check():
    """ヘルスチェック"""
    bot = None
    try:
        bot = get_bot()
    except Exception:
        pass

    return {
        "status": "ok",
        "bot_ready": bot is not None and bot.is_ready() if bot else False,
        "guilds": len(bot.guilds) if bot else 0,
    }


# ========== Botステータス ==========

@app.get("/bot/status", dependencies=[Depends(verify_api_key)])
async def get_bot_status():
    """Botの現在の状態を取得"""
    bot = get_bot()

    return {
        "name": bot.user.name if bot.user else "Unknown",
        "id": str(bot.user.id) if bot.user else None,
        "guilds": len(bot.guilds),
        "latency_ms": round(bot.latency * 1000, 2),
        "is_ready": bot.is_ready(),
    }


@app.get("/bot/guilds", dependencies=[Depends(verify_api_key)])
async def get_guilds():
    """接続中のサーバー一覧"""
    bot = get_bot()

    return {
        "guilds": [
            {
                "id": str(g.id),
                "name": g.name,
                "member_count": g.member_count,
                "icon_url": str(g.icon.url) if g.icon else None,
            }
            for g in bot.guilds
        ]
    }


# ========== Cog管理 ==========

@app.get("/bot/cogs", dependencies=[Depends(verify_api_key)])
async def get_cogs():
    """ロードされているCog一覧"""
    bot = get_bot()

    return {
        "cogs": [
            {
                "name": name,
                "qualified_name": cog.qualified_name,
                "description": cog.description or "",
            }
            for name, cog in bot.cogs.items()
        ]
    }


@app.post("/bot/cogs/{cog_name}/reload", dependencies=[Depends(verify_api_key)])
async def reload_cog(cog_name: str):
    """Cogをリロード"""
    bot = get_bot()

    # Cog名からextension名を推測
    extension_map = {
        "RankCommands": "cogs.rank.ranking",
        "RankLogging": "cogs.rank.logging",
        # 他のCogも追加
    }

    extension = extension_map.get(cog_name)
    if not extension:
        raise HTTPException(status_code=404, detail=f"Cog '{cog_name}' not found")

    try:
        await bot.reload_extension(extension)
        return {"success": True, "message": f"Reloaded {cog_name}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


# ========== ルーター登録 ==========

from api.routers import (  # noqa: E402
    aus,
    checkpoint,
    database,
    features,
    manage,
    rank,
    settings,
    stream,
    voice,
)

app.include_router(rank.router, prefix="/rank", tags=["Rank"])
app.include_router(database.router, prefix="/db", tags=["Database"])
app.include_router(settings.router, prefix="/settings", tags=["Settings"])
app.include_router(manage.router, prefix="/manage", tags=["Manage"])
app.include_router(stream.router, prefix="/stream", tags=["Stream"])
app.include_router(aus.router, prefix="/aus", tags=["AUS"])
app.include_router(voice.router, prefix="/voice", tags=["Voice"])
app.include_router(checkpoint.router, prefix="/checkpoint", tags=["Checkpoint"])
app.include_router(features.router, prefix="/features", tags=["Features"])
