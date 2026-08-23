"""
Coverage for streak_service.py -- the daily-streak gamification feature.
Key correctness property this guards: day comparisons must be by
calendar day in the user's timezone, never by raw elapsed hours (the
most common place this class of feature gets built wrong).
"""
from __future__ import annotations

import sys
import uuid
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal
from app.db.models.user_streak import UserStreak
from app.services.social.streak_service import get_streak, record_activity


@pytest.fixture
def db():
    created_user_ids = []
    session = SessionLocal()
    try:
        yield session, created_user_ids
    finally:
        session.rollback()
        if created_user_ids:
            session.query(UserStreak).filter(
                UserStreak.user_id.in_(created_user_ids)
            ).delete(synchronize_session=False)
        session.commit()
        session.close()


def test_first_ever_ping_starts_a_streak_of_one(db):
    session, created = db
    user_id = f"streak_{uuid.uuid4().hex[:8]}"
    created.append(user_id)

    state = record_activity(session, user_id=user_id, client_timezone="UTC")

    assert state.current_streak == 1
    assert state.longest_streak == 1
    assert state.last_active_date == date.today()


def test_pinging_again_the_same_day_is_a_no_op(db):
    session, created = db
    user_id = f"streak_{uuid.uuid4().hex[:8]}"
    created.append(user_id)

    record_activity(session, user_id=user_id, client_timezone="UTC")
    state = record_activity(session, user_id=user_id, client_timezone="UTC")

    assert state.current_streak == 1
    assert state.longest_streak == 1


def test_consecutive_day_increments_the_streak(db):
    session, created = db
    user_id = f"streak_{uuid.uuid4().hex[:8]}"
    created.append(user_id)

    record_activity(session, user_id=user_id, client_timezone="UTC")
    streak = session.query(UserStreak).filter(UserStreak.user_id == user_id).one()
    streak.last_active_date = date.today() - timedelta(days=1)
    session.commit()

    state = record_activity(session, user_id=user_id, client_timezone="UTC")

    assert state.current_streak == 2
    assert state.longest_streak == 2


def test_missed_day_resets_current_streak_but_keeps_longest(db):
    session, created = db
    user_id = f"streak_{uuid.uuid4().hex[:8]}"
    created.append(user_id)

    record_activity(session, user_id=user_id, client_timezone="UTC")
    streak = session.query(UserStreak).filter(UserStreak.user_id == user_id).one()
    streak.current_streak = 5
    streak.longest_streak = 5
    streak.last_active_date = date.today() - timedelta(days=3)
    session.commit()

    state = record_activity(session, user_id=user_id, client_timezone="UTC")

    assert state.current_streak == 1
    assert state.longest_streak == 5


def test_day_boundary_is_calendar_day_not_raw_hours_elapsed(db):
    session, created = db
    user_id = f"streak_{uuid.uuid4().hex[:8]}"
    created.append(user_id)

    # Simulate "active late last night, active again early this
    # morning" -- under 24 raw hours could easily have elapsed, but it's
    # a different calendar day, so this must still count as the next
    # consecutive streak day, not a no-op or a reset.
    record_activity(session, user_id=user_id, client_timezone="UTC")
    streak = session.query(UserStreak).filter(UserStreak.user_id == user_id).one()
    streak.last_active_date = date.today() - timedelta(days=1)
    session.commit()

    state = record_activity(session, user_id=user_id, client_timezone="UTC")
    assert state.current_streak == 2


def test_an_implausible_backward_timezone_jump_never_moves_the_streak_backward(db):
    session, created = db
    user_id = f"streak_{uuid.uuid4().hex[:8]}"
    created.append(user_id)

    record_activity(session, user_id=user_id, client_timezone="UTC")
    streak = session.query(UserStreak).filter(UserStreak.user_id == user_id).one()
    streak.last_active_date = date.today() + timedelta(days=1)
    streak.current_streak = 3
    streak.longest_streak = 3
    session.commit()

    state = record_activity(session, user_id=user_id, client_timezone="UTC")

    assert state.current_streak == 3
    assert state.last_active_date == date.today() + timedelta(days=1)


def test_an_unrecognized_timezone_name_falls_back_to_utc_instead_of_erroring(db):
    session, created = db
    user_id = f"streak_{uuid.uuid4().hex[:8]}"
    created.append(user_id)

    state = record_activity(session, user_id=user_id, client_timezone="Not/A_Real_Zone")

    assert state.current_streak == 1


def test_get_streak_for_a_user_with_no_history_returns_zeros(db):
    session, _ = db
    result = get_streak(session, user_id=f"never_seen_{uuid.uuid4().hex[:8]}")

    assert result.current_streak == 0
    assert result.longest_streak == 0
    assert result.last_active_date is None
