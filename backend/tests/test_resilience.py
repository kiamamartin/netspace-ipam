"""Reliability tests: database failure and recovery scenarios.

Documented equivalent of the roadmap's M9 reliability coverage for
M9-AC-004 (MILESTONES.md §M9; M9's roadmap `backend/tests/security/` and
`backend/tests/performance/` paths stay in their documented flat-layout
substitutions alongside these files).

What is exercised here, against the real API surface:
- a failing database is reported as a structured error envelope, never
  exposing stack traces or driver internals;
- the API recovers immediately once the database is healthy again (no
  restart of the application);
- a write whose commit fails must leave nothing partially committed.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Callable, Iterator

import pytest
from conftest import *  # noqa: F401,F403 — Base, engine, init_db, client fixture
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.api.v1.auth import _LOGIN_ATTEMPTS
from app.core.config import get_settings
from app.core.security import encode_token, password_hash, runtime_secret
from app.db.session import SessionLocal, engine, get_db, init_db
from app.main import app
from app.models import Base
from app.models.network import Network
from app.models.user import User


@pytest.fixture()
def safe_client() -> TestClient:
    """TestClient that surfaces the app's 500 envelope instead of re-raising."""
    Base.metadata.drop_all(bind=engine)
    init_db()
    _LOGIN_ATTEMPTS.clear()
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def _db_network_count() -> int:
    """Independent DB read with a fresh session (not the failing friendship)."""
    with SessionLocal() as db:
        try:
            return int(db.scalar(select(func.count()).select_from(Network)))
        finally:
            db.rollback()


def _admin_token() -> str:
    """Bearer token for the admin fixture account (created on demand)."""
    with SessionLocal() as db:
        admin = db.query(User).filter(User.username == "adminuser").first()
        if admin is None:
            admin = User(
                username="adminuser",
                role="admin",
                password_hash=password_hash("AdminPass1!"),
            )
            db.add(admin)
            db.commit()
        return encode_token(
            {"uid": admin.id, "role": "admin"},
            runtime_secret(get_settings().auth_secret),
            expires_minutes=get_settings().jwt_expires_minutes,
        )


def _unreachable_db_dependency() -> Callable[[], Iterator[Session]]:
    """Dependency override: every acquisition raises (database unreachable)."""

    def override() -> Generator[Session, None, None]:
        raise OperationalError("CONNECT", {}, "simulated connection failure")
        yield  # pragma: no cover — a generator needs the yield site

    return override


def test_db_unavailable_returns_structured_error(safe_client: TestClient) -> None:
    """A dead database surfaces as {code,message,details} — no internals leak."""
    app.dependency_overrides[get_db] = _unreachable_db_dependency()
    try:
        res = safe_client.get("/api/v1/networks")
        assert res.status_code == 500, res.text
        body = res.json()
        assert body["error"]["code"] == "internal_error"
        leaked = res.text.lower()
        for fragment in ("sqlite", "traceback", "operationalerror"):
            assert fragment not in leaked, fragment
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_api_recovers_after_db_failure_without_restart(safe_client: TestClient) -> None:
    """After recovery the same application instance serves reads and writes."""
    app.dependency_overrides[get_db] = _unreachable_db_dependency()
    try:
        assert safe_client.get("/api/v1/networks").status_code == 500
    finally:
        app.dependency_overrides.pop(get_db, None)

    recovered = safe_client.get("/api/v1/networks")
    assert recovered.status_code == 200, recovered.text
    assert "items" in recovered.json()


def test_health_endpoint_serves_while_db_broken(safe_client: TestClient) -> None:
    """Recovery doc §1: /health stays up even with the database unreachable."""
    app.dependency_overrides[get_db] = _unreachable_db_dependency()
    try:
        res = safe_client.get("/health")
        assert res.status_code == 200, res.text
        assert res.json()["status"] == "ok"
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_failed_commit_leaves_no_partial_state(safe_client: TestClient) -> None:
    """A write that dies at commit must persist nothing (M9-AC-004)."""
    headers = {"Authorization": f"Bearer {_admin_token()}"}
    sessions: list[Session] = []

    def failing_commit_dependency() -> Generator[Session, None, None]:
        db = SessionLocal()
        sessions.append(db)
        original_rollback = db.rollback

        def commit_then_fail() -> None:
            original_rollback()  # discard buffered rows, keep the session healthy
            raise OperationalError(
                "COMMIT", {}, "simulated commit failure inside the request"
            )

        db.commit = commit_then_fail  # type: ignore[method-assign]
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = failing_commit_dependency
    try:
        res = safe_client.post(
            "/api/v1/networks",
            headers=headers,
            json={"name": "Half Written", "cidr": "10.77.0.0/24"},
        )
        assert res.status_code == 500, res.text
        assert res.json()["error"]["code"] == "internal_error"
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert _db_network_count() == 0, "a failed commit must not persist rows"
    assert safe_client.get("/api/v1/networks").status_code == 200
    for db in sessions:
        db.close()
