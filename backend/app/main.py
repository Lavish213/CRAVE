from __future__ import annotations

from contextlib import asynccontextmanager
import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config.settings import settings
from app.api import router as api_router
from app.api.v1.routes.health import router as health_router
from app.middleware.request_id import RequestIDMiddleware
from app.core.logging_config import RequestIDFilter
from app.scheduler import create_scheduler

# ---------------------------------------------------------
# FORCE MODEL REGISTRY LOAD (CRITICAL)
# ---------------------------------------------------------
from app.db import models  # noqa: F401


# ============================================================
# Logging
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

# Attach request_id to all log records (populated by RequestIDMiddleware)
logging.getLogger().addFilter(RequestIDFilter())

logger = logging.getLogger("lavish")


# ============================================================
# Lifespan
# ============================================================

def _validate_prod_config() -> None:
    """
    Hard-fail startup in prod if critical security config was left at its
    insecure default. This is what makes the dev-mode bypasses in
    app/core/auth.py and app/core/user_auth.py safe to have at all — they
    can only ever apply when this check has already refused to boot.
    """
    if not settings.is_prod:
        return

    problems: list[str] = []

    if settings.secret_key == "change-me-in-production":
        problems.append("SECRET_KEY is still the default placeholder value")

    if not settings.supabase_jwt_secret:
        problems.append(
            "SUPABASE_JWT_SECRET is unset — user-auth verification cannot run "
            "(Project Settings > API > JWT Settings > JWT Secret in Supabase)"
        )

    if settings.cors_allow_origins.strip() == "*":
        problems.append("CORS_ALLOW_ORIGINS is '*' — not allowed in prod")

    if not settings.database_url:
        problems.append(
            "DATABASE_URL is unset — will silently boot on ephemeral SQLite and lose all data on restart"
        )

    import os as _os
    if not _os.environ.get("API_KEY", "").strip():
        problems.append(
            "API_KEY is unset — all write endpoints are open to unauthenticated requests"
        )

    if problems:
        for p in problems:
            logger.critical("startup_validation_failed prod_config=%s", p)
        raise RuntimeError(
            "Refusing to start in prod with insecure config: " + "; ".join(problems)
        )

    logger.info("startup_validation prod_config=ok")


def _startup_validation() -> None:
    """Validate critical imports and DB connectivity at startup."""
    from app.db.session import SessionLocal
    from app.db.models.place import Place
    from sqlalchemy import select, text

    _validate_prod_config()

    db = SessionLocal()
    try:
        # Verify DB is reachable and models are mapped
        db.execute(text("SELECT 1"))
        logger.info("startup_validation db=ok")
    except Exception as exc:
        logger.critical("startup_validation db=FAILED error=%s", exc)
        raise
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):

    logger.info("startup")

    # hard fail if models fail to register
    _ = models

    _startup_validation()

    # Start background pipeline scheduler
    scheduler = create_scheduler()
    scheduler.start()
    logger.info("scheduler_started jobs=%s", len(scheduler.get_jobs()))

    yield

    # Graceful scheduler shutdown — wait for running jobs to finish
    scheduler.shutdown(wait=True)
    logger.info("scheduler_stopped")

    logger.info("shutdown")


# ============================================================
# App
# ============================================================

# /docs, /redoc, and /openapi.json are disabled in prod — they were
# previously public regardless of environment, publishing the full route/
# schema surface to anyone.
app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    debug=settings.debug_enabled,
    lifespan=lifespan,
    docs_url=None if settings.is_prod else "/docs",
    redoc_url=None if settings.is_prod else "/redoc",
    openapi_url=None if settings.is_prod else "/openapi.json",
)


# ============================================================
# Routers
# ============================================================

app.include_router(api_router, prefix="/api")
app.include_router(health_router)


# ============================================================
# Middleware
# ============================================================

# CORS — previously absent entirely. Fail-closed by default (no origins
# configured = no browser origin is allowed), matching what a native-app-only
# API needs; set CORS_ALLOW_ORIGINS (comma-separated) if a web client is
# added later.
_cors_origins = [
    o.strip() for o in settings.cors_allow_origins.split(",") if o.strip()
]
if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.middleware("http")
async def security_headers(request: Request, call_next):
    """
    Baseline security headers — none of these existed before. Doesn't
    replace TLS/HSTS at the edge (Railway terminates TLS in front of this),
    but stops the app from actively undermining it if ever put behind
    something that doesn't.
    """
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if settings.is_prod:
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response


@app.middleware("http")
async def request_metrics(request: Request, call_next):

    start = time.perf_counter()

    try:
        response = await call_next(request)
    except Exception:
        logger.exception("request_failed path=%s", request.url.path)
        raise

    duration = time.perf_counter() - start

    response.headers["X-Process-Time"] = f"{duration:.4f}"

    logger.info(
        "%s %s | %.3fs",
        request.method,
        request.url.path,
        duration,
    )

    return response


# RequestIDMiddleware runs first (last-added = first-executed in Starlette).
# It generates/validates the UUID and sets the X-Request-ID response header.
app.add_middleware(RequestIDMiddleware)


# ============================================================
# Global Exception Handler
# ============================================================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):

    logger.exception("unhandled_error path=%s", request.url.path)

    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )