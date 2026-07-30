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
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()

def initialize_database():
    with get_connection() as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL DEFAULT 'New Chat',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('user','assistant')),
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
        );
        """)

def create_conversation(title="New Chat"):
    now = utc_now()
    title = title.strip() or "New Chat"
    with get_connection() as connection:
        cursor = connection.execute(
            "INSERT INTO conversations(title,created_at,updated_at) VALUES(?,?,?)",
            (title, now, now),
        )
        conversation_id = cursor.lastrowid
    return {"id": conversation_id, "title": title, "created_at": now, "updated_at": now}

def list_conversations():
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT id,title,created_at,updated_at FROM conversations ORDER BY updated_at DESC"
        ).fetchall()
    return [dict(row) for row in rows]

def get_conversation(conversation_id):
    with get_connection() as connection:
        row = connection.execute(
            "SELECT id,title,created_at,updated_at FROM conversations WHERE id=?",
            (conversation_id,),
        ).fetchone()
    return dict(row) if row else None

def conversation_exists(conversation_id):
    return get_conversation(conversation_id) is not None

def rename_conversation(conversation_id, title):
    title = title.strip()[:100] or "New Chat"
    now = utc_now()
    with get_connection() as connection:
        connection.execute(
            "UPDATE conversations SET title=?,updated_at=? WHERE id=?",
            (title, now, conversation_id),
        )
    return get_conversation(conversation_id)

def delete_conversation(conversation_id):
    with get_connection() as connection:
        connection.execute("DELETE FROM messages WHERE conversation_id=?", (conversation_id,))
        connection.execute("DELETE FROM conversations WHERE id=?", (conversation_id,))

def clear_all_conversations():
    with get_connection() as connection:
        connection.execute("DELETE FROM messages")
        connection.execute("DELETE FROM conversations")

def save_message(conversation_id, role, content):
    now = utc_now()
    with get_connection() as connection:
        connection.execute(
            "INSERT INTO messages(conversation_id,role,content,created_at) VALUES(?,?,?,?)",
            (conversation_id, role, content, now),
        )
        connection.execute(
            "UPDATE conversations SET updated_at=? WHERE id=?",
            (now, conversation_id),
        )

def get_messages(conversation_id):
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT id,role,content,created_at FROM messages WHERE conversation_id=? ORDER BY id",
            (conversation_id,),
        ).fetchall()
    return [dict(row) for row in rows]

def get_recent_messages(conversation_id, limit=20):
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT role,content FROM messages WHERE conversation_id=? ORDER BY id DESC LIMIT ?",
            (conversation_id, limit),
        ).fetchall()
    return [{"role": row["role"], "content": row["content"]} for row in reversed(rows)]

def update_default_title(conversation_id, first_message):
    conversation = get_conversation(conversation_id)
    if not conversation or conversation["title"] != "New Chat":
        return
    normalized = " ".join(first_message.split())
    title = normalized[:45] + ("…" if len(normalized) > 45 else "")
    rename_conversation(conversation_id, title or "New Chat")

def delete_last_assistant_message(conversation_id):
    with get_connection() as connection:
        row = connection.execute(
            "SELECT id FROM messages WHERE conversation_id=? AND role='assistant' ORDER BY id DESC LIMIT 1",
            (conversation_id,),
        ).fetchone()
        if row:
            connection.execute("DELETE FROM messages WHERE id=?", (row["id"],))
