import sqlite3
import os
from pathlib import Path
from app.config.settings import SQLITE_DB_PATH, DATA_DIR


def get_db_connection(db_path: Path = None) -> sqlite3.Connection:
    """
    Creates and returns a SQLite database connection with WAL mode enabled
    and row factory set to sqlite3.Row.
    """
    target_path = db_path or SQLITE_DB_PATH
    target_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(target_path), timeout=30.0)
    conn.row_factory = sqlite3.Row

    # Enable WAL mode for high performance
    conn.execute("PRAGMA journal_mode=WAL;")
    # Enable Foreign Keys
    conn.execute("PRAGMA foreign_keys=ON;")

    return conn


def verify_fts5_support(conn: sqlite3.Connection = None) -> bool:
    """
    Verifies at runtime that SQLite FTS5 extension is built-in and supported.
    Raises RuntimeError if FTS5 is missing.
    """
    close_after = False
    if conn is None:
        conn = get_db_connection()
        close_after = True

    try:
        conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS _fts5_verify_test USING fts5(col1);")
        conn.execute("DROP TABLE _fts5_verify_test;")
        return True
    except sqlite3.OperationalError as err:
        raise RuntimeError(f"SQLite FTS5 extension is not available in current Python runtime: {err}")
    finally:
        if close_after:
            conn.close()


def initialize_database(db_path: Path = None):
    """
    Safely initializes SQLite tables, metadata indexes, and FTS5 virtual tables.
    """
    conn = get_db_connection(db_path)
    try:
        verify_fts5_support(conn)

        with conn:
            # Metadata Table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    doc_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    path TEXT NOT NULL UNIQUE,
                    extension TEXT NOT NULL,
                    folder TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    modified_time REAL NOT NULL,
                    indexed_time REAL NOT NULL
                );
            """)

            # Fast lookup indexes
            conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_name ON documents(name);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_folder ON documents(folder);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_path ON documents(path);")

            # FTS5 Virtual Table for full-text search across filename, folder, path, and content
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
                    doc_id UNINDEXED,
                    name,
                    folder,
                    path,
                    content,
                    tokenize='unicode61'
                );
            """)
    finally:
        conn.close()
