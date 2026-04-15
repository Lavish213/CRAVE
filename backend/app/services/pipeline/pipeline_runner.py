from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.services.pipeline.candidate_normalizer import normalize_batch
from app.services.pipeline.spam_filter import filter_candidates
from app.services.pipeline.place_resolver import resolve_batch, write_unresolved_to_discovery
from app.services.pipeline.signal_writer import write_signal

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    total_input: int = 0
    normalized: int = 0
    spam_rejected: int = 0
    resolved: int = 0
    unresolved: int = 0
    signals_written: int = 0
    signals_duplicate: int = 0
    discovery_candidates_created: int = 0
    errors: list[str] = field(default_factory=list)


def run_pipeline(
    records: list[dict],
    *,
    db: Session = None,
    commit: bool = True,
) -> PipelineResult:
    """
    Full pipeline: raw records → normalized → spam filter → resolve → write signals.

    Idempotent — safe to re-run on same data.
    Does NOT write to Place table directly.
    Unresolved candidates go to DiscoveryCandidate table only.
    """
    result = PipelineResult(total_input=len(records))
    _own_session = db is None

    if _own_session:
        db = SessionLocal()

    try:
        # Stage 1: Normalize
        candidates = normalize_batch(records)
        result.normalized = len(candidates)

        # Stage 2: Spam filter
        accepted, rejected = filter_candidates(candidates)
        result.spam_rejected = len(rejected)

        # Stage 3: Resolve
        resolved_list = resolve_batch(db, accepted)

        for resolved in resolved_list:
            if resolved.place_id:
                result.resolved += 1

                # Stage 4a: Write signal
                write_result = write_signal(db, resolved)
                if write_result:
                    if write_result.duplicate:
                        result.signals_duplicate += 1
                    elif not write_result.skipped:
                        result.signals_written += 1
            else:
                result.unresolved += 1

                # Stage 4b: Write to discovery staging
                try:
                    candidate_id = write_unresolved_to_discovery(db, resolved)
                    if candidate_id:
                        result.discovery_candidates_created += 1
                except Exception as exc:
                    result.errors.append(f"discovery_write_failed: {exc}")

        if commit:
            db.commit()

        logger.info(
            "pipeline_complete input=%s normalized=%s spam_rejected=%s "
            "resolved=%s unresolved=%s signals=%s duplicates=%s discovery=%s",
            result.total_input, result.normalized, result.spam_rejected,
            result.resolved, result.unresolved, result.signals_written,
            result.signals_duplicate, result.discovery_candidates_created,
        )

    except Exception as exc:
        db.rollback()
        logger.exception("pipeline_failed error=%s", exc)
        result.errors.append(str(exc))
    finally:
        if _own_session:
            db.close()

    return result
