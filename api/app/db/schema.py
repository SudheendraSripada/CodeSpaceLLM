from __future__ import annotations

import json
from datetime import datetime, timezone

from app.auth import hash_password
from app.config import Settings
from app.db.session import connect


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin', 'user')),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS app_settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    provider TEXT NOT NULL,
    model_name TEXT NOT NULL,
    system_prompt TEXT NOT NULL,
    enabled_tools TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system', 'tool')),
    content TEXT NOT NULL,
    attachments TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS files (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    content_type TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    summary TEXT NOT NULL,
    extracted_text TEXT NOT NULL,
    metadata TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS tool_runs (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    input TEXT NOT NULL,
    output TEXT NOT NULL,
    ok INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_conversations_user_updated
    ON conversations(user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_conversation_created
    ON messages(conversation_id, created_at);
CREATE INDEX IF NOT EXISTS idx_files_user_created
    ON files(user_id, created_at DESC);
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_db(settings: Settings) -> None:
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    with connect(settings) as connection:
        connection.executescript(SCHEMA)
        _ensure_settings(connection, settings)
        _ensure_owner(connection, settings)


def _ensure_settings(connection, settings: Settings) -> None:
    existing = connection.execute("SELECT id FROM app_settings WHERE id = 1").fetchone()
    if existing:
        connection.execute(
            "UPDATE app_settings SET provider = ?, updated_at = ? WHERE id = 1",
            (settings.model_provider, utc_now()),
        )
        return

    connection.execute(
        """
        INSERT INTO app_settings (id, provider, model_name, system_prompt, enabled_tools, updated_at)
        VALUES (1, ?, ?, ?, ?, ?)
        """,
        (
            settings.model_provider,
            settings.default_model_name,
            settings.default_system_prompt,
            json.dumps(["datetime", "calculator", "summarize_file"]),
            utc_now(),
        ),
    )


def _ensure_owner(connection, settings: Settings) -> None:
    if not settings.owner_password:
        return

    existing = connection.execute(
        "SELECT id, role FROM users WHERE email = ?",
        (settings.owner_email,),
    ).fetchone()
    if existing:
        if existing["role"] != "admin":
            connection.execute("UPDATE users SET role = 'admin' WHERE id = ?", (existing["id"],))
        return

    import uuid

    connection.execute(
        """
        INSERT INTO users (id, email, password_hash, role, created_at)
        VALUES (?, ?, ?, 'admin', ?)
        """,
        (str(uuid.uuid4()), settings.owner_email, hash_password(settings.owner_password), utc_now()),
    )

