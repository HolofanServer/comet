"""
Database API ルーター

全DBの状態確認・クエリ実行
"""
import os
import re

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from api.main import verify_api_key
from cogs.cp.db import checkpoint_db
from utils.database import get_db_pool

router = APIRouter()

# セキュリティ: テーブル名の検証用正規表現（英数字とアンダースコアのみ許可）
TABLE_NAME_PATTERN = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')


def validate_table_name(table_name: str) -> bool:
    """
    テーブル名が安全かどうかを検証する

    Args:
        table_name: 検証するテーブル名

    Returns:
        テーブル名が安全な場合True
    """
    if not table_name or len(table_name) > 128:
        return False
    if not TABLE_NAME_PATTERN.match(table_name):
        return False
    # セキュリティ: PostgreSQLの内部テーブルや拡張機能のテーブルへのアクセスを防止
    if table_name.startswith(("_pg_", "_timescaledb_")):
        return False
    return True

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
        # セキュリティ: pg_tablesから取得したテーブル名も検証
        if not validate_table_name(table_name):
            continue
        # パラメータ化クエリは識別子に使えないため、検証済みのテーブル名を使用
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
    # セキュリティ: テーブル名を検証してSQLインジェクションを防止
    if not validate_table_name(table_name):
        raise HTTPException(status_code=400, detail="Invalid table name")

    pool = await resolve_pool(db_name)

    # カラム情報を取得
    async with pool.acquire() as conn:
        columns = await conn.fetch("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = $1
            ORDER BY ordinal_position
        """, table_name)

        # データを取得（検証済みのテーブル名を使用）
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


def _normalize_query_for_security(query: str) -> str:
    """
    セキュリティチェック用にクエリを正規化する

    SQLコメントを除去し、連続する空白を1つにまとめる
    これにより、コメントや空白を使ったキーワードバイパスを防止する
    """
    # ブロックコメント /* ... */ を除去
    normalized = re.sub(r'/\*.*?\*/', ' ', query, flags=re.DOTALL)
    # 行コメント -- ... を除去
    normalized = re.sub(r'--[^\n]*', ' ', normalized)
    # 連続する空白を1つにまとめる
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    return normalized


@router.post("/query/{db_name}", dependencies=[Depends(verify_api_key)])
async def execute_query(db_name: str, request: QueryRequest):
    """SQLクエリを実行（SELECTのみ、セキュリティ強化版）"""
    query_normalized = request.query.strip()

    # セキュリティ: コメントと空白を正規化してバイパスを防止
    query_compact = _normalize_query_for_security(query_normalized).upper()

    # セキュリティ: SELECTのみ許可（複文やサブクエリでの攻撃を防止）
    if not query_compact.startswith("SELECT"):
        raise HTTPException(status_code=400, detail="Only SELECT queries allowed")

    # セキュリティ: 危険なキーワードをブロック（単語境界でマッチ）
    # 単語境界を使用することで、カラム名（updated_at, deleted_flag等）の誤検知を防止
    dangerous_keywords = [
        "INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER", "TRUNCATE",
        "GRANT", "REVOKE", "EXECUTE", "EXEC", "INTO OUTFILE", "INTO DUMPFILE",
        "LOAD_FILE", "PG_SLEEP", "BENCHMARK", "WAITFOR",
    ]
    for keyword in dangerous_keywords:
        # 単語境界でマッチ（\bは単語境界を表す）
        if re.search(rf'\b{re.escape(keyword)}\b', query_compact):
            raise HTTPException(
                status_code=400,
                detail=f"Query contains forbidden keyword: {keyword}"
            )

    # セキュリティ: DBLINK関数呼び出しをブロック（関数呼び出しパターンのみ）
    if re.search(r'\bDBLINK\s*\(', query_compact) or re.search(r'\bDBLINK_CONNECT\s*\(', query_compact):
        raise HTTPException(
            status_code=400,
            detail="Query contains forbidden keyword: DBLINK"
        )

    # セキュリティ: セミコロンによる複文実行を防止
    # 文字列リテラル内のセミコロンは許可するため、文字列リテラルを除去してからチェック
    # PostgreSQLの複数の文字列リテラル形式に対応:
    # - 単一引用符: 'text' または 'O''Brien' (エスケープされた引用符)
    # - 二重引用符: "identifier" (識別子用だがセミコロンも含む可能性がある)
    # - ドルクォート: $$text$$ または $tag$text$tag$ 
    query_without_strings = query_compact
    # 単一引用符リテラル（エスケープされた引用符を含む）を除去
    query_without_strings = re.sub(r"'(?:[^']|'')*'", '', query_without_strings)
    # 二重引用符リテラル（識別子）を除去
    query_without_strings = re.sub(r'"(?:[^"]|"")*"', '', query_without_strings)
    # ドルクォートリテラル（$$...$$または$tag$...$tag$形式）を除去
    # まず tagged dollar quotes ($tag$...$tag$) を処理
    query_without_strings = re.sub(r'\$[a-zA-Z_][a-zA-Z0-9_]*\$.*?\$[a-zA-Z_][a-zA-Z0-9_]*\$', '', query_without_strings, flags=re.DOTALL)
    # 次に simple dollar quotes ($$...$$) を処理
    query_without_strings = re.sub(r'\$\$.*?\$\$', '', query_without_strings, flags=re.DOTALL)
    
    if ";" in query_without_strings:
        raise HTTPException(status_code=400, detail="Multiple statements not allowed")

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
        # セキュリティ: エラーメッセージから機密情報を除去
        error_msg = str(e)
        error_msg_lower = error_msg.lower()
        sensitive_patterns = [
            "password", "passwd", "secret", "token", "key",
            "credential", "auth", "api_key", "apikey", "private"
        ]
        if any(pattern in error_msg_lower for pattern in sensitive_patterns):
            error_msg = "Query execution failed"
        raise HTTPException(status_code=400, detail=error_msg) from e
