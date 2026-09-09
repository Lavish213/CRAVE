from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.api.v1.routes.contributions import ContributionCreate


def _payload(**overrides):
    data = {
        "client_id": "draft-1",
        "place_id": "place-1",
        "intent": "private_log",
        "reaction": "good",
        "caption": "Dinner",
        "visibility": "private",
    }
    data.update(overrides)
    return data


def test_private_log_can_commit_without_media() -> None:
    parsed = ContributionCreate(**_payload())
    assert parsed.intent == "private_log"
    assert parsed.image_id is None
    assert parsed.video_id is None


def test_private_log_cannot_escape_private_visibility() -> None:
    with pytest.raises(ValidationError):
        ContributionCreate(**_payload(visibility="public"))


def test_social_post_requires_media_and_explicit_social_audience() -> None:
    with pytest.raises(ValidationError):
        ContributionCreate(**_payload(intent="social_post", visibility="public"))
    with pytest.raises(ValidationError):
        ContributionCreate(**_payload(intent="social_post", visibility="private", image_id="image-1"))

    parsed = ContributionCreate(
        **_payload(intent="social_post", visibility="connections", image_id="image-1")
    )
    assert parsed.visibility == "connections"


def test_contribution_rejects_two_media_assets() -> None:
    with pytest.raises(ValidationError):
        ContributionCreate(
            **_payload(intent="social_post", visibility="public", image_id="image-1", video_id="video-1")
        )


def test_occurred_at_requires_timezone_and_cannot_be_future() -> None:
    with pytest.raises(ValidationError):
        ContributionCreate(**_payload(occurred_at=datetime.now()))
    with pytest.raises(ValidationError):
        ContributionCreate(**_payload(occurred_at=datetime.now(timezone.utc) + timedelta(minutes=1)))

    occurred = datetime.now(timezone.utc) - timedelta(days=2)
    parsed = ContributionCreate(**_payload(occurred_at=occurred))
    assert parsed.occurred_at == occurred


def test_reaction_vocabulary_is_closed() -> None:
    with pytest.raises(ValidationError):
        ContributionCreate(**_payload(reaction="five_stars"))
