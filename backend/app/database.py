import sqlite3
import json
import uuid
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

_DB_INITIALIZED = False

def _create_connection() -> sqlite3.Connection:
    path = get_db_path()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn

def get_connection() -> sqlite3.Connection:
    global _DB_INITIALIZED
    conn = _create_connection()
    if not _DB_INITIALIZED:
        _DB_INITIALIZED = True
        _run_init_db(conn)
    return conn

def _run_init_db(conn: sqlite3.Connection) -> None:
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
                gstr2b_filepath TEXT,
                results_json TEXT,
                supplier_summary_json TEXT
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
        # Phase 5: Additive tables for persistent conversations & messages
        conn.execute("""
            CREATE TABLE IF NOT EXISTS agent_conversations (
                conversation_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS agent_messages (
                message_id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                intent TEXT,
                tools_used TEXT,
                plan TEXT,
                steps_executed TEXT,
                evidence TEXT,
                suggested_action TEXT,
                draft_notice TEXT,
                context_json TEXT,
                timestamp TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_conv_session ON agent_conversations(session_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_msg_conv ON agent_messages(conversation_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_msg_session ON agent_messages(session_id)")

        # Phase 1 Safe Additive Migration: Add results_json & supplier_summary_json if missing in existing DB
        cursor = conn.execute("PRAGMA table_info(reconciliation_sessions)")
        existing_cols = {row["name"] for row in cursor.fetchall()}
        if "results_json" not in existing_cols:
            conn.execute("ALTER TABLE reconciliation_sessions ADD COLUMN results_json TEXT")
        if "supplier_summary_json" not in existing_cols:
            conn.execute("ALTER TABLE reconciliation_sessions ADD COLUMN supplier_summary_json TEXT")

def init_db() -> None:
    """Initialize the SQLite database with foundation and Phase 1 session/audit tables."""
    global _DB_INITIALIZED
    _DB_INITIALIZED = True
    conn = _create_connection()
    try:
        _run_init_db(conn)
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
    results_json: Optional[str] = None,
    supplier_summary_json: Optional[str] = None,
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
                        purchase_filepath, gstr2b_filepath, results_json, supplier_summary_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                        gstr2b_filepath or "",
                        results_json or "",
                        supplier_summary_json or ""
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
                if results_json is not None:
                    updates.append("results_json = ?")
                    params.append(results_json)
                if supplier_summary_json is not None:
                    updates.append("supplier_summary_json = ?")
                    params.append(supplier_summary_json)

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
            "SELECT * FROM reconciliation_sessions WHERE session_id = ?",
            (session_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def get_reconciliation_history(limit: int = 50) -> List[Dict[str, Any]]:
    """Fetches historical reconciliation sessions for audit and recovery."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            SELECT session_id, created_at, purchase_filename, gstr2b_filename,
                   purchase_row_count, gstr2b_row_count, status, summary_json
            FROM reconciliation_sessions
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,)
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()

# ==============================================================================
# Phase 5: Persistent Conversation Management
# ==============================================================================

def create_conversation(session_id: str, title: str = "Investigation Thread") -> Dict[str, Any]:
    """Creates a new persistent conversation thread scoped to a reconciliation session."""
    cid = f"conv-{uuid.uuid4().hex[:12]}"
    now_iso = datetime.now(timezone.utc).isoformat()
    conn = get_connection()
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO agent_conversations (conversation_id, session_id, title, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (cid, session_id, title, now_iso, now_iso)
            )
        return {
            "conversation_id": cid,
            "session_id": session_id,
            "title": title,
            "created_at": now_iso,
            "updated_at": now_iso,
        }
    finally:
        conn.close()

def get_conversations(session_id: str) -> List[Dict[str, Any]]:
    """Retrieves all conversation threads for a given session."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            SELECT conversation_id, session_id, title, created_at, updated_at
            FROM agent_conversations
            WHERE session_id = ?
            ORDER BY updated_at DESC
            """,
            (session_id,)
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()

def get_conversation(conversation_id: str) -> Optional[Dict[str, Any]]:
    """Fetches single conversation details."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM agent_conversations WHERE conversation_id = ?",
            (conversation_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def save_agent_message(
    conversation_id: str,
    session_id: str,
    role: str,
    content: str,
    intent: Optional[str] = None,
    tools_used: Optional[List[str]] = None,
    plan: Optional[List[str]] = None,
    steps_executed: Optional[List[Dict[str, Any]]] = None,
    evidence: Optional[List[Dict[str, Any]]] = None,
    suggested_action: Optional[str] = None,
    draft_notice: Optional[Dict[str, Any]] = None,
    context_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Persists a message to the SQLite store with structured metadata."""
    mid = f"msg-{uuid.uuid4().hex[:12]}"
    now_iso = datetime.now(timezone.utc).isoformat()
    conn = get_connection()
    try:
        with conn:
            # Ensure conversation exists; create if not present
            existing = conn.execute(
                "SELECT conversation_id FROM agent_conversations WHERE conversation_id = ?",
                (conversation_id,)
            ).fetchone()
            if not existing:
                conn.execute(
                    """
                    INSERT INTO agent_conversations (conversation_id, session_id, title, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (conversation_id, session_id, content[:40] if role == 'user' else "Investigation", now_iso, now_iso)
                )
            else:
                conn.execute(
                    "UPDATE agent_conversations SET updated_at = ? WHERE conversation_id = ?",
                    (now_iso, conversation_id)
                )

            conn.execute(
                """
                INSERT INTO agent_messages (
                    message_id, conversation_id, session_id, role, content,
                    intent, tools_used, plan, steps_executed, evidence,
                    suggested_action, draft_notice, context_json, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    mid,
                    conversation_id,
                    session_id,
                    role,
                    content,
                    intent or "",
                    json.dumps(tools_used or []),
                    json.dumps(plan or []),
                    json.dumps(steps_executed or []),
                    json.dumps(evidence or []),
                    suggested_action or "",
                    json.dumps(draft_notice) if draft_notice else "",
                    json.dumps(context_data or {}),
                    now_iso
                )
            )
        return {
            "message_id": mid,
            "conversation_id": conversation_id,
            "session_id": session_id,
            "role": role,
            "content": content,
            "intent": intent,
            "timestamp": now_iso
        }
    finally:
        conn.close()

def get_conversation_messages(conversation_id: str) -> List[Dict[str, Any]]:
    """Fetches all messages for a conversation ordered chronologically."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            SELECT * FROM agent_messages
            WHERE conversation_id = ?
            ORDER BY timestamp ASC
            """,
            (conversation_id,)
        )
        rows = []
        for r in cursor.fetchall():
            d = dict(r)
            d["tools_used"] = json.loads(d["tools_used"]) if d.get("tools_used") else []
            d["plan"] = json.loads(d["plan"]) if d.get("plan") else []
            d["steps_executed"] = json.loads(d["steps_executed"]) if d.get("steps_executed") else []
            d["evidence"] = json.loads(d["evidence"]) if d.get("evidence") else []
            d["draft_notice"] = json.loads(d["draft_notice"]) if d.get("draft_notice") else None
            d["context"] = json.loads(d["context_json"]) if d.get("context_json") else {}
            rows.append(d)
        return rows
    finally:
        conn.close()

def delete_conversation(conversation_id: str) -> bool:
    """Deletes conversation and associated messages."""
    conn = get_connection()
    try:
        with conn:
            conn.execute("DELETE FROM agent_messages WHERE conversation_id = ?", (conversation_id,))
            conn.execute("DELETE FROM agent_conversations WHERE conversation_id = ?", (conversation_id,))
        return True
    finally:
        conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully at:", get_db_path())
