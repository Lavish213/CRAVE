from __future__ import annotations

from contextlib import asynccontextmanager
import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config.settings import settings
from app.api import router as api_router

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

logger = logging.getLogger("lavish")


# ============================================================
# Lifespan
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):

    logger.info("startup")

    # hard fail if models fail to register
    _ = models

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


# ============================================================
# Middleware
# ============================================================

@app.middleware("http")
async def request_metrics(request: Request, call_next):

    request_id = str(uuid.uuid4())
    start = time.perf_counter()

    try:
        response = await call_next(request)
    except Exception:
        logger.exception("request_failed path=%s", request.url.path)
        raise

    duration = time.perf_counter() - start

    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = f"{duration:.4f}"

    logger.info(
        "%s %s | %.3fs",
        request.method,
        request.url.path,
        duration,
    )

    return response


# ============================================================
# Health
# ============================================================

@app.get("/health")
def health():
    return {"status": "ok"}


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