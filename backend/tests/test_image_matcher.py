from types import SimpleNamespace

import pytest

from app.services.images.image_matcher import ImageMatcher


@pytest.mark.parametrize(
    "reference",
    [
        "places/ChIJ_abc-123/photos/AW_Xyz-789",
        "places/place_123/photos/photo-456",
    ],
)
def test_matcher_accepts_google_place_photo_resource_names(reference):
    matched = ImageMatcher().match(
        place=SimpleNamespace(id="place-id"),
        candidates=[{"url": reference, "source": "google_places"}],
    )

    assert [candidate["url"] for candidate in matched] == [reference]


@pytest.mark.parametrize(
    "reference",
    [
        "places/abc/photos",
        "places/abc/photos/../../secret",
        "places/abc/other/photo",
        "javascript:alert(1)",
        "//example.com/image.jpg",
    ],
)
def test_matcher_rejects_malformed_or_unsafe_resource_names(reference):
    matched = ImageMatcher().match(
        place=SimpleNamespace(id="place-id"),
        candidates=[{"url": reference, "source": "google_places"}],
    )

    assert matched == []
