from __future__ import annotations

from datetime import datetime, timezone
import uuid

from app.db.models.hitlist_save import HitlistSave
from app.db.models.place import Place
from app.db.models.place_ranking import TIER_DISLIKED, TIER_LIKED, PlaceRanking
from app.db.models.recommendation_event import (
    EVENT_CLICK,
    EVENT_IMPRESSION,
    RecommendationEvent,
    SURFACE_FEED,
)
from app.db.models.visit_evidence import VISIT_TIER_DECLARED, VisitEvidence
from app.db.session import SessionLocal
from app.services.feed.user_evidence_resolver import (
    PreferenceDirection,
    SessionRejection,
    resolve_user_evidence,
)


def _place(db, *, name: str) -> Place:
    place = Place(
        id=str(uuid.uuid4()),
        name=name,
        city_id="00000000-0000-0000-0000-000000000001",
        lat=37.8044,
        lng=-122.2712,
        is_active=True,
        rank_score=0.5,
    )
    db.add(place)
    db.flush()
    return place


def test_visit_is_history_not_positive_preference() -> None:
    db = SessionLocal()
    user_id = f"fv2-visit-{uuid.uuid4()}"
    place = _place(db, name="Visit Only")
    try:
        db.add(
            VisitEvidence(
                user_id=user_id,
                place_id=place.id,
                tier=VISIT_TIER_DECLARED,
                source="test",
                source_ref=str(uuid.uuid4()),
                occurred_at=datetime.now(timezone.utc),
                confirmed_at=datetime.now(timezone.utc),
                factual_history=True,
                recommendation_influence=True,
            )
        )
        db.commit()

        evidence = resolve_user_evidence(db, user_id=user_id, place_ids=[place.id])[place.id]
        assert evidence.factual_history.has_visit is True
        assert evidence.factual_history.recommendation_influence_enabled is True
        assert evidence.durable_preference.direction is PreferenceDirection.UNKNOWN
        assert evidence.durable_preference.has_explicit_preference is False
    finally:
        db.query(VisitEvidence).filter(VisitEvidence.user_id == user_id).delete()
        db.delete(place)
        db.commit()
        db.close()


def test_explicit_negative_rank_is_preserved_even_with_save_and_visit() -> None:
    db = SessionLocal()
    user_id = f"fv2-negative-{uuid.uuid4()}"
    place = _place(db, name="Explicit Negative")
    try:
        db.add(
            PlaceRanking(
                user_id=user_id,
                place_id=place.id,
                tier=TIER_DISLIKED,
                rank_score=1.5,
            )
        )
        db.add(
            HitlistSave(
                user_id=user_id,
                place_name=place.name,
                place_id=place.id,
                resolution_status="matched",
                dedup_key=f"save:{place.id}",
            )
        )
        db.add(
            VisitEvidence(
                user_id=user_id,
                place_id=place.id,
                tier=VISIT_TIER_DECLARED,
                source="test",
                source_ref=str(uuid.uuid4()),
                occurred_at=datetime.now(timezone.utc),
                factual_history=True,
                recommendation_influence=True,
            )
        )
        db.commit()

        evidence = resolve_user_evidence(db, user_id=user_id, place_ids=[place.id])[place.id]
        assert evidence.durable_preference.direction is PreferenceDirection.NEGATIVE
        assert evidence.prospective_intent.native_save is True
        assert evidence.factual_history.has_visit is True
    finally:
        db.query(VisitEvidence).filter(VisitEvidence.user_id == user_id).delete()
        db.query(HitlistSave).filter(HitlistSave.user_id == user_id).delete()
        db.query(PlaceRanking).filter(PlaceRanking.user_id == user_id).delete()
        db.delete(place)
        db.commit()
        db.close()


def test_session_rejection_is_ephemeral_and_does_not_rewrite_durable_taste() -> None:
    db = SessionLocal()
    user_id = f"fv2-session-{uuid.uuid4()}"
    place = _place(db, name="Not Tonight")
    try:
        db.add(
            PlaceRanking(
                user_id=user_id,
                place_id=place.id,
                tier=TIER_LIKED,
                rank_score=8.8,
            )
        )
        db.commit()

        evidence = resolve_user_evidence(
            db,
            user_id=user_id,
            place_ids=[place.id],
            session_rejections=[SessionRejection(place_id=place.id, reason="not tonight")],
        )[place.id]
        assert evidence.durable_preference.direction is PreferenceDirection.POSITIVE
        assert evidence.session_intent.rejected is True
        assert evidence.session_intent.rejection_reason == "not tonight"

        fresh = resolve_user_evidence(db, user_id=user_id, place_ids=[place.id])[place.id]
        assert fresh.durable_preference.direction is PreferenceDirection.POSITIVE
        assert fresh.session_intent.rejected is False
    finally:
        db.query(PlaceRanking).filter(PlaceRanking.user_id == user_id).delete()
        db.delete(place)
        db.commit()
        db.close()


def test_exposure_is_counted_separately_from_preference() -> None:
    db = SessionLocal()
    user_id = f"fv2-exposure-{uuid.uuid4()}"
    place = _place(db, name="Exposure Only")
    try:
        db.add_all(
            [
                RecommendationEvent(
                    user_id=user_id,
                    place_id=place.id,
                    surface=SURFACE_FEED,
                    event_type=EVENT_IMPRESSION,
                    position=0,
                ),
                RecommendationEvent(
                    user_id=user_id,
                    place_id=place.id,
                    surface=SURFACE_FEED,
                    event_type=EVENT_IMPRESSION,
                    position=1,
                ),
                RecommendationEvent(
                    user_id=user_id,
                    place_id=place.id,
                    surface=SURFACE_FEED,
                    event_type=EVENT_CLICK,
                    position=1,
                ),
            ]
        )
        db.commit()

        evidence = resolve_user_evidence(db, user_id=user_id, place_ids=[place.id])[place.id]
        assert evidence.exposure.impression_count == 2
        assert evidence.exposure.click_count == 1
        assert evidence.exposure.has_passive_exposure is True
        assert evidence.durable_preference.direction is PreferenceDirection.UNKNOWN
    finally:
        db.query(RecommendationEvent).filter(RecommendationEvent.user_id == user_id).delete()
        db.delete(place)
        db.commit()
        db.close()


def test_candidate_scope_returns_unknown_evidence_for_unseen_place() -> None:
    db = SessionLocal()
    user_id = f"fv2-unknown-{uuid.uuid4()}"
    place = _place(db, name="Unknown Candidate")
    try:
        evidence = resolve_user_evidence(db, user_id=user_id, place_ids=[place.id])[place.id]
        assert evidence.durable_preference.direction is PreferenceDirection.UNKNOWN
        assert evidence.prospective_intent.has_interest is False
        assert evidence.factual_history.has_visit is False
        assert evidence.exposure.has_passive_exposure is False
        assert evidence.session_intent.rejected is False
    finally:
        db.delete(place)
        db.commit()
        db.close()
