from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field


class UserOut(BaseModel):
    id: str
    email: EmailStr
    role: Literal["admin", "user"]


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class RegisterRequest(LoginRequest):
    pass


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class AppSettingsOut(BaseModel):
    provider: str
    model_name: str
    system_prompt: str
    enabled_tools: list[str]
    updated_at: str


class AppSettingsUpdate(BaseModel):
    model_name: str = Field(min_length=1, max_length=120)
    system_prompt: str = Field(min_length=1, max_length=8000)
    enabled_tools: list[str] = Field(default_factory=list)


class FileOut(BaseModel):
    id: str
    filename: str
    content_type: str
    summary: str
    metadata: dict[str, Any]
    created_at: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=20000)
    conversation_id: str | None = None
    file_ids: list[str] = Field(default_factory=list)


class MessageOut(BaseModel):
    id: str
    role: Literal["user", "assistant", "system", "tool"]
    content: str
    attachments: list[FileOut] = Field(default_factory=list)
    created_at: str


class ConversationOut(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str


class ChatResponse(BaseModel):
    conversation: ConversationOut
    message: MessageOut


class ToolCallRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolCallResponse(BaseModel):
    name: str
    ok: bool
    result: dict[str, Any] | None = None
    error: str | None = None

