"""
Exercises the REAL food_classifier.tflite model (committed at
app/services/video/food_classifier.tflite) against real fixture images --
unlike test_food_classifier.py and test_video_processing_worker.py, which
mock the classifier entirely. This is the only test in the suite that
would catch the model file itself going missing/corrupt, the runtime
failing to load it, or the real per-frame scoring code (_score_frame's
preprocessing, not the sliding-window logic already covered elsewhere)
producing nonsense output.

Fixtures (tests/fixtures/video/) are real photos, not synthetic images --
sample_food.jpg is a crop from the model's own training-data preview
(a bowl of chili, from the MobileNetV2-FoodClassifier repo's
Data_preprocessing.ipynb), sample_not_food.jpg is a real dog photo
(pytorch/hub's own demo image, used unrelated to any food classifier).

The exact score values are NOT asserted -- JPEG re-compression and PIL's
resize can shift them slightly run to run/across Pillow versions, and
that's not what this test is protecting against. It only asserts the
real gap this session found by hand: real food scores meaningfully
higher than real non-food. See food_classifier.py's module docstring for
why this gap is a coarse signal, not a guarantee.
"""
from __future__ import annotations

import os

from app.services.video.food_classifier import (
    FoodClassifierUnavailableError,
    _load_interpreter,
    _score_frame,
    MODEL_PATH,
    LABELS_PATH,
)

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "video")
FOOD_IMAGE = os.path.join(FIXTURES_DIR, "sample_food.jpg")
NOT_FOOD_IMAGE = os.path.join(FIXTURES_DIR, "sample_not_food.jpg")


def test_model_file_is_present():
    # The whole point of committing this file (see food_classifier.py's
    # module docstring) is that scoring works out of the box, with no
    # separate download/setup step -- this catches it going missing.
    assert os.path.exists(MODEL_PATH)


def test_labels_file_matches_the_models_82_classes():
    assert os.path.exists(LABELS_PATH)
    with open(LABELS_PATH) as f:
        labels = [line.strip() for line in f if line.strip()]
    assert len(labels) == 82
    assert labels == sorted(labels)  # matches Keras's alphabetical class_names order


def test_real_food_photo_scores_meaningfully_higher_than_real_non_food():
    try:
        interpreter = _load_interpreter()
    except FoodClassifierUnavailableError as exc:
        # Only reachable if ai-edge-litert/tflite-runtime/tensorflow
        # genuinely isn't installed in whatever environment runs this --
        # the model file itself is always present (see the test above).
        import pytest
        pytest.skip(f"no TFLite runtime installed: {exc}")

    food_score = _score_frame(interpreter, FOOD_IMAGE)
    not_food_score = _score_frame(interpreter, NOT_FOOD_IMAGE)

    assert 0.0 <= food_score <= 1.0
    assert 0.0 <= not_food_score <= 1.0
    # The real gap found this session: food ~0.97-1.0, non-food ~0.45-0.6.
    # A wide margin, not a tight bound, so small preprocessing differences
    # across Pillow/runtime versions don't make this test flaky.
    assert food_score > 0.85
    assert not_food_score < 0.7
    assert food_score - not_food_score > 0.25
