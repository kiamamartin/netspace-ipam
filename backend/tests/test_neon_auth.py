"""Neon Auth identity path: JWT verification surface + app-session exchange.

The JWKS fetch is network-bound, so these tests patch ``neon_auth._decode``
(the verified-claims boundary) and keep everything else real: user provisioning,
role mapping, token minting and the v1 ``/auth/me`` guard.
"""

from __future__ import annotations

import pytest

from app.api.v1 import neon_auth
from app.core.errors import AppError
from app.db.session import SessionLocal
from app.models.user import User


def _claims(email: str = "neon-user@example.com", sub: str = "neon-1") -> dict[str, object]:
    return {"sub": sub, "email": email, "name": "Neon User", "iss": "https://auth.example"}


def test_neon_me_requires_bearer_token(client) -> None:
    res = client.get("/api/v1/auth/neon/me")
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "unauthorized"


def test_neon_me_returns_verified_identity(client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(neon_auth, "_decode", lambda token: _claims())
    res = client.get("/api/v1/auth/neon/me", headers={"Authorization": "Bearer valid"})
    assert res.status_code == 200
    body = res.json()
    assert body["provider"] == "neon-auth"
    assert body["email"] == "neon-user@example.com"


def test_neon_session_provisions_viewer_and_issues_app_token(
    client, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(neon_auth, "_decode", lambda token: _claims())
    res = client.post("/api/v1/auth/neon/session", headers={"Authorization": "Bearer valid"})
    assert res.status_code == 200
    body = res.json()
    assert body["username"] == "neon-user@example.com"
    assert body["role"] == "viewer"

    # The minted token is a first-class v1 app session.
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json()["username"] == "neon-user@example.com"

    # Second exchange reuses the same local identity instead of duplicating it.
    again = client.post("/api/v1/auth/neon/session", headers={"Authorization": "Bearer valid"})
    assert again.status_code == 200
    db = SessionLocal()
    try:
        assert db.query(User).filter(User.username == "neon-user@example.com").count() == 1
    finally:
        db.close()


def test_neon_session_maps_configured_admin_email(
    client, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(neon_auth.settings, "neon_admin_emails", "boss@example.com")
    monkeypatch.setattr(neon_auth, "_decode", lambda token: _claims("Boss@Example.com"))
    res = client.post("/api/v1/auth/neon/session", headers={"Authorization": "Bearer valid"})
    assert res.status_code == 200
    assert res.json()["role"] == "admin"


def test_neon_session_rejects_invalid_token(client, monkeypatch: pytest.MonkeyPatch) -> None:
    def _reject(token: str) -> dict[str, object]:
        raise AppError("invalid_token", "Token is invalid or expired", 401)

    monkeypatch.setattr(neon_auth, "_decode", _reject)
    res = client.post("/api/v1/auth/neon/session", headers={"Authorization": "Bearer nope"})
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "invalid_token"


def test_neon_session_rejects_disabled_local_account(
    client, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = SessionLocal()
    try:
        db.add(
            User(
                username="disabled@example.com",
                password_hash="pbkdf2_sha256$1$salt$deadbeef",
                role="viewer",
                is_active=False,
            )
        )
        db.commit()
    finally:
        db.close()

    monkeypatch.setattr(neon_auth, "_decode", lambda token: _claims("disabled@example.com"))
    res = client.post("/api/v1/auth/neon/session", headers={"Authorization": "Bearer valid"})
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "account_disabled"
