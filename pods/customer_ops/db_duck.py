"""
DuckDB + VSS vector store for scalable semantic search.

Provides:
- get_conn() - Get/create DuckDB connection with VSS extension
- upsert_chunks() - Insert or replace chunks with embeddings
- query_embeddings() - Semantic search with cosine similarity
"""

import json
import os
from pathlib import Path
from typing import Any

import duckdb


def get_conn(
    db_path: str = "data/knowledge.duckdb", embedding_dim: int | None = None
) -> duckdb.DuckDBPyConnection:
    """
    Get or create DuckDB connection with VSS extension loaded.

    Args:
        db_path: Path to DuckDB file (default: data/knowledge.duckdb)
        embedding_dim: Embedding dimension (auto-detected if None)

    Returns:
        DuckDB connection with VSS extension loaded
    """
    # Ensure parent directory exists
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    # Connect to DuckDB
    conn = duckdb.connect(db_path)

    # Install and load VSS extension
    conn.execute("INSTALL vss;")
    conn.execute("LOAD vss;")

    # Detect existing embedding dimension or use default
    if embedding_dim is None:
        # Try to detect from existing table
        try:
            result = conn.execute("SELECT COUNT(*) as cnt FROM chunks LIMIT 1;").fetchone()
            # Table exists, get dimension from first row
            first_row = conn.execute("SELECT embedding FROM chunks LIMIT 1;").fetchone()
            if first_row and first_row[0]:
                embedding_dim = len(first_row[0])
            else:
                # Table exists but empty, use environment variable or default
                embedding_dim = int(os.getenv("EMBEDDING_DIM", "768"))
        except:
            # Table doesn't exist yet, use environment variable or default
            embedding_dim = int(os.getenv("EMBEDDING_DIM", "768"))

    # Create chunks table if not exists
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS chunks(
            id TEXT PRIMARY KEY,
            tenant_id TEXT,
            content TEXT,
            metadata JSON,
            embedding FLOAT[{embedding_dim}]
        );
    """)

    # Create VSS index if not exists (cosine similarity)
    try:
        conn.execute("""
            CREATE INDEX IF NOT EXISTS chunks_vss
            ON chunks USING HNSW(embedding)
            WITH (metric='cosine');
        """)
    except Exception:
        # Index might already exist, ignore error
        pass

    # Create API keys table if not exists
    conn.execute("""
        CREATE TABLE IF NOT EXISTS api_keys(
            key TEXT PRIMARY KEY,
            tenant_id TEXT,
            role TEXT,
            name TEXT,
            created_at TIMESTAMP DEFAULT current_timestamp,
            enabled BOOLEAN DEFAULT TRUE,
            rpm_limit INTEGER,
            daily_quota INTEGER,
            daily_count INTEGER DEFAULT 0,
            daily_reset DATE DEFAULT current_date
        );
    """)

    return conn


def upsert_chunks(
    chunks: list[dict[str, Any]], metadata: dict[str, Any], tenant_id: str | None = None
) -> int:
    """
    Insert or replace chunks with embeddings into DuckDB.

    Args:
        chunks: List of dicts with {id, content, embedding}
        metadata: Shared metadata to merge with each chunk (e.g., source)
        tenant_id: Optional tenant identifier

    Returns:
        Number of chunks upserted
    """
    if not chunks:
        return 0

    # Get connection from environment or default
    db_path = os.getenv("DUCKDB_PATH", "data/knowledge.duckdb")

    # Detect embedding dimension from first chunk
    embedding_dim = len(chunks[0].get("embedding", [])) if chunks else None
    conn = get_conn(db_path, embedding_dim=embedding_dim)

    try:
        # Prepare rows for insertion
        for chunk in chunks:
            chunk_id = chunk.get("id")
            content = chunk.get("content", "")
            embedding = chunk.get("embedding", [])

            # Merge metadata per-chunk
            chunk_metadata = {**metadata, **chunk.get("metadata", {})}

            # DuckDB doesn't support INSERT OR REPLACE with array types
            # Use DELETE + INSERT pattern instead
            conn.execute("DELETE FROM chunks WHERE id = ?;", [chunk_id])
            conn.execute(
                """
                INSERT INTO chunks (id, tenant_id, content, metadata, embedding)
                VALUES (?, ?, ?, ?, ?);
            """,
                [chunk_id, tenant_id, content, json.dumps(chunk_metadata), embedding],
            )

        return len(chunks)
    finally:
        conn.close()


def query_embeddings(
    query_vec: list[float], tenant_id: str | None = None, top_k: int = 5
) -> list[dict[str, Any]]:
    """
    Semantic search using VSS cosine similarity.

    Args:
        query_vec: Query embedding vector (1536 dims for OpenAI)
        tenant_id: Optional tenant filter (None = no filter)
        top_k: Maximum number of results to return

    Returns:
        List of dicts with {id, content, metadata, distance}
    """
    # Get connection from environment or default
    db_path = os.getenv("DUCKDB_PATH", "data/knowledge.duckdb")

    # Detect embedding dimension from query vector
    embedding_dim = len(query_vec)
    conn = get_conn(db_path, embedding_dim=embedding_dim)

    try:
        # Build query with optional tenant filter (dynamic embedding dimension)
        if tenant_id is None:
            result = conn.execute(
                f"""
                SELECT id, content, metadata, array_cosine_distance(embedding, ?::FLOAT[{embedding_dim}]) AS distance
                FROM chunks
                WHERE tenant_id IS NULL
                ORDER BY distance
                LIMIT ?;
            """,
                [query_vec, top_k],
            ).fetchall()
        else:
            result = conn.execute(
                f"""
                SELECT id, content, metadata, array_cosine_distance(embedding, ?::FLOAT[{embedding_dim}]) AS distance
                FROM chunks
                WHERE tenant_id = ?
                ORDER BY distance
                LIMIT ?;
            """,
                [query_vec, tenant_id, top_k],
            ).fetchall()

        # Convert to list of dicts
        rows = []
        for row in result:
            rows.append(
                {
                    "id": row[0],
                    "content": row[1],
                    "metadata": json.loads(row[2]) if row[2] else {},
                    "distance": float(row[3]),
                }
            )

        return rows
    finally:
        conn.close()


def query_lexical(
    query: str, tenant_id: str | None = None, top_k: int = 20
) -> list[dict[str, Any]]:
    """
    Lexical/keyword search using LIKE queries on content.
    Tokenizes query and counts matches for BM25-style scoring.

    Args:
        query: Search query text (tokenized by whitespace)
        tenant_id: Optional tenant filter (None = no filter)
        top_k: Maximum number of results to return

    Returns:
        List of dicts with {id, content, metadata, score_lex}
        where score_lex is the number of matched tokens
    """
    db_path = os.getenv("DUCKDB_PATH", "data/knowledge.duckdb")
    conn = get_conn(db_path)

    try:
        # Tokenize query (simple whitespace split, lowercase)
        tokens = [t.strip().lower() for t in query.split() if t.strip()]
        if not tokens:
            return []

        # Build LIKE clauses for each token
        # Score = count of matching tokens
        like_conditions = []
        for token in tokens:
            # Escape special LIKE characters
            escaped = token.replace("%", "\\%").replace("_", "\\_")
            like_conditions.append(f"LOWER(content) LIKE '%{escaped}%'")

        # Build score expression: sum of CAST(condition AS INTEGER)
        score_parts = [f"CAST({cond} AS INTEGER)" for cond in like_conditions]
        score_expr = " + ".join(score_parts)

        # Build WHERE clause: at least one token must match
        where_clause = " OR ".join(like_conditions)

        # Add tenant filter
        if tenant_id is not None:
            where_clause = f"tenant_id = ? AND ({where_clause})"
        else:
            where_clause = f"tenant_id IS NULL AND ({where_clause})"

        # Execute query
        sql = f"""
            SELECT id, content, metadata, ({score_expr}) AS score_lex
            FROM chunks
            WHERE {where_clause}
            ORDER BY score_lex DESC
            LIMIT ?;
        """

        if tenant_id is not None:
            result = conn.execute(sql, [tenant_id, top_k]).fetchall()
        else:
            result = conn.execute(sql, [top_k]).fetchall()

        # Convert to list of dicts
        rows = []
        for row in result:
            rows.append(
                {
                    "id": row[0],
                    "content": row[1],
                    "metadata": json.loads(row[2]) if row[2] else {},
                    "score_lex": int(row[3]),
                }
            )

        return rows
    finally:
        conn.close()


def recent_ingests(limit: int = 20) -> list[dict[str, Any]]:
    """
    Get recent ingestion summaries with metadata.

    Args:
        limit: Maximum number of documents to return

    Returns:
        List of dicts with document metadata and stats
    """
    db_path = os.getenv("DUCKDB_PATH", "data/knowledge.duckdb")
    conn = get_conn(db_path)

    try:
        # Aggregate chunks by source document (url or source field)
        result = conn.execute(
            """
            WITH chunk_metadata AS (
                SELECT
                    id,
                    tenant_id,
                    content,
                    metadata,
                    COALESCE(
                        json_extract_string(metadata, '$.url'),
                        json_extract_string(metadata, '$.source'),
                        'unknown'
                    ) AS doc_key,
                    json_extract_string(metadata, '$.title') AS title,
                    json_extract_string(metadata, '$.lang') AS lang,
                    json_extract_string(metadata, '$.published') AS published,
                    json_extract_string(metadata, '$.url') AS url,
                    json_extract_string(metadata, '$.extraction') AS extraction,
                    COALESCE(
                        CAST(json_extract(metadata, '$.ingested_at') AS DOUBLE),
                        0.0
                    ) AS ingested_at,
                    LENGTH(content) AS content_len
                FROM chunks
            )
            SELECT
                doc_key,
                ANY_VALUE(title) AS title,
                ANY_VALUE(lang) AS lang,
                ANY_VALUE(published) AS published,
                ANY_VALUE(url) AS url,
                ANY_VALUE(extraction) AS extraction,
                ANY_VALUE(tenant_id) AS tenant_id,
                COUNT(*) AS chunks,
                SUM(content_len) AS total_chars,
                MAX(ingested_at) AS latest_ingest
            FROM chunk_metadata
            GROUP BY doc_key
            ORDER BY latest_ingest DESC
            LIMIT ?;
        """,
            [limit],
        ).fetchall()

        # Convert to list of dicts
        docs = []
        for row in result:
            docs.append(
                {
                    "doc_key": row[0],
                    "title": row[1],
                    "lang": row[2],
                    "published": row[3],
                    "url": row[4],
                    "extraction": row[5],
                    "tenant_id": row[6],
                    "chunks": int(row[7]),
                    "total_chars": int(row[8]),
                    "ingested_at": float(row[9]) if row[9] else None,
                }
            )

        return docs
    finally:
        conn.close()


# ============================================================================
# API Key Management
# ============================================================================


def upsert_api_key(
    key: str,
    tenant_id: str,
    role: str,
    name: str | None = None,
    rpm_limit: int | None = None,
    daily_quota: int | None = None,
    enabled: bool = True,
) -> dict[str, Any]:
    """
    Insert or update an API key.

    Args:
        key: API key string
        tenant_id: Tenant identifier
        role: 'viewer', 'editor', or 'admin'
        name: Human-readable label
        rpm_limit: Requests per minute limit (None = unlimited)
        daily_quota: Daily request quota (None = unlimited)
        enabled: Whether key is active

    Returns:
        Dict with key details
    """
    db_path = os.getenv("DUCKDB_PATH", "data/knowledge.duckdb")
    conn = get_conn(db_path)

    try:
        conn.execute(
            """
            INSERT INTO api_keys (key, tenant_id, role, name, rpm_limit, daily_quota, enabled)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                tenant_id = excluded.tenant_id,
                role = excluded.role,
                name = excluded.name,
                rpm_limit = excluded.rpm_limit,
                daily_quota = excluded.daily_quota,
                enabled = excluded.enabled;
        """,
            [key, tenant_id, role, name, rpm_limit, daily_quota, enabled],
        )

        return get_api_key(key)
    finally:
        conn.close()


def get_api_key(key: str) -> dict[str, Any] | None:
    """Get API key details by key string."""
    db_path = os.getenv("DUCKDB_PATH", "data/knowledge.duckdb")
    conn = get_conn(db_path)

    try:
        row = conn.execute(
            """
            SELECT key, tenant_id, role, name, created_at, enabled,
                   rpm_limit, daily_quota, daily_count, daily_reset
            FROM api_keys
            WHERE key = ?
        """,
            [key],
        ).fetchone()

        if not row:
            return None

        return {
            "key": row[0],
            "tenant_id": row[1],
            "role": row[2],
            "name": row[3],
            "created_at": row[4].isoformat() if row[4] else None,
            "enabled": bool(row[5]),
            "rpm_limit": row[6],
            "daily_quota": row[7],
            "daily_count": row[8],
            "daily_reset": row[9].isoformat() if row[9] else None,
        }
    finally:
        conn.close()


def list_api_keys(limit: int = 100) -> list[dict[str, Any]]:
    """List all API keys."""
    db_path = os.getenv("DUCKDB_PATH", "data/knowledge.duckdb")
    conn = get_conn(db_path)

    try:
        rows = conn.execute(
            """
            SELECT key, tenant_id, role, name, created_at, enabled,
                   rpm_limit, daily_quota, daily_count, daily_reset
            FROM api_keys
            ORDER BY created_at DESC
            LIMIT ?
        """,
            [limit],
        ).fetchall()

        keys = []
        for row in rows:
            keys.append(
                {
                    "key": row[0],
                    "tenant_id": row[1],
                    "role": row[2],
                    "name": row[3],
                    "created_at": row[4].isoformat() if row[4] else None,
                    "enabled": bool(row[5]),
                    "rpm_limit": row[6],
                    "daily_quota": row[7],
                    "daily_count": row[8],
                    "daily_reset": row[9].isoformat() if row[9] else None,
                }
            )

        return keys
    finally:
        conn.close()


def set_api_key_enabled(key: str, enabled: bool) -> bool:
    """Enable or disable an API key."""
    db_path = os.getenv("DUCKDB_PATH", "data/knowledge.duckdb")
    conn = get_conn(db_path)

    try:
        conn.execute(
            """
            UPDATE api_keys SET enabled = ? WHERE key = ?
        """,
            [enabled, key],
        )
        return True
    finally:
        conn.close()


def delete_api_key(key: str) -> bool:
    """Delete an API key."""
    db_path = os.getenv("DUCKDB_PATH", "data/knowledge.duckdb")
    conn = get_conn(db_path)

    try:
        conn.execute("DELETE FROM api_keys WHERE key = ?", [key])
        return True
    finally:
        conn.close()


def bump_api_key_counters(key: str) -> tuple[bool, str | None]:
    """
    Increment API key usage counters and check quotas.

    Returns:
        (ok, reason) - (True, None) if within limits, (False, reason) if exceeded
    """
    import datetime

    db_path = os.getenv("DUCKDB_PATH", "data/knowledge.duckdb")
    conn = get_conn(db_path)

    try:
        # Get current state
        row = conn.execute(
            """
            SELECT daily_quota, daily_count, daily_reset
            FROM api_keys
            WHERE key = ?
        """,
            [key],
        ).fetchone()

        if not row:
            return (False, "key_not_found")

        daily_quota, daily_count, daily_reset = row[0], row[1], row[2]
        today = datetime.date.today()

        # Reset counter if new day
        if daily_reset != today:
            conn.execute(
                """
                UPDATE api_keys
                SET daily_count = 0, daily_reset = ?
                WHERE key = ?
            """,
                [today, key],
            )
            daily_count = 0

        # Check quota
        if daily_quota is not None and daily_count >= daily_quota:
            return (False, "daily_quota_exceeded")

        # Increment counter
        conn.execute(
            """
            UPDATE api_keys
            SET daily_count = daily_count + 1
            WHERE key = ?
        """,
            [key],
        )

        return (True, None)
    finally:
        conn.close()
