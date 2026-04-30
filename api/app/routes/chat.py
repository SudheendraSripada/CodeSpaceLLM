from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import CurrentUser
from app.config import Settings
from app.dependencies import get_current_user, get_db, get_settings
from app.schemas import ChatRequest, ChatResponse, ConversationOut, MessageOut
from app.services.conversation_service import (
    add_message,
    get_conversation,
    get_or_create_conversation,
    list_conversations,
    list_messages,
    model_history,
)
from app.services.file_processor import get_file_contexts
from app.services.model_service import ModelService, ModelServiceError, image_part_from_file
from app.services.settings_service import get_app_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.get("/conversations", response_model=list[ConversationOut])
def conversations(
    user: CurrentUser = Depends(get_current_user),
    db=Depends(get_db),
) -> list[dict]:
    return list_conversations(db, user)


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageOut])
def messages(
    conversation_id: str,
    user: CurrentUser = Depends(get_current_user),
    db=Depends(get_db),
) -> list[dict]:
    return list_messages(db, user, conversation_id)


@router.post("", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    user: CurrentUser = Depends(get_current_user),
    db=Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    conversation = get_or_create_conversation(db, user, payload.conversation_id, payload.message)
    file_contexts = get_file_contexts(db, user, payload.file_ids)
    attachment_summaries = [_attachment_out(item) for item in file_contexts]

    user_content_for_model = _message_with_file_context(payload.message, file_contexts, settings)
    add_message(
        db,
        user=user,
        conversation_id=conversation["id"],
        role="user",
        content=payload.message,
        attachments=attachment_summaries,
    )

    app_settings = get_app_settings(db, settings)
    history = model_history(db, user, conversation["id"])
    if history and history[-1]["role"] == "user":
        history[-1]["content"] = user_content_for_model

    try:
        model_response = await ModelService(settings).complete(
            model_name=app_settings["model_name"],
            system_prompt=app_settings["system_prompt"],
            messages=history,
        )
    except ModelServiceError as exc:
        logger.exception("Chat model call failed")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    assistant_message = add_message(
        db,
        user=user,
        conversation_id=conversation["id"],
        role="assistant",
        content=model_response.content,
    )
    return {
        "conversation": get_conversation(db, user, conversation["id"]),
        "message": assistant_message,
    }


def _message_with_file_context(message: str, file_contexts: list[dict], settings: Settings) -> str | list[dict]:
    if not file_contexts:
        return message
    sections = []
    content_parts: list[dict] = []
    for item in file_contexts:
        extracted = item.get("extracted_text") or ""
        image_note = ""
        if item["content_type"].startswith("image/"):
            image_part = image_part_from_file(
                item["storage_path"],
                item["content_type"],
                item["filename"],
                settings.max_inline_image_bytes,
            )
            if image_part:
                content_parts.append(image_part)
                image_note = "Image bytes attached for model vision."
            else:
                image_note = "Image bytes were not attached because the file is missing or too large."
        sections.append(
            "\n".join(
                [
                    f"File: {item['filename']}",
                    f"Type: {item['content_type']}",
                    f"Summary: {item['summary']}",
                    image_note,
                    f"Extracted text: {extracted[:8000] if extracted else '[No text extracted]'}",
                ]
            )
        )
    text = f"{message}\n\nAttached file context:\n\n" + "\n\n---\n\n".join(sections)
    if not content_parts:
        return text
    return [{"type": "text", "text": text}, *content_parts]


def _attachment_out(item: dict) -> dict:
    return {
        "id": item["id"],
        "filename": item["filename"],
        "content_type": item["content_type"],
        "summary": item["summary"],
        "metadata": item["metadata"],
        "created_at": item["created_at"],
    }
