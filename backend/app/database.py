import sqlite3
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any
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
    """Initialize the SQLite database with foundation and Phase 4 session/audit tables."""
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
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reconciliation_sessions (
                    session_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    purchase_filename TEXT,
                    gstr2b_filename TEXT,
                    purchase_row_count INTEGER DEFAULT 0,
                    gstr2b_row_count INTEGER DEFAULT 0,
                    status TEXT NOT NULL,
                    summary_json TEXT,
                    purchase_filepath TEXT,
                    gstr2b_filepath TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    details TEXT NOT NULL
                )
            """)
    finally:
        conn.close()

def log_audit_event(session_id: str, event_type: str, details: str) -> None:
    """Records an audit trail event for compliance and traceability."""
    now_iso = datetime.now(timezone.utc).isoformat()
    conn = get_connection()
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO audit_events (session_id, event_type, timestamp, details)
                VALUES (?, ?, ?, ?)
                """,
                (session_id, event_type, now_iso, details)
            )
    finally:
        conn.close()

def get_audit_events(session_id: str) -> List[Dict[str, Any]]:
    """Retrieves all audit events associated with a reconciliation session."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            SELECT id, session_id, event_type, timestamp, details
            FROM audit_events
            WHERE session_id = ?
            ORDER BY id ASC
            """,
            (session_id,)
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()

def save_or_update_session(
    session_id: str,
    status: str,
    purchase_filename: Optional[str] = None,
    gstr2b_filename: Optional[str] = None,
    purchase_row_count: Optional[int] = None,
    gstr2b_row_count: Optional[int] = None,
    summary_json: Optional[str] = None,
    purchase_filepath: Optional[str] = None,
    gstr2b_filepath: Optional[str] = None,
) -> None:
    """Inserts or updates a reconciliation session in SQLite."""
    conn = get_connection()
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        with conn:
            existing = conn.execute(
                "SELECT session_id FROM reconciliation_sessions WHERE session_id = ?",
                (session_id,)
            ).fetchone()

            if not existing:
                conn.execute(
                    """
                    INSERT INTO reconciliation_sessions (
                        session_id, created_at, purchase_filename, gstr2b_filename,
                        purchase_row_count, gstr2b_row_count, status, summary_json,
                        purchase_filepath, gstr2b_filepath
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session_id,
                        now_iso,
                        purchase_filename or "",
                        gstr2b_filename or "",
                        purchase_row_count or 0,
                        gstr2b_row_count or 0,
                        status,
                        summary_json or "",
                        purchase_filepath or "",
                        gstr2b_filepath or ""
                    )
                )
            else:
                updates = ["status = ?"]
                params: List[Any] = [status]
                if purchase_filename is not None:
                    updates.append("purchase_filename = ?")
                    params.append(purchase_filename)
                if gstr2b_filename is not None:
                    updates.append("gstr2b_filename = ?")
                    params.append(gstr2b_filename)
                if purchase_row_count is not None:
                    updates.append("purchase_row_count = ?")
                    params.append(purchase_row_count)
                if gstr2b_row_count is not None:
                    updates.append("gstr2b_row_count = ?")
                    params.append(gstr2b_row_count)
                if summary_json is not None:
                    updates.append("summary_json = ?")
                    params.append(summary_json)
                if purchase_filepath is not None:
                    updates.append("purchase_filepath = ?")
                    params.append(purchase_filepath)
                if gstr2b_filepath is not None:
                    updates.append("gstr2b_filepath = ?")
                    params.append(gstr2b_filepath)

                params.append(session_id)
                query = f"UPDATE reconciliation_sessions SET {', '.join(updates)} WHERE session_id = ?"
                conn.execute(query, tuple(params))
    finally:
        conn.close()

def get_reconciliation_session(session_id: str) -> Optional[Dict[str, Any]]:
    """Fetches reconciliation session details by ID."""
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT session_id, created_at, purchase_filename, gstr2b_filename,
                   purchase_row_count, gstr2b_row_count, status, summary_json,
                   purchase_filepath, gstr2b_filepath
            FROM reconciliation_sessions
            WHERE session_id = ?
            """,
            (session_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully at:", get_db_path())
