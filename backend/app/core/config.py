"""Application configuration loaded from environment variables (.env supported)."""

from functools import lru_cache

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

    # Limits
    max_departments_per_plan: int = 256
    max_page_size: int = 200
    default_page_size: int = 50

    # VLSM
    algorithm_version: str = "vlsm-1.0.0"

    @property
    def cors_origins_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
