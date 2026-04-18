from functools import lru_cache
from typing import Literal
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


# ------------------------------------------------------------
# PROJECT ROOT (DETERMINISTIC + SAFE)
# ------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parents[3]
BACKEND_DIR = BASE_DIR / "backend"
DEFAULT_SQLITE_PATH = (BACKEND_DIR / "app.db").resolve()


class Settings(BaseSettings):
    """
    FINALIZED PRODUCTION SETTINGS

    Guarantees:
    - Single source of truth for DB URL
    - Safe for FastAPI + Alembic + scripts
    - Deterministic SQLite fallback
    - Env override support
    - Dev/Prod parity
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --------------------------------------------------
    # APP
    # --------------------------------------------------

    app_name: str = "Lavish Backend"
    app_env: Literal["dev", "staging", "prod"] = "dev"

    # 🔥 AUTO DERIVED (never manually toggle in prod)
    debug: bool = False

    # --------------------------------------------------
    # DATABASE
    # --------------------------------------------------

    database_url: str | None = None

    # --------------------------------------------------
    # SECURITY
    # --------------------------------------------------

    secret_key: str = "change-me-in-production"

    # --------------------------------------------------
    # EXTERNAL APIS
    # --------------------------------------------------

    google_places_api_key: str = ""

    # --------------------------------------------------
    # DERIVED PROPERTIES
    # --------------------------------------------------

    @property
    def resolved_database_url(self) -> str:
        raw = (self.database_url or "").strip()

        if not raw:
            return f"sqlite:///{DEFAULT_SQLITE_PATH}"

        # Heroku and some providers emit the deprecated "postgres://" scheme.
        # SQLAlchemy 1.4+ requires "postgresql://".
        if raw.startswith("postgres://"):
            raw = raw.replace("postgres://", "postgresql://", 1)

        return raw

    @property
    def is_dev(self) -> bool:
        return self.app_env == "dev"

    @property
    def is_prod(self) -> bool:
        return self.app_env == "prod"

    @property
    def is_staging(self) -> bool:
        return self.app_env == "staging"

    # 🔥 DEBUG AUTO CONTROL (no manual mistakes)
    @property
    def debug_enabled(self) -> bool:
        return self.app_env == "dev"


# ------------------------------------------------------------
# SINGLETON (CRITICAL)
# ------------------------------------------------------------

@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()