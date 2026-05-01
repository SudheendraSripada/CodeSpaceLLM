from __future__ import annotations

from fastapi import APIRouter, Depends

from app.auth import CurrentUser
from app.config import Settings
from app.dependencies import get_current_user, get_db, get_settings
from app.schemas import ToolCallRequest, ToolCallResponse
from app.services.settings_service import get_app_settings
from app.services.supabase_store import SupabaseStore
from app.services.tool_dispatcher import ToolDispatcher

router = APIRouter(prefix="/api/tools", tags=["tools"])


@router.get("")
def list_tools(
    user: CurrentUser = Depends(get_current_user),
    db=Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    app_settings = SupabaseStore(settings).get_app_settings() if settings.data_backend == "supabase" else get_app_settings(db, settings)
    dispatcher = ToolDispatcher(db, user, app_settings["enabled_tools"])
    return {"available": dispatcher.available_tools, "enabled": app_settings["enabled_tools"]}


@router.post("/call", response_model=ToolCallResponse)
def call_tool(
    payload: ToolCallRequest,
    user: CurrentUser = Depends(get_current_user),
    db=Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    app_settings = SupabaseStore(settings).get_app_settings() if settings.data_backend == "supabase" else get_app_settings(db, settings)
    if settings.data_backend == "supabase" and payload.name == "summarize_file":
        if payload.name not in app_settings["enabled_tools"]:
            from fastapi import HTTPException, status

            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Tool disabled: {payload.name}")
        file_id = str(payload.arguments.get("file_id", ""))
        if not file_id:
            return {"name": payload.name, "ok": False, "result": None, "error": "Missing file_id"}
        store = SupabaseStore(settings)
        file_context = store.get_file_contexts(user, [file_id])[0]
        result = {
            "file_id": file_id,
            "filename": file_context["filename"],
            "summary": file_context["summary"],
            "preview": (file_context.get("extracted_text") or "")[:1200],
        }
        store.record_tool_run(user=user, tool_name=payload.name, input_data=payload.arguments, output=result, ok=True)
        return {"name": payload.name, "ok": True, "result": result, "error": None}
    return ToolDispatcher(db, user, app_settings["enabled_tools"]).call(payload.name, payload.arguments)
