"""
Share-to-CRAVE parser worker.

Picks up CraveItems with status='pending', plus 'error'/'unmatched' items
whose backoff window (next_retry_at) has elapsed, fetches the URL to
extract restaurant name hints from Open Graph / HTML title metadata, then
attempts a fuzzy match against Place.name using rapidfuzz (already in
requirements).

Match rules:
  - confidence > 0.7  → status='matched', creates a PlaceSignal(signal_type='creator')
  - confidence <= 0.7 → status='unmatched', retried later with backoff
  - HTTP / parse error → status='error', retried later with backoff

See _schedule_retry for the backoff schedule and retry cap.

Run via:
    python -m app.workers.share_parser_worker

Or import run_share_parser() and call it from the master worker.
"""
from __future__ import annotations

import ipaddress
import logging
import socket
import time
from contextlib import suppress
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from rapidfuzz import fuzz
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.models.crave_item import CraveItem
from app.db.models.place import Place
from app.db.models.place_signal import PlaceSignal
from app.services.social.oembed_client import get_oembed_data
from app.services.discovery.discovery_service import ingest_candidate_v2

logger = logging.getLogger(__name__)

BATCH_SIZE = 10
CONFIDENCE_THRESHOLD = 0.7
HTTP_TIMEOUT = 10.0
INTERVAL_SECONDS = 60

# Confidence assigned to a DiscoveryCandidate created from a single unmatched
# share — deliberately low. One person sharing one TikTok about a place isn't
# enough to promote it on its own (MIN_CONFIDENCE_THRESHOLD is 0.72); it takes
# multiple independent shares/signals converging on the same place before the
# scheduler's discovery job promotes it automatically. See
# app/services/discovery/promotion_orchestrator_v2.py.
UNMATCHED_SHARE_CANDIDATE_CONFIDENCE = 0.3

# Retry / backoff for 'error' and 'unmatched' items — see CraveItem.next_retry_at's
# docstring. Same exponential-backoff-with-cap shape as
# promotion_orchestrator_v2's DiscoveryCandidate retry handling: delay doubles
# per attempt up to a cap, and once failure_count reaches the cap next_retry_at
# is left NULL so the item stops being picked up (permanently, not just until
# the next backoff window).
MAX_RETRY_ATTEMPTS = 5
RETRY_BACKOFF_BASE_MINUTES = 30
RETRY_BACKOFF_MAX_MINUTES = 480  # 8 hours

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; CRAVEbot/1.0; +https://crave.app/bot)"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

_MAX_REDIRECTS = 5


# ---------------------------------------------------------------------------
# SSRF protection
# ---------------------------------------------------------------------------
#
# share_intake (app/api/v1/routes/share.py) deliberately accepts arbitrary
# "web"/"other" URLs, not just known platforms — sharing a blog post/article
# about a restaurant is a real, intended use case, so this can't be a domain
# allowlist. Instead, validate the actual network destination: reject any
# URL whose host resolves to a private, loopback, link-local (this is what
# catches cloud metadata endpoints like 169.254.169.254), multicast,
# reserved, or unspecified address. Every authenticated user can trigger
# this fetch by submitting a URL, so without this a signed-in user could
# make the backend issue requests to internal services or the metadata
# endpoint just by sharing a crafted link.

def _resolve_host_ips(host: str) -> list[str]:
    try:
        infos = socket.getaddrinfo(host, None)
    except (socket.gaierror, UnicodeError):
        return []
    return list({info[4][0] for info in infos})


def _is_public_ip(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def _is_safe_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except Exception:
        return False

    if parsed.scheme not in ("http", "https"):
        return False

    host = parsed.hostname
    if not host:
        return False

    ips = _resolve_host_ips(host)
    if not ips:
        # Doesn't resolve — fail closed rather than let httpx's own resolver
        # hit something this lookup didn't see.
        return False

    return all(_is_public_ip(ip) for ip in ips)


def _safe_get(url: str, *, headers: dict, timeout: float) -> httpx.Response:
    """
    GET with the safety check re-run at every redirect hop — a URL that
    resolves to a public IP on the first request can still 30x to an
    internal address, and blindly following redirects (the previous
    behavior) would chase it there.
    """
    current_url = url
    for _ in range(_MAX_REDIRECTS + 1):
        if not _is_safe_url(current_url):
            raise ValueError(f"unsafe URL blocked: {current_url}")

        with httpx.Client(timeout=timeout, headers=headers, follow_redirects=False) as client:
            response = client.get(current_url)

        if response.is_redirect:
            location = response.headers.get("location")
            if not location:
                return response
            current_url = str(httpx.URL(current_url).join(location))
            continue

        return response

    raise ValueError(f"too many redirects: {url}")


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
# Retry / backoff
# ---------------------------------------------------------------------------

def _schedule_retry(item: CraveItem, now: datetime, error: Optional[str] = None) -> None:
    """Bump failure_count and set next_retry_at with exponential backoff.

    Called for both real failures (status='error') and non-terminal outcomes
    that deserve another look later (status='unmatched' — the catalog may
    grow to include the place). Once failure_count reaches MAX_RETRY_ATTEMPTS,
    next_retry_at is left NULL so the item stops being selected at all.
    """
    item.failure_count = (item.failure_count or 0) + 1
    if error:
        item.last_error = error[:500]

    if item.failure_count >= MAX_RETRY_ATTEMPTS:
        item.next_retry_at = None
        logger.info(
            "share_retry_exhausted id=%s failure_count=%s status=%s",
            item.id, item.failure_count, item.status,
        )
    else:
        delay_minutes = min(
            RETRY_BACKOFF_BASE_MINUTES * (2 ** (item.failure_count - 1)),
            RETRY_BACKOFF_MAX_MINUTES,
        )
        item.next_retry_at = now + timedelta(minutes=delay_minutes)


def _clear_retry_state(item: CraveItem) -> None:
    item.failure_count = 0
    item.last_error = None
    item.next_retry_at = None


# ---------------------------------------------------------------------------
# Single-item processor
# ---------------------------------------------------------------------------

def _process_item(db: Session, item: CraveItem) -> None:
    """Fetch, parse, match, and persist results for one CraveItem."""
    now = datetime.now(timezone.utc)

    # oEmbed first for platforms that publish it (TikTok, YouTube — Instagram
    # once INSTAGRAM_OEMBED_ACCESS_TOKEN is configured). This is real caption
    # text from the platform's own API, not a guess at scraped HTML — a
    # plain GET against a JS-rendered app like TikTok/Instagram usually just
    # returns a login-wall shell with no usable title. Also pulls
    # thumbnail_url/embed_html/author_name, previously discarded entirely —
    # without these there was no way to show "seen on TikTok" content
    # anywhere in the app, only a bare matched/unmatched status.
    oembed = get_oembed_data(item.source_type, item.url)

    place_name: Optional[str] = None
    city_hint: Optional[str] = item.parsed_city_hint

    if oembed:
        if oembed.get("thumbnail_url"):
            item.thumbnail_url = oembed["thumbnail_url"][:1024]
        if oembed.get("html"):
            item.embed_html = oembed["html"]
        if oembed.get("author_name"):
            item.author_name = oembed["author_name"][:255]

        oembed_text = oembed.get("title")
        item.raw_content = oembed_text[:4000] if oembed_text else None
        place_name = oembed_text
    else:
        try:
            response = _safe_get(item.url, headers=_HEADERS, timeout=HTTP_TIMEOUT)
            response.raise_for_status()
            html = response.text
        except Exception as exc:
            logger.warning("share_fetch_failed id=%s url=%s error=%s", item.id, item.url, exc)
            item.status = "error"
            item.processed_at = now
            _schedule_retry(item, now, error=str(exc))
            db.commit()
            return

        # Store raw snippet (first 4000 chars to keep the column lean)
        item.raw_content = html[:4000]

        place_name = _extract_place_name_from_html(html, item.url)
        city_hint = city_hint or _extract_city_hint_from_html(html)

    item.parsed_place_name = place_name
    if city_hint:
        item.parsed_city_hint = city_hint

    if not place_name:
        logger.info("share_no_name_extracted id=%s url=%s", item.id, item.url)
        item.status = "unmatched"
        item.processed_at = now
        _schedule_retry(item, now)
        db.commit()
        return

    place_id, confidence = _find_best_place_match(db, place_name, city_hint)

    item.match_confidence = confidence
    item.processed_at = now

    if place_id and confidence >= CONFIDENCE_THRESHOLD:
        item.matched_place_id = place_id
        item.status = "matched"
        _clear_retry_state(item)

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
            _clear_retry_state(item)
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
        _schedule_retry(item, now)

        # No existing place matched — this is likely a genuinely new spot,
        # not just a bad name guess. Feed it into the discovery-candidate
        # pipeline instead of dead-ending here (previously it just sat as
        # "unmatched" forever with no further action). Low confidence,
        # since a single scraped/oEmbed'd caption is weak, unverified
        # evidence — see UNMATCHED_SHARE_CANDIDATE_CONFIDENCE. If enough
        # independent shares (or GPS confirmations, or hitlist suggestions)
        # converge on the same place, it crosses the promotion threshold on
        # its own via the scheduler's discovery job — no extra logic needed
        # here.
        try:
            ingest_candidate_v2(
                db=db,
                name=place_name[:160],
                city_name=city_hint,
                source="user_share",
                confidence=UNMATCHED_SHARE_CANDIDATE_CONFIDENCE,
                raw_payload={"crave_item_id": item.id, "url": item.url, "source_type": item.source_type},
                contributor_key=f"user_share:{item.submitted_by or item.id}",
            )
        except ValueError as exc:
            # Most commonly: no city could be resolved from a bare caption
            # with no location info. Not an error — just not enough to work
            # with yet.
            logger.debug("share_candidate_skip id=%s reason=%s", item.id, exc)
        except Exception as exc:
            logger.warning("share_candidate_failed id=%s error=%s", item.id, exc)

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
        now = datetime.now(timezone.utc)
        # 'pending' items are always eligible (first attempt). 'error'/
        # 'unmatched' items are only picked up once their backoff window has
        # elapsed — see _schedule_retry/CraveItem.next_retry_at. Items whose
        # next_retry_at was cleared to NULL after exhausting MAX_RETRY_ATTEMPTS
        # are deliberately excluded here (only 'pending' matches a NULL
        # next_retry_at) so they stop being retried forever.
        pending = db.execute(
            select(CraveItem)
            .where(
                or_(
                    CraveItem.status == "pending",
                    and_(
                        CraveItem.status.in_(("error", "unmatched")),
                        CraveItem.next_retry_at.isnot(None),
                        CraveItem.next_retry_at <= now,
                    ),
                )
            )
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
                    _schedule_retry(item, datetime.now(timezone.utc), error=str(exc))
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
