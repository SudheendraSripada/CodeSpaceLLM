from __future__ import annotations

import json
import uuid
from sqlite3 import Connection

from fastapi import HTTPException, status

from app.auth import CurrentUser
from app.db.schema import utc_now


def list_conversations(db: Connection, user: CurrentUser) -> list[dict]:
    rows = db.execute(
        """
        SELECT id, title, created_at, updated_at
        FROM conversations
        WHERE user_id = ?
        ORDER BY updated_at DESC
        LIMIT 100
        """,
        (user.id,),
    ).fetchall()
    return [dict(row) for row in rows]


def get_or_create_conversation(db: Connection, user: CurrentUser, conversation_id: str | None, first_message: str) -> dict:
    if conversation_id:
        row = db.execute(
            """
            SELECT id, title, created_at, updated_at
            FROM conversations
            WHERE id = ? AND user_id = ?
            """,
            (conversation_id, user.id),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
        return dict(row)

    now = utc_now()
    new_id = str(uuid.uuid4())
    title = _title_from_message(first_message)
    db.execute(
        """
        INSERT INTO conversations (id, user_id, title, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (new_id, user.id, title, now, now),
    )
    db.commit()
    return {"id": new_id, "title": title, "created_at": now, "updated_at": now}


def add_message(
    db: Connection,
    *,
    user: CurrentUser,
    conversation_id: str,
    role: str,
    content: str,
    attachments: list[dict] | None = None,
) -> dict:
    now = utc_now()
    message_id = str(uuid.uuid4())
    db.execute(
        """
        INSERT INTO messages (id, conversation_id, user_id, role, content, attachments, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (message_id, conversation_id, user.id, role, content, json.dumps(attachments or []), now),
    )
    db.execute(
        "UPDATE conversations SET updated_at = ? WHERE id = ? AND user_id = ?",
        (now, conversation_id, user.id),
    )
    db.commit()
    return {
        "id": message_id,
        "role": role,
        "content": content,
        "attachments": attachments or [],
        "created_at": now,
    }


def list_messages(db: Connection, user: CurrentUser, conversation_id: str) -> list[dict]:
    _ensure_conversation(db, user, conversation_id)
    rows = db.execute(
        """
        SELECT id, role, content, attachments, created_at
        FROM messages
        WHERE conversation_id = ?
        ORDER BY created_at ASC
        """,
        (conversation_id,),
    ).fetchall()
    return [_message_from_row(row) for row in rows]


def model_history(db: Connection, user: CurrentUser, conversation_id: str, limit: int = 20) -> list[dict]:
    _ensure_conversation(db, user, conversation_id)
    rows = db.execute(
        """
        SELECT role, content
        FROM messages
        WHERE conversation_id = ? AND role IN ('user', 'assistant')
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (conversation_id, limit),
    ).fetchall()
    return [{"role": row["role"], "content": row["content"]} for row in reversed(rows)]


def get_conversation(db: Connection, user: CurrentUser, conversation_id: str) -> dict:
    row = db.execute(
        """
        SELECT id, title, created_at, updated_at
        FROM conversations
        WHERE id = ? AND user_id = ?
        """,
        (conversation_id, user.id),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return dict(row)


def _ensure_conversation(db: Connection, user: CurrentUser, conversation_id: str) -> None:
    get_conversation(db, user, conversation_id)


def _message_from_row(row) -> dict:
    return {
        "id": row["id"],
        "role": row["role"],
        "content": row["content"],
        "attachments": json.loads(row["attachments"]),
        "created_at": row["created_at"],
    }


def _title_from_message(message: str) -> str:
    one_line = " ".join(message.split())
    if len(one_line) <= 48:
        return one_line or "New conversation"
    return one_line[:45].rstrip() + "..."

