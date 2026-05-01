from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile

from app.auth import CurrentUser
from app.config import Settings
from app.dependencies import get_current_user, get_db, get_settings
from app.schemas import FileOut
from app.services.file_processor import list_files_for_user, save_and_process_upload
from app.services.supabase_store import SupabaseStore

router = APIRouter(prefix="/api/files", tags=["files"])


@router.get("", response_model=list[FileOut])
def list_files(
    user: CurrentUser = Depends(get_current_user),
    db=Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> list[dict]:
    if settings.data_backend == "supabase":
        return SupabaseStore(settings).list_files_for_user(user)
    return list_files_for_user(db, user)


@router.post("/upload", response_model=FileOut)
def upload_file(
    file: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user),
    db=Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    if settings.data_backend == "supabase":
        return SupabaseStore(settings).save_and_process_upload(user=user, upload=file)
    return save_and_process_upload(db=db, settings=settings, user=user, upload=file)
