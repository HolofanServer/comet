"""
Bot設定 API ルーター

各Cogの設定を管理
"""
import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.main import get_bot, verify_api_key
from utils.database import get_db_pool

router = APIRouter()

# セキュリティ: Extension操作の許可リスト
# 環境変数で設定可能（カンマ区切り）、未設定の場合はすべて拒否
_allowed_extensions_env = os.environ.get("ALLOWED_EXTENSIONS", "")
ALLOWED_EXTENSIONS: set[str] = {
    ext.strip() for ext in _allowed_extensions_env.split(",") if ext.strip()
} if _allowed_extensions_env else set()

# セキュリティ: Extension操作を完全に無効化するフラグ
EXTENSION_MANAGEMENT_ENABLED = os.environ.get(
    "EXTENSION_MANAGEMENT_ENABLED", "false"
).lower() == "true"


# ========== モデル ==========

class GuildSettings(BaseModel):
    """サーバー設定"""
    guild_id: str
    settings: dict


# ========== エンドポイント ==========

@router.get("/guild/{guild_id}", dependencies=[Depends(verify_api_key)])
async def get_guild_settings(guild_id: str):
    """サーバーの全設定を取得"""
    bot = get_bot()
    guild = bot.get_guild(int(guild_id))

    if not guild:
        raise HTTPException(status_code=404, detail="Guild not found")

    pool = await get_db_pool()

    # 各機能の設定を収集
    settings = {}

    # 匿名DM設定
    async with pool.acquire() as conn:
        anon_dm = await conn.fetchrow(
            "SELECT * FROM anon_dm_categories WHERE guild_id = $1",
            int(guild_id)
        )
        if anon_dm:
            settings["anonymous_dm"] = {
                "enabled": True,
                "category_id": str(anon_dm.get("category_id")) if anon_dm.get("category_id") else None,
            }
        else:
            settings["anonymous_dm"] = {"enabled": False}

    # Rank設定
    from cogs.rank.models import rank_db
    rank_config = await rank_db.get_config(int(guild_id))
    settings["rank"] = {
        "enabled": rank_config.is_enabled,
        "message_xp": rank_config.message_xp,
        "streak_bonus": rank_config.streak_bonus_enabled,
        "quality_bonus": rank_config.quality_bonus_enabled,
        "global_multiplier": rank_config.global_multiplier,
    }

    # Checkpoint設定
    from cogs.cp.db import checkpoint_db
    if checkpoint_db._initialized:
        async with checkpoint_db.pool.acquire() as conn:
            cp_config = await conn.fetchrow(
                "SELECT * FROM cp_config WHERE guild_id = $1",
                int(guild_id)
            )
            settings["checkpoint"] = {
                "enabled": cp_config.get("is_enabled", True) if cp_config else True,
            }

    return {
        "guild_id": guild_id,
        "guild_name": guild.name,
        "settings": settings,
    }


@router.get("/cogs", dependencies=[Depends(verify_api_key)])
async def get_all_cogs():
    """全Cogの一覧と状態を取得"""
    bot = get_bot()

    cogs_info = []
    for name, cog in bot.cogs.items():
        cog_info = {
            "name": name,
            "qualified_name": cog.qualified_name,
            "description": cog.description or "",
            "commands": [],
        }

        # アプリコマンドを取得
        if hasattr(cog, "__cog_app_commands__"):
            for cmd in cog.__cog_app_commands__:
                cog_info["commands"].append({
                    "name": cmd.name,
                    "description": cmd.description,
                })

        cogs_info.append(cog_info)

    return {"cogs": cogs_info}


@router.get("/extensions", dependencies=[Depends(verify_api_key)])
async def get_extensions():
    """ロード可能なExtensionの一覧"""
    import os

    extensions = []
    cogs_dir = "cogs"

    for category in os.listdir(cogs_dir):
        category_path = os.path.join(cogs_dir, category)
        if not os.path.isdir(category_path) or category.startswith("_"):
            continue

        for filename in os.listdir(category_path):
            if filename.endswith(".py") and not filename.startswith("_"):
                ext_name = f"cogs.{category}.{filename[:-3]}"
                extensions.append({
                    "name": ext_name,
                    "category": category,
                    "loaded": ext_name in list(get_bot().extensions),
                })

    return {"extensions": extensions}


def _check_extension_allowed(extension_name: str) -> None:
    """
    Extension操作が許可されているかチェックする

    Args:
        extension_name: チェックするExtension名

    Raises:
        HTTPException: 操作が許可されていない場合
    """
    if not EXTENSION_MANAGEMENT_ENABLED:
        raise HTTPException(
            status_code=403,
            detail="Extension management is disabled. Set EXTENSION_MANAGEMENT_ENABLED=true to enable."
        )
    if ALLOWED_EXTENSIONS and extension_name not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=403,
            detail=f"Extension '{extension_name}' is not in the allowed list"
        )


@router.post("/extensions/{extension_name}/load", dependencies=[Depends(verify_api_key)])
async def load_extension(extension_name: str):
    """Extensionをロード（セキュリティ: 許可リストで制限）"""
    _check_extension_allowed(extension_name)
    bot = get_bot()
    try:
        await bot.load_extension(extension_name)
        return {"success": True, "message": f"Loaded {extension_name}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/extensions/{extension_name}/unload", dependencies=[Depends(verify_api_key)])
async def unload_extension(extension_name: str):
    """Extensionをアンロード（セキュリティ: 許可リストで制限）"""
    _check_extension_allowed(extension_name)
    bot = get_bot()
    try:
        await bot.unload_extension(extension_name)
        return {"success": True, "message": f"Unloaded {extension_name}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/extensions/{extension_name}/reload", dependencies=[Depends(verify_api_key)])
async def reload_extension(extension_name: str):
    """Extensionをリロード（セキュリティ: 許可リストで制限）"""
    _check_extension_allowed(extension_name)
    bot = get_bot()
    try:
        await bot.reload_extension(extension_name)
        return {"success": True, "message": f"Reloaded {extension_name}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
