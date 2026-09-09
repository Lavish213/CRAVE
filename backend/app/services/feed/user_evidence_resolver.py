from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Mapping, Sequence

from sqlalchemy.orm import Session

from app.db.models.crave_item import CraveItem
from app.db.models.hitlist_save import HitlistSave
from app.db.models.place_ranking import (
    TIER_DISLIKED,
    TIER_FINE,
    TIER_LIKED,
    PlaceRanking,
)
from app.db.models.recommendation_event import (
    EVENT_CLICK,
    EVENT_IMPRESSION,
    RecommendationEvent,
)
from app.db.models.visit_evidence import VisitEvidence


class PreferenceDirection(str, Enum):
    """Durable preference direction supported by explicit evidence."""

    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class SessionRejection:
    """Ephemeral Decision Session evidence supplied by the session owner.

    This is deliberately not loaded from durable storage in FV2-01. A rejection
    can mean "too far", "too expensive", "not tonight", or a genuine taste
    rejection; preserving the reason is more important than flattening all four
    into one permanent dislike.
    """

    place_id: str
    reason: str | None = None


@dataclass(frozen=True)
class DurablePreferenceEvidence:
    direction: PreferenceDirection
    rank_tier: str | None = None
    rank_score: float | None = None
    ranked_at: datetime | None = None

    @property
    def has_explicit_preference(self) -> bool:
        return self.rank_tier is not None


@dataclass(frozen=True)
class ProspectiveIntentEvidence:
    native_save: bool = False
    manual_or_other_save: bool = False
    imported_crave: bool = False
    latest_saved_at: datetime | None = None
    latest_imported_at: datetime | None = None

    @property
    def has_interest(self) -> bool:
        return self.native_save or self.manual_or_other_save or self.imported_crave


@dataclass(frozen=True)
class FactualHistoryEvidence:
    has_visit: bool = False
    latest_visit_at: datetime | None = None
    strongest_visit_tier: str | None = None
    recommendation_influence_enabled: bool = False


@dataclass(frozen=True)
class ExposureEvidence:
    impression_count: int = 0
    click_count: int = 0
    latest_impression_at: datetime | None = None
    latest_click_at: datetime | None = None

    @property
    def has_passive_exposure(self) -> bool:
        return self.impression_count > 0 or self.click_count > 0


@dataclass(frozen=True)
class SessionIntentEvidence:
    rejected: bool = False
    rejection_reason: str | None = None


@dataclass(frozen=True)
class ResolvedPlaceEvidence:
    """Typed evidence for one user/place pair.

    The categories intentionally remain separate. Consumers may evaluate them,
    but this resolver never turns a visit into a like, a save into love, a click
    into durable taste, or a temporary rejection into a permanent dislike.
    """

    place_id: str
    durable_preference: DurablePreferenceEvidence
    prospective_intent: ProspectiveIntentEvidence
    factual_history: FactualHistoryEvidence
    exposure: ExposureEvidence
    session_intent: SessionIntentEvidence
    collaborative_support: float | None = None


_VISIT_TIER_PRIORITY = {
    "inferred": 1,
    "declared": 2,
    "verified": 3,
}


def _preference_from_ranking(row: PlaceRanking | None) -> DurablePreferenceEvidence:
    if row is None:
        return DurablePreferenceEvidence(direction=PreferenceDirection.UNKNOWN)

    if row.tier == TIER_LIKED:
        direction = PreferenceDirection.POSITIVE
    elif row.tier == TIER_DISLIKED:
        direction = PreferenceDirection.NEGATIVE
    elif row.tier == TIER_FINE:
        direction = PreferenceDirection.NEUTRAL
    else:
        # The database constraint should make this unreachable, but keeping the
        # resolver conservative is safer than inventing meaning for unknown data.
        direction = PreferenceDirection.UNKNOWN

    return DurablePreferenceEvidence(
        direction=direction,
        rank_tier=row.tier,
        rank_score=float(row.rank_score),
        ranked_at=row.updated_at or row.created_at,
    )


def _latest_datetime(values: Sequence[datetime | None]) -> datetime | None:
    present = [value for value in values if value is not None]
    return max(present) if present else None


def _history_from_visits(rows: Sequence[VisitEvidence]) -> FactualHistoryEvidence:
    factual_rows = [row for row in rows if row.factual_history]
    if not factual_rows:
        return FactualHistoryEvidence()

    strongest = max(
        factual_rows,
        key=lambda row: _VISIT_TIER_PRIORITY.get(row.tier, 0),
    )
    return FactualHistoryEvidence(
        has_visit=True,
        latest_visit_at=_latest_datetime([row.occurred_at for row in factual_rows]),
        strongest_visit_tier=strongest.tier,
        # This flag means at least one current visit source is allowed to
        # influence recommendation recency/history. It does NOT make the visit
        # positive preference evidence.
        recommendation_influence_enabled=any(
            row.recommendation_influence for row in factual_rows
        ),
    )


def _intent_from_saves(
    saves: Sequence[HitlistSave],
    imports: Sequence[CraveItem],
) -> ProspectiveIntentEvidence:
    native = [row for row in saves if row.dedup_key.startswith("save:")]
    other = [row for row in saves if not row.dedup_key.startswith("save:")]
    return ProspectiveIntentEvidence(
        native_save=bool(native),
        manual_or_other_save=bool(other),
        imported_crave=bool(imports),
        latest_saved_at=_latest_datetime([row.created_at for row in saves]),
        latest_imported_at=_latest_datetime([row.created_at for row in imports]),
    )


def _exposure_from_events(rows: Sequence[RecommendationEvent]) -> ExposureEvidence:
    impressions = [row for row in rows if row.event_type == EVENT_IMPRESSION]
    clicks = [row for row in rows if row.event_type == EVENT_CLICK]
    return ExposureEvidence(
        impression_count=len(impressions),
        click_count=len(clicks),
        latest_impression_at=_latest_datetime([row.created_at for row in impressions]),
        latest_click_at=_latest_datetime([row.created_at for row in clicks]),
    )


def _apply_place_filter(query, column, place_ids: tuple[str, ...] | None):
    if place_ids is not None:
        return query.filter(column.in_(place_ids))
    return query


def resolve_user_evidence(
    db: Session,
    *,
    user_id: str,
    place_ids: Sequence[str] | None = None,
    session_rejections: Sequence[SessionRejection] = (),
    collaborative_support: Mapping[str, float] | None = None,
) -> dict[str, ResolvedPlaceEvidence]:
    """Resolve current Feed-consumable evidence for a user.

    FV2-01 is intentionally an evidence authority, not a scoring model. It reads
    only evidence that exists today and preserves its semantics/provenance. The
    evaluator introduced in FV2-02 will decide how these dimensions affect a
    candidate; this function does not assign recommendation weights.

    `place_ids` should be supplied by candidate evaluation whenever possible so
    a request does not load a user's entire history unnecessarily. Passing an
    empty sequence returns immediately. Session rejections and collaborative
    support are caller-owned ephemeral inputs and are never persisted here.
    """
    normalized_place_ids: tuple[str, ...] | None
    if place_ids is None:
        normalized_place_ids = None
    else:
        normalized_place_ids = tuple(dict.fromkeys(str(value) for value in place_ids if value))
        if not normalized_place_ids:
            return {}

    rankings_query = db.query(PlaceRanking).filter(PlaceRanking.user_id == user_id)
    rankings = _apply_place_filter(
        rankings_query, PlaceRanking.place_id, normalized_place_ids
    ).all()

    visits_query = db.query(VisitEvidence).filter(VisitEvidence.user_id == user_id)
    visits = _apply_place_filter(
        visits_query, VisitEvidence.place_id, normalized_place_ids
    ).all()

    saves_query = db.query(HitlistSave).filter(
        HitlistSave.user_id == user_id,
        HitlistSave.place_id.is_not(None),
    )
    saves = _apply_place_filter(
        saves_query, HitlistSave.place_id, normalized_place_ids
    ).all()

    imports_query = db.query(CraveItem).filter(
        CraveItem.submitted_by == user_id,
        CraveItem.status == "matched",
        CraveItem.matched_place_id.is_not(None),
    )
    imports = _apply_place_filter(
        imports_query, CraveItem.matched_place_id, normalized_place_ids
    ).all()

    events_query = db.query(RecommendationEvent).filter(
        RecommendationEvent.user_id == user_id,
        RecommendationEvent.place_id.is_not(None),
        RecommendationEvent.event_type.in_((EVENT_IMPRESSION, EVENT_CLICK)),
    )
    events = _apply_place_filter(
        events_query, RecommendationEvent.place_id, normalized_place_ids
    ).all()

    ranking_by_place = {row.place_id: row for row in rankings}
    visits_by_place: dict[str, list[VisitEvidence]] = {}
    saves_by_place: dict[str, list[HitlistSave]] = {}
    imports_by_place: dict[str, list[CraveItem]] = {}
    events_by_place: dict[str, list[RecommendationEvent]] = {}

    for row in visits:
        visits_by_place.setdefault(row.place_id, []).append(row)
    for row in saves:
        if row.place_id is not None:
            saves_by_place.setdefault(row.place_id, []).append(row)
    for row in imports:
        if row.matched_place_id is not None:
            imports_by_place.setdefault(row.matched_place_id, []).append(row)
    for row in events:
        if row.place_id is not None:
            events_by_place.setdefault(row.place_id, []).append(row)

    rejection_by_place = {row.place_id: row for row in session_rejections}
    support = collaborative_support or {}

    if normalized_place_ids is None:
        resolved_ids = set(ranking_by_place)
        resolved_ids.update(visits_by_place)
        resolved_ids.update(saves_by_place)
        resolved_ids.update(imports_by_place)
        resolved_ids.update(events_by_place)
        resolved_ids.update(rejection_by_place)
        resolved_ids.update(support)
    else:
        # Candidate-scoped callers need an explicit unknown-evidence object for
        # every candidate, not only candidates that already have history.
        resolved_ids = set(normalized_place_ids)

    return {
        place_id: ResolvedPlaceEvidence(
            place_id=place_id,
            durable_preference=_preference_from_ranking(ranking_by_place.get(place_id)),
            prospective_intent=_intent_from_saves(
                saves_by_place.get(place_id, ()), imports_by_place.get(place_id, ())
            ),
            factual_history=_history_from_visits(visits_by_place.get(place_id, ())),
            exposure=_exposure_from_events(events_by_place.get(place_id, ())),
            session_intent=SessionIntentEvidence(
                rejected=place_id in rejection_by_place,
                rejection_reason=(
                    rejection_by_place[place_id].reason
                    if place_id in rejection_by_place
                    else None
                ),
            ),
            collaborative_support=(
                float(support[place_id]) if place_id in support else None
            ),
        )
        for place_id in sorted(resolved_ids)
    }
