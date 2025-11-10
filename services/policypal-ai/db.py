"""
Database helper for PolicyPal AI
SQLite-based persistence layer
"""

import os
import sqlite3
from contextlib import contextmanager

DB_PATH = os.getenv("POLICYPAL_DB_PATH") or os.getenv("DB_PATH") or "./policypal.db"


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
            CREATE TABLE IF NOT EXISTS policies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                policy_number TEXT NOT NULL,
                policy_type TEXT,
                carrier TEXT,
                policyholder TEXT,
                effective_date TEXT,
                expiration_date TEXT,
                premium_amount REAL,
                coverage_amount REAL,
                summary TEXT,
                created_at TEXT NOT NULL,
                created_by_key TEXT
            )
        """)

        # Add created_by_key column to existing table (safe for existing databases)
        try:
            conn.execute("ALTER TABLE policies ADD COLUMN created_by_key TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists

        # Performance indexes
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_policies_expiration ON policies(expiration_date)"
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_policies_type ON policies(policy_type)")

        conn.commit()
