from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import Settings
from app.db.schema import init_db
from app.routes import auth, chat, files, settings, tools
from app.services.supabase_store import SupabaseStore


def create_app() -> FastAPI:
    app_settings = Settings.from_env()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = app_settings
        if app_settings.data_backend == "supabase":
            SupabaseStore(app_settings).ensure_defaults()
        else:
            init_db(app_settings)
        yield

    app = FastAPI(title="AI Assistant Foundation API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_logging(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        logging.getLogger("app.requests").info(
            "%s %s -> %s %.1fms",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception):
        logging.getLogger(__name__).exception("Unhandled error for %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"ok": "true", "provider": app_settings.model_provider}

    app.include_router(auth.router)
    app.include_router(chat.router)
    app.include_router(files.router)
    app.include_router(settings.router)
    app.include_router(tools.router)
    return app


app = create_app()
