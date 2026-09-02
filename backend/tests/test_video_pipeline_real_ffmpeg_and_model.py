"""
End-to-end coverage for the real video-processing chain: real ffmpeg
(ffprobe duration, compression, frame extraction) piped into the real
TFLite food classifier -- score_video() -- on genuine video files, not
mocked ffmpeg output or a single static image.

Every other test in this area (test_video_processing_worker.py,
test_food_classifier.py) mocks ffmpeg entirely or scores a single frame
directly; test_food_classifier_real_model.py exercises the real model but
only against static images, never through real frame extraction from an
actual video container. This was the exact gap called out in
CRAVE_STATUS.md's backlog: "no real video was queued during the [scheduler]
canary, so real R2 transfer/ffmpeg encoding/classifier quality is still
unverified." R2 transfer still needs production access to test, but the
ffmpeg+classifier portion needs neither a device nor production -- it's
server-side backend logic, testable anywhere ffmpeg and the TFLite runtime
are installed (this suite, and production).

Skips cleanly (not a failure) wherever ffmpeg isn't installed -- CI's
runner doesn't currently have it, matching the existing skip pattern this
file borrows from test_food_classifier_real_model.py for a missing TFLite
runtime.
"""
from __future__ import annotations

import os
import shutil
import subprocess

import pytest

from app.config.settings import settings
from app.services.video import ffmpeg_steps
from app.services.video.food_classifier import (
    FoodClassifierUnavailableError,
    _load_interpreter,
    score_video,
)

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "video")
FOOD_IMAGE = os.path.join(FIXTURES_DIR, "sample_food.jpg")
NOT_FOOD_IMAGE = os.path.join(FIXTURES_DIR, "sample_not_food.jpg")


def _skip_if_unavailable():
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("ffmpeg/ffprobe not installed in this environment")
    try:
        _load_interpreter()
    except FoodClassifierUnavailableError as exc:
        pytest.skip(f"no TFLite runtime installed: {exc}")


def _build_video_from_image(image_path: str, out_path: str, *, seconds: int = 3) -> str:
    """A real, valid H.264 mp4 built from a real still image -- genuine
    ffmpeg container/codec output for check_duration_ms/compress_video/
    extract_sample_frames to operate on, not a hand-rolled fake file."""
    result = subprocess.run(
        [
            "ffmpeg", "-y",
            "-loop", "1", "-i", image_path,
            "-c:v", "libx264", "-t", str(seconds),
            "-pix_fmt", "yuv420p",
            "-vf", "scale=640:640",
            out_path,
        ],
        capture_output=True, timeout=30, check=False,
    )
    assert result.returncode == 0, result.stderr.decode(errors="replace")[:500]
    return out_path


@pytest.fixture()
def food_video(tmp_path):
    _skip_if_unavailable()
    return _build_video_from_image(FOOD_IMAGE, str(tmp_path / "food.mp4"))


@pytest.fixture()
def not_food_video(tmp_path):
    _skip_if_unavailable()
    return _build_video_from_image(NOT_FOOD_IMAGE, str(tmp_path / "not_food.mp4"))


def test_real_pipeline_scores_a_real_food_video_above_threshold(food_video):
    duration_ms = ffmpeg_steps.check_duration_ms(food_video)
    assert duration_ms > 0

    compressed = ffmpeg_steps.compress_video(food_video)
    score = score_video(compressed)

    assert 0.0 <= score <= 1.0
    assert score >= settings.video_food_score_threshold


def test_real_pipeline_scores_a_real_non_food_video_below_threshold(not_food_video):
    duration_ms = ffmpeg_steps.check_duration_ms(not_food_video)
    assert duration_ms > 0

    compressed = ffmpeg_steps.compress_video(not_food_video)
    score = score_video(compressed)

    assert 0.0 <= score <= 1.0
    assert score < settings.video_food_score_threshold
