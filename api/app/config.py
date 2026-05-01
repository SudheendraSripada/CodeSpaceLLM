from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _csv_env(name: str, default: list[str]) -> list[str]:
    value = os.getenv(name)
    if not value:
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


def _default_model(provider: str) -> str:
    if provider == "openai":
        return "gpt-4o-mini"
    if provider == "openrouter":
        return "qwen/qwen3-32b"
    if provider == "groq":
        return "qwen/qwen3-32b"
    if provider == "ollama":
        return "qwen3:32b"
    if provider in {"anthropic", "claude"}:
        return "claude-3-5-sonnet-latest"
    return "mock-local"


@dataclass(frozen=True)
class Settings:
    api_root: Path
    database_path: Path
    upload_dir: Path
    auth_provider: str
    data_backend: str
    jwt_secret: str
    access_token_minutes: int
    owner_email: str
    owner_password: str | None
    allow_signups: bool
    cors_origins: list[str]
    model_provider: str
    default_model_name: str
    default_system_prompt: str
    openai_api_key: str | None
    openai_base_url: str
    openai_compatible_api_key: str | None
    openai_compatible_base_url: str | None
    openrouter_api_key: str | None
    groq_api_key: str | None
    anthropic_api_key: str | None
    anthropic_base_url: str
    supabase_url: str | None
    supabase_publishable_key: str | None
    supabase_service_role_key: str | None
    supabase_storage_bucket: str
    model_timeout_seconds: float
    model_max_retries: int
    model_temperature: float
    model_max_output_tokens: int
    max_inline_image_bytes: int

    @classmethod
    def from_env(cls) -> "Settings":
        api_root = Path(__file__).resolve().parents[1]
        repo_root = api_root.parent
        try:
            from dotenv import load_dotenv

            load_dotenv(repo_root / ".env")
            load_dotenv(api_root / ".env")
        except ImportError:
            pass

        provider = os.getenv("MODEL_PROVIDER", "mock").strip().lower()
        return cls(
            api_root=api_root,
            database_path=Path(os.getenv("DATABASE_PATH", api_root / "assistant.db")),
            upload_dir=Path(os.getenv("UPLOAD_DIR", api_root / "uploads")),
            auth_provider=os.getenv("AUTH_PROVIDER", "local").strip().lower(),
            data_backend=os.getenv("DATA_BACKEND", "sqlite").strip().lower(),
            jwt_secret=os.getenv("JWT_SECRET", "dev-only-change-me"),
            access_token_minutes=int(os.getenv("ACCESS_TOKEN_MINUTES", "1440")),
            owner_email=os.getenv("OWNER_EMAIL", "owner@example.com").strip().lower(),
            owner_password=os.getenv("OWNER_PASSWORD"),
            allow_signups=_bool_env("ALLOW_SIGNUPS", True),
            cors_origins=_csv_env(
                "CORS_ORIGINS",
                ["http://localhost:3000", "http://127.0.0.1:3000"],
            ),
            model_provider=provider,
            default_model_name=os.getenv("MODEL_NAME", _default_model(provider)),
            default_system_prompt=os.getenv(
                "SYSTEM_PROMPT",
                "You are a helpful, careful AI assistant. Be concise, honest, and practical.",
            ),
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            openai_compatible_api_key=os.getenv("OPENAI_COMPATIBLE_API_KEY"),
            openai_compatible_base_url=os.getenv("OPENAI_COMPATIBLE_BASE_URL"),
            openrouter_api_key=os.getenv("OPENROUTER_API_KEY"),
            groq_api_key=os.getenv("GROQ_API_KEY"),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
            anthropic_base_url=os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1"),
            supabase_url=os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL"),
            supabase_publishable_key=(
                os.getenv("SUPABASE_PUBLISHABLE_KEY")
                or os.getenv("SUPABASE_ANON_KEY")
                or os.getenv("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY")
            ),
            supabase_service_role_key=os.getenv("SUPABASE_SERVICE_ROLE_KEY"),
            supabase_storage_bucket=os.getenv("SUPABASE_STORAGE_BUCKET", "assistant-files"),
            model_timeout_seconds=float(os.getenv("MODEL_TIMEOUT_SECONDS", "45")),
            model_max_retries=int(os.getenv("MODEL_MAX_RETRIES", "2")),
            model_temperature=float(os.getenv("MODEL_TEMPERATURE", "0.4")),
            model_max_output_tokens=int(os.getenv("MODEL_MAX_OUTPUT_TOKENS", "2048")),
            max_inline_image_bytes=int(os.getenv("MAX_INLINE_IMAGE_BYTES", "5242880")),
        )
