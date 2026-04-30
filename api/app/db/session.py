from __future__ import annotations

import sqlite3
from collections.abc import Iterator

from app.config import Settings


def connect(settings: Settings) -> sqlite3.Connection:
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(settings.database_path, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def connection_context(settings: Settings) -> Iterator[sqlite3.Connection]:
    connection = connect(settings)
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()
