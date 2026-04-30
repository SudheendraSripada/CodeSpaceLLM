from __future__ import annotations

import json
from sqlite3 import Connection

from fastapi import HTTPException, status

from app.config import Settings
from app.db.schema import utc_now


def get_app_settings(db: Connection, env_settings: Settings) -> dict:
    row = db.execute(
        """
        SELECT provider, model_name, system_prompt, enabled_tools, updated_at
        FROM app_settings
        WHERE id = 1
        """
    ).fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Settings are not initialized")
    return {
        "provider": env_settings.model_provider,
        "model_name": row["model_name"],
        "system_prompt": row["system_prompt"],
        "enabled_tools": json.loads(row["enabled_tools"]),
        "updated_at": row["updated_at"],
    }


def update_app_settings(
    db: Connection,
    *,
    env_settings: Settings,
    model_name: str,
    system_prompt: str,
    enabled_tools: list[str],
) -> dict:
    unique_tools = sorted({tool.strip() for tool in enabled_tools if tool.strip()})
    db.execute(
        """
        UPDATE app_settings
        SET provider = ?, model_name = ?, system_prompt = ?, enabled_tools = ?, updated_at = ?
        WHERE id = 1
        """,
        (
            env_settings.model_provider,
            model_name.strip(),
            system_prompt.strip(),
            json.dumps(unique_tools),
            utc_now(),
        ),
    )
    db.commit()
    return get_app_settings(db, env_settings)

