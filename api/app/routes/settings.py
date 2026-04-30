from __future__ import annotations

from fastapi import APIRouter, Depends

from app.auth import CurrentUser
from app.config import Settings
from app.dependencies import get_db, get_settings, require_admin
from app.schemas import AppSettingsOut, AppSettingsUpdate
from app.services.settings_service import get_app_settings, update_app_settings

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=AppSettingsOut)
def read_settings(
    _admin: CurrentUser = Depends(require_admin),
    db=Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    return get_app_settings(db, settings)


@router.put("", response_model=AppSettingsOut)
def write_settings(
    payload: AppSettingsUpdate,
    _admin: CurrentUser = Depends(require_admin),
    db=Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    return update_app_settings(
        db,
        env_settings=settings,
        model_name=payload.model_name,
        system_prompt=payload.system_prompt,
        enabled_tools=payload.enabled_tools,
    )

