from __future__ import annotations

import uuid
from sqlite3 import Connection, IntegrityError

from fastapi import HTTPException, status

from app.auth import CurrentUser, hash_password
from app.db.schema import utc_now


def create_user(db: Connection, email: str, password: str, role: str = "user") -> CurrentUser:
    user_id = str(uuid.uuid4())
    try:
        db.execute(
            """
            INSERT INTO users (id, email, password_hash, role, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, email.lower(), hash_password(password), role, utc_now()),
        )
        db.commit()
    except IntegrityError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered") from exc
    return CurrentUser(id=user_id, email=email.lower(), role=role)


def get_user_by_email(db: Connection, email: str):
    return db.execute(
        "SELECT id, email, password_hash, role FROM users WHERE email = ?",
        (email.lower(),),
    ).fetchone()

