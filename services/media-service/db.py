"""
Database helper for Media Service
SQLite-based media tracking
"""
import os
import sqlite3
from contextlib import contextmanager

DB_PATH = os.getenv("MEDIA_DB_PATH", "./media.db")

@contextmanager
def get_db():
    """Context manager for database connections"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    """Initialize database schema"""
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS uploads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                media_id TEXT NOT NULL UNIQUE,
                filename TEXT NOT NULL,
                original_filename TEXT,
                url TEXT NOT NULL,
                mime_type TEXT,
                size_bytes INTEGER,
                job_id TEXT,
                tag TEXT,
                created_at TEXT NOT NULL
            )
        """)

        # Performance indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_uploads_job_id ON uploads(job_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_uploads_created ON uploads(created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_uploads_tag ON uploads(tag)")

        conn.commit()
