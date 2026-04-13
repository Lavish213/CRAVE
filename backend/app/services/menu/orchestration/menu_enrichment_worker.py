from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from app.db.models.enrichment_job import EnrichmentJob
from app.db.models.place import Place

from app.services.menu.fetchers.grubhub_fetcher import (
    fetch_grubhub_menu,
    _resolve_grubhub_url,
)
from app.services.menu.providers.grubhub_parser import parse_grubhub_payload
from app.services.menu.adapters.grubhub_adapter import adapt_grubhub_items
from app.services.menu.validation.validate_extracted_items import validate_extracted_items
from app.services.menu.validation.validate_normalized_items import validate_normalized_items
from app.services.menu.menu_pipeline import process_extracted_menu
from app.services.menu.normalization.fingerprint import build_menu_fingerprint
from app.services.menu.contracts import NormalizedMenuItem
from app.services.menu.claims.menu_claim_emitter import emit_menu_claims
from app.services.menu.materialize_menu_truth import materialize_menu_truth


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _print(msg: str) -> None:
    print(f"[{_utcnow().isoformat()}] {msg}", flush=True)


# ─────────────────────────────────────────────────────────────────────────────
# SAFE JOB STATE HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _purge_stale_inactive_jobs(db: Session, job: EnrichmentJob) -> None:
    """
    Delete any pre-existing inactive (is_active=False) jobs for the same
    (place_id, job_type) EXCLUDING the current job.

    WHY: The enrichment_jobs table has a UNIQUE constraint on
    (place_id, job_type, is_active). Since is_active is boolean, at most
    one inactive row can exist per (place, type). Without purging the old
    inactive job first, marking the current job inactive would violate
    this constraint on every run after the first.
    """
    if not job.place_id or not job.job_type or not job.id:
        return
    try:
        db.query(EnrichmentJob).filter(
            EnrichmentJob.place_id == job.place_id,
            EnrichmentJob.job_type == job.job_type,
            EnrichmentJob.is_active.is_(False),
            EnrichmentJob.id != job.id,
        ).delete(synchronize_session=False)
    except Exception:
        pass  # best-effort; commit will surface a real conflict


def _mark_job_failed(
    db: Session,
    job: EnrichmentJob,
    error: str,
) -> None:
    """
    Mark a job failed. NEVER throws — uses rollback + retry-once pattern.
    """
    now = _utcnow()
    try:
        _purge_stale_inactive_jobs(db, job)
        job.status = "failed"
        job.last_error = str(error)[:500]
        job.is_active = False
        job.locked_at = None
        job.locked_by = None
        job.completed_at = now
        job.updated_at = now
        db.commit()
    except Exception:
        try:
            db.rollback()
            _purge_stale_inactive_jobs(db, job)
            job.status = "failed"
            job.last_error = str(error)[:500]
            job.is_active = False
            job.locked_at = None
            job.locked_by = None
            job.completed_at = now
            job.updated_at = now
            db.commit()
        except Exception:
            # Last resort: rollback and move on — outer loop handles recovery
            try:
                db.rollback()
            except Exception:
                pass


def _mark_job_completed(
    db: Session,
    job: EnrichmentJob,
    *,
    place: Optional[Place] = None,
) -> None:
    """
    Mark a job completed. NEVER throws.
    """
    now = _utcnow()
    try:
        _purge_stale_inactive_jobs(db, job)
        job.status = "completed"
        job.is_active = False
        job.locked_at = None
        job.locked_by = None
        job.last_error = None
        job.completed_at = now
        job.updated_at = now

        if place is not None:
            place.has_menu = True
            place.last_menu_updated_at = now

        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# NORMALIZED ITEM BUILDER (from CanonicalMenu)
# ─────────────────────────────────────────────────────────────────────────────

def _build_normalized_items(canonical_menu) -> List[NormalizedMenuItem]:
    seen: set = set()
    out: List[NormalizedMenuItem] = []

    for section in getattr(canonical_menu, "sections", []) or []:
        section_name = (getattr(section, "name", None) or "Other").strip()

        for item in getattr(section, "items", []) or []:
            name = (getattr(item, "name", None) or "").strip()
            if not name:
                continue

            currency = (getattr(item, "currency", None) or "USD").upper()
            fp = build_menu_fingerprint(name=name, section=section_name, currency=currency)

            if fp in seen:
                continue
            seen.add(fp)

            out.append(NormalizedMenuItem(
                name=name,
                section=section_name,
                price_cents=getattr(item, "price_cents", None),
                currency=currency,
                description=getattr(item, "description", None),
                fingerprint=fp,
            ))

    return out


# ─────────────────────────────────────────────────────────────────────────────
# MAIN WORKER
# ─────────────────────────────────────────────────────────────────────────────

def process_menu_job(
    db: Session,
    job: EnrichmentJob,
) -> None:
    """
    Full Grubhub menu pipeline for one job.

    Every failure stage:
    - prints FAILURE STAGE + FILE + ERROR
    - marks job failed safely
    - returns (never raises)

    Worker loop NEVER dies from a single job failure.
    """

    job_id = job.id
    place_id = job.place_id

    # ── Mark running ──────────────────────────────────────────────────────────
    # NOTE: the enrichment loop pre-marks jobs "running" and increments attempts
    # before calling this function. Only increment if still pending (direct call).
    try:
        now = _utcnow()
        already_running = job.status == "running"
        job.status = "running"
        job.locked_at = now
        if not already_running:
            job.attempts = (job.attempts or 0) + 1
        job.last_attempted_at = now
        job.updated_at = now
        db.commit()
    except Exception as exc:
        try:
            db.rollback()
        except Exception:
            pass
        _print(f"FAILURE STAGE: WORKER_DB_FAIL\nFILE: menu_enrichment_worker.py\nERROR: could not mark job running: {exc}")
        return

    _print(f"\n[JOB START]\nplace_id={place_id}")

    # ── Load place ────────────────────────────────────────────────────────────
    try:
        place = db.query(Place).filter(Place.id == place_id).first()
    except Exception as exc:
        _print(f"FAILURE STAGE: WORKER_DB_FAIL\nFILE: menu_enrichment_worker.py\nERROR: could not load place: {exc}")
        _mark_job_failed(db, job, f"db_load_place: {exc}")
        return

    if not place:
        _print(f"FAILURE STAGE: WORKER_DB_FAIL\nFILE: menu_enrichment_worker.py\nERROR: place not found place_id={place_id}")
        _mark_job_failed(db, job, "missing_place")
        return

    # ── STEP 1: URL RESOLUTION ────────────────────────────────────────────────
    resolved_url = _resolve_grubhub_url(place)
    _print(f"[URL]\ngrubhub_url={getattr(place, 'grubhub_url', None)!r}\nmenu_source_url={getattr(place, 'menu_source_url', None)!r}\nwebsite={getattr(place, 'website', None)!r}\nresolved={resolved_url!r}")

    if not resolved_url:
        _print(f"FAILURE STAGE: NO_URL\nFILE: menu_enrichment_worker.py\nERROR: no grubhub URL on place")
        _mark_job_failed(db, job, "NO_URL: no grubhub_url on place")
        return

    # ── STEP 2: FETCH ─────────────────────────────────────────────────────────
    try:
        payload = fetch_grubhub_menu(place)
    except Exception as exc:
        _print(f"FAILURE STAGE: FETCH_FAIL\nFILE: grubhub_fetcher.py\nERROR: {exc}")
        _mark_job_failed(db, job, f"FETCH_FAIL: {exc}")
        return

    _print(f"[FETCH]\npayload={payload is not None}")

    if payload is None:
        _print(f"FAILURE STAGE: FETCH_FAIL\nFILE: grubhub_fetcher.py\nERROR: fetch returned None (bot block or bad URL)")
        _mark_job_failed(db, job, "FETCH_FAIL: payload is None")
        return

    # ── STEP 3: PARSE ─────────────────────────────────────────────────────────
    try:
        raw_items = parse_grubhub_payload(payload)
    except Exception as exc:
        _print(f"FAILURE STAGE: PARSE_EMPTY\nFILE: grubhub_parser.py\nERROR: {exc}")
        _mark_job_failed(db, job, f"PARSE_EMPTY: {exc}")
        return

    _print(f"[PARSE]\nparsed_count={len(raw_items)}")

    if not raw_items:
        _print(f"FAILURE STAGE: PARSE_EMPTY\nFILE: grubhub_parser.py\nERROR: parser returned 0 items")
        _mark_job_failed(db, job, "PARSE_EMPTY: 0 items from parser")
        return

    # ── STEP 4: ADAPT ─────────────────────────────────────────────────────────
    try:
        extracted = adapt_grubhub_items(raw_items)
    except Exception as exc:
        _print(f"FAILURE STAGE: ADAPT_EMPTY\nFILE: grubhub_adapter.py\nERROR: {exc}")
        _mark_job_failed(db, job, f"ADAPT_EMPTY: {exc}")
        return

    _print(f"[ADAPT]\nadapted_count={len(extracted)}")

    if not extracted:
        _print(f"FAILURE STAGE: ADAPT_EMPTY\nFILE: grubhub_adapter.py\nERROR: adapter returned 0 items")
        _mark_job_failed(db, job, "ADAPT_EMPTY: 0 items from adapter")
        return

    # ── STEP 5: VALIDATE EXTRACTED ────────────────────────────────────────────
    try:
        validated = validate_extracted_items(extracted)
    except Exception as exc:
        _print(f"FAILURE STAGE: VALIDATION_EMPTY\nFILE: validate_extracted_items.py\nERROR: {exc}")
        _mark_job_failed(db, job, f"VALIDATION_EMPTY: {exc}")
        return

    _print(f"[VALIDATE EXTRACTED]\nvalidated_extracted_count={len(validated)}")

    if not validated:
        _print(f"FAILURE STAGE: VALIDATION_EMPTY\nFILE: validate_extracted_items.py\nERROR: validation removed all items")
        _mark_job_failed(db, job, "VALIDATION_EMPTY: 0 items after validation")
        return

    # ── STEP 6: PIPELINE ──────────────────────────────────────────────────────
    try:
        canonical_menu = process_extracted_menu(validated)
    except Exception as exc:
        _print(f"FAILURE STAGE: PIPELINE_EMPTY\nFILE: menu_pipeline.py\nERROR: {exc}")
        _mark_job_failed(db, job, f"PIPELINE_EMPTY: {exc}")
        return

    canonical_count = getattr(canonical_menu, "item_count", 0)

    # Build normalized items from canonical output
    try:
        normalized = _build_normalized_items(canonical_menu)
        normalized = validate_normalized_items(normalized)
    except Exception as exc:
        _print(f"FAILURE STAGE: PIPELINE_EMPTY\nFILE: menu_enrichment_worker.py\nERROR: normalization failed: {exc}")
        _mark_job_failed(db, job, f"PIPELINE_EMPTY: normalization: {exc}")
        return

    _print(f"[PIPELINE]\ncanonical_count={canonical_count}\nnormalized_count={len(normalized)}")

    if canonical_count < 2 or not normalized:
        _print(f"FAILURE STAGE: PIPELINE_EMPTY\nFILE: menu_pipeline.py\nERROR: pipeline produced {canonical_count} canonical items")
        _mark_job_failed(db, job, f"PIPELINE_EMPTY: {canonical_count} items")
        return

    # ── STEP 7: CLAIMS ────────────────────────────────────────────────────────
    try:
        claims = emit_menu_claims(
            db=db,
            place_id=place_id,
            items=normalized,
            source="menu_enrichment_worker",
            confidence=0.9,
            weight=1.0,
        ) or []
    except Exception as exc:
        _print(f"FAILURE STAGE: CLAIMS_FAIL\nFILE: menu_claim_emitter.py\nERROR: {exc}")
        _mark_job_failed(db, job, f"CLAIMS_FAIL: {exc}")
        return

    _print(f"[CLAIMS]\nclaims_count={len(claims)}")

    if not claims:
        _print(f"FAILURE STAGE: CLAIMS_FAIL\nFILE: menu_claim_emitter.py\nERROR: 0 claims emitted")
        _mark_job_failed(db, job, "CLAIMS_FAIL: 0 claims emitted")
        return

    # ── STEP 8: MATERIALIZE ───────────────────────────────────────────────────
    try:
        materialized_menu = materialize_menu_truth(db=db, place_id=place_id)
        materialized = materialized_menu is not None
    except Exception as exc:
        _print(f"FAILURE STAGE: MATERIALIZE_FAIL\nFILE: materialize_menu_truth.py\nERROR: {exc}")
        _mark_job_failed(db, job, f"MATERIALIZE_FAIL: {exc}")
        return

    _print(f"[MATERIALIZE]\nmaterialized={materialized}")

    if not materialized:
        _print(f"FAILURE STAGE: MATERIALIZE_FAIL\nFILE: materialize_menu_truth.py\nERROR: returned None")
        _mark_job_failed(db, job, "MATERIALIZE_FAIL: returned None")
        return

    # ── COMPLETE ──────────────────────────────────────────────────────────────
    _mark_job_completed(db, job, place=place)
    _print(f"[JOB COMPLETE] place_id={place_id} claims={len(claims)} materialized={materialized}")
