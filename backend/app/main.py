from __future__ import annotations

from contextlib import asynccontextmanager
import logging
import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config.settings import settings
from app.api import router as api_router
from app.api.v1.routes.health import router as health_router
from app.middleware.request_id import RequestIDMiddleware
from app.core.logging_config import RequestIDFilter

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

def _startup_validation() -> None:
    """Validate critical imports and DB connectivity at startup."""
    from app.db.session import SessionLocal
    from app.db.models.place import Place
    from sqlalchemy import select, text

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

    yield

    logger.info("shutdown")


# ============================================================
# App
# ============================================================

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    debug=settings.debug,
    lifespan=lifespan,
)


# ============================================================
# Routers
# ============================================================

app.include_router(api_router, prefix="/api")
app.include_router(health_router)


# ============================================================
# Middleware
# ============================================================

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