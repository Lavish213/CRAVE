from logging.config import fileConfig

from sqlalchemy import create_engine, pool
from alembic import context

from app.config.settings import settings
from app.db.models.base import Base


# --------------------------------------------------
# 🔥 FORCE-LOAD ALL MODELS (CRITICAL)
# --------------------------------------------------

# Core models
from app.db.models.place import Place  # noqa: F401
from app.db.models.menu_item import MenuItem  # noqa: F401
from app.db.models.category import Category  # noqa: F401
from app.db.models.city import City  # noqa: F401

# Relationship / supporting models
from app.db.models.place_claim import PlaceClaim  # noqa: F401
from app.db.models.place_truth import PlaceTruth  # noqa: F401
from app.db.models.place_image import PlaceImage  # noqa: F401
from app.db.models.place_categories import place_categories  # noqa: F401

# Discovery / pipeline models
from app.db.models.discovery_candidate import DiscoveryCandidate  # noqa: F401
from app.db.models.enrichment_job import EnrichmentJob  # noqa: F401
from app.db.models.menu_source import MenuSource  # noqa: F401
from app.db.models.place_signal import PlaceSignal  # noqa: F401

# Snapshot / pipeline models
from app.db.models.place_feed_snapshot import PlaceFeedSnapshot  # noqa: F401
from app.db.models.menu_snapshot import MenuSnapshot  # noqa: F401

# Ranking
from app.db.models.city_place_ranking import CityPlaceRanking  # noqa: F401

# Fetch logs
from app.db.models.place_image_fetch_log import PlaceImageFetchLog  # noqa: F401

# Hit List
from app.db.models.hitlist_save import HitlistSave  # noqa: F401
from app.db.models.hitlist_suggestion import HitlistSuggestion  # noqa: F401
from app.db.models.hitlist_dedup_key import HitlistDedupKey  # noqa: F401


# --------------------------------------------------
# Alembic Config
# --------------------------------------------------

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


# --------------------------------------------------
# Metadata (single source of truth)
# --------------------------------------------------

target_metadata = Base.metadata


# --------------------------------------------------
# Resolve DB URL
# --------------------------------------------------

DATABASE_URL = str(settings.resolved_database_url)

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not configured properly.")

# Normalise Heroku legacy scheme (postgres://) — already handled by settings,
# but guard here in case the URL is injected via alembic.ini directly.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

config.set_main_option("sqlalchemy.url", DATABASE_URL)


# --------------------------------------------------
# SQLite check
# --------------------------------------------------

IS_SQLITE = DATABASE_URL.startswith("sqlite")


# --------------------------------------------------
# OFFLINE
# --------------------------------------------------

def run_migrations_offline() -> None:

    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        render_as_batch=IS_SQLITE,
    )

    with context.begin_transaction():
        context.run_migrations()


# --------------------------------------------------
# ONLINE
# --------------------------------------------------

def run_migrations_online() -> None:

    connectable = create_engine(
        DATABASE_URL,
        poolclass=pool.NullPool,
        future=True,
    )

    with connectable.connect() as connection:

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            render_as_batch=IS_SQLITE,
        )

        with context.begin_transaction():
            context.run_migrations()


# --------------------------------------------------
# ENTRY
# --------------------------------------------------

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()