"""
Stream API ルーター

配信通知システムの管理
"""
from fastapi import APIRouter, Depends

from api.main import get_bot, verify_api_key

router = APIRouter()


@router.get("/status", dependencies=[Depends(verify_api_key)])
async def get_stream_status():
    """配信通知システムの状態"""
    bot = get_bot()

    # StreamNotifier Cogを取得
    stream_cog = bot.get_cog("StreamNotifier")
    if not stream_cog:
        return {"enabled": False, "error": "StreamNotifier not loaded"}

    return {
        "enabled": True,
        "is_running": stream_cog.check_streams.is_running() if hasattr(stream_cog, "check_streams") else False,
    }


@router.get("/live", dependencies=[Depends(verify_api_key)])
async def get_live_streams():
    """現在のライブ配信一覧"""
    bot = get_bot()
    stream_cog = bot.get_cog("StreamNotifier")

    if not stream_cog:
        return {"streams": [], "error": "StreamNotifier not loaded"}

    # キャッシュから取得
    if hasattr(stream_cog, "_live_cache"):
        return {"streams": list(stream_cog._live_cache.keys())}

    return {"streams": []}


@router.get("/config/{guild_id}", dependencies=[Depends(verify_api_key)])
async def get_stream_config(guild_id: str):
    """配信通知設定を取得"""
    import os

    # 環境変数から設定を取得
    return {
        "jp_channel": os.environ.get("HOLODEX_STREAM_JP_CHANNEL_ID"),
        "en_channel": os.environ.get("HOLODEX_STREAM_EN_CHANNEL_ID"),
        "id_channel": os.environ.get("HOLODEX_STREAM_ID_CHANNEL_ID"),
        "dev_is_channel": os.environ.get("HOLODEX_STREAM_DEV_IS_CHANNEL_ID"),
    }


@router.post("/refresh", dependencies=[Depends(verify_api_key)])
async def refresh_streams():
    """配信情報を手動で更新"""
    bot = get_bot()
    stream_cog = bot.get_cog("StreamNotifier")

    if not stream_cog:
        return {"success": False, "error": "StreamNotifier not loaded"}

    # 手動で配信チェックを実行
    if hasattr(stream_cog, "_check_streams"):
        await stream_cog._check_streams()
        return {"success": True}

    return {"success": False, "error": "Method not found"}
