"""
app/services/video/food_classifier.py

Scores a video clip 0-1 on "does this actually show food" by sampling
frames (see ffmpeg_steps.extract_sample_frames) and running each through
a MobileNetV2-FoodClassifier TFLite model.

Ported from a Node.js reference scaffold that had to shell out to a
separate Python subprocess to reach a TFLite runtime at all -- since this
backend already IS Python, that whole subprocess bridge is unnecessary
complexity this version doesn't have: the interpreter is just called
directly, in-process.

Setup (deliberately NOT a hard dependency of this app -- see
requirements.txt's own comment on why bundling a heavy ML runtime here is
risky for Railway's build until it's actually needed):
  1. pip install tflite-runtime  (preferred, much smaller) OR tensorflow
  2. Download/convert MobileNetV2-FoodClassifier per its own README:
     https://github.com/Pramit726/MobileNetV2-FoodClassifier
  3. Place the resulting file at app/services/video/food_classifier.tflite

Until both of those are done, score_video() raises
FoodClassifierUnavailableError -- the worker treats that as a pipeline
failure (status='failed', needs attention) rather than a content
rejection (status='rejected'), so videos aren't silently rejected for a
reason that has nothing to do with their actual content.
"""
from __future__ import annotations

import os
import shutil
from typing import List, Optional

import numpy as np
from PIL import Image

from app.services.video import ffmpeg_steps

MODEL_PATH = os.path.join(os.path.dirname(__file__), "food_classifier.tflite")
LABELS_PATH = os.path.join(os.path.dirname(__file__), "labels.txt")
INPUT_SIZE = (224, 224)  # MobileNetV2 standard input


class FoodClassifierUnavailableError(Exception):
    """
    The classifier isn't set up yet (missing tflite-runtime/tensorflow, or
    missing the .tflite model file) -- a deployment/setup problem, not a
    verdict on any particular video's content.
    """


def _load_tflite_module():
    try:
        import tflite_runtime.interpreter as tflite  # type: ignore
        return tflite
    except ImportError:
        pass
    try:
        import tensorflow as tf  # type: ignore
        return tf.lite
    except ImportError as exc:
        raise FoodClassifierUnavailableError(
            "Neither tflite-runtime nor tensorflow is installed. Run "
            "`pip install tflite-runtime` (preferred) or `pip install "
            "tensorflow`, then see this module's docstring for the model "
            "file setup step."
        ) from exc


def _load_interpreter():
    tflite = _load_tflite_module()

    if not os.path.exists(MODEL_PATH):
        raise FoodClassifierUnavailableError(
            f"Food classifier model not found at {MODEL_PATH}. See this "
            f"module's docstring for setup instructions -- every video "
            f"will fail to score until this is resolved."
        )

    interpreter = tflite.Interpreter(model_path=MODEL_PATH)
    interpreter.allocate_tensors()
    return interpreter


def _load_labels() -> Optional[List[str]]:
    if not os.path.exists(LABELS_PATH):
        return None
    with open(LABELS_PATH) as f:
        return [line.strip() for line in f if line.strip()]


def _preprocess(image_path: str) -> np.ndarray:
    img = Image.open(image_path).convert("RGB").resize(INPUT_SIZE)
    arr = np.asarray(img, dtype=np.float32)
    arr = (arr / 127.5) - 1.0  # MobileNetV2's standard [-1, 1] normalization
    return np.expand_dims(arr, axis=0)


def _score_frame(interpreter, image_path: str) -> float:
    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()

    input_data = _preprocess(image_path)
    interpreter.set_tensor(input_details[0]["index"], input_data)
    interpreter.invoke()
    output = interpreter.get_tensor(output_details[0]["index"])[0]

    # Every class in this model's label set is a food category (Food-101-
    # derived) -- there's no explicit "not food" class, so the top class
    # probability itself IS used as the food-confidence signal: low
    # max-probability means the model isn't confident this frame matches
    # ANY food category well, which in practice correlates with "this
    # frame doesn't clearly show food" (a face, a table, motion blur)
    # even though that's an indirect proxy, not a direct food/not-food
    # decision boundary. If a future model version adds an explicit
    # non-food/background class, change this to (1 - that class's
    # probability) instead.
    return float(np.max(output))


def find_best_highlight_window(video_path: str, window_sec: float) -> tuple[float, float]:
    """
    Scores every ~1s sampled frame across the whole clip (same frames
    score_video() would use) and returns (start_second, avg_score) for
    the highest-average-scoring contiguous window of length window_sec.

    Used by video_processing_worker.py's auto-highlight step: a source
    clip longer than settings.video_max_duration_ms but still within
    settings.video_highlight_max_source_duration_ms gets trimmed to this
    window (via ffmpeg_steps.trim_video) instead of being hard-rejected
    for its length. Raises FoodClassifierUnavailableError under the same
    conditions as score_video().
    """
    interpreter = _load_interpreter()  # raises early, before spending time on ffmpeg

    frames = ffmpeg_steps.extract_sample_frames(video_path)
    if not frames:
        raise RuntimeError("No frames extracted for highlight scoring")

    frame_dir = os.path.dirname(frames[0])
    try:
        scores = [_score_frame(interpreter, p) for p in frames]
    finally:
        shutil.rmtree(frame_dir, ignore_errors=True)

    window_frames = max(1, round(window_sec / ffmpeg_steps.FRAME_SAMPLE_INTERVAL_SEC))
    if window_frames >= len(scores):
        # Clip isn't meaningfully longer than the target window -- the
        # whole thing already fits it.
        return 0.0, sum(scores) / len(scores)

    window_sum = sum(scores[:window_frames])
    best_avg = window_sum / window_frames
    best_start_idx = 0
    for i in range(1, len(scores) - window_frames + 1):
        window_sum += scores[i + window_frames - 1] - scores[i - 1]
        avg = window_sum / window_frames
        if avg > best_avg:
            best_avg = avg
            best_start_idx = i

    best_start_sec = best_start_idx * ffmpeg_steps.FRAME_SAMPLE_INTERVAL_SEC
    return float(best_start_sec), best_avg


def score_video(video_path: str) -> float:
    """
    Samples frames from video_path (see ffmpeg_steps.extract_sample_frames)
    and returns the average food-confidence score across them, 0-1.
    Raises FoodClassifierUnavailableError if the classifier itself isn't
    set up (see module docstring) -- callers must not treat that as a
    content rejection.
    """
    interpreter = _load_interpreter()  # raises early, before spending time on ffmpeg
    _labels = _load_labels()  # unused by _score_frame today -- see its own comment

    frames = ffmpeg_steps.extract_sample_frames(video_path)
    if not frames:
        raise RuntimeError("No frames extracted for food scoring")

    frame_dir = os.path.dirname(frames[0])
    try:
        scores = [_score_frame(interpreter, p) for p in frames]
        return sum(scores) / len(scores)
    finally:
        shutil.rmtree(frame_dir, ignore_errors=True)
