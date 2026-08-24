"""
Coverage for app.services.video.video_processing_worker -- the
download -> duration-gate -> compress -> food-score -> thumbnail ->
approve/reject pipeline. Every external call (R2, ffmpeg, the food
classifier) is mocked: there's no real ffmpeg binary or TFLite model file
in this test environment, matching how the worker itself is designed to
behave when the classifier isn't set up yet (see food_classifier.py).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from app.db.session import SessionLocal
from app.db.models.city import City
from app.db.models.place import Place
from app.db.models.place_video import (
    PlaceVideo,
    STATUS_PENDING,
    STATUS_QUEUED,
    STATUS_PROCESSING,
    STATUS_APPROVED,
    STATUS_REJECTED,
    STATUS_FAILED,
    REJECT_CORRUPT,
    REJECT_DURATION,
    REJECT_FOOD_SCORE,
    REJECT_ABANDONED_UPLOAD,
)
from app.services.video.ffmpeg_steps import VideoCorruptError
from app.services.video.food_classifier import FoodClassifierUnavailableError
from app.services.video.video_processing_worker import (
    process_one_video,
    process_pending_videos,
    reject_abandoned_pending_uploads,
    _select_batch,
)


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def place(db):
    suffix = uuid.uuid4().hex[:8]
    c = City(slug=f"video-worker-test-{suffix}", name=f"Video Worker Test City {suffix}")
    db.add(c)
    db.commit()
    p = Place(name=f"Place {suffix}", city_id=c.id, is_active=True)
    db.add(p)
    db.commit()
    yield p
    db.query(PlaceVideo).filter(PlaceVideo.place_id == p.id).delete()
    db.query(Place).filter(Place.id == p.id).delete()
    db.query(City).filter(City.id == c.id).delete()
    db.commit()


def _make_video(db, place, *, status: str, created_at=None, updated_at=None) -> PlaceVideo:
    v = PlaceVideo(
        place_id=place.id,
        uploaded_by="user-a",
        orig_key=f"places/{place.id}/videos/orig/{uuid.uuid4().hex}.mp4",
        status=status,
    )
    db.add(v)
    db.commit()
    if created_at is not None or updated_at is not None:
        if created_at is not None:
            db.query(PlaceVideo).filter(PlaceVideo.id == v.id).update({"created_at": created_at})
        if updated_at is not None:
            db.query(PlaceVideo).filter(PlaceVideo.id == v.id).update({"updated_at": updated_at})
        db.commit()
        db.refresh(v)
    return v


# ---------------------------------------------------------------------------
# reject_abandoned_pending_uploads
# ---------------------------------------------------------------------------

def test_sweeps_a_pending_video_older_than_the_threshold(db, place):
    old = datetime.now(timezone.utc) - timedelta(minutes=999)
    video = _make_video(db, place, status=STATUS_PENDING, created_at=old)

    with patch("app.services.video.video_processing_worker.delete_object") as mock_delete:
        count = reject_abandoned_pending_uploads(db)

    assert count == 1
    mock_delete.assert_called_once_with(video.orig_key)
    db.refresh(video)
    assert video.status == STATUS_REJECTED
    assert video.reject_reason == REJECT_ABANDONED_UPLOAD


def test_does_not_sweep_a_recently_pending_video(db, place):
    _make_video(db, place, status=STATUS_PENDING)

    count = reject_abandoned_pending_uploads(db)

    assert count == 0


def test_does_not_sweep_queued_or_processing_videos_regardless_of_age(db, place):
    # This is the actual fix over the Node scaffold's orphan sweep, which
    # had no way to tell "client never uploaded" apart from "worker's
    # been down a while" and destructively deleted both. A DB-polling
    # worker never needs that distinction: 'queued'/'processing' rows are
    # always found again by _select_batch, sweeping them here would just
    # be actively wrong.
    old = datetime.now(timezone.utc) - timedelta(minutes=999)
    queued = _make_video(db, place, status=STATUS_QUEUED, created_at=old)
    processing = _make_video(db, place, status=STATUS_PROCESSING, created_at=old, updated_at=old)

    count = reject_abandoned_pending_uploads(db)

    assert count == 0
    db.refresh(queued)
    db.refresh(processing)
    assert queued.status == STATUS_QUEUED
    assert processing.status == STATUS_PROCESSING


# ---------------------------------------------------------------------------
# _select_batch
# ---------------------------------------------------------------------------

def test_select_batch_includes_queued_and_stale_processing(db, place):
    queued = _make_video(db, place, status=STATUS_QUEUED)
    stale = _make_video(
        db, place, status=STATUS_PROCESSING,
        updated_at=datetime.now(timezone.utc) - timedelta(minutes=999),
    )
    fresh_processing = _make_video(db, place, status=STATUS_PROCESSING)

    batch_ids = {v.id for v in _select_batch(db, limit=10)}

    assert queued.id in batch_ids
    assert stale.id in batch_ids
    assert fresh_processing.id not in batch_ids


# ---------------------------------------------------------------------------
# process_one_video -- each stage's reject/fail path
# ---------------------------------------------------------------------------

def test_corrupt_file_is_rejected_not_failed(db, place):
    video = _make_video(db, place, status=STATUS_QUEUED)

    with patch("app.services.video.video_processing_worker.download_to_file"), \
         patch("app.services.video.video_processing_worker.ffmpeg_steps.check_duration_ms",
               side_effect=VideoCorruptError("bad file")), \
         patch("app.services.video.video_processing_worker.delete_object") as mock_delete:
        outcome = process_one_video(db, video)

    assert outcome == STATUS_REJECTED
    mock_delete.assert_called_once()
    db.refresh(video)
    assert video.reject_reason == REJECT_CORRUPT


def test_out_of_range_duration_is_rejected(db, place):
    video = _make_video(db, place, status=STATUS_QUEUED)

    with patch("app.services.video.video_processing_worker.download_to_file"), \
         patch("app.services.video.video_processing_worker.ffmpeg_steps.check_duration_ms",
               return_value=999_999), \
         patch("app.services.video.video_processing_worker.delete_object"):
        outcome = process_one_video(db, video)

    assert outcome == STATUS_REJECTED
    db.refresh(video)
    assert video.reject_reason == REJECT_DURATION
    assert video.duration_ms == 999_999


def test_food_classifier_unavailable_fails_not_rejects(db, place):
    # The key distinction: this is a config/setup problem, not a verdict
    # on the video's content -- it must land in 'failed' (retried once
    # the classifier is actually set up) not 'rejected' (permanent,
    # user-facing "your video didn't qualify").
    video = _make_video(db, place, status=STATUS_QUEUED)

    with patch("app.services.video.video_processing_worker.download_to_file"), \
         patch("app.services.video.video_processing_worker.ffmpeg_steps.check_duration_ms",
               return_value=5000), \
         patch("app.services.video.video_processing_worker.ffmpeg_steps.compress_video",
               return_value="/tmp/fake-compressed.mp4"), \
         patch("app.services.video.video_processing_worker.score_video",
               side_effect=FoodClassifierUnavailableError("no model file")):
        outcome = process_one_video(db, video)

    assert outcome == STATUS_FAILED
    db.refresh(video)
    assert "food_classifier_unavailable" in (video.error_message or "")


def test_low_food_score_is_rejected(db, place):
    video = _make_video(db, place, status=STATUS_QUEUED)

    with patch("app.services.video.video_processing_worker.download_to_file"), \
         patch("app.services.video.video_processing_worker.ffmpeg_steps.check_duration_ms",
               return_value=5000), \
         patch("app.services.video.video_processing_worker.ffmpeg_steps.compress_video",
               return_value="/tmp/fake-compressed.mp4"), \
         patch("app.services.video.video_processing_worker.score_video",
               return_value=0.1), \
         patch("app.services.video.video_processing_worker.delete_object"):
        outcome = process_one_video(db, video)

    assert outcome == STATUS_REJECTED
    db.refresh(video)
    assert video.reject_reason == REJECT_FOOD_SCORE
    assert video.food_score == 0.1


def test_successful_pipeline_approves_and_stores_keys(db, place):
    video = _make_video(db, place, status=STATUS_QUEUED)

    with patch("app.services.video.video_processing_worker.download_to_file"), \
         patch("app.services.video.video_processing_worker.ffmpeg_steps.check_duration_ms",
               return_value=5000), \
         patch("app.services.video.video_processing_worker.ffmpeg_steps.compress_video",
               return_value="/tmp/fake-compressed.mp4"), \
         patch("app.services.video.video_processing_worker.score_video",
               return_value=0.9), \
         patch("app.services.video.video_processing_worker.ffmpeg_steps.generate_thumbnail",
               return_value="/tmp/fake-thumb.jpg"), \
         patch("app.services.video.video_processing_worker.upload_file") as mock_upload, \
         patch("app.services.video.video_processing_worker.delete_object") as mock_delete:
        outcome = process_one_video(db, video)

    assert outcome == STATUS_APPROVED
    assert mock_upload.call_count == 2  # processed + thumb
    mock_delete.assert_called_once_with(video.orig_key)
    db.refresh(video)
    assert video.status == STATUS_APPROVED
    assert video.duration_ms == 5000
    assert video.food_score == 0.9
    assert video.processed_key is not None
    assert video.thumb_key is not None


# ---------------------------------------------------------------------------
# process_one_video -- auto-highlight for source clips longer than
# video_max_duration_ms but within video_highlight_max_source_duration_ms
# ---------------------------------------------------------------------------

def test_source_within_normal_window_never_calls_highlight_scoring(db, place):
    video = _make_video(db, place, status=STATUS_QUEUED)

    with patch("app.services.video.video_processing_worker.download_to_file"), \
         patch("app.services.video.video_processing_worker.ffmpeg_steps.check_duration_ms",
               return_value=5000), \
         patch("app.services.video.video_processing_worker.find_best_highlight_window") as mock_window, \
         patch("app.services.video.video_processing_worker.ffmpeg_steps.trim_video") as mock_trim, \
         patch("app.services.video.video_processing_worker.ffmpeg_steps.compress_video",
               return_value="/tmp/fake-compressed.mp4"), \
         patch("app.services.video.video_processing_worker.score_video",
               return_value=0.9), \
         patch("app.services.video.video_processing_worker.ffmpeg_steps.generate_thumbnail",
               return_value="/tmp/fake-thumb.jpg"), \
         patch("app.services.video.video_processing_worker.upload_file"), \
         patch("app.services.video.video_processing_worker.delete_object"):
        outcome = process_one_video(db, video)

    assert outcome == STATUS_APPROVED
    mock_window.assert_not_called()
    mock_trim.assert_not_called()


def test_source_over_max_but_within_highlight_ceiling_is_trimmed_and_approved(db, place):
    video = _make_video(db, place, status=STATUS_QUEUED)

    with patch("app.services.video.video_processing_worker.download_to_file"), \
         patch("app.services.video.video_processing_worker.ffmpeg_steps.check_duration_ms",
               side_effect=[30_000, 10_000]), \
         patch("app.services.video.video_processing_worker.find_best_highlight_window",
               return_value=(12.0, 0.85)) as mock_window, \
         patch("app.services.video.video_processing_worker.ffmpeg_steps.trim_video",
               return_value="/tmp/fake-trimmed.mp4") as mock_trim, \
         patch("app.services.video.video_processing_worker.ffmpeg_steps.compress_video",
               return_value="/tmp/fake-compressed.mp4"), \
         patch("app.services.video.video_processing_worker.score_video",
               return_value=0.9), \
         patch("app.services.video.video_processing_worker.ffmpeg_steps.generate_thumbnail",
               return_value="/tmp/fake-thumb.jpg"), \
         patch("app.services.video.video_processing_worker.upload_file"), \
         patch("app.services.video.video_processing_worker.delete_object"):
        outcome = process_one_video(db, video)

    assert outcome == STATUS_APPROVED
    mock_window.assert_called_once()
    args, _kwargs = mock_window.call_args
    assert args[1] == 10.0  # settings.video_max_duration_ms (10_000) as seconds
    mock_trim.assert_called_once_with(args[0], 12.0, 10.0)
    db.refresh(video)
    assert video.duration_ms == 10_000  # the trimmed clip's duration, not the source's


def test_source_over_highlight_ceiling_is_rejected_without_scoring(db, place):
    video = _make_video(db, place, status=STATUS_QUEUED)

    with patch("app.services.video.video_processing_worker.download_to_file"), \
         patch("app.services.video.video_processing_worker.ffmpeg_steps.check_duration_ms",
               return_value=90_000), \
         patch("app.services.video.video_processing_worker.find_best_highlight_window") as mock_window, \
         patch("app.services.video.video_processing_worker.delete_object"):
        outcome = process_one_video(db, video)

    assert outcome == STATUS_REJECTED
    mock_window.assert_not_called()
    db.refresh(video)
    assert video.reject_reason == REJECT_DURATION
    assert video.duration_ms == 90_000


def test_highlight_scoring_classifier_unavailable_fails_not_rejects(db, place):
    video = _make_video(db, place, status=STATUS_QUEUED)

    with patch("app.services.video.video_processing_worker.download_to_file"), \
         patch("app.services.video.video_processing_worker.ffmpeg_steps.check_duration_ms",
               return_value=30_000), \
         patch("app.services.video.video_processing_worker.find_best_highlight_window",
               side_effect=FoodClassifierUnavailableError("no model file")):
        outcome = process_one_video(db, video)

    assert outcome == STATUS_FAILED
    db.refresh(video)
    assert "food_classifier_unavailable" in (video.error_message or "")


def test_highlight_trim_failure_fails_the_video(db, place):
    video = _make_video(db, place, status=STATUS_QUEUED)

    with patch("app.services.video.video_processing_worker.download_to_file"), \
         patch("app.services.video.video_processing_worker.ffmpeg_steps.check_duration_ms",
               return_value=30_000), \
         patch("app.services.video.video_processing_worker.find_best_highlight_window",
               return_value=(5.0, 0.7)), \
         patch("app.services.video.video_processing_worker.ffmpeg_steps.trim_video",
               side_effect=RuntimeError("ffmpeg trim failed")):
        outcome = process_one_video(db, video)

    assert outcome == STATUS_FAILED
    db.refresh(video)
    assert "highlight_trim_failed" in (video.error_message or "")


# ---------------------------------------------------------------------------
# Push notifications on approve/reject (see
# app/services/notifications/expo_push.py). Every scenario patches
# send_push_to_user itself rather than letting it run for real -- these
# tests only need to confirm the worker calls it with the right outcome,
# not exercise the HTTP client (see test_expo_push.py for that).
# ---------------------------------------------------------------------------

def test_approval_sends_a_push_notification(db, place):
    video = _make_video(db, place, status=STATUS_QUEUED)

    with patch("app.services.video.video_processing_worker.download_to_file"), \
         patch("app.services.video.video_processing_worker.ffmpeg_steps.check_duration_ms",
               return_value=5000), \
         patch("app.services.video.video_processing_worker.ffmpeg_steps.compress_video",
               return_value="/tmp/fake-compressed.mp4"), \
         patch("app.services.video.video_processing_worker.score_video",
               return_value=0.9), \
         patch("app.services.video.video_processing_worker.ffmpeg_steps.generate_thumbnail",
               return_value="/tmp/fake-thumb.jpg"), \
         patch("app.services.video.video_processing_worker.upload_file"), \
         patch("app.services.video.video_processing_worker.delete_object"), \
         patch("app.services.video.video_processing_worker.send_push_to_user") as mock_push:
        outcome = process_one_video(db, video)

    assert outcome == STATUS_APPROVED
    mock_push.assert_called_once()
    args, kwargs = mock_push.call_args
    assert args[1] == video.uploaded_by
    assert kwargs["data"]["type"] == "video_approved"


def test_rejection_sends_a_push_notification_with_the_reason(db, place):
    video = _make_video(db, place, status=STATUS_QUEUED)

    with patch("app.services.video.video_processing_worker.download_to_file"), \
         patch("app.services.video.video_processing_worker.ffmpeg_steps.check_duration_ms",
               return_value=999_999), \
         patch("app.services.video.video_processing_worker.delete_object"), \
         patch("app.services.video.video_processing_worker.send_push_to_user") as mock_push:
        outcome = process_one_video(db, video)

    assert outcome == STATUS_REJECTED
    mock_push.assert_called_once()
    args, kwargs = mock_push.call_args
    assert args[1] == video.uploaded_by
    assert kwargs["data"]["type"] == "video_rejected"
    assert kwargs["data"]["reason"] == REJECT_DURATION


def test_a_failed_pipeline_run_does_not_send_a_push_notification(db, place):
    # 'failed' is a setup/config problem (see food_classifier.py's
    # docstring), not a verdict on the video -- the uploader shouldn't be
    # told anything until it's actually resolved one way or the other.
    video = _make_video(db, place, status=STATUS_QUEUED)

    with patch("app.services.video.video_processing_worker.download_to_file",
               side_effect=Exception("connection reset")), \
         patch("app.services.video.video_processing_worker.send_push_to_user") as mock_push:
        outcome = process_one_video(db, video)

    assert outcome == STATUS_FAILED
    mock_push.assert_not_called()


def test_a_broken_notification_step_does_not_break_the_pipeline_outcome(db, place):
    video = _make_video(db, place, status=STATUS_QUEUED)

    with patch("app.services.video.video_processing_worker.download_to_file"), \
         patch("app.services.video.video_processing_worker.ffmpeg_steps.check_duration_ms",
               return_value=5000), \
         patch("app.services.video.video_processing_worker.ffmpeg_steps.compress_video",
               return_value="/tmp/fake-compressed.mp4"), \
         patch("app.services.video.video_processing_worker.score_video",
               return_value=0.9), \
         patch("app.services.video.video_processing_worker.ffmpeg_steps.generate_thumbnail",
               return_value="/tmp/fake-thumb.jpg"), \
         patch("app.services.video.video_processing_worker.upload_file"), \
         patch("app.services.video.video_processing_worker.delete_object"), \
         patch("app.services.video.video_processing_worker.send_push_to_user",
               side_effect=RuntimeError("push provider is down")):
        outcome = process_one_video(db, video)

    assert outcome == STATUS_APPROVED
    db.refresh(video)
    assert video.status == STATUS_APPROVED


def test_download_failure_fails_the_video_not_the_batch(db, place):
    video = _make_video(db, place, status=STATUS_QUEUED)

    with patch("app.services.video.video_processing_worker.download_to_file",
               side_effect=Exception("connection reset")):
        outcome = process_one_video(db, video)

    assert outcome == STATUS_FAILED
    db.refresh(video)
    assert "download_failed" in (video.error_message or "")


# ---------------------------------------------------------------------------
# process_pending_videos -- batch orchestration
# ---------------------------------------------------------------------------

def test_process_pending_videos_keeps_going_after_one_bad_video(db, place):
    good = _make_video(db, place, status=STATUS_QUEUED)
    bad = _make_video(db, place, status=STATUS_QUEUED)

    def fake_download(key, dest):
        if key == bad.orig_key:
            raise RuntimeError("boom")

    with patch("app.services.video.video_processing_worker.download_to_file",
               side_effect=fake_download), \
         patch("app.services.video.video_processing_worker.ffmpeg_steps.check_duration_ms",
               return_value=5000), \
         patch("app.services.video.video_processing_worker.ffmpeg_steps.compress_video",
               return_value="/tmp/fake-compressed.mp4"), \
         patch("app.services.video.video_processing_worker.score_video",
               return_value=0.9), \
         patch("app.services.video.video_processing_worker.ffmpeg_steps.generate_thumbnail",
               return_value="/tmp/fake-thumb.jpg"), \
         patch("app.services.video.video_processing_worker.upload_file"), \
         patch("app.services.video.video_processing_worker.delete_object"):
        result = process_pending_videos(db, limit=10)

    assert result["approved"] == 1
    assert result["failed"] == 1
    db.refresh(good)
    db.refresh(bad)
    assert good.status == STATUS_APPROVED
    assert bad.status == STATUS_FAILED
