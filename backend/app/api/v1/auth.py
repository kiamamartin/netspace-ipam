"""Authentication and user administration endpoints (M5)."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Mapping

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_current_user_strict, require_admin
from app.core.config import get_settings
from app.core.security import (
    DEFAULT_EXPIRES_MINUTES,
    USER_ROLES,
    encode_token,
    password_hash,
    runtime_secret,
    verify_password,
)
from app.db.session import get_db
from app.models.user import User

router = APIRouter()
settings = get_settings()

# --- schemas -----------------------------------------------------------------


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=200)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int
    username: str
    role: str


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=64, pattern=r"^[A-Za-z0-9._-]+$")
    password: str = Field(min_length=8, max_length=200)
    role: str = Field(default="viewer")


class UserUpdate(BaseModel):
    role: str | None = Field(default=None)
    password: str | None = Field(default=None, min_length=8, max_length=200)
    is_active: bool | None = None


# --- rate limiting for the public login endpoint ------------------------------
# Fixed 60 s window per client IP, in-process (single-worker deployments).
_LOGIN_ATTEMPTS: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=5))
_LOGIN_WINDOW_SECONDS = 60
_LOGIN_MAX_ATTEMPTS = 5


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _check_login_rate(request: Request) -> None:
    ip = _client_ip(request)
    now = time.monotonic()
    attempts = _LOGIN_ATTEMPTS[ip]
    while attempts and now - attempts[0] > _LOGIN_WINDOW_SECONDS:
        attempts.popleft()
    if len(attempts) >= _LOGIN_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts; retry in a minute",
        )
    attempts.append(now)


# --- endpoints ----------------------------------------------------------------


@router.post("/login", response_model=TokenOut, summary="Issue a bearer token")
def login(payload: LoginIn, request: Request, db: Session = Depends(get_db)) -> TokenOut:
    _check_login_rate(request)
    user = db.query(User).filter(User.username == payload.username).first()
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        # generic message: never reveal whether the username exists
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = encode_token(
        {"sub": user.username, "uid": user.id, "role": user.role},
        runtime_secret(settings.auth_secret),
        settings.jwt_expires_minutes or DEFAULT_EXPIRES_MINUTES,
    )
    return TokenOut(
        access_token=token,
        expires_in_minutes=settings.jwt_expires_minutes or DEFAULT_EXPIRES_MINUTES,
        username=user.username,
        role=user.role,
    )


@router.get("/me", response_model=UserOut, summary="Current credentials")
def me(user: User = Depends(get_current_user)) -> User:
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


def _get_current_user_strict(
    request: Request, db: Session = Depends(get_db)
) -> User:
    """Keep the temporary 401-raising auth adapter alongside get_current_user.
    This is used only by the report exporter until the dependency upstream
    contract is finalized; it is intentionally not registered on the router.
    """
    user = get_current_user(request, db)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


@router.get("/users", response_model=list[UserOut], summary="List users (admin)")
def list_users(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[User]:
    return list(db.query(User).order_by(User.id).all())


@router.post(
    "/users",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a user (admin)",
)
def create_user(
    payload: UserCreate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> User:
    if payload.role not in USER_ROLES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unknown role")
    if db.query(User).filter(User.username == payload.username).first() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already taken")
    user = User(
        username=payload.username,
        role=payload.role,
        password_hash=password_hash(payload.password),
        is_active=True,
    )
    db.add(user)
    db.flush()

    from app.models import AuditEvent

    db.add(
        AuditEvent(
            actor=admin.username if isinstance(admin, User) else None,
            resource_type="user",
            resource_id=str(user.id),
            action="create",
            summary=f"User created: {user.username} ({user.role})",
        )
    )

    db.commit()
    db.refresh(user)
    return user


@router.patch("/users/{user_id}", response_model=UserOut, summary="Update a user (admin)")
def update_user(
    user_id: int,
    payload: UserUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    updates: Mapping[str, object] = payload.model_dump(exclude_unset=True)
    if "role" in updates:
        if updates["role"] not in USER_ROLES:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unknown role")
        if user.id == admin.id and updates["role"] != "admin":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cannot change your own role away from admin")
        user.role = str(updates["role"])  # type: ignore[assignment]
    if "password" in updates and updates["password"]:
        user.password_hash = password_hash(str(updates["password"]))
    if "is_active" in updates and updates["is_active"] is not None:
        if user.id == admin.id and not updates["is_active"]:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cannot deactivate your own admin account")
        user.is_active = bool(updates["is_active"])
    db.commit()
    db.refresh(user)
    return user


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a user (admin)")
def delete_user(
    user_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> None:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.role == "admin":
        remaining_admins = (
            db.query(User).filter(User.role == "admin", User.id != user_id).count()
        )
        if remaining_admins == 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot delete the last admin account",
            )
    db.delete(user)
    db.commit()
    return None
