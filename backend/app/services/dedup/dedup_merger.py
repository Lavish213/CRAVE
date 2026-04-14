from __future__ import annotations

import logging
from contextlib import suppress
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.models.place import Place
from app.db.models.place_claim import PlaceClaim
from app.db.models.place_truth import PlaceTruth


logger = logging.getLogger(__name__)


def _pick_winner(place_a: Place, place_b: Place) -> tuple[Place, Place]:
    """
    Pick the canonical place (winner) to keep.

    Preference order:
    1. Higher master_score
    2. Older record (earlier created_at) — more established
    3. Alphabetical by id as final stable tie-break
    """
    score_a = place_a.master_score or 0.0
    score_b = place_b.master_score or 0.0

    if score_a > score_b:
        return place_a, place_b

    if score_b > score_a:
        return place_b, place_a

    # Equal score — prefer older record
    ts_a = getattr(place_a, "created_at", None)
    ts_b = getattr(place_b, "created_at", None)

    if ts_a and ts_b:
        return (place_a, place_b) if ts_a <= ts_b else (place_b, place_a)

    return (place_a, place_b) if place_a.id < place_b.id else (place_b, place_a)


def merge_duplicate_places(
    db: Session,
    *,
    place_a_id: str,
    place_b_id: str,
    dry_run: bool = True,
) -> Optional[str]:
    """
    Merge two duplicate places.

    Reassigns claims and truths from the loser to the winner,
    then marks the loser inactive. DOES NOT delete records.

    Returns the winner's place_id, or None on failure.
    Set dry_run=True (default) to log without writing.
    """

    place_a = db.get(Place, place_a_id)
    place_b = db.get(Place, place_b_id)

    if not place_a or not place_b:
        logger.warning("merge_failed missing place a=%s b=%s", place_a_id, place_b_id)
        return None

    if not place_a.is_active or not place_b.is_active:
        logger.info("merge_skipped one_inactive a=%s b=%s", place_a_id, place_b_id)
        return None

    winner, loser = _pick_winner(place_a, place_b)

    logger.info(
        "merge_plan winner=%s loser=%s dry_run=%s",
        winner.id,
        loser.id,
        dry_run,
    )

    if dry_run:
        return winner.id

    # --- Reassign claims ---
    with suppress(Exception):
        db.execute(
            update(PlaceClaim)
            .where(PlaceClaim.place_id == loser.id)
            .values(place_id=winner.id)
        )

    # --- Reassign truths (delete loser's — winner's truths take precedence) ---
    with suppress(Exception):
        loser_truths = db.execute(
            select(PlaceTruth).where(PlaceTruth.place_id == loser.id)
        ).scalars().all()
        for truth in loser_truths:
            db.delete(truth)

    # --- Mark loser inactive ---
    loser.is_active = False

    # --- Propagate missing data to winner ---
    if not winner.website and loser.website:
        winner.website = loser.website
    if not winner.grubhub_url and getattr(loser, "grubhub_url", None):
        winner.grubhub_url = loser.grubhub_url  # type: ignore[assignment]

    db.flush()

    logger.info("merge_complete winner=%s loser_deactivated=%s", winner.id, loser.id)

    return winner.id
