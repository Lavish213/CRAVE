"""
Coverage for the CraveItem retry/backoff added to app.workers.share_parser_worker.

Before this, run_share_parser only ever selected status='pending' items — a
transient fetch failure ('error') or a not-yet-in-the-catalog place
('unmatched') was never revisited. This exercises the backoff scheduling
(_schedule_retry/_clear_retry_state) and the batch query's next_retry_at
filtering that picks 'error'/'unmatched' items back up once their window
elapses, and permanently excludes items that exhausted MAX_RETRY_ATTEMPTS.
"""
from __future__ import annotations

import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal
from app.db.models.crave_item import CraveItem
from app.workers.share_parser_worker import (
    MAX_RETRY_ATTEMPTS,
    RETRY_BACKOFF_BASE_MINUTES,
    _clear_retry_state,
    _schedule_retry,
    run_share_parser,
)


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def make_item(db):
    created_ids = []

    def _make(**overrides):
        item = CraveItem(url=f"https://example.com/{uuid.uuid4().hex}", source_type="web")
        for key, value in overrides.items():
            setattr(item, key, value)
        db.add(item)
        db.commit()
        created_ids.append(item.id)
        return item

    yield _make

    # Some tests mutate `item` in-memory without committing (e.g. calling
    # _schedule_retry directly) — discard that pending state first, or the
    # bulk delete() below (which issues a raw DELETE without autoflushing)
    # leaves a dangling UPDATE that fails at commit time with StaleDataError
    # once its target row is already gone.
    db.rollback()
    db.query(CraveItem).filter(CraveItem.id.in_(created_ids)).delete(synchronize_session=False)
    db.commit()


# ---------------------------------------------------------------------------
# _schedule_retry / _clear_retry_state
# ---------------------------------------------------------------------------

def test_schedule_retry_increments_failure_count_and_sets_backoff(make_item):
    item = make_item(status="error")
    now = datetime.now(timezone.utc)

    _schedule_retry(item, now, error="boom")

    assert item.failure_count == 1
    assert item.last_error == "boom"
    assert item.next_retry_at is not None
    assert item.next_retry_at >= now + timedelta(minutes=RETRY_BACKOFF_BASE_MINUTES) - timedelta(seconds=5)


def test_schedule_retry_backs_off_further_on_repeated_failures(make_item):
    item = make_item(status="error")
    now = datetime.now(timezone.utc)

    _schedule_retry(item, now, error="first")
    first_delay = item.next_retry_at - now

    _schedule_retry(item, now, error="second")
    second_delay = item.next_retry_at - now

    assert item.failure_count == 2
    assert second_delay > first_delay


def test_schedule_retry_leaves_next_retry_at_null_once_exhausted(make_item):
    item = make_item(status="error")
    now = datetime.now(timezone.utc)

    for _ in range(MAX_RETRY_ATTEMPTS):
        _schedule_retry(item, now, error="still failing")

    assert item.failure_count == MAX_RETRY_ATTEMPTS
    assert item.next_retry_at is None


def test_clear_retry_state_resets_all_fields(make_item):
    item = make_item(status="error", failure_count=3, last_error="old error")
    item.next_retry_at = datetime.now(timezone.utc) + timedelta(hours=1)

    _clear_retry_state(item)

    assert item.failure_count == 0
    assert item.last_error is None
    assert item.next_retry_at is None


# ---------------------------------------------------------------------------
# run_share_parser query — which items get picked up
# ---------------------------------------------------------------------------

def test_run_share_parser_skips_error_item_still_in_backoff_window(db, make_item):
    item = make_item(
        status="error",
        failure_count=1,
        next_retry_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )

    with patch("app.workers.share_parser_worker._process_item") as mock_process:
        run_share_parser(db=db, limit=10)

    processed_ids = {call.args[1].id for call in mock_process.call_args_list}
    assert item.id not in processed_ids


def test_run_share_parser_picks_up_error_item_past_backoff_window(db, make_item):
    item = make_item(
        status="error",
        failure_count=1,
        next_retry_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )

    with patch("app.workers.share_parser_worker._process_item") as mock_process:
        run_share_parser(db=db, limit=10)

    processed_ids = {call.args[1].id for call in mock_process.call_args_list}
    assert item.id in processed_ids


def test_run_share_parser_picks_up_unmatched_item_past_backoff_window(db, make_item):
    item = make_item(
        status="unmatched",
        failure_count=1,
        next_retry_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )

    with patch("app.workers.share_parser_worker._process_item") as mock_process:
        run_share_parser(db=db, limit=10)

    processed_ids = {call.args[1].id for call in mock_process.call_args_list}
    assert item.id in processed_ids


def test_run_share_parser_excludes_exhausted_retry_item(db, make_item):
    # failure_count at the cap with next_retry_at NULL (the exhausted state
    # _schedule_retry leaves behind) must never be picked up again.
    item = make_item(
        status="error",
        failure_count=MAX_RETRY_ATTEMPTS,
        next_retry_at=None,
    )

    with patch("app.workers.share_parser_worker._process_item") as mock_process:
        run_share_parser(db=db, limit=10)

    processed_ids = {call.args[1].id for call in mock_process.call_args_list}
    assert item.id not in processed_ids


def test_run_share_parser_always_picks_up_pending_regardless_of_next_retry_at(db, make_item):
    item = make_item(status="pending")
    assert item.next_retry_at is None

    with patch("app.workers.share_parser_worker._process_item") as mock_process:
        run_share_parser(db=db, limit=10)

    processed_ids = {call.args[1].id for call in mock_process.call_args_list}
    assert item.id in processed_ids


# ---------------------------------------------------------------------------
# _process_item outcomes wire up retry state correctly
# ---------------------------------------------------------------------------

def test_process_item_fetch_failure_schedules_retry(db, make_item):
    item = make_item(status="pending")

    with patch(
        "app.workers.share_parser_worker._safe_get",
        side_effect=ValueError("unsafe URL blocked: x"),
    ), patch("app.workers.share_parser_worker.get_oembed_data", return_value=None):
        run_share_parser(db=db, limit=10)

    db.refresh(item)
    assert item.status == "error"
    assert item.failure_count == 1
    assert item.next_retry_at is not None
    assert item.last_error is not None
