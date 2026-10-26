"""Security core for authentication and authorization.

Standards:
- Passwords: PBKDF2-HMAC-SHA256 (600k iterations, per-user random salt) — stdlib
  only, no third-party crypto dependency.
- Tokens: HS256 JSON Web Tokens, signed with the runtime secret. Auth secrets
  come from the environment; if unset, a per-process random secret is generated
  (dev convenience: tokens do not survive restarts) with one startup warning.

Roles (permission matrix, enforced server-side):
- ``admin``    — everything, including user administration and role changes.
- ``operator`` — all inventory/planning writes (networks, subnets, addresses,
                 departments, plans) and reads.
- ``viewer``   — authenticated status/identity and reads (read-write endpoints
                 reject viewers with 403).
- anonymous    — read-only GET access to inventory/report/dashboard data; every
                 mutating endpoint requires a valid bearer token (401).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import secrets
import time

logger = logging.getLogger("netspace.security")

PBKDF2_ITERATIONS = 600_000
_ALGORITHM_TAG = "pbkdf2_sha256"
DEFAULT_EXPIRES_MINUTES = 480
USER_ROLES = ("viewer", "operator", "admin")
ROLE_PERMISSIONS: dict[str, tuple[str, ...]] = {
    "viewer": ("read",),
    "operator": ("read", "write"),
    "admin": ("read", "write", "administrate"),
}

_ephemeral_secret: str | None = None


def password_hash(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), PBKDF2_ITERATIONS
    )
    return f"{_ALGORITHM_TAG}${PBKDF2_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        tag, iterations, salt, expected_hex = stored.split("$", 3)
    except ValueError:
        return False
    if tag != _ALGORITHM_TAG or not iterations.isdigit():
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), int(iterations)
    )
    return hmac.compare_digest(digest.hex(), expected_hex)


# --- minimal HS256 JWT ------------------------------------------------------


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(segment: str) -> bytes:
    return base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))


def runtime_secret(configured: str) -> str:
    """Resolve the token-signing secret, generating a dev fallback if unset.

    The fallback is generated **once per process** and reused afterwards: an
    ephemeral secret that changed between encode and verify would make every
    issued token invalid. It still does not survive restarts.
    """
    global _ephemeral_secret
    if configured.strip():
        return configured.strip()
    if _ephemeral_secret is None:
        logger.warning(
            "NETSPACE_AUTH_SECRET is not configured: tokens are signed with a "
            "per-process random secret and will not survive restarts."
        )
        _ephemeral_secret = secrets.token_hex(32)
    return _ephemeral_secret


def encode_token(payload: dict[str, object], secret: str, expires_minutes: int) -> str:
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    body = {**payload, "iat": now, "exp": now + int(expires_minutes) * 60}
    signing_input = "{}.{}".format(
        _b64url(json.dumps(header, separators=(",", ":")).encode("utf-8")),
        _b64url(json.dumps(body, separators=(",", ":")).encode("utf-8")),
    )
    signature = hmac.new(secret.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256)
    return f"{signing_input}.{_b64url(signature.digest())}"


def decode_token(token: str, secret: str) -> dict[str, object]:
    """Verify signature and expiry; raise ``ValueError`` on ANY failure."""
    try:
        header_part, payload_part, signature_part = token.split(".")
    except ValueError as exc:
        raise ValueError("malformed token") from exc
    signing_input = f"{header_part}.{payload_part}"
    expected = _b64url(hmac.new(secret.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256).digest())
    if not hmac.compare_digest(expected, signature_part):
        raise ValueError("bad signature")
    try:
        payload = json.loads(_b64url_decode(payload_part))
    except (ValueError, KeyError) as exc:
        raise ValueError("malformed token payload") from exc
    if not isinstance(payload, dict) or int(payload.get("exp", 0)) < int(time.time()):
        raise ValueError("token expired")
    return payload
