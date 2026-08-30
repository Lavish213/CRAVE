from types import SimpleNamespace
from unittest.mock import MagicMock

from app.services.images.image_reader import ImageReader


def _reader(*, provider_images, website_images, google_images):
    google = MagicMock()
    google.fetch.return_value = google_images
    provider = MagicMock()
    provider.extract.return_value = provider_images
    website = MagicMock()
    website.extract.return_value = website_images
    return ImageReader(
        google_fetcher=google,
        provider_extractor=provider,
        website_extractor=website,
    ), google


def _candidate(index):
    return {"url": f"https://images.example.test/{index}.jpg", "source": "website"}


def test_reader_skips_paid_google_when_free_sources_fill_gallery():
    reader, google = _reader(
        provider_images=[_candidate(1)],
        website_images=[_candidate(2), _candidate(3)],
        google_images=[_candidate(4)],
    )

    images = reader.read(place=SimpleNamespace(id="p1"), db=MagicMock())

    assert len(images) == 3
    google.fetch.assert_not_called()


def test_reader_uses_google_as_fallback_when_free_sources_are_insufficient():
    reader, google = _reader(
        provider_images=[_candidate(1)],
        website_images=[],
        google_images=[_candidate(2), _candidate(3)],
    )

    images = reader.read(place=SimpleNamespace(id="p1"), db=MagicMock())

    assert len(images) == 3
    google.fetch.assert_called_once()


def test_invalid_or_duplicate_free_candidates_do_not_suppress_google_fallback():
    duplicate = _candidate(1)
    reader, google = _reader(
        provider_images=[duplicate, duplicate],
        website_images=[{"url": "javascript:alert(1)", "source": "website"}],
        google_images=[_candidate(2)],
    )

    reader.read(place=SimpleNamespace(id="p1"), db=MagicMock())

    google.fetch.assert_called_once()
