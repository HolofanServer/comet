"""
Database API ルーター

全DBの状態確認・クエリ実行
"""
import os

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from api.main import verify_api_key
from cogs.cp.db import checkpoint_db
from utils.database import get_db_pool

router = APIRouter()

# 追加DBのプール（遅延初期化）
_extra_pools: dict[str, asyncpg.Pool | None] = {
    "aus": None,
    "tag_moderation": None,
    "voice": None,
}


async def get_extra_pool(db_name: str) -> asyncpg.Pool | None:
    """追加DBのプールを取得（遅延初期化）"""
    global _extra_pools

    if db_name not in _extra_pools:
        return None

    if _extra_pools[db_name] is None:
        env_map = {
            "aus": "AUS_DATABASE_URL",
            "tag_moderation": "TAG_MODERATION_DATABASE_URL",
            "voice": "VOICE_DATABASE_URL",
        }
        url = os.getenv(env_map.get(db_name, ""))
        if url:
            if url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql://", 1)
            try:
                _extra_pools[db_name] = await asyncpg.create_pool(url, min_size=1, max_size=5)
            except Exception:
                return None

    return _extra_pools[db_name]


# ========== モデル ==========

class QueryRequest(BaseModel):
    """クエリ実行リクエスト"""
    query: str
    params: list | None = None


# ========== DB情報 ==========

DB_INFO = {
    "main": {
        "name": "メインDB",
        "description": "設定、スタッフDM、通知等",
        "env": "DATABASE_PUBLIC_URL",
    },
    "checkpoint": {
        "name": "Checkpoint DB",
        "description": "Rank、ログ収集、統計",
        "env": "CP_DATABASE_URL",
    },
    "aus": {
        "name": "AUS DB",
        "description": "無断転載検知",
        "env": "AUS_DATABASE_URL",
    },
    "tag_moderation": {
        "name": "タグモデレーションDB",
        "description": "タグ管理",
        "env": "TAG_MODERATION_DATABASE_URL",
    },
    "voice": {
        "name": "Voice DB",
        "description": "録音、Voice関連",
        "env": "VOICE_DATABASE_URL",
    },
}


# ========== エンドポイント ==========

@router.get("/status", dependencies=[Depends(verify_api_key)])
async def get_status():
    """全DBの接続状態を取得"""
    results = {}

    # Main DB
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        results["main"] = {"connected": True, **DB_INFO["main"]}
    except Exception as e:
        results["main"] = {"connected": False, "error": str(e), **DB_INFO["main"]}

    # Checkpoint DB
    if checkpoint_db._initialized:
        try:
            async with checkpoint_db.pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            results["checkpoint"] = {"connected": True, **DB_INFO["checkpoint"]}
        except Exception as e:
            results["checkpoint"] = {"connected": False, "error": str(e), **DB_INFO["checkpoint"]}
    else:
        results["checkpoint"] = {"connected": False, "error": "Not initialized", **DB_INFO["checkpoint"]}

    # 他のDBは必要に応じて追加
    for db_key in ["aus", "tag_moderation", "voice"]:
        results[db_key] = {"connected": False, "error": "Check not implemented", **DB_INFO[db_key]}

    return {"databases": results}


async def resolve_pool(db_name: str):
    """DB名からプールを解決"""
    if db_name == "main":
        return await get_db_pool()
    elif db_name == "checkpoint":
        if not checkpoint_db._initialized:
            raise HTTPException(status_code=503, detail="Checkpoint DB not initialized")
        return checkpoint_db.pool
    elif db_name in ("aus", "tag_moderation", "voice"):
        pool = await get_extra_pool(db_name)
        if not pool:
            raise HTTPException(status_code=503, detail=f"{db_name} DB not available")
        return pool
    else:
        raise HTTPException(status_code=400, detail=f"Unknown database: {db_name}")


@router.get("/tables/{db_name}", dependencies=[Depends(verify_api_key)])
async def get_tables(db_name: str):
    """テーブル一覧を取得"""
    pool = await resolve_pool(db_name)

    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT tablename FROM pg_tables
            WHERE schemaname = 'public'
            ORDER BY tablename
        """)

    tables = []
    for row in rows:
        table_name = row["tablename"]
        count = await pool.fetchval(f'SELECT COUNT(*) FROM "{table_name}"')
        tables.append({"name": table_name, "count": count})

    return {"tables": tables}


@router.get("/table/{db_name}/{table_name}", dependencies=[Depends(verify_api_key)])
async def get_table_data(
    db_name: str,
    table_name: str,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """テーブルのデータを取得"""
    pool = await resolve_pool(db_name)

    # カラム情報を取得
    async with pool.acquire() as conn:
        columns = await conn.fetch("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = $1
            ORDER BY ordinal_position
        """, table_name)

        # データを取得
        rows = await conn.fetch(
            f'SELECT * FROM "{table_name}" LIMIT $1 OFFSET $2',
            limit, offset
        )

        # 総件数
        total = await conn.fetchval(f'SELECT COUNT(*) FROM "{table_name}"')

    return {
        "columns": [{"name": c["column_name"], "type": c["data_type"]} for c in columns],
        "rows": [dict(row) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("/query/{db_name}", dependencies=[Depends(verify_api_key)])
async def execute_query(db_name: str, request: QueryRequest):
    """SQLクエリを実行（SELECTのみ）"""
    # SELECTのみ許可
    query = request.query.strip().upper()
    if not query.startswith("SELECT"):
        raise HTTPException(status_code=400, detail="Only SELECT queries allowed")

    pool = await resolve_pool(db_name)

    try:
        async with pool.acquire() as conn:
            if request.params:
                rows = await conn.fetch(request.query, *request.params)
            else:
                rows = await conn.fetch(request.query)

        return {
            "success": True,
            "rows": [dict(row) for row in rows],
            "count": len(rows),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
