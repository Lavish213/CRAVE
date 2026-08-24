from __future__ import annotations

from sqlalchemy import Boolean, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base, JSONType, TimestampMixin


class VideoTemplate(Base, TimestampMixin):
    """
    A shot template for the food-video record flow (e.g. "Cheese Pull",
    "First Cut") — data, not code, so adding/editing/disabling one is an
    INSERT/UPDATE, never a deploy. `beat_cues` is JSON so each template can
    define its own number/shape of on-screen prompts without a schema
    change.

    `id` is a short human-readable slug (e.g. "cheese_pull"), not a UUID —
    it's referenced directly by the client's bundled overlay assets and by
    PlaceVideo.template_id, so a stable, readable key is more useful here
    than a surrogate one.

    `min_food_area_pct` is advisory only, same as in the original scaffold
    this ported from — nothing in the processing pipeline enforces it yet.
    Kept so a future composition-quality check has a place to read a
    per-template threshold from instead of a schema change.
    """

    __tablename__ = "video_templates"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)

    name: Mapped[str] = mapped_column(String(128), nullable=False)

    overlay_asset_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # [{"t": 0, "cue": "hold plate steady"}, ...] — seconds offset + prompt text.
    beat_cues: Mapped[list] = mapped_column(JSONType, nullable=False, default=list)

    min_food_area_pct: Mapped[int] = mapped_column(
        Integer, nullable=False, default=30, server_default=text("30"),
    )

    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true"),
    )

    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0"),
    )
