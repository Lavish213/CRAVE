from __future__ import annotations

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from app.config.settings import settings


def _build_engine() -> Engine:

    database_url = settings.resolved_database_url

    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured.")

    if database_url.startswith("sqlite"):

        engine = create_engine(
            database_url,
            connect_args={
                "check_same_thread": False,
            },
            future=True,
            echo=settings.debug,
        )

        @event.listens_for(engine, "connect")
        def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON;")
            cursor.close()

        return engine

    return create_engine(
        database_url,
        future=True,
        echo=settings.debug,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        pool_recycle=1800,
        pool_timeout=30,
    )


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