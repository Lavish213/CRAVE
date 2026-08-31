"""
Coverage for app.services.video.food_classifier.find_best_highlight_window
-- the sliding-window scorer used by video_processing_worker.py's
auto-highlight step. The TFLite interpreter and ffmpeg frame extraction
are both mocked: there's no real model file or ffmpeg binary output in
this test environment (same approach as test_video_processing_worker.py).
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from app.services.video.food_classifier import (
    FoodClassifierUnavailableError,
    find_best_highlight_window,
    score_image,
)


def _frame_paths(n: int) -> list[str]:
    return [f"/tmp/fake-frames/frame-{i:03d}.jpg" for i in range(n)]


def test_picks_the_highest_average_window():
    # 10 one-second frames; the best 3-second window is frames [6,7,8]
    # (0.9, 0.95, 0.9) averaging higher than any other run of three.
    scores = [0.1, 0.1, 0.2, 0.1, 0.3, 0.2, 0.9, 0.95, 0.9, 0.2]
    frames = _frame_paths(len(scores))

    with patch("app.services.video.food_classifier._load_interpreter", return_value="fake-interp"), \
         patch("app.services.video.food_classifier.ffmpeg_steps.extract_sample_frames",
               return_value=frames), \
         patch("app.services.video.food_classifier._score_frame",
               side_effect=lambda interp, path: scores[frames.index(path)]), \
         patch("app.services.video.food_classifier.shutil.rmtree"):
        start_sec, avg_score = find_best_highlight_window("/tmp/fake-source.mp4", window_sec=3)

    assert start_sec == 6.0
    assert avg_score == (0.9 + 0.95 + 0.9) / 3


def test_window_at_least_as_long_as_the_clip_scores_the_whole_thing():
    scores = [0.4, 0.6, 0.5]
    frames = _frame_paths(len(scores))

    with patch("app.services.video.food_classifier._load_interpreter", return_value="fake-interp"), \
         patch("app.services.video.food_classifier.ffmpeg_steps.extract_sample_frames",
               return_value=frames), \
         patch("app.services.video.food_classifier._score_frame",
               side_effect=lambda interp, path: scores[frames.index(path)]), \
         patch("app.services.video.food_classifier.shutil.rmtree"):
        start_sec, avg_score = find_best_highlight_window("/tmp/fake-source.mp4", window_sec=10)

    assert start_sec == 0.0
    assert avg_score == sum(scores) / len(scores)


def test_ties_prefer_the_earliest_window():
    scores = [0.5, 0.5, 0.1, 0.5, 0.5]
    frames = _frame_paths(len(scores))

    with patch("app.services.video.food_classifier._load_interpreter", return_value="fake-interp"), \
         patch("app.services.video.food_classifier.ffmpeg_steps.extract_sample_frames",
               return_value=frames), \
         patch("app.services.video.food_classifier._score_frame",
               side_effect=lambda interp, path: scores[frames.index(path)]), \
         patch("app.services.video.food_classifier.shutil.rmtree"):
        start_sec, _avg_score = find_best_highlight_window("/tmp/fake-source.mp4", window_sec=2)

    assert start_sec == 0.0


def test_score_image_scores_a_single_local_image_with_no_frame_extraction():
    """The image-holdout experiment
    (docs/IMAGE_CLASSIFICATION_HOLDOUT_DESIGN_2026-08-31.md) needs to score
    already-downloaded place-photo thumbnails, not video frames -- confirms
    score_image() reuses the same model/scorer without touching ffmpeg or
    any temp-directory cleanup, since the caller owns the image's lifecycle."""
    with patch("app.services.video.food_classifier._load_interpreter", return_value="fake-interp") as mock_load, \
         patch("app.services.video.food_classifier._score_frame", return_value=0.73) as mock_score, \
         patch("app.services.video.food_classifier.ffmpeg_steps.extract_sample_frames") as mock_ffmpeg, \
         patch("app.services.video.food_classifier.shutil.rmtree") as mock_rmtree:
        result = score_image("/tmp/place-photo-thumb.jpg")

    assert result == 0.73
    mock_load.assert_called_once()
    mock_score.assert_called_once_with("fake-interp", "/tmp/place-photo-thumb.jpg")
    mock_ffmpeg.assert_not_called()
    mock_rmtree.assert_not_called()


def test_score_image_propagates_unavailable_error_without_masking_it_as_not_food():
    """Same caller contract as score_video(): a missing/unset-up classifier
    must surface as FoodClassifierUnavailableError, not get treated as a
    low food-confidence score for the image."""
    with patch(
        "app.services.video.food_classifier._load_interpreter",
        side_effect=FoodClassifierUnavailableError("model file missing"),
    ):
        with pytest.raises(FoodClassifierUnavailableError):
            score_image("/tmp/place-photo-thumb.jpg")
