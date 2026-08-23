from __future__ import annotations

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from app.config.settings import settings


def _build_engine() -> Engine:
    # resolved_database_url already normalises "postgres://" -> "postgresql://"
    # (Heroku legacy scheme) and falls back to SQLite for local dev.
    database_url = settings.resolved_database_url

    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured.")

    if database_url.startswith("sqlite"):
        engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False},
            future=True,
            echo=settings.debug,
        )

        @event.listens_for(engine, "connect")
        def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON;")
            cursor.close()

        return engine

    if database_url.startswith("postgresql"):
        return create_engine(
            database_url,
            future=True,
            echo=settings.debug,
            pool_pre_ping=True,   # validate connections before use (handles stale connections)
            # See settings.py's db_pool_size/db_max_overflow comment: this
            # engine is built fresh in every process that imports this
            # module, so the web service and the standalone scheduler
            # worker (app/scheduler_worker.py) each get their own pool
            # against the same Postgres instance -- sized conservatively
            # by default since Railway Postgres's own max_connections
            # limit (100 by default) has to cover both services combined,
            # plus Alembic, the Console, and Postgres's own reserved
            # connections.
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_recycle=1800,    # recycle connections every 30 min
            pool_timeout=30,
        )

    # Other databases — no special pooling args
    return create_engine(database_url, future=True, echo=settings.debug)


engine: Engine = _build_engine()


SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    future=True,
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()