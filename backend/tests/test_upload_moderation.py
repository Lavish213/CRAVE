"""
Coverage for the upload screening pipeline:
  app/services/images/quality_analyzer.py
  app/services/images/exif_reader.py
  app/services/images/upload_moderation.py

Before this existed a user upload went straight to status="ready" and was
immediately eligible to be a place's primary image, with no safety check,
no quality floor, and is_approved hardcoded True at upload with nothing
anywhere ever setting it False.

The measurement ordering is the subtle part and is pinned here explicitly:
app/utils/image_pipeline.py sharpens and then strips EXIF, so a blur score
taken after processing would be grading our own sharpening filter, and a
GPS read taken after processing would find nothing at all.
"""
from __future__ import annotations

import io
import random
import uuid

import pytest
from PIL import Image, ImageDraw, ImageFilter

from app.db.session import SessionLocal
from app.db.models.city import City
from app.db.models.place import Place
from app.db.models.place_image import PlaceImage
from app.services.images import upload_moderation as mod
from app.services.images.exif_reader import (
    ExifReport,
    gps_matches_place,
    meters_between,
    read_exif,
)
from app.services.images.quality_analyzer import (
    BLUR_REJECT_BELOW,
    MIN_DIMENSION,
    analyze_image,
)
from app.services.images.safety_scanner import SafetyReport, UNSCANNED
from app.utils.image_pipeline import process_image


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _detailed(size=900, color=(190, 120, 60)) -> Image.Image:
    """A photo-like image with genuine high-frequency detail."""
    img = Image.new("RGB", (size, size), color=color)
    draw = ImageDraw.Draw(img)
    rng = random.Random(99)
    for i in range(0, size, max(8, size // 50)):
        draw.line([(i, 0), (i, size)], fill=(15, 15, 15), width=3)
    for _ in range(120):
        x, y = rng.randint(0, size - 60), rng.randint(0, size - 60)
        draw.rectangle([x, y, x + rng.randint(10, 50), y + rng.randint(10, 50)],
                       outline=(245, 245, 245), width=2)
    return img


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def place(db):
    suffix = uuid.uuid4().hex[:8]
    city = City(slug=f"moderation-test-{suffix}", name=f"Moderation City {suffix}",
                lat=37.7749, lng=-122.4194)
    db.add(city)
    db.flush()
    p = Place(name=f"Moderation Place {suffix}", city_id=city.id,
              lat=37.7749, lng=-122.4194)
    db.add(p)
    db.commit()

    yield p

    db.query(PlaceImage).filter(PlaceImage.place_id == p.id).delete()
    db.query(Place).filter(Place.id == p.id).delete()
    db.query(City).filter(City.id == city.id).delete()
    db.commit()


def _image_row(db, place, uploaded_by="mod-test-user") -> PlaceImage:
    row = PlaceImage(place_id=place.id, uploaded_by=uploaded_by)
    db.add(row)
    db.commit()
    return row


# ---------------------------------------------------------------------------
# Quality analysis
# ---------------------------------------------------------------------------

def test_sharp_detailed_photo_is_acceptable():
    report = analyze_image(_detailed())
    assert report.acceptable
    assert report.rejection_reason is None
    assert report.blur_score > BLUR_REJECT_BELOW
    assert 0.0 <= report.quality_score <= 1.0


def test_heavily_blurred_photo_is_rejected():
    blurred = _detailed().filter(ImageFilter.GaussianBlur(12))
    report = analyze_image(blurred)
    assert not report.acceptable
    assert report.rejection_reason == "too_blurry"


def test_sharper_photo_scores_higher_than_blurred_one():
    sharp = analyze_image(_detailed())
    soft = analyze_image(_detailed().filter(ImageFilter.GaussianBlur(3)))
    assert sharp.blur_score > soft.blur_score
    assert sharp.quality_score > soft.quality_score


def test_undersized_photo_is_rejected():
    small = _detailed(size=MIN_DIMENSION - 50)
    assert analyze_image(small).rejection_reason == "too_small"


def test_near_black_photo_is_rejected_as_dark_not_blurry():
    """A black frame has no edge detail either, so a blur-first check would
    mislabel it — exposure is the more useful diagnosis in the queue."""
    assert analyze_image(Image.new("RGB", (900, 900), (4, 4, 4))).rejection_reason == "too_dark"


def test_blown_out_photo_is_rejected():
    # Near-white with only faint structure — a real blown-out frame. Uses
    # light-on-light detail deliberately: _detailed()'s dark lines would
    # pull the mean back down into an acceptable range and stop testing
    # exposure at all.
    img = Image.new("RGB", (900, 900), (254, 254, 254))
    draw = ImageDraw.Draw(img)
    for i in range(0, 900, 12):
        draw.line([(i, 0), (i, 900)], fill=(250, 250, 250), width=2)
    assert analyze_image(img).rejection_reason == "overexposed"


def test_analysis_never_raises_on_odd_modes():
    for mode in ("L", "RGBA", "P"):
        report = analyze_image(Image.new(mode, (900, 900)))
        assert report is not None


# ---------------------------------------------------------------------------
# The ordering trap: measure BEFORE the processing pipeline
# ---------------------------------------------------------------------------

def test_processing_pipeline_inflates_sharpness_so_order_matters():
    """process_image() runs denoise → sharpen → autocontrast. Grading after
    it would measure our own filter, not the user's photo — this is why
    screening takes the original bytes."""
    blurred = _detailed().filter(ImageFilter.GaussianBlur(6))

    before = analyze_image(blurred).blur_score
    after = analyze_image(process_image(blurred)).blur_score

    assert after > before


def test_processing_pipeline_strips_exif_so_gps_must_be_read_first():
    """process_image() ends with strip_exif(). Any GPS read afterwards
    finds nothing, which is why read_exif runs on the original."""
    assert read_exif(process_image(_detailed())).has_gps is False


# ---------------------------------------------------------------------------
# EXIF / GPS
# ---------------------------------------------------------------------------

def test_photo_without_exif_reports_no_gps():
    report = read_exif(_detailed())
    assert report.has_gps is False
    assert report.gps_lat is None


def test_gps_match_requires_both_sides():
    no_gps = ExifReport()
    assert gps_matches_place(no_gps, place_lat=37.7, place_lng=-122.4) is False

    has_gps = ExifReport(gps_lat=37.7, gps_lng=-122.4)
    assert gps_matches_place(has_gps, place_lat=None, place_lng=None) is False


def test_gps_within_radius_matches_and_far_away_does_not():
    at_place = ExifReport(gps_lat=37.77490, gps_lng=-122.41940)
    assert gps_matches_place(at_place, place_lat=37.77490, place_lng=-122.41940) is True

    across_town = ExifReport(gps_lat=37.8100, gps_lng=-122.4100)
    assert gps_matches_place(across_town, place_lat=37.7749, place_lng=-122.4194) is False


def test_meters_between_is_roughly_right():
    # ~0.001 degree of latitude is ~111m.
    distance = meters_between(37.7749, -122.4194, 37.7759, -122.4194)
    assert 100 < distance < 125


# ---------------------------------------------------------------------------
# Moderation decisions
# ---------------------------------------------------------------------------

def _clean_scan(monkeypatch):
    monkeypatch.setattr(mod, "scan_image_url", lambda url: SafetyReport(scanned=True, verdict="clean"))
    monkeypatch.setattr(mod, "safety_scanning_configured", lambda: True)


def test_good_photo_with_clean_scan_publishes_immediately(db, place, monkeypatch):
    _clean_scan(monkeypatch)
    decision = mod.screen_upload(
        db, image=_image_row(db, place), original=_detailed(),
        public_url="https://example.com/x.jpg",
    )
    assert decision.status == mod.MOD_APPROVED
    assert decision.is_publishable


def test_blurry_photo_is_rejected_before_any_paid_scan(db, place, monkeypatch):
    calls = []
    monkeypatch.setattr(mod, "scan_image_url", lambda url: calls.append(url) or UNSCANNED)

    decision = mod.screen_upload(
        db, image=_image_row(db, place),
        original=_detailed().filter(ImageFilter.GaussianBlur(12)),
        public_url="https://example.com/x.jpg",
    )

    assert decision.status == mod.MOD_REJECTED
    assert decision.reason == "too_blurry"
    # The whole point of ordering quality before safety: never pay Vision
    # for a photo the free local check already threw out.
    assert calls == []


def test_safety_reject_blocks_the_upload(db, place, monkeypatch):
    monkeypatch.setattr(mod, "safety_scanning_configured", lambda: True)
    monkeypatch.setattr(
        mod, "scan_image_url",
        lambda url: SafetyReport(scanned=True, verdict="reject", detail="adult"),
    )
    decision = mod.screen_upload(
        db, image=_image_row(db, place), original=_detailed(),
        public_url="https://example.com/x.jpg",
    )
    assert decision.status == mod.MOD_REJECTED
    assert decision.reason == "safety_adult"


def test_ambiguous_safety_result_goes_to_review_not_rejection(db, place, monkeypatch):
    monkeypatch.setattr(mod, "safety_scanning_configured", lambda: True)
    monkeypatch.setattr(
        mod, "scan_image_url",
        lambda url: SafetyReport(scanned=True, verdict="review", detail="racy"),
    )
    decision = mod.screen_upload(
        db, image=_image_row(db, place), original=_detailed(),
        public_url="https://example.com/x.jpg",
    )
    assert decision.status == mod.MOD_PENDING_REVIEW
    assert not decision.is_publishable


def test_unconfigured_scanning_still_publishes(db, place, monkeypatch):
    """A deployment that hasn't enabled Vision must not hold every photo:
    nobody could ever reach the trust threshold, so the queue would grow
    without bound and never drain."""
    monkeypatch.setattr(mod, "safety_scanning_configured", lambda: False)
    monkeypatch.setattr(mod, "scan_image_url", lambda url: UNSCANNED)

    decision = mod.screen_upload(
        db, image=_image_row(db, place, uploaded_by=f"brand-new-{uuid.uuid4().hex[:6]}"),
        original=_detailed(), public_url="https://example.com/x.jpg",
    )
    assert decision.status == mod.MOD_APPROVED


def test_scan_failure_holds_a_brand_new_contributor(db, place, monkeypatch):
    monkeypatch.setattr(mod, "safety_scanning_configured", lambda: True)
    monkeypatch.setattr(mod, "scan_image_url", lambda url: UNSCANNED)

    decision = mod.screen_upload(
        db, image=_image_row(db, place, uploaded_by=f"brand-new-{uuid.uuid4().hex[:6]}"),
        original=_detailed(), public_url="https://example.com/x.jpg",
    )
    assert decision.status == mod.MOD_PENDING_REVIEW
    assert decision.reason == "scan_unavailable_new_contributor"


def test_scan_failure_does_not_hold_an_established_contributor(db, place, monkeypatch):
    monkeypatch.setattr(mod, "safety_scanning_configured", lambda: True)
    monkeypatch.setattr(mod, "scan_image_url", lambda url: UNSCANNED)

    user_id = f"established-{uuid.uuid4().hex[:6]}"
    for _ in range(mod.TRUSTED_UPLOAD_COUNT):
        prior = PlaceImage(place_id=place.id, uploaded_by=user_id,
                           moderation_status=mod.MOD_APPROVED)
        db.add(prior)
    db.commit()

    decision = mod.screen_upload(
        db, image=_image_row(db, place, uploaded_by=user_id),
        original=_detailed(), public_url="https://example.com/x.jpg",
    )
    assert decision.status == mod.MOD_APPROVED


def test_gps_verification_bypasses_the_trust_wait(db, place, monkeypatch):
    """Being physically at the restaurant is stronger evidence than
    account tenure, so it publishes even with no scan and no history."""
    monkeypatch.setattr(mod, "safety_scanning_configured", lambda: True)
    monkeypatch.setattr(mod, "scan_image_url", lambda url: UNSCANNED)
    monkeypatch.setattr(
        mod, "read_exif",
        lambda img: ExifReport(gps_lat=place.lat, gps_lng=place.lng),
    )

    decision = mod.screen_upload(
        db, image=_image_row(db, place, uploaded_by=f"new-{uuid.uuid4().hex[:6]}"),
        original=_detailed(), public_url="https://example.com/x.jpg",
    )
    assert decision.gps_verified is True
    assert decision.status == mod.MOD_APPROVED


# ---------------------------------------------------------------------------
# Writing the decision back
# ---------------------------------------------------------------------------

def test_apply_decision_writes_every_field(db, place, monkeypatch):
    _clean_scan(monkeypatch)
    image = _image_row(db, place)
    decision = mod.screen_upload(
        db, image=image, original=_detailed(), public_url="https://example.com/x.jpg",
    )
    mod.apply_decision(image, decision)

    assert image.moderation_status == mod.MOD_APPROVED
    assert image.is_approved is True
    assert image.quality_score is not None
    assert image.blur_score is not None
    assert image.safety_scanned is True


def test_apply_decision_marks_rejected_images_unapproved(db, place, monkeypatch):
    monkeypatch.setattr(mod, "scan_image_url", lambda url: UNSCANNED)
    image = _image_row(db, place)
    decision = mod.screen_upload(
        db, image=image, original=_detailed().filter(ImageFilter.GaussianBlur(12)),
        public_url="https://example.com/x.jpg",
    )
    mod.apply_decision(image, decision)

    # is_approved was previously hardcoded True at upload with nothing ever
    # setting it False — this is the column finally meaning what it says.
    assert image.is_approved is False
    assert image.moderation_status == mod.MOD_REJECTED
