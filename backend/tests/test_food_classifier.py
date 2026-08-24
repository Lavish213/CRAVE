"""
Coverage for app.services.video.food_classifier.find_best_highlight_window
-- the sliding-window scorer used by video_processing_worker.py's
auto-highlight step. The TFLite interpreter and ffmpeg frame extraction
are both mocked: there's no real model file or ffmpeg binary output in
this test environment (same approach as test_video_processing_worker.py).
"""
from __future__ import annotations

from unittest.mock import patch

from app.services.video.food_classifier import find_best_highlight_window


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
