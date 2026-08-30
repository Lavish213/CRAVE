from types import SimpleNamespace

from app.services.images.image_ingest_service import ImageIngestService


def _image(*, primary=False):
    return SimpleNamespace(is_primary=primary)


def test_partial_gallery_is_not_treated_as_complete():
    service = ImageIngestService()

    assert service._has_complete_gallery(
        SimpleNamespace(images=[_image(primary=True)])
    ) is False
    assert service._has_complete_gallery(
        SimpleNamespace(images=[_image(), _image()])
    ) is False


def test_gallery_requires_minimum_count_and_primary_to_skip_ingestion():
    service = ImageIngestService()

    assert service._has_complete_gallery(
        SimpleNamespace(images=[_image(), _image(), _image()])
    ) is False
    assert service._has_complete_gallery(
        SimpleNamespace(images=[_image(primary=True), _image(), _image()])
    ) is True
