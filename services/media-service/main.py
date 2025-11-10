"""
AetherLink Media Service
Handles file uploads and storage for all vertical apps
"""

import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from db import get_db, init_db
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="AetherLink Media Service", version="1.0.0")

# Initialize database on startup
init_db()

# Environment configuration
MEDIA_ROOT = os.getenv("MEDIA_ROOT", "./media")
BASE_URL = os.getenv("MEDIA_BASE_URL", "http://localhost:9109")
STORAGE_MODE = os.getenv("MEDIA_STORAGE", "local")  # later: s3, r2

# Create media storage directory
Path(MEDIA_ROOT).mkdir(parents=True, exist_ok=True)

# CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3001", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files (local mode)
app.mount("/media", StaticFiles(directory=MEDIA_ROOT), name="media")


@app.get("/health")
def health():
    return {"status": "ok", "service": "media-service"}


@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    job_id: str | None = Form(None),
    tag: str | None = Form(None),
):
    """
    Simple single-shot upload.
    For chunked/resumable we can extend later.
    """
    if STORAGE_MODE != "local":
        raise HTTPException(500, "Non-local storage not implemented yet")

    ext = Path(file.filename).suffix or ".bin"
    media_id = str(uuid.uuid4())
    filename = f"{media_id}{ext}"
    dest_path = Path(MEDIA_ROOT) / filename

    contents = await file.read()
    file_size = len(contents)

    with open(dest_path, "wb") as f:
        f.write(contents)

    url = f"{BASE_URL}/media/{filename}"
    now = datetime.utcnow().isoformat()

    # Track upload in database
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO uploads (
                media_id, filename, original_filename, url,
                mime_type, size_bytes, job_id, tag, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                media_id,
                filename,
                file.filename,
                url,
                file.content_type,
                file_size,
                job_id,
                tag,
                now,
            ),
        )
        conn.commit()

    return {
        "media_id": media_id,
        "url": url,
        "job_id": job_id,
        "tag": tag,
        "uploaded_at": now,
    }


@app.get("/uploads")
def list_uploads(
    job_id: str | None = Query(None), tag: str | None = Query(None), limit: int = Query(50, le=500)
):
    """List uploaded media, optionally filtered by job_id or tag"""
    with get_db() as conn:
        if job_id and tag:
            rows = conn.execute(
                "SELECT * FROM uploads WHERE job_id = ? AND tag = ? ORDER BY created_at DESC LIMIT ?",
                (job_id, tag, limit),
            ).fetchall()
        elif job_id:
            rows = conn.execute(
                "SELECT * FROM uploads WHERE job_id = ? ORDER BY created_at DESC LIMIT ?",
                (job_id, limit),
            ).fetchall()
        elif tag:
            rows = conn.execute(
                "SELECT * FROM uploads WHERE tag = ? ORDER BY created_at DESC LIMIT ?", (tag, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM uploads ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()

    return [dict(row) for row in rows]


@app.get("/uploads/stats")
def upload_stats():
    """Get storage and upload statistics (summary/details + flat for backwards-compat)."""
    now_utc = datetime.now(UTC)
    today_utc = now_utc.date().isoformat()
    since_24h = (now_utc - timedelta(hours=24)).isoformat()

    with get_db() as conn:
        # Totals
        total_files = conn.execute("SELECT COUNT(*) FROM uploads").fetchone()[0]
        total_size_bytes = conn.execute(
            "SELECT COALESCE(SUM(size_bytes), 0) FROM uploads"
        ).fetchone()[0]

        # Activity windows
        uploads_today = conn.execute(
            "SELECT COUNT(*) FROM uploads WHERE created_at >= ?",
            (today_utc,),
        ).fetchone()[0]

        uploads_last_24h = conn.execute(
            "SELECT COUNT(*) FROM uploads WHERE created_at >= ?",
            (since_24h,),
        ).fetchone()[0]

        # Distribution
        mime_rows = conn.execute(
            "SELECT mime_type, COUNT(*) as c FROM uploads GROUP BY mime_type"
        ).fetchall()
        by_mime_type = {(row[0] or "unknown"): row[1] for row in mime_rows}

    total_files = total_files or 0
    total_size_bytes = total_size_bytes or 0
    uploads_today = uploads_today or 0
    uploads_last_24h = uploads_last_24h or 0
    total_size_mb = round(total_size_bytes / (1024 * 1024), 2)
    ts = datetime.utcnow().isoformat() + "Z"

    # Structured (preferred) + flat (compat)
    return {
        "summary": {
            "total_files": total_files,
            "total_size_mb": total_size_mb,
            "uploads_today": uploads_today,
        },
        "details": {
            "total_size_bytes": total_size_bytes,
            "uploads_last_24h": uploads_last_24h,
            "by_mime_type": by_mime_type,
            "timestamp": ts,
        },
        # Backwards-compatible flat fields
        "total_files": total_files,
        "total_size_bytes": total_size_bytes,
        "total_size_mb": total_size_mb,
        "uploads_today": uploads_today,
        "uploads_last_24h": uploads_last_24h,
        "by_mime_type": by_mime_type,
        "timestamp": ts,
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 9109))
    uvicorn.run(app, host="0.0.0.0", port=port)
