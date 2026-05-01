from __future__ import annotations

import json
import mimetypes
import shutil
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx
from fastapi import HTTPException, UploadFile, status

from app.auth import CurrentUser
from app.config import Settings
from app.db.schema import utc_now
from app.services.file_processor import _safe_filename, process_file


class SupabaseConfigError(RuntimeError):
    pass


def verify_supabase_user(settings: Settings, token: str) -> CurrentUser:
    _require_supabase_auth(settings)
    response = httpx.get(
        f"{settings.supabase_url.rstrip('/')}/auth/v1/user",
        headers={
            "apikey": settings.supabase_publishable_key or "",
            "Authorization": f"Bearer {token}",
        },
        timeout=15,
    )
    if response.status_code >= 400:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Supabase session")

    data = response.json()
    user_id = data.get("id")
    email = (data.get("email") or "").lower()
    if not user_id or not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Supabase user is missing id or email")

    role = "admin" if email == settings.owner_email else "user"
    if settings.data_backend == "supabase" and settings.supabase_service_role_key:
        store = SupabaseStore(settings)
        profile = store.ensure_profile(user_id, email, role)
        role = profile.get("role") or role
    return CurrentUser(id=user_id, email=email, role=role)


class SupabaseStore:
    def __init__(self, settings: Settings):
        self.settings = settings
        _require_supabase_data(settings)
        self.base_url = settings.supabase_url.rstrip("/")
        self.service_key = settings.supabase_service_role_key or ""

    def ensure_defaults(self) -> None:
        settings = self.get_app_settings(allow_missing=True)
        if settings:
            self._rest("PATCH", "app_settings", query="?id=eq.1", json_body={"provider": self.settings.model_provider})
            return

        self._rest(
            "POST",
            "app_settings",
            json_body={
                "id": 1,
                "provider": self.settings.model_provider,
                "model_name": self.settings.default_model_name,
                "system_prompt": self.settings.default_system_prompt,
                "enabled_tools": ["datetime", "calculator", "summarize_file"],
                "updated_at": utc_now(),
            },
        )

    def ensure_profile(self, user_id: str, email: str, default_role: str) -> dict[str, Any]:
        existing = self._rest(
            "GET",
            "profiles",
            query=f"?id=eq.{quote(user_id)}&select=*",
            prefer_return=False,
        )
        if existing:
            return existing[0]

        created = self._rest(
            "POST",
            "profiles",
            json_body={"id": user_id, "email": email.lower(), "role": default_role, "created_at": utc_now()},
        )
        return created[0]

    def get_app_settings(self, allow_missing: bool = False) -> dict[str, Any] | None:
        rows = self._rest("GET", "app_settings", query="?id=eq.1&select=*", prefer_return=False)
        if not rows:
            if allow_missing:
                return None
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Supabase settings row is missing")
        row = rows[0]
        return {
            "provider": self.settings.model_provider,
            "model_name": row["model_name"],
            "system_prompt": row["system_prompt"],
            "enabled_tools": row.get("enabled_tools") or [],
            "updated_at": row["updated_at"],
        }

    def update_app_settings(self, *, model_name: str, system_prompt: str, enabled_tools: list[str]) -> dict[str, Any]:
        unique_tools = sorted({tool.strip() for tool in enabled_tools if tool.strip()})
        self._rest(
            "PATCH",
            "app_settings",
            query="?id=eq.1",
            json_body={
                "provider": self.settings.model_provider,
                "model_name": model_name.strip(),
                "system_prompt": system_prompt.strip(),
                "enabled_tools": unique_tools,
                "updated_at": utc_now(),
            },
        )
        current = self.get_app_settings()
        assert current is not None
        return current

    def list_conversations(self, user: CurrentUser) -> list[dict[str, Any]]:
        return self._rest(
            "GET",
            "conversations",
            query=f"?user_id=eq.{quote(user.id)}&select=id,title,created_at,updated_at&order=updated_at.desc&limit=100",
            prefer_return=False,
        )

    def get_conversation(self, user: CurrentUser, conversation_id: str) -> dict[str, Any]:
        rows = self._rest(
            "GET",
            "conversations",
            query=f"?id=eq.{quote(conversation_id)}&user_id=eq.{quote(user.id)}&select=id,title,created_at,updated_at",
            prefer_return=False,
        )
        if not rows:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
        return rows[0]

    def get_or_create_conversation(self, user: CurrentUser, conversation_id: str | None, first_message: str) -> dict[str, Any]:
        if conversation_id:
            return self.get_conversation(user, conversation_id)

        now = utc_now()
        created = self._rest(
            "POST",
            "conversations",
            json_body={
                "id": str(uuid.uuid4()),
                "user_id": user.id,
                "title": _title_from_message(first_message),
                "created_at": now,
                "updated_at": now,
            },
        )
        return created[0]

    def add_message(
        self,
        *,
        user: CurrentUser,
        conversation_id: str,
        role: str,
        content: str,
        attachments: list[dict] | None = None,
    ) -> dict[str, Any]:
        now = utc_now()
        created = self._rest(
            "POST",
            "messages",
            json_body={
                "id": str(uuid.uuid4()),
                "conversation_id": conversation_id,
                "user_id": user.id,
                "role": role,
                "content": content,
                "attachments": attachments or [],
                "created_at": now,
            },
        )
        self._rest(
            "PATCH",
            "conversations",
            query=f"?id=eq.{quote(conversation_id)}&user_id=eq.{quote(user.id)}",
            json_body={"updated_at": now},
        )
        return _message_out(created[0])

    def list_messages(self, user: CurrentUser, conversation_id: str) -> list[dict[str, Any]]:
        self.get_conversation(user, conversation_id)
        rows = self._rest(
            "GET",
            "messages",
            query=f"?conversation_id=eq.{quote(conversation_id)}&select=id,role,content,attachments,created_at&order=created_at.asc",
            prefer_return=False,
        )
        return [_message_out(row) for row in rows]

    def model_history(self, user: CurrentUser, conversation_id: str, limit: int = 20) -> list[dict[str, Any]]:
        self.get_conversation(user, conversation_id)
        rows = self._rest(
            "GET",
            "messages",
            query=(
                f"?conversation_id=eq.{quote(conversation_id)}"
                "&role=in.(user,assistant)&select=role,content&order=created_at.desc"
                f"&limit={limit}"
            ),
            prefer_return=False,
        )
        return [{"role": row["role"], "content": row["content"]} for row in reversed(rows)]

    def list_files_for_user(self, user: CurrentUser) -> list[dict[str, Any]]:
        rows = self._rest(
            "GET",
            "files",
            query=f"?user_id=eq.{quote(user.id)}&select=id,filename,content_type,summary,metadata,created_at&order=created_at.desc&limit=50",
            prefer_return=False,
        )
        return [_file_out(row) for row in rows]

    def save_and_process_upload(self, *, user: CurrentUser, upload: UploadFile) -> dict[str, Any]:
        filename = _safe_filename(upload.filename or "upload")
        content_type = upload.content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
        file_id = str(uuid.uuid4())
        local_path = self.settings.upload_dir / f"{file_id}-{filename}"
        self.settings.upload_dir.mkdir(parents=True, exist_ok=True)

        with local_path.open("wb") as destination:
            shutil.copyfileobj(upload.file, destination)

        try:
            extracted = process_file(local_path, content_type)
            storage_key = f"{user.id}/{file_id}/{filename}"
            self._upload_object(storage_key, local_path, content_type)
            created = self._rest(
                "POST",
                "files",
                json_body={
                    "id": file_id,
                    "user_id": user.id,
                    "filename": filename,
                    "content_type": content_type,
                    "storage_path": f"supabase://{self.settings.supabase_storage_bucket}/{storage_key}",
                    "summary": extracted["summary"],
                    "extracted_text": extracted["extracted_text"],
                    "metadata": json.loads(extracted["metadata_json"]),
                    "created_at": utc_now(),
                },
            )
        except Exception:
            local_path.unlink(missing_ok=True)
            raise
        return _file_out(created[0])

    def get_file_contexts(self, user: CurrentUser, file_ids: list[str]) -> list[dict[str, Any]]:
        if not file_ids:
            return []
        id_filter = ",".join(quote(file_id) for file_id in file_ids)
        rows = self._rest(
            "GET",
            "files",
            query=f"?user_id=eq.{quote(user.id)}&id=in.({id_filter})&select=*",
            prefer_return=False,
        )
        found = {row["id"] for row in rows}
        missing = set(file_ids) - found
        if missing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"File not found: {sorted(missing)[0]}")
        return [self._file_context(row) for row in rows]

    def record_tool_run(self, *, user: CurrentUser, tool_name: str, input_data: dict[str, Any], output: dict[str, Any], ok: bool) -> None:
        self._rest(
            "POST",
            "tool_runs",
            json_body={
                "id": str(uuid.uuid4()),
                "user_id": user.id,
                "tool_name": tool_name,
                "input": input_data,
                "output": output,
                "ok": ok,
                "created_at": utc_now(),
            },
        )

    def _file_context(self, row: dict[str, Any]) -> dict[str, Any]:
        storage_path = row["storage_path"]
        local_path = self.settings.upload_dir / f"{row['id']}-{row['filename']}"
        if storage_path.startswith("supabase://") and not local_path.exists():
            local_path.parent.mkdir(parents=True, exist_ok=True)
            storage_key = storage_path.split("/", 3)[3]
            local_path.write_bytes(self._download_object(storage_key))
        return {
            "id": row["id"],
            "filename": row["filename"],
            "content_type": row["content_type"],
            "storage_path": str(local_path),
            "summary": row["summary"],
            "extracted_text": row["extracted_text"],
            "metadata": row.get("metadata") or {},
            "created_at": row["created_at"],
        }

    def _upload_object(self, storage_key: str, path: Path, content_type: str) -> None:
        encoded_key = quote(storage_key, safe="/")
        response = httpx.post(
            f"{self.base_url}/storage/v1/object/{self.settings.supabase_storage_bucket}/{encoded_key}",
            headers={
                "apikey": self.service_key,
                "Authorization": f"Bearer {self.service_key}",
                "Content-Type": content_type,
                "x-upsert": "true",
            },
            content=path.read_bytes(),
            timeout=60,
        )
        _raise_for_supabase(response)

    def _download_object(self, storage_key: str) -> bytes:
        encoded_key = quote(storage_key, safe="/")
        response = httpx.get(
            f"{self.base_url}/storage/v1/object/{self.settings.supabase_storage_bucket}/{encoded_key}",
            headers={"apikey": self.service_key, "Authorization": f"Bearer {self.service_key}"},
            timeout=60,
        )
        _raise_for_supabase(response)
        return response.content

    def _rest(
        self,
        method: str,
        table: str,
        *,
        query: str = "",
        json_body: dict[str, Any] | None = None,
        prefer_return: bool = True,
    ) -> list[dict[str, Any]]:
        headers = {
            "apikey": self.service_key,
            "Authorization": f"Bearer {self.service_key}",
            "Content-Type": "application/json",
        }
        if prefer_return:
            headers["Prefer"] = "return=representation"

        response = httpx.request(
            method,
            f"{self.base_url}/rest/v1/{table}{query}",
            headers=headers,
            json=json_body,
            timeout=30,
        )
        _raise_for_supabase(response)
        if response.status_code == 204 or not response.content:
            return []
        return response.json()


def _require_supabase_auth(settings: Settings) -> None:
    if not settings.supabase_url or not settings.supabase_publishable_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Supabase auth requires SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY",
        )


def _require_supabase_data(settings: Settings) -> None:
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise SupabaseConfigError("Supabase data backend requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY")


def _raise_for_supabase(response: httpx.Response) -> None:
    if response.status_code < 400:
        return
    detail = response.text[:500]
    raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Supabase request failed: {detail}")


def _message_out(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "role": row["role"],
        "content": row["content"],
        "attachments": row.get("attachments") or [],
        "created_at": row["created_at"],
    }


def _file_out(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "filename": row["filename"],
        "content_type": row["content_type"],
        "summary": row["summary"],
        "metadata": row.get("metadata") or {},
        "created_at": row["created_at"],
    }


def _title_from_message(message: str) -> str:
    one_line = " ".join(message.split())
    if len(one_line) <= 48:
        return one_line or "New conversation"
    return one_line[:45].rstrip() + "..."
