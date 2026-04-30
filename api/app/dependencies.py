from __future__ import annotations

from collections.abc import Iterator
from sqlite3 import Connection

from fastapi import Depends, Header, HTTPException, Request, status

from app.auth import CurrentUser, decode_access_token
from app.config import Settings
from app.db.session import connection_context


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_db(settings: Settings = Depends(get_settings)) -> Iterator[Connection]:
    yield from connection_context(settings)


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Connection = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> CurrentUser:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_access_token(token, settings)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    user = db.execute(
        "SELECT id, email, role FROM users WHERE id = ?",
        (payload["sub"],),
    ).fetchone()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User no longer exists")
    return CurrentUser(id=user["id"], email=user["email"], role=user["role"])


def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user

