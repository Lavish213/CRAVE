"""
Share-to-CRAVE parser worker.

Picks up CraveItems with status='pending', fetches the URL to extract
restaurant name hints from Open Graph / HTML title metadata, then attempts
a fuzzy match against Place.name using rapidfuzz (already in requirements).

Match rules:
  - confidence > 0.7  → status='matched', creates a PlaceSignal(signal_type='creator')
  - confidence <= 0.7 → status='unmatched'
  - HTTP / parse error → status='error'

Run via:
    python -m app.workers.share_parser_worker

Or import run_share_parser() and call it from the master worker.
"""
from __future__ import annotations

import logging
import time
from contextlib import suppress
from datetime import datetime, timezone
from typing import Optional

import httpx
from bs4 import BeautifulSoup
from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.models.crave_item import CraveItem
from app.db.models.place import Place
from app.db.models.place_signal import PlaceSignal

logger = logging.getLogger(__name__)

BATCH_SIZE = 10
CONFIDENCE_THRESHOLD = 0.7
HTTP_TIMEOUT = 10.0
INTERVAL_SECONDS = 60

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; CRAVEbot/1.0; +https://crave.app/bot)"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


# ---------------------------------------------------------------------------
# HTML helpers
# ---------------------------------------------------------------------------

def _extract_place_name_from_html(html: str, url: str) -> Optional[str]:
    """
    Attempt to extract a restaurant name candidate from page HTML.

    Priority order:
    1. og:title meta tag
    2. <title> element
    3. First path segment of the URL (last resort)
    """
    try:
        soup = BeautifulSoup(html, "html.parser")

        # 1. og:title
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            return og_title["content"].strip()

        # 2. <title>
        title_tag = soup.find("title")
        if title_tag and title_tag.string:
            return title_tag.string.strip()

    except Exception as exc:
        logger.debug("html_parse_failed url=%s error=%s", url, exc)

    # 3. URL path segment fallback
    try:
        from urllib.parse import urlparse
        path = urlparse(url).path.strip("/")
        if path:
            segment = path.split("/")[0]
            # turn slug-style paths into readable names
            return segment.replace("-", " ").replace("_", " ").title()
    except Exception:
        pass

    return None


def _extract_city_hint_from_html(html: str) -> Optional[str]:
    """
    Try to extract a city hint from og:locale or geo.region meta tags.
    Returns None if nothing useful is found.
    """
    try:
        soup = BeautifulSoup(html, "html.parser")
        for prop in ("geo.placename", "og:locality", "article:location"):
            tag = soup.find("meta", {"name": prop}) or soup.find("meta", {"property": prop})
            if tag and tag.get("content"):
                return tag["content"].strip()
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Place matching
# ---------------------------------------------------------------------------

def _find_best_place_match(
    db: Session,
    place_name: str,
    city_hint: Optional[str],
) -> tuple[Optional[str], float]:
    """
    Fuzzy-match `place_name` against Place.name in the DB.

    If city_hint is provided, filter to places whose city.name ILIKE city_hint.
    Returns (place_id, confidence) or (None, 0.0).
    """
    if not place_name:
        return None, 0.0

    # Build candidate query — use ILIKE for the city hint if supplied
    stmt = select(Place).where(Place.is_active == True)  # noqa: E712

    if city_hint:
        # join through city to filter — use a subquery-friendly approach
        from app.db.models.city import City
        stmt = (
            stmt
            .join(Place.city)
            .where(City.name.ilike(f"%{city_hint}%"))
        )

    candidates = db.execute(stmt).scalars().all()

    if not candidates:
        # No city filter match — broaden to all active places
        candidates = db.execute(
            select(Place).where(Place.is_active == True)  # noqa: E712
        ).scalars().all()

    best_id: Optional[str] = None
    best_score: float = 0.0

    name_lower = place_name.lower().strip()

    for place in candidates:
        score = fuzz.token_set_ratio(name_lower, place.name.lower()) / 100.0
        if score > best_score:
            best_score = score
            best_id = place.id

    return best_id, best_score


# ---------------------------------------------------------------------------
# Single-item processor
# ---------------------------------------------------------------------------

def _process_item(db: Session, item: CraveItem) -> None:
    """Fetch, parse, match, and persist results for one CraveItem."""
    now = datetime.now(timezone.utc)

    try:
        with httpx.Client(timeout=HTTP_TIMEOUT, headers=_HEADERS, follow_redirects=True) as client:
            response = client.get(item.url)
            response.raise_for_status()
            html = response.text
    except Exception as exc:
        logger.warning("share_fetch_failed id=%s url=%s error=%s", item.id, item.url, exc)
        item.status = "error"
        item.processed_at = now
        db.commit()
        return

    # Store raw snippet (first 4000 chars to keep the column lean)
    item.raw_content = html[:4000]

    place_name = _extract_place_name_from_html(html, item.url)
    city_hint = item.parsed_city_hint or _extract_city_hint_from_html(html)

    item.parsed_place_name = place_name
    if city_hint:
        item.parsed_city_hint = city_hint

    if not place_name:
        logger.info("share_no_name_extracted id=%s url=%s", item.id, item.url)
        item.status = "unmatched"
        item.processed_at = now
        db.commit()
        return

    place_id, confidence = _find_best_place_match(db, place_name, city_hint)

    item.match_confidence = confidence
    item.processed_at = now

    if place_id and confidence >= CONFIDENCE_THRESHOLD:
        item.matched_place_id = place_id
        item.status = "matched"

        # Create a PlaceSignal so this URL feeds into the ranking pipeline
        signal = PlaceSignal(
            place_id=place_id,
            signal_type="creator",
            provider=item.source_type if item.source_type != "other" else "generic",
            value=min(1.0, confidence),
            raw_value=item.url[:255],
            external_event_id=f"crave_share:{item.id}",
            signal_class="discovery",
        )
        try:
            db.add(signal)
            db.flush()   # let DB raise IntegrityError if duplicate signal
        except Exception as exc:
            # Duplicate signal — that's fine, still mark as matched
            db.rollback()
            # Re-apply item fields explicitly after rollback so they are not lost
            item.matched_place_id = place_id
            item.status = "matched"
            item.match_confidence = confidence
            item.processed_at = now
            logger.debug("share_signal_duplicate id=%s error=%s", item.id, exc)
        db.commit()
        logger.info(
            "share_matched id=%s place_id=%s confidence=%.2f",
            item.id,
            place_id,
            confidence,
        )
    else:
        item.status = "unmatched"
        db.commit()
        logger.info(
            "share_unmatched id=%s name=%r confidence=%.2f",
            item.id,
            place_name,
            confidence,
        )


# ---------------------------------------------------------------------------
# Batch runner
# ---------------------------------------------------------------------------

def run_share_parser(db: Session | None = None, limit: int = BATCH_SIZE) -> dict:
    """
    Process up to `limit` pending CraveItems.

    Returns a summary dict: {processed, matched, unmatched, error}.
    If `db` is not provided, opens and closes its own session.
    """
    own_session = db is None
    if own_session:
        db = SessionLocal()

    summary = {"processed": 0, "matched": 0, "unmatched": 0, "error": 0}

    try:
        pending = db.execute(
            select(CraveItem)
            .where(CraveItem.status == "pending")
            .order_by(CraveItem.created_at.asc())
            .limit(limit)
        ).scalars().all()

        for item in pending:
            try:
                _process_item(db, item)
                summary["processed"] += 1
                summary[item.status] = summary.get(item.status, 0) + 1
            except Exception as exc:
                logger.exception("share_item_fatal id=%s error=%s", item.id, exc)
                with suppress(Exception):
                    db.rollback()
                with suppress(Exception):
                    item.status = "error"
                    item.processed_at = datetime.now(timezone.utc)
                    db.commit()
                summary["error"] += 1

    except Exception as exc:
        logger.exception("share_parser_batch_failed error=%s", exc)
        with suppress(Exception):
            db.rollback()
    finally:
        if own_session:
            with suppress(Exception):
                db.close()

    return summary


# ---------------------------------------------------------------------------
# Long-running loop entry point
# ---------------------------------------------------------------------------

def run_share_parser_worker() -> None:
    logger.info("share_parser_worker_start")

    while True:
        db = SessionLocal()
        try:
            result = run_share_parser(db=db)
            if result["processed"]:
                logger.info(
                    "share_parser_cycle processed=%s matched=%s unmatched=%s error=%s",
                    result["processed"],
                    result["matched"],
                    result["unmatched"],
                    result["error"],
                )
        except Exception as exc:
            logger.exception("share_parser_worker_error error=%s", exc)
            with suppress(Exception):
                db.rollback()
        finally:
            with suppress(Exception):
                db.close()

        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_share_parser_worker()
