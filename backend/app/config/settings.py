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
    # CACHE
    # --------------------------------------------------

    # Redis URL for shared cache. Leave blank to disable Redis (in-memory only).
    # Format: redis://[:password@]host[:port][/db]
    redis_url: str = ""

    # --------------------------------------------------
    # SECURITY
    # --------------------------------------------------

    secret_key: str = "change-me-in-production"

    # Supabase project's JWT secret (Project Settings > API > JWT Settings >
    # JWT Secret). Required in prod — used to verify the Authorization: Bearer
    # token the frontend sends, so the backend knows who's actually calling
    # instead of trusting a client-supplied user_id. See app/core/user_auth.py.
    supabase_jwt_secret: str = ""

    # CORS — comma-separated list of allowed origins. Leave blank in native-app
    # only deployments (no browser client); set explicitly if a web client is
    # ever added. "*" is rejected in prod (see app/main.py startup check).
    cors_allow_origins: str = ""

    # Sentry DSN — error monitoring. Leave blank to disable (local dev default).
    # Get one from sentry.io > Project Settings > Client Keys (DSN).
    sentry_dsn: str = ""

    # --------------------------------------------------
    # EXTERNAL APIS
    # --------------------------------------------------

    google_places_api_key: str = ""

    # Nominatim's usage policy (https://operations.osmfoundation.org/policies/nominatim/)
    # requires a genuinely identifying User-Agent (app name + a way to contact
    # you — email or URL). A generic User-Agent can be blocked without warning.
    # Set to e.g. "hello@yourcompany.com" or "https://yourapp.com/contact".
    nominatim_contact: str = ""

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