import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
DATABASE_PATH = BASE_DIR / "chatbot.db"


def utc_now():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def get_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 5000")
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def initialize_database():
    with get_connection() as connection:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            title TEXT NOT NULL DEFAULT 'New Chat',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('user','assistant')),
            content TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'complete' CHECK(status IN ('pending','complete','failed','cancelled')),
            created_at TEXT NOT NULL,
            FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            filename TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS document_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            content TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS trace_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trace_id TEXT NOT NULL,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            conversation_id INTEGER REFERENCES conversations(id) ON DELETE CASCADE,
            event_type TEXT NOT NULL,
            tool_name TEXT,
            duration_ms INTEGER,
            success INTEGER NOT NULL DEFAULT 1,
            details TEXT,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_messages_conversation_id_id ON messages(conversation_id, id);
        """)
        conversation_columns = {row[1] for row in connection.execute("PRAGMA table_info(conversations)")}
        if "user_id" not in conversation_columns:
            connection.execute("ALTER TABLE conversations ADD COLUMN user_id INTEGER")
        message_columns = {row[1] for row in connection.execute("PRAGMA table_info(messages)")}
        if "status" not in message_columns:
            connection.execute("ALTER TABLE messages ADD COLUMN status TEXT NOT NULL DEFAULT 'complete'")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_conversations_user_updated ON conversations(user_id, updated_at DESC)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_document_chunks_user ON document_chunks(user_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_trace_events_user_created ON trace_events(user_id, created_at DESC)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_trace_events_trace ON trace_events(trace_id, id)")


def create_user(email, password_hash):
    now = utc_now()
    with get_connection() as connection:
        cursor = connection.execute(
            "INSERT INTO users(email,password_hash,created_at) VALUES(?,?,?)",
            (email.strip().lower(), password_hash, now),
        )
    return get_user(cursor.lastrowid)


def get_user(user_id):
    with get_connection() as connection:
        row = connection.execute(
            "SELECT id,email,created_at,password_hash FROM users WHERE id=?", (user_id,)
        ).fetchone()
    return dict(row) if row else None


def get_user_by_email(email):
    with get_connection() as connection:
        row = connection.execute(
            "SELECT id,email,created_at,password_hash FROM users WHERE email=?",
            (email.strip().lower(),),
        ).fetchone()
    return dict(row) if row else None


def create_document(user_id, filename, chunks):
    now = utc_now()
    with get_connection() as connection:
        cursor = connection.execute(
            "INSERT INTO documents(user_id,filename,created_at) VALUES(?,?,?)",
            (user_id, filename, now),
        )
        document_id = cursor.lastrowid
        connection.executemany(
            "INSERT INTO document_chunks(document_id,user_id,content) VALUES(?,?,?)",
            [(document_id, user_id, chunk) for chunk in chunks],
        )
    return {"id": document_id, "filename": filename, "created_at": now, "chunks": len(chunks)}


def list_documents(user_id):
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT id,filename,created_at FROM documents WHERE user_id=? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def delete_document(document_id, user_id):
    with get_connection() as connection:
        cursor = connection.execute("DELETE FROM documents WHERE id=? AND user_id=?", (document_id, user_id))
    return cursor.rowcount > 0


def search_document_chunks(user_id, terms, limit=4):
    if not terms:
        return []
    pattern = "%" + "%".join(terms[:8]) + "%"
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT content FROM document_chunks WHERE user_id=? AND lower(content) LIKE lower(?) LIMIT ?",
            (user_id, pattern, limit),
        ).fetchall()
    return [row["content"] for row in rows]


def create_conversation(user_id, title="New Chat"):
    now = utc_now()
    title = title.strip() or "New Chat"
    with get_connection() as connection:
        cursor = connection.execute(
            "INSERT INTO conversations(user_id,title,created_at,updated_at) VALUES(?,?,?,?)",
            (user_id, title, now, now),
        )
        conversation_id = cursor.lastrowid
    return {"id": conversation_id, "title": title, "created_at": now, "updated_at": now}


def list_conversations(user_id):
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT id,title,created_at,updated_at FROM conversations WHERE user_id=? ORDER BY updated_at DESC",
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_conversation(conversation_id, user_id):
    with get_connection() as connection:
        row = connection.execute(
            "SELECT id,title,created_at,updated_at,user_id FROM conversations WHERE id=? AND user_id=?",
            (conversation_id, user_id),
        ).fetchone()
    return dict(row) if row else None


def conversation_exists(conversation_id, user_id):
    return get_conversation(conversation_id, user_id) is not None


def rename_conversation(conversation_id, user_id, title):
    title = title.strip()[:100] or "New Chat"
    now = utc_now()
    with get_connection() as connection:
        connection.execute(
            "UPDATE conversations SET title=?,updated_at=? WHERE id=? AND user_id=?",
            (title, now, conversation_id, user_id),
        )
    return get_conversation(conversation_id, user_id)


def delete_conversation(conversation_id, user_id):
    with get_connection() as connection:
        connection.execute("DELETE FROM conversations WHERE id=? AND user_id=?", (conversation_id, user_id))


def clear_all_conversations(user_id):
    with get_connection() as connection:
        connection.execute("DELETE FROM conversations WHERE user_id=?", (user_id,))


def save_message(conversation_id, user_id, role, content, status="complete"):
    if status not in {"pending", "complete", "failed", "cancelled"}:
        raise ValueError("Invalid message status")
    now = utc_now()
    with get_connection() as connection:
        connection.execute(
            "INSERT INTO messages(conversation_id,role,content,status,created_at) VALUES(?,?,?,?,?)",
            (conversation_id, role, content, status, now),
        )
        connection.execute(
            "UPDATE conversations SET updated_at=? WHERE id=? AND user_id=?",
            (now, conversation_id, user_id),
        )


def get_messages(conversation_id, user_id):
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT m.id,m.role,m.content,m.status,m.created_at FROM messages m "
            "JOIN conversations c ON c.id=m.conversation_id "
            "WHERE m.conversation_id=? AND c.user_id=? ORDER BY m.id",
            (conversation_id, user_id),
        ).fetchall()
    return [dict(row) for row in rows]


def get_recent_messages(conversation_id, user_id, limit=20):
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT m.role,m.content FROM messages m JOIN conversations c ON c.id=m.conversation_id "
            "WHERE m.conversation_id=? AND c.user_id=? ORDER BY m.id DESC LIMIT ?",
            (conversation_id, user_id, limit),
        ).fetchall()
    return [{"role": row["role"], "content": row["content"]} for row in reversed(rows)]


def update_default_title(conversation_id, user_id, first_message):
    conversation = get_conversation(conversation_id, user_id)
    if not conversation or conversation["title"] != "New Chat":
        return
    normalized = " ".join(first_message.split())
    title = normalized[:45] + ("…" if len(normalized) > 45 else "")
    rename_conversation(conversation_id, user_id, title or "New Chat")


def delete_assistant_message(conversation_id, user_id, message_id=None):
    with get_connection() as connection:
        if message_id is None:
            row = connection.execute(
                "SELECT m.id FROM messages m JOIN conversations c ON c.id=m.conversation_id "
                "WHERE m.conversation_id=? AND c.user_id=? AND m.role='assistant' "
                "ORDER BY m.id DESC LIMIT 1",
                (conversation_id, user_id),
            ).fetchone()
        else:
            row = connection.execute(
                "SELECT m.id FROM messages m JOIN conversations c ON c.id=m.conversation_id "
                "WHERE m.conversation_id=? AND m.id=? AND c.user_id=? AND m.role='assistant'",
                (conversation_id, message_id, user_id),
            ).fetchone()
        if row:
            connection.execute("DELETE FROM messages WHERE id=?", (row["id"],))
            return True
    return False


def add_trace_event(trace_id, user_id, event_type, conversation_id=None, tool_name=None,
                    duration_ms=None, success=True, details=None):
    """Persist a safe lifecycle event without storing prompt or response content."""
    import json
    with get_connection() as connection:
        cursor = connection.execute(
            "INSERT INTO trace_events(trace_id,user_id,conversation_id,event_type,tool_name,"
            "duration_ms,success,details,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (trace_id, user_id, conversation_id, event_type, tool_name, duration_ms,
             1 if success else 0, json.dumps(details or {}, sort_keys=True), utc_now()),
        )
    return cursor.lastrowid


def list_trace_events(user_id, trace_id=None, limit=100):
    with get_connection() as connection:
        if trace_id:
            rows = connection.execute(
                "SELECT id,trace_id,conversation_id,event_type,tool_name,duration_ms,success,details,created_at "
                "FROM trace_events WHERE user_id=? AND trace_id=? ORDER BY id LIMIT ?",
                (user_id, trace_id, limit),
            ).fetchall()
        else:
            rows = connection.execute(
                "SELECT id,trace_id,conversation_id,event_type,tool_name,duration_ms,success,details,created_at "
                "FROM trace_events WHERE user_id=? ORDER BY id DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
    return [dict(row) for row in rows]
