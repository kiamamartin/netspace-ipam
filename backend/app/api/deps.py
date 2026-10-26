"""Shared FastAPI dependencies for authentication and role authorization."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import decode_token, runtime_secret
from app.db.session import get_db
from app.models.user import User

settings = get_settings()


def _authorization_header(request: Request) -> str | None:
    """Read the Authorization header without FastAPI parameter-injection quirks."""
    return request.headers.get("authorization")


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    """Resolve the bearer token to an active user; anonymous callers get None."""
    auth_header = _authorization_header(request)
    if not auth_header or not auth_header.lower().startswith("bearer "):
        return None
    token = auth_header.split(" ", 1)[1].strip()
    try:
        payload = decode_token(token, runtime_secret(settings.auth_secret))
    except ValueError:
        return None
    user = db.query(User).filter(User.id == int(payload["uid"])).first()  # type: ignore[arg-type]
    if user is None or not user.is_active:
        return None
    return user


def get_current_user_strict(request: Request, db: Session = Depends(get_db)) -> User:
    """Public 403/401 raising auth adapter (module-level, transient).

    The inventory and planning APIs recently tightened ``require_operator`` so
    anonymous calls now raise ``401 Unauthenticated`` instead of the older behavior
    where some reads returned empty collections. This adapter keeps the report
    exporter's ``/api/v1/reports/*`` contract stable while that change is still
    being rolled out and while upstream callers are being updated.
    """
    user = get_current_user(request, db)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_role(*allowed: str) -> Callable[..., Any]:
    """Dependency factory: caller must hold one of the given roles (403 otherwise)."""

    def dependency(user: User | None = Depends(get_current_user)) -> User:
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Role '{user.role}' is not authorized for this action "
                    f"(requires: {', '.join(allowed)})"
                ),
            )
        return user

    return dependency


#: write access to inventory/planning resources
require_operator = require_role("operator", "admin")
#: user administration exclusively
require_admin = require_role("admin")
