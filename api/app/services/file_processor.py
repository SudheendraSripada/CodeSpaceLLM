from __future__ import annotations

import mimetypes
import re
import shutil
import uuid
from pathlib import Path
from sqlite3 import Connection

from fastapi import HTTPException, UploadFile, status

from app.auth import CurrentUser
from app.config import Settings
from app.db.schema import utc_now

MAX_TEXT_CHARS = 50_000
SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def save_and_process_upload(
    *,
    db: Connection,
    settings: Settings,
    user: CurrentUser,
    upload: UploadFile,
) -> dict:
    filename = _safe_filename(upload.filename or "upload")
    content_type = upload.content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
    file_id = str(uuid.uuid4())
    storage_name = f"{file_id}-{filename}"
    storage_path = settings.upload_dir / storage_name
    settings.upload_dir.mkdir(parents=True, exist_ok=True)

    with storage_path.open("wb") as destination:
        shutil.copyfileobj(upload.file, destination)

    try:
        extracted = process_file(storage_path, content_type)
    except Exception:
        storage_path.unlink(missing_ok=True)
        raise
    db.execute(
        """
        INSERT INTO files (id, user_id, filename, content_type, storage_path, summary, extracted_text, metadata, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            file_id,
            user.id,
            filename,
            content_type,
            str(storage_path),
            extracted["summary"],
            extracted["extracted_text"],
            extracted["metadata_json"],
            utc_now(),
        ),
    )
    db.commit()
    return get_file_for_user(db, user, file_id)


def get_file_for_user(db: Connection, user: CurrentUser, file_id: str) -> dict:
    row = db.execute(
        """
        SELECT id, filename, content_type, summary, metadata, created_at
        FROM files
        WHERE id = ? AND user_id = ?
        """,
        (file_id, user.id),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    import json

    return {
        "id": row["id"],
        "filename": row["filename"],
        "content_type": row["content_type"],
        "summary": row["summary"],
        "metadata": json.loads(row["metadata"]),
        "created_at": row["created_at"],
    }


def get_file_contexts(db: Connection, user: CurrentUser, file_ids: list[str]) -> list[dict]:
    if not file_ids:
        return []
    placeholders = ",".join("?" for _ in file_ids)
    rows = db.execute(
        f"""
        SELECT id, filename, content_type, storage_path, summary, extracted_text, metadata, created_at
        FROM files
        WHERE user_id = ? AND id IN ({placeholders})
        """,
        (user.id, *file_ids),
    ).fetchall()
    found = {row["id"] for row in rows}
    missing = set(file_ids) - found
    if missing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"File not found: {sorted(missing)[0]}")

    import json

    return [
        {
            "id": row["id"],
            "filename": row["filename"],
            "content_type": row["content_type"],
            "storage_path": row["storage_path"],
            "summary": row["summary"],
            "extracted_text": row["extracted_text"],
            "metadata": json.loads(row["metadata"]),
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def list_files_for_user(db: Connection, user: CurrentUser) -> list[dict]:
    rows = db.execute(
        """
        SELECT id, filename, content_type, summary, metadata, created_at
        FROM files
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT 50
        """,
        (user.id,),
    ).fetchall()
    import json

    return [
        {
            "id": row["id"],
            "filename": row["filename"],
            "content_type": row["content_type"],
            "summary": row["summary"],
            "metadata": json.loads(row["metadata"]),
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def process_file(path: Path, content_type: str) -> dict:
    if content_type.startswith("text/") or path.suffix.lower() in {".txt", ".md", ".csv", ".json", ".log"}:
        return _process_text(path)
    if content_type == "application/pdf" or path.suffix.lower() == ".pdf":
        return _process_pdf(path)
    if content_type.startswith("image/") or path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
        return _process_image(path)
    raise HTTPException(
        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        detail="Unsupported file type. Upload images, PDFs, or text files.",
    )


def _process_text(path: Path) -> dict:
    data = path.read_bytes()
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("latin-1", errors="replace")
    text = text[:MAX_TEXT_CHARS]
    return _processed(
        summary=f"Text file with {len(text)} extracted characters.",
        extracted_text=text,
        metadata={"kind": "text", "bytes": path.stat().st_size},
    )


def _process_pdf(path: Path) -> dict:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="PDF processing requires pypdf. Install backend requirements.",
        ) from exc

    reader = PdfReader(str(path))
    page_text = []
    for page in reader.pages:
        page_text.append(page.extract_text() or "")
    text = "\n\n".join(page_text)[:MAX_TEXT_CHARS]
    return _processed(
        summary=f"PDF with {len(reader.pages)} page(s) and {len(text)} extracted characters.",
        extracted_text=text,
        metadata={"kind": "pdf", "pages": len(reader.pages), "bytes": path.stat().st_size},
    )


def _process_image(path: Path) -> dict:
    try:
        from PIL import Image
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Image processing requires Pillow. Install backend requirements.",
        ) from exc

    with Image.open(path) as image:
        metadata = {
            "kind": "image",
            "format": image.format,
            "width": image.width,
            "height": image.height,
            "mode": image.mode,
            "bytes": path.stat().st_size,
        }
    # TODO: Add OCR or vision-model captioning when a production provider is configured.
    return _processed(
        summary=f"Image file ({metadata['format'] or 'unknown'}) {metadata['width']}x{metadata['height']}.",
        extracted_text="",
        metadata=metadata,
    )


def _processed(*, summary: str, extracted_text: str, metadata: dict) -> dict:
    import json

    return {
        "summary": summary,
        "extracted_text": extracted_text,
        "metadata_json": json.dumps(metadata),
    }


def _safe_filename(filename: str) -> str:
    cleaned = SAFE_NAME_RE.sub("-", Path(filename).name).strip(".-")
    return cleaned or "upload"
