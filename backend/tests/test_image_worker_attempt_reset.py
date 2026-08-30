from unittest.mock import MagicMock
import uuid

import pytest

from app.db.models.city import City
from app.db.models.place import Place
from app.db.session import SessionLocal
from app.workers.image_worker import ImageWorker


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.mark.parametrize(
    ("attempts", "blocked", "force_refresh"),
    [
        (2, False, False),
        (3, True, True),
    ],
)
def test_successful_ingestion_clears_failure_state(
    db,
    attempts,
    blocked,
    force_refresh,
):
    suffix = uuid.uuid4().hex[:8]
    city = City(slug=f"image-reset-{suffix}", name=f"Image Reset {suffix}")
    db.add(city)
    db.flush()
    place = Place(
        name=f"Recovered {suffix}",
        city_id=city.id,
        is_active=True,
    )
    place.image_fetch_attempts = attempts
    place.image_blocked = blocked
    db.add(place)
    db.commit()

    try:
        ingest_service = MagicMock()
        ingest_service.ingest_place_images.return_value = [MagicMock()]
        worker = ImageWorker(
            ingest_service=ingest_service,
            invariant_service=MagicMock(),
        )

        result = worker.run(
            db=db,
            limit=1,
            place_ids=[place.id],
            force_refresh=force_refresh,
        )

        db.refresh(place)
        assert result["images_written"] == 1
        assert place.image_fetch_attempts == 0
        assert place.image_blocked is False
    finally:
        db.delete(place)
        db.delete(city)
        db.commit()
