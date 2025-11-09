"""
Database helper for PeakPro CRM
SQLite-based persistence layer
"""
import os
import sqlite3
from contextlib import contextmanager

DB_PATH = os.getenv("PEAKPRO_DB_PATH") or os.getenv("DB_PATH") or "./peakpro.db"

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
            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                company TEXT,
                created_at TEXT NOT NULL,
                created_by_key TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS deals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                value REAL DEFAULT 0,
                stage TEXT DEFAULT 'new',
                probability INTEGER DEFAULT 50,
                contact_id INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                created_by_key TEXT,
                FOREIGN KEY (contact_id) REFERENCES contacts(id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contact_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                created_by_key TEXT,
                FOREIGN KEY (contact_id) REFERENCES contacts(id)
            )
        """)

        # Add created_by_key columns to existing tables (safe for existing databases)
        try:
            conn.execute("ALTER TABLE contacts ADD COLUMN created_by_key TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        try:
            conn.execute("ALTER TABLE deals ADD COLUMN created_by_key TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists
            
        try:
            conn.execute("ALTER TABLE notes ADD COLUMN created_by_key TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists

        # Performance indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_deals_stage ON deals(stage)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_deals_updated ON deals(updated_at)")

        conn.commit()
