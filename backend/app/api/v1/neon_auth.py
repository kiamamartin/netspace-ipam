"""Neon Auth (Managed Better Auth) identity endpoint.

Verifies bearer JWTs issued by the branch's managed Auth server against its
published JWKS (``NEON_AUTH_JWKS_URL``). This is an additional identity path
for the M12 automation groundwork; the v1 username/password bearer flow in
``app/api/v1/auth.py`` is untouched, so no existing endpoint changes behavior.
"""

from __future__ import annotations

import hashlib
import secrets
import time
from typing import Any

import jwt
from fastapi import APIRouter, Depends, Header
from jwt import PyJWKClient
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import (
    DEFAULT_EXPIRES_MINUTES,
    USER_ROLES,
    encode_token,
    password_hash,
    runtime_secret,
)
from app.db.session import get_db
from app.models.user import User

router = APIRouter()
settings = get_settings()


class NeonIdentity(BaseModel):
    """Verified identity returned to the caller."""

    subject: str
    email: str | None = None
    name: str | None = None
    issuer: str | None = None
    provider: str = "neon-auth"


class NeonSessionOut(BaseModel):
    """App bearer session minted for a verified Neon identity."""

    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int
    username: str
    role: str

# JWKS documents rotate; re-create the client periodically so key changes are
# picked up without a full restart.
_JWKS_TTL_SECONDS = 300
_jwks: dict[str, Any] = {"client": None, "built": 0.0, "url": ""}


def _jwks_client() -> PyJWKClient:
    url = settings.neon_auth_jwks_url
    if not url:
        raise AppError(
            "neon_auth_unavailable",
            "Neon Auth is not configured (NEON_AUTH_JWKS_URL is empty)",
            503,
        )
    now = time.monotonic()
    if _jwks["client"] is None or _jwks["url"] != url or now - _jwks["built"] > _JWKS_TTL_SECONDS:
        _jwks.update(client=PyJWKClient(url, cache_keys=True), built=now, url=url)
    return _jwks["client"]


def _allowed_issuers() -> set[str]:
    """Managed Better Auth stamps `iss` with its origin (no `/db/auth` path)."""
    base = settings.neon_auth_base_url
    if not base:
        return set()
    origin = base.split("/", 3)
    short = "/".join(origin[:3]) if len(origin) >= 3 else base
    return {base, short}


def _decode(token: str) -> dict[str, Any]:
    try:
        signing_key = _jwks_client().get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=[signing_key.algorithm_name],
            # Better Auth sets `aud` to its own origin; the client audience is
            # not an app-specific value here, so signature + expiry are the
            # enforced checks and the issuer is validated below.
            options={"require": ["exp", "sub"], "verify_aud": False},
        )
    except jwt.PyJWTError as exc:  # invalid signature, expired, malformed, unknown kid
        raise AppError("invalid_token", "Token is invalid or expired", 401) from exc
    except Exception as exc:  # JWKS endpoint unreachable — never leak internals
        raise AppError("neon_auth_unavailable", "Neon Auth verification is temporarily unavailable", 503) from exc
    # The managed server sets `iss` to its own origin; enforce it when known.
    allowed = _allowed_issuers()
    if allowed and claims.get("iss") not in (None, *allowed):
        raise AppError("invalid_token", "Token issuer is not the configured Neon Auth instance", 401)
    return claims


def _require_bearer(authorization: str | None) -> dict[str, Any]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AppError("unauthorized", "Missing bearer token", 401)
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise AppError("unauthorized", "Missing bearer token", 401)
    return _decode(token)


_USERNAME_MAX = 64


def _local_username(email: str) -> str:
    """Stable local username for an email (the v1 users.username cap is 64)."""
    normalized = email.strip().lower()
    if len(normalized) <= _USERNAME_MAX:
        return normalized
    suffix = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]
    return f"{normalized[: _USERNAME_MAX - len(suffix) - 1]}-{suffix}"


def _role_for(email: str) -> str:
    if email.lower() in settings.neon_admin_email_set:
        return "admin"
    role = settings.neon_default_role.strip().lower()
    return role if role in USER_ROLES else "viewer"


@router.get("/me", summary="Current Neon Auth identity (bearer JWT)")
def neon_me(authorization: str | None = Header(default=None)) -> NeonIdentity:
    """Validate the ``Authorization: Bearer <jwt>`` token against Neon Auth JWKS.

    Returns the identity claims that identify the caller. Anonymous or invalid
    tokens receive the standard error envelope with ``401``.
    """
    claims = _require_bearer(authorization)
    return NeonIdentity(
        subject=str(claims.get("sub", "")),
        email=claims.get("email"),
        name=claims.get("name"),
        issuer=claims.get("iss"),
        provider="neon-auth",
    )


@router.post(
    "/session",
    response_model=NeonSessionOut,
    summary="Exchange a Neon Auth JWT for an application session",
)
def neon_session(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> NeonSessionOut:
    """Trade a verified Neon identity for the app's own bearer session.

    The local user is provisioned on first exchange (default role from
    ``NETSPACE_NEON_DEFAULT_ROLE``; admin only for emails listed in
    ``NETSPACE_NEON_ADMIN_EMAILS``) so the SPA can enter the app shell without
    a second credential. v1 login is untouched and disabled accounts stay
    disabled.
    """
    claims = _require_bearer(authorization)
    email = str(claims.get("email") or "").strip().lower()
    if not email:
        raise AppError("invalid_token", "Neon Auth token has no email claim", 401)

    username = _local_username(email)
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        user = User(
            username=username,
            # Provisioned identities never sign in through the v1 password flow.
            password_hash=password_hash(secrets.token_urlsafe(32)),
            role=_role_for(email),
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    if not user.is_active:
        raise AppError("account_disabled", "This account is disabled", 403)

    expires = settings.jwt_expires_minutes or DEFAULT_EXPIRES_MINUTES
    token = encode_token(
        {"sub": user.username, "uid": user.id, "role": user.role},
        runtime_secret(settings.auth_secret),
        expires,
    )
    return NeonSessionOut(
        access_token=token,
        expires_in_minutes=expires,
        username=user.username,
        role=user.role,
    )
