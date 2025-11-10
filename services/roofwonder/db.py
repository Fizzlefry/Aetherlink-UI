"""
Database helper for RoofWonder
SQLite-based persistence layer
"""

import os
import sqlite3
from contextlib import contextmanager

DB_PATH = os.getenv("ROOFWONDER_DB_PATH") or os.getenv("DB_PATH") or "./roofwonder.db"


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
            CREATE TABLE IF NOT EXISTS properties (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                address TEXT NOT NULL,
                city TEXT,
                state TEXT,
                zip_code TEXT,
                roof_type TEXT,
                roof_age INTEGER,
                created_at TEXT NOT NULL,
                created_by_key TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_name TEXT NOT NULL,
                property_id INTEGER,
                address TEXT NOT NULL,
                status TEXT DEFAULT 'scheduled',
                scheduled_date TEXT,
                completion_date TEXT,
                estimate_amount REAL,
                actual_amount REAL,
                notes TEXT,
                created_at TEXT NOT NULL,
                created_by_key TEXT,
                FOREIGN KEY (property_id) REFERENCES properties(id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS job_photos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL,
                photo_url TEXT NOT NULL,
                created_at TEXT NOT NULL,
                created_by_key TEXT,
                FOREIGN KEY (job_id) REFERENCES jobs(id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS estimates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL,
                materials_cost REAL,
                labor_cost REAL,
                total_cost REAL,
                notes TEXT,
                created_at TEXT NOT NULL,
                created_by_key TEXT,
                FOREIGN KEY (job_id) REFERENCES jobs(id)
            )
        """)

        # Add created_by_key columns to existing tables (safe for existing databases)
        try:
            conn.execute("ALTER TABLE properties ADD COLUMN created_by_key TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists

        try:
            conn.execute("ALTER TABLE jobs ADD COLUMN created_by_key TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists

        try:
            conn.execute("ALTER TABLE job_photos ADD COLUMN created_by_key TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists

        try:
            conn.execute("ALTER TABLE estimates ADD COLUMN created_by_key TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists

        # Performance indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_scheduled ON jobs(scheduled_date)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_job_photos_job ON job_photos(job_id)")

        conn.commit()
