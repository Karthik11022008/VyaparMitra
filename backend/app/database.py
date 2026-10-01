import sqlite3
from pathlib import Path
from backend.app.config import settings

def get_db_path() -> Path:
    db_path = Path(settings.DATABASE_PATH)
    if not db_path.is_absolute():
        from backend.app.config import BASE_DIR
        db_path = BASE_DIR / db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path

def get_connection() -> sqlite3.Connection:
    path = get_db_path()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db() -> None:
    """Initialize the SQLite database with foundation tables. Safe to run repeatedly."""
    conn = get_connection()
    try:
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_sessions (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL
                )
            """)
    finally:
        conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully at:", get_db_path())
