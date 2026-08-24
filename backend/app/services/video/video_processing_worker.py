"""
app/services/video/video_processing_worker.py

Batch-picks-up-pending-rows worker for the video upload pipeline, in the
same style as app/workers/image_worker.py and the other scheduler-driven
workers in this app -- NOT a message queue (no Redis/BullMQ, unlike the
Node.js reference scaffold this was ported from). That choice matters for
more than just consistency: because a "queued" video is a row this
worker's own SELECT will always find again on its next tick, there is no
separate queue state that can go stale the way a message-broker job can.
The Node scaffold's orphan sweep had a real bug because of exactly that --
it swept (and destructively deleted) any row still "processing" past a
fixed age, with no way to tell "client never uploaded" apart from "worker
box has been down for 40 minutes, the job is still perfectly valid." This
version doesn't need that distinction: a stale 'processing' row (crash
mid-item) is simply re-claimed by _select_batch below and retried, no
sweep required. The only rows that genuinely need sweeping are 'pending'
ones nothing ever confirmed -- see reject_abandoned_pending_uploads.
"""
from __future__ import annotations

import logging
import os
import shutil
import tempfile
from datetime import datetime, timedelta, timezone
from typing import List

from sqlalchemy.orm import Session

from app.config.settings import settings
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
from app.services.upload.key_builder import build_video_processed_key, build_video_thumb_key
from app.services.upload.r2_client import delete_object, download_to_file, upload_file
from app.services.video import ffmpeg_steps
from app.services.video.ffmpeg_steps import VideoCorruptError
from app.services.video.food_classifier import (
    score_video,
    find_best_highlight_window,
    FoodClassifierUnavailableError,
)

logger = logging.getLogger(__name__)

DEFAULT_BATCH_LIMIT = 20


def reject_abandoned_pending_uploads(db: Session) -> int:
    """
    A 'pending' row (upload slot created) that nobody ever confirmed --
    client crashed, cancelled, or lost its connection before the PUT
    finished -- is never revisited by anything else in the system (the
    processing batch below only ever selects 'queued'/'processing').
    Reject anything still 'pending' past settings.video_orphan_pending_minutes.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=settings.video_orphan_pending_minutes)
    rows = (
        db.query(PlaceVideo)
        .filter(PlaceVideo.status == STATUS_PENDING, PlaceVideo.created_at < cutoff)
        .all()
    )
    for row in rows:
        if row.orig_key:
            # Best-effort -- a client that never finished the PUT means
            # there's often no object to delete, and that's fine.
            try:
                delete_object(row.orig_key)
            except Exception:
                pass
        row.status = STATUS_REJECTED
        row.reject_reason = REJECT_ABANDONED_UPLOAD
    if rows:
        db.commit()
    return len(rows)


def _select_batch(db: Session, limit: int) -> List[PlaceVideo]:
    stale_cutoff = datetime.now(timezone.utc) - timedelta(
        minutes=settings.video_stale_processing_minutes
    )
    return (
        db.query(PlaceVideo)
        .filter(
            (PlaceVideo.status == STATUS_QUEUED)
            | (
                (PlaceVideo.status == STATUS_PROCESSING)
                & (PlaceVideo.updated_at < stale_cutoff)
            )
        )
        .order_by(PlaceVideo.created_at.asc())
        .limit(limit)
        .all()
    )


def _reject(db: Session, video: PlaceVideo, reason: str, *, duration_ms: int | None = None, food_score: float | None = None) -> None:
    if video.orig_key:
        try:
            delete_object(video.orig_key)
        except Exception:
            logger.exception("video_cleanup_failed video_id=%s", video.id)
    video.status = STATUS_REJECTED
    video.reject_reason = reason
    if duration_ms is not None:
        video.duration_ms = duration_ms
    if food_score is not None:
        video.food_score = food_score
    db.commit()


def _fail(db: Session, video: PlaceVideo, message: str) -> None:
    video.status = STATUS_FAILED
    video.error_message = message[:500]
    db.commit()


def process_one_video(db: Session, video: PlaceVideo) -> str:
    """
    Runs the full pipeline for one already-batch-selected video. Returns
    the resulting status string. Every exit path (approve/reject/fail)
    commits before returning -- there is no path back to the caller that
    leaves the row uncommitted.
    """
    video.status = STATUS_PROCESSING
    db.commit()

    workdir = tempfile.mkdtemp(prefix=f"crave-video-{video.id}-")
    orig_ext = os.path.splitext(video.orig_key or "")[1] or ".mp4"
    local_orig = os.path.join(workdir, f"orig{orig_ext}")

    try:
        try:
            download_to_file(video.orig_key, local_orig)
        except Exception as exc:
            _fail(db, video, f"download_failed: {exc}")
            return STATUS_FAILED

        try:
            duration_ms = ffmpeg_steps.check_duration_ms(local_orig)
        except VideoCorruptError:
            _reject(db, video, REJECT_CORRUPT)
            return STATUS_REJECTED

        if (
            duration_ms < settings.video_min_duration_ms
            or duration_ms > settings.video_highlight_max_source_duration_ms
        ):
            _reject(db, video, REJECT_DURATION, duration_ms=duration_ms)
            return STATUS_REJECTED

        working_path = local_orig
        if duration_ms > settings.video_max_duration_ms:
            # Too long for the feed's target window, but within the
            # highlight ceiling -- find the best-scoring
            # video_max_duration_ms-length window instead of throwing away
            # the whole upload (see find_best_highlight_window's
            # docstring).
            window_sec = settings.video_max_duration_ms / 1000
            try:
                start_sec, _window_score = find_best_highlight_window(local_orig, window_sec)
            except FoodClassifierUnavailableError as exc:
                _fail(db, video, f"food_classifier_unavailable: {exc}")
                return STATUS_FAILED
            except Exception as exc:
                _fail(db, video, f"highlight_scoring_failed: {exc}")
                return STATUS_FAILED

            try:
                working_path = ffmpeg_steps.trim_video(local_orig, start_sec, window_sec)
            except Exception as exc:
                _fail(db, video, f"highlight_trim_failed: {exc}")
                return STATUS_FAILED

            try:
                duration_ms = ffmpeg_steps.check_duration_ms(working_path)
            except VideoCorruptError as exc:
                _fail(db, video, f"highlight_trim_produced_corrupt_output: {exc}")
                return STATUS_FAILED

        try:
            compressed_path = ffmpeg_steps.compress_video(working_path)
        except Exception as exc:
            _fail(db, video, f"compression_failed: {exc}")
            return STATUS_FAILED

        try:
            food_score = score_video(compressed_path)
        except FoodClassifierUnavailableError as exc:
            # Config/setup problem, not a verdict on this video's content
            # -- see food_classifier.py's docstring. Leaving this as
            # 'failed' (not 'rejected') means it's still picked up and
            # retried by a later run once the classifier is actually set
            # up, exactly like any other stale-'processing' recovery.
            _fail(db, video, f"food_classifier_unavailable: {exc}")
            return STATUS_FAILED
        except Exception as exc:
            _fail(db, video, f"food_scoring_failed: {exc}")
            return STATUS_FAILED

        if food_score < settings.video_food_score_threshold:
            _reject(db, video, REJECT_FOOD_SCORE, duration_ms=duration_ms, food_score=food_score)
            return STATUS_REJECTED

        try:
            thumbnail_path = ffmpeg_steps.generate_thumbnail(compressed_path)
        except Exception as exc:
            _fail(db, video, f"thumbnail_failed: {exc}")
            return STATUS_FAILED

        processed_key = build_video_processed_key(video.place_id, video.id)
        thumb_key = build_video_thumb_key(video.place_id, video.id)

        try:
            # Processed output is immutable once written -- a given video
            # never gets recompressed -- so a long Cache-Control lets a
            # fronting CDN and client players cache it hard.
            upload_file(
                key=processed_key, local_path=compressed_path,
                content_type="video/mp4",
                cache_control="public, max-age=31536000, immutable",
            )
            upload_file(
                key=thumb_key, local_path=thumbnail_path,
                content_type="image/jpeg",
                cache_control="public, max-age=31536000, immutable",
            )
        except Exception as exc:
            _fail(db, video, f"upload_failed: {exc}")
            return STATUS_FAILED

        # The original uploads/... object is only useful during
        # processing -- leaving it in place after a successful compress
        # doubles storage cost for every video, forever, for a copy
        # nothing ever reads again.
        try:
            delete_object(video.orig_key)
        except Exception:
            logger.exception("video_orig_cleanup_failed video_id=%s", video.id)

        video.status = STATUS_APPROVED
        video.duration_ms = duration_ms
        video.food_score = food_score
        video.processed_key = processed_key
        video.thumb_key = thumb_key
        db.commit()
        return STATUS_APPROVED
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def process_pending_videos(db: Session, limit: int = DEFAULT_BATCH_LIMIT) -> dict:
    abandoned = reject_abandoned_pending_uploads(db)

    batch = _select_batch(db, limit)
    counts = {"approved": 0, "rejected": 0, "failed": 0}
    for video in batch:
        try:
            outcome = process_one_video(db, video)
        except Exception as exc:
            logger.exception("video_processing_unhandled_error video_id=%s", video.id)
            try:
                _fail(db, video, f"unhandled_error: {exc}")
            except Exception:
                db.rollback()
            outcome = STATUS_FAILED
        counts[outcome] = counts.get(outcome, 0) + 1

    return {
        "abandoned_pending_rejected": abandoned,
        "batch_size": len(batch),
        **counts,
    }
