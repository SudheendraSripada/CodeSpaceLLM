from __future__ import annotations

import asyncio
import base64
import json
import logging
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelResponse:
    content: str
    provider: str
    model: str


class ModelServiceError(RuntimeError):
    pass


class ModelService:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def complete(
        self,
        *,
        model_name: str,
        system_prompt: str,
        messages: list[dict[str, Any]],
    ) -> ModelResponse:
        provider = self.settings.model_provider
        if provider == "mock":
            return await self._mock_complete(model_name=model_name, messages=messages)
        if provider == "openai":
            return await self._openai_complete(model_name=model_name, system_prompt=system_prompt, messages=messages)
        if provider in {"anthropic", "claude"}:
            return await self._anthropic_complete(model_name=model_name, system_prompt=system_prompt, messages=messages)
        raise ModelServiceError(f"Unsupported MODEL_PROVIDER '{provider}'")

    async def _mock_complete(self, *, model_name: str, messages: list[dict[str, Any]]) -> ModelResponse:
        last_user = next((_content_to_text(item["content"]) for item in reversed(messages) if item["role"] == "user"), "")
        preview = last_user[:600]
        return ModelResponse(
            content=(
                "Mock assistant response. Configure MODEL_PROVIDER=openai or MODEL_PROVIDER=anthropic "
                f"and add an API key to call a real model.\n\nYou said:\n{preview}"
            ),
            provider="mock",
            model=model_name,
        )

    async def _openai_complete(
        self,
        *,
        model_name: str,
        system_prompt: str,
        messages: list[dict[str, Any]],
    ) -> ModelResponse:
        if not self.settings.openai_api_key:
            raise ModelServiceError("OPENAI_API_KEY is required when MODEL_PROVIDER=openai")
        payload = {
            "model": model_name,
            "temperature": self.settings.model_temperature,
            "max_tokens": self.settings.model_max_output_tokens,
            "messages": [{"role": "system", "content": system_prompt}, *_openai_messages(messages)],
        }
        data = await self._post_json(
            f"{self.settings.openai_base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {self.settings.openai_api_key}"},
            json_body=payload,
        )
        try:
            content = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise ModelServiceError("OpenAI response did not include assistant content") from exc
        return ModelResponse(content=content, provider="openai", model=model_name)

    async def _anthropic_complete(
        self,
        *,
        model_name: str,
        system_prompt: str,
        messages: list[dict[str, Any]],
    ) -> ModelResponse:
        if not self.settings.anthropic_api_key:
            raise ModelServiceError("ANTHROPIC_API_KEY is required when MODEL_PROVIDER=anthropic")
        payload = {
            "model": model_name,
            "system": system_prompt,
            "max_tokens": self.settings.model_max_output_tokens,
            "temperature": self.settings.model_temperature,
            "messages": _anthropic_messages(messages),
        }
        data = await self._post_json(
            f"{self.settings.anthropic_base_url.rstrip('/')}/messages",
            headers={
                "x-api-key": self.settings.anthropic_api_key,
                "anthropic-version": "2023-06-01",
            },
            json_body=payload,
        )
        try:
            content_blocks = data["content"]
            content = "\n".join(block.get("text", "") for block in content_blocks if block.get("type") == "text")
        except (KeyError, TypeError) as exc:
            raise ModelServiceError("Anthropic response did not include assistant content") from exc
        return ModelResponse(content=content, provider="anthropic", model=model_name)

    async def _post_json(self, url: str, *, headers: dict[str, str], json_body: dict) -> dict:
        last_error: Exception | None = None
        for attempt in range(self.settings.model_max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.settings.model_timeout_seconds) as client:
                    response = await client.post(url, headers=headers, json=json_body)
                    response.raise_for_status()
                    try:
                        return response.json()
                    except json.JSONDecodeError as exc:
                        raise ModelServiceError("Model provider returned invalid JSON") from exc
            except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.TransportError) as exc:
                last_error = exc
                if isinstance(exc, httpx.HTTPStatusError) and not _should_retry_status(exc.response.status_code):
                    break
                logger.warning("Model request failed on attempt %s: %s", attempt + 1, exc)
                await asyncio.sleep(min(2**attempt, 6))
        raise ModelServiceError(_provider_error_message(last_error)) from last_error


def _openai_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    for item in messages:
        role = item["role"]
        if role == "system":
            continue
        if role not in {"user", "assistant"}:
            role = "user"
        cleaned.append({"role": role, "content": _openai_content(item["content"])})
    return cleaned


def _anthropic_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    for item in messages:
        role = item["role"]
        if role == "system":
            continue
        if role not in {"user", "assistant"}:
            role = "user"
        cleaned.append({"role": role, "content": _anthropic_content(item["content"])})
    return cleaned


def _openai_content(content: Any) -> str | list[dict[str, Any]]:
    if isinstance(content, str):
        return content
    parts: list[dict[str, Any]] = []
    for part in content:
        if part["type"] == "text":
            parts.append({"type": "text", "text": part["text"]})
        elif part["type"] == "image":
            parts.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{part['media_type']};base64,{part['data']}",
                        "detail": "auto",
                    },
                }
            )
    return parts or ""


def _anthropic_content(content: Any) -> str | list[dict[str, Any]]:
    if isinstance(content, str):
        return content
    parts: list[dict[str, Any]] = []
    for part in content:
        if part["type"] == "text":
            parts.append({"type": "text", "text": part["text"]})
        elif part["type"] == "image":
            parts.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": part["media_type"],
                        "data": part["data"],
                    },
                }
            )
    return parts or ""


def image_part_from_file(path: str, media_type: str, filename: str, max_bytes: int) -> dict[str, Any] | None:
    from pathlib import Path

    image_path = Path(path)
    if not image_path.exists() or image_path.stat().st_size > max_bytes:
        return None
    return {
        "type": "image",
        "filename": filename,
        "media_type": _normalize_image_media_type(media_type, image_path.suffix.lower()),
        "data": base64.b64encode(image_path.read_bytes()).decode("ascii"),
    }


def _normalize_image_media_type(media_type: str, suffix: str) -> str:
    if media_type == "image/jpg":
        return "image/jpeg"
    if media_type in {"image/jpeg", "image/png", "image/gif", "image/webp"}:
        return media_type
    suffix_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }
    return suffix_map.get(suffix, "image/png")


def _content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    text_parts = []
    for part in content:
        if part["type"] == "text":
            text_parts.append(part["text"])
        elif part["type"] == "image":
            text_parts.append(f"[Image: {part.get('filename', 'uploaded image')}]")
    return "\n".join(text_parts)


def _should_retry_status(status_code: int) -> bool:
    return status_code == 429 or status_code >= 500


def _provider_error_message(error: Exception | None) -> str:
    if isinstance(error, httpx.HTTPStatusError):
        body = error.response.text[:500]
        return f"Model provider returned HTTP {error.response.status_code}: {body}"
    if error is None:
        return "Model provider request failed"
    return f"Model provider request failed: {error}"
