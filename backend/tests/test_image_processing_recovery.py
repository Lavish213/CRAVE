"""
Coverage for app.workers.image_processing_worker.reclaim_stale_image_uploads
-- the self-healing sweep for PlaceImage rows stuck 'pending'/'processing'.

process_image_upload() runs as a FastAPI BackgroundTask off POST
/upload/confirm (unlike videos, which are entirely scheduler-driven for
exactly this durability reason -- see app/scheduler.py's own
_job_video_processing docstring). A BackgroundTask has no persistence: if
the serving process is killed or redeployed mid-task (every Railway
deploy), the row is stuck forever with nothing else to ever revisit it,
and the frontend's status poll (useImageStatusPoll.ts) spins indefinitely
with no way to reach 'ready' or 'failed'. PlaceImage has no `updated_at`
column (unlike PlaceVideo), so staleness here is judged off `created_at`
-- safe, since process_image_upload is a single HTTP-bound background
task expected to finish in well under a minute, not staged/resumable
work like video's ffmpeg encoding.

process_image_upload itself is fully covered elsewhere
(test_image_processing_worker.py) -- these tests only cover the
selection/reclaim logic, with process_image_upload mocked at the call
site.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.db.session import SessionLocal
from app.db.models.city import City
from app.db.models.place import Place
from app.db.models.place_image import PlaceImage
import app.workers.image_processing_worker as worker_module
from app.workers.image_processing_worker import reclaim_stale_image_uploads


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def place(db):
    suffix = uuid.uuid4().hex[:8]
    city = City(
        id=str(uuid.uuid4()), name=f"Image Recovery Test City {suffix}",
        slug=f"image-recovery-test-{suffix}", lat=37.8, lng=-122.27, is_active=True,
    )
    db.add(city)
    db.flush()
    p = Place(name=f"Image Recovery Test Place {suffix}", city_id=city.id, is_active=True)
    db.add(p)
    db.commit()
    yield p
    db.query(PlaceImage).filter(PlaceImage.place_id == p.id).delete()
    db.query(Place).filter(Place.id == p.id).delete()
    db.query(City).filter(City.id == city.id).delete()
    db.commit()


def _make_image(db, place, *, status: str, created_at: datetime) -> PlaceImage:
    image = PlaceImage(
        id=str(uuid.uuid4()),
        place_id=place.id,
        orig_key=f"places/{place.id}/orig/{uuid.uuid4()}.jpg",
        status=status,
        uploaded_by="test-user",
        created_at=created_at,
    )
    db.add(image)
    db.commit()
    return image


def test_a_fresh_processing_row_is_not_reclaimed(db, place, monkeypatch):
    """A row that entered 'processing' moments ago is still genuinely in
    flight -- reclaiming it now would risk a concurrent second call while
    the original BackgroundTask is still legitimately running."""
    _make_image(db, place, status="processing", created_at=datetime.now(timezone.utc))

    calls = []
    monkeypatch.setattr(worker_module, "process_image_upload", lambda image_id: calls.append(image_id))

    reclaimed = reclaim_stale_image_uploads()

    assert reclaimed == 0
    assert calls == []


def test_a_stale_processing_row_is_reclaimed(db, place, monkeypatch):
    """The actual crash-recovery case: a row still 'processing' well past
    photo_stale_processing_minutes almost certainly means the process
    serving its BackgroundTask was killed or redeployed mid-item."""
    stale_at = datetime.now(timezone.utc) - timedelta(hours=2)
    image = _make_image(db, place, status="processing", created_at=stale_at)

    calls = []
    monkeypatch.setattr(worker_module, "process_image_upload", lambda image_id: calls.append(image_id))

    reclaimed = reclaim_stale_image_uploads()

    assert reclaimed == 1
    assert calls == [image.id]


def test_a_stale_pending_row_is_also_reclaimed(db, place, monkeypatch):
    """A 'pending' row (upload slot created, PUT never confirmed) is the
    same shape of stuck -- process_image_upload's own guard already
    accepts re-entry from 'pending', and calling it lets a genuinely
    abandoned upload fail cleanly (R2 object missing) instead of sitting
    forever."""
    stale_at = datetime.now(timezone.utc) - timedelta(hours=2)
    image = _make_image(db, place, status="pending", created_at=stale_at)

    calls = []
    monkeypatch.setattr(worker_module, "process_image_upload", lambda image_id: calls.append(image_id))

    reclaimed = reclaim_stale_image_uploads()

    assert reclaimed == 1
    assert calls == [image.id]


def test_ready_and_failed_rows_are_never_touched(db, place, monkeypatch):
    stale_at = datetime.now(timezone.utc) - timedelta(hours=2)
    _make_image(db, place, status="ready", created_at=stale_at)
    _make_image(db, place, status="failed", created_at=stale_at)

    calls = []
    monkeypatch.setattr(worker_module, "process_image_upload", lambda image_id: calls.append(image_id))

    reclaimed = reclaim_stale_image_uploads()

    assert reclaimed == 0
    assert calls == []


def test_a_single_reclaim_failure_does_not_block_the_rest_of_the_batch(db, place, monkeypatch):
    image_a = _make_image(
        db, place, status="processing",
        created_at=datetime.now(timezone.utc) - timedelta(hours=3),
    )
    image_b = _make_image(
        db, place, status="processing",
        created_at=datetime.now(timezone.utc) - timedelta(hours=2),
    )

    calls = []

    def _process(image_id):
        calls.append(image_id)
        if image_id == image_a.id:
            # process_image_upload never actually raises past its own
            # top-level try/except (it catches everything and marks the
            # row 'failed') -- this only simulates something escaping
            # that, to prove one bad row can't stop the rest of the batch.
            raise RuntimeError("simulated crash mid-reclaim")

    monkeypatch.setattr(worker_module, "process_image_upload", _process)

    reclaimed = reclaim_stale_image_uploads()

    # Both rows counted as attempted -- the return value tracks selection,
    # not per-row success.
    assert reclaimed == 2
    assert calls == [image_a.id, image_b.id]


def test_respects_the_limit_argument(db, place, monkeypatch):
    stale_at = datetime.now(timezone.utc) - timedelta(hours=2)
    for _ in range(3):
        _make_image(db, place, status="processing", created_at=stale_at)

    calls = []
    monkeypatch.setattr(worker_module, "process_image_upload", lambda image_id: calls.append(image_id))

    reclaimed = reclaim_stale_image_uploads(limit=2)

    assert reclaimed == 2
    assert len(calls) == 2
