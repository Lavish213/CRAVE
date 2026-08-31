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

    # APScheduler's BackgroundScheduler runs its jobs in threads inside this
    # same process — fine for local dev (single-service, low traffic), but
    # in prod with a single uvicorn worker (see railway.toml's startCommand)
    # it means CPU-bound job work (image resize/hash, HTML parsing, OCR)
    # directly competes with the GIL for time the async event loop needs to
    # serve HTTP requests, causing request timeouts that have nothing to do
    # with client network quality. Confirmed in production: a single
    # menu_enrichment run took 3h21m end to end while image_ingestion ran
    # every 20 minutes concurrently.
    #
    # Default True keeps existing single-service deployments working
    # unchanged. Once a second Railway service is running
    # `python -m app.scheduler_worker` (see that module's docstring), set
    # this to False on the WEB service specifically — otherwise both
    # processes run every scheduled job, double-billing paid APIs
    # (Google Places/Vision) and double-writing data.
    run_embedded_scheduler: bool = True

    # --------------------------------------------------
    # DATABASE
    # --------------------------------------------------

    database_url: str | None = None

    # Previously hardcoded pool_size=20/max_overflow=40 (60 max connections
    # per process) directly in app/db/session.py. That was sized for a
    # single process; now that the scheduler runs as a separate Railway
    # service (see run_embedded_scheduler above), TWO processes each
    # maintain their own pool against the same database -- worst case
    # 120 combined connections, which already exceeds Railway Postgres's
    # default max_connections of 100 on its own, before counting Alembic
    # migration connections, the Railway Console, or Postgres's own
    # reserved_connections. Made configurable (not just lowered) so each
    # service can be tuned independently via its own Railway env vars
    # without a code change -- the busier web service and the mostly-
    # sequential worker don't need the same ceiling.
    db_pool_size: int = 10
    db_max_overflow: int = 10

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

    # Supabase project URL (Project Settings > API > Project URL) — same
    # value as the frontend's EXPO_PUBLIC_SUPABASE_URL. Required in prod —
    # used to fetch the project's public JWKS and verify the
    # Authorization: Bearer token the frontend sends, so the backend knows
    # who's actually calling instead of trusting a client-supplied user_id.
    # Supabase signs access tokens with an asymmetric key (ES256), not a
    # shared secret, so there's no separate "secret" value to configure.
    # See app/core/user_auth.py.
    supabase_url: str = ""

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

    # Safety cap on total Google Places API calls made by a single
    # GooglePlacesIngest run (search_nearby + scan_grid combined) — stops a
    # bad grid/cell count or a runaway retry loop from silently running up
    # billing. 0 disables the cap (unlimited).
    google_places_max_calls_per_run: int = 2000

    # --------------------------------------------------
    # VIDEO (see app/services/video/)
    # --------------------------------------------------

    video_max_duration_ms: int = 10_000
    video_min_duration_ms: int = 1_000
    # A source clip longer than video_max_duration_ms but no longer than
    # this is no longer a hard REJECT_DURATION -- see
    # video_processing_worker.py's auto-highlight step, which finds the
    # best-scoring video_max_duration_ms-length window inside it (via
    # food_classifier.find_best_highlight_window) and trims to that
    # instead of throwing away the whole upload. Only reachable today from
    # a future looser recording UI or an imported clip -- the current
    # record screen's own MAX_DURATION_SEC already caps recording at
    # video_max_duration_ms, so this ceiling exists for when that changes.
    video_highlight_max_source_duration_ms: int = 60_000
    video_max_upload_mb: int = 50
    # Was a pure guess (0.5) before the classifier model existed. Now
    # informed by actually running the real model (see
    # food_classifier.py's module docstring for the full caveat) against
    # real images: genuine food photos scored 0.988-1.000, real non-food
    # photos scored 0.52-0.57. 0.8 sits with wide margin above the
    # non-food scores and below the food ones -- but it's still informed
    # by a handful of manually-picked images, not a real validation set,
    # and it does nothing against the model's confirmed blind spot
    # (content unlike any of its 82 training classes can still score
    # deceptively high). Revisit once real user-submitted clips exist.
    video_food_score_threshold: float = 0.8
    video_compression_bitrate: str = "2500k"
    video_compression_max_height: int = 1920
    # Rows still 'pending' (upload slot created, never confirmed) past this
    # many minutes are abandoned uploads -- nothing else ever revisits a
    # pure 'pending' row, unlike 'queued'/'processing' which the worker's
    # own batch-select query already retries indefinitely on its own.
    video_orphan_pending_minutes: int = 30
    # A 'processing' row this old almost certainly means the worker
    # crashed mid-item (process killed, deploy, OOM) rather than still
    # being genuinely in progress -- ffmpeg/classifier calls are bounded
    # by their own timeouts well under this. The batch-select query
    # re-claims rows this stale instead of leaving them stuck forever.
    video_stale_processing_minutes: int = 15
    # Photo upload's equivalent of the two video settings above, collapsed
    # into one: PlaceImage has no `updated_at` column (unlike PlaceVideo),
    # so `created_at` is the only timestamp available to judge staleness by
    # for both a never-confirmed 'pending' row and a crashed 'processing'
    # one. That's still safe -- process_image_upload() is a single HTTP-
    # bound background task (R2 download/upload, one safety-scan API call),
    # not staged/resumable work like ffmpeg encoding, so it's expected to
    # finish in well under a minute; nothing legitimate should still be
    # 'pending' or 'processing' this long after its upload slot was created.
    # See reclaim_stale_image_uploads() in image_processing_worker.py.
    photo_stale_processing_minutes: int = 30
    # Path to the interpreter that has tflite-runtime (or tensorflow)
    # installed, if it differs from whatever "python3" resolves to on the
    # worker box (e.g. a dedicated venv). See
    # app/services/video/food_classifier.py.
    food_classifier_python: str = "python3"

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