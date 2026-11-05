"""Application configuration loaded from environment variables (.env supported)."""

from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings. All values can be overridden via NETSPACE_* env vars."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="NETSPACE_",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "NetSpace IPAM"
    api_v1_prefix: str = "/api/v1"
    debug: bool = False
    log_level: str = "INFO"

    # SQLite for local development; any SQLAlchemy URL works (PostgreSQL for production).
    database_url: str = "sqlite:///./netspace.db"

    # Comma separated list. Use "*" to allow all origins (development only).
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Auth (M5). Leave auth_secret empty to auto-generate a per-process secret
    # (dev convenience: tokens do not survive restarts). Set a strong random
    # value in production; never commit it to source control.
    auth_secret: str = ""
    jwt_expires_minutes: int = 480

    # Neon Auth (Managed Better Auth, M12 groundwork). Values are injected by
    # `neon deploy` / `neon env pull` with their NEON_* names, so they are read
    # via explicit aliases instead of the NETSPACE_ prefix.
    neon_auth_base_url: str = Field(
        default="",
        validation_alias=AliasChoices("NEON_AUTH_BASE_URL", "NETSPACE_NEON_AUTH_BASE_URL"),
    )
    neon_auth_jwks_url: str = Field(
        default="",
        validation_alias=AliasChoices("NEON_AUTH_JWKS_URL", "NETSPACE_NEON_AUTH_JWKS_URL"),
    )
    # Local role given to a Neon identity the first time it signs in. Never
    # grants more than the v1 role matrix allows; admin must be explicit.
    neon_default_role: str = "viewer"
    # Comma-separated emails that map to the local ``admin`` role on exchange.
    neon_admin_emails: str = ""
    max_request_body_bytes: int = 1_048_576  # 1 MiB guard for exposed endpoints

    # Limits
    max_departments_per_plan: int = 256
    max_page_size: int = 200
    default_page_size: int = 50

    # VLSM
    algorithm_version: str = "vlsm-1.0.0"

    @property
    def neon_admin_email_set(self) -> set[str]:
        return {e.strip().lower() for e in self.neon_admin_emails.split(",") if e.strip()}

    @property
    def cors_origins_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
