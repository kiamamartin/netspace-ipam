"""FastAPI application entry point.

Run locally:

    uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import get_logger, setup_logging
from app.db.session import init_db
from app.schemas.inventory import HealthResponse

settings = get_settings()
logger = get_logger("netspace")


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(settings.log_level)
    logger.info("Starting %s (DB: %s)", settings.app_name, _db_label())
    init_db()  # dev convenience; Alembic owns the production schema
    yield
    logger.info("Shutting down %s", settings.app_name)


def _db_label() -> str:
    url = settings.database_url
    return url.split("://", 1)[0] if "://" in url else "sqlite"


class MaxBodySizeMiddleware:
    """Reject oversized request bodies before they are read (M5-AC-007)."""

    def __init__(self, app: object, max_bytes: int = 1_048_576) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):  # type: ignore[no-untyped-def]
        if scope["type"] == "http":
            content_length = next(
                (v for k, v in ((k.decode(), x) for k, x in scope.get("headers", [])) if k == "content-length"),
                None,
            )
            if content_length is not None and int(content_length) > self.max_bytes:
                response = RichTooLarge()
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


class RichTooLarge:
    def __init__(self) -> None:
        pass

    async def __call__(self, scope, receive, send):  # type: ignore[no-untyped-def]
        import json

        body = json.dumps(
            {"error": {"code": "request_too_large", "message": "Request body exceeds the maximum allowed size"}}
        ).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [[b"content-type", b"application/json"], [b"content-length", str(len(body)).encode()]],
            }
        )
        await send({"type": "http.response.body", "body": body})


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        description=(
            "IP Address Management & VLSM subnet planning platform.\n\n"
            "All calculations are performed by the authoritative backend engine; "
            "the frontend never implements competing allocation logic."
        ),
        openapi_url=f"{settings.api_v1_prefix}/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    app.add_middleware(MaxBodySizeMiddleware, max_bytes=settings.max_request_body_bytes)
    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.get("/health", tags=["health"], response_model=HealthResponse, summary="Health check")
    def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            app=settings.app_name,
            version="1.0.0",
            database=_db_label(),
            algorithm_version=settings.algorithm_version,
        )

    return app


app = create_app()
