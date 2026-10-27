"""SQLite Database management for DouyinVN Studio."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from typing import Optional

if getattr(sys, "frozen", False):
    ROOT_DIR = Path(sys.executable).resolve().parent
else:
    ROOT_DIR = Path(__file__).resolve().parent.parent

DB_PATH = ROOT_DIR / "data" / "douyinvn.db"


def get_db_connection(db_file: Optional[Path] = None) -> sqlite3.Connection:
    """Create and configure a thread-safe connection to SQLite."""
    target_path = db_file or DB_PATH
    target_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target_path), timeout=30.0)
    conn.row_factory = sqlite3.Row
    # Enable WAL mode for better concurrency across threads
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_file: Optional[Path] = None) -> None:
    """Initialize database tables and indexes."""
    conn = get_db_connection(db_file)
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_path TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                progress INTEGER NOT NULL DEFAULT 0,
                current_step TEXT NOT NULL DEFAULT '',
                video_width INTEGER DEFAULT 0,
                video_height INTEGER DEFAULT 0,
                duration REAL DEFAULT 0.0,
                fps REAL DEFAULT 0.0,
                has_audio INTEGER DEFAULT 1,
                subtitles_json TEXT DEFAULT '[]',
                output_video_path TEXT DEFAULT '',
                output_srt_path TEXT DEFAULT '',
                workspace_dir TEXT DEFAULT '',
                error_message TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at);
        """)
    conn.close()
