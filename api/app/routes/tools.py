from __future__ import annotations

from fastapi import APIRouter, Depends

from app.auth import CurrentUser
from app.config import Settings
from app.dependencies import get_current_user, get_db, get_settings
from app.schemas import ToolCallRequest, ToolCallResponse
from app.services.settings_service import get_app_settings
from app.services.tool_dispatcher import ToolDispatcher

router = APIRouter(prefix="/api/tools", tags=["tools"])


@router.get("")
def list_tools(
    user: CurrentUser = Depends(get_current_user),
    db=Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    app_settings = get_app_settings(db, settings)
    dispatcher = ToolDispatcher(db, user, app_settings["enabled_tools"])
    return {"available": dispatcher.available_tools, "enabled": app_settings["enabled_tools"]}


@router.post("/call", response_model=ToolCallResponse)
def call_tool(
    payload: ToolCallRequest,
    user: CurrentUser = Depends(get_current_user),
    db=Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    app_settings = get_app_settings(db, settings)
    return ToolDispatcher(db, user, app_settings["enabled_tools"]).call(payload.name, payload.arguments)

