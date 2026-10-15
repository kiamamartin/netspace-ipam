"""Database engine, session factory and FastAPI dependency."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings

settings = get_settings()

connect_args: dict[str, object] = {}
engine_kwargs: dict[str, object] = {"pool_pre_ping": True}
if settings.database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
    if ":memory:" in settings.database_url:
        # Share one in-memory database across all sessions (tests).
        engine_kwargs["poolclass"] = StaticPool

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    **engine_kwargs,
)

if settings.database_url.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency providing a request-scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create tables (development convenience; Alembic owns production schema)."""
    from app import models  # noqa: F401  ensure models are registered

    models.Base.metadata.create_all(bind=engine)
