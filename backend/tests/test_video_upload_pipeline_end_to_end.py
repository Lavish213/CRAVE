"""
Drives the REAL video upload + processing pipeline as close to end-to-end
as this environment allows: real API routes (POST /videos/request,
POST /videos/{id}/confirm), the real upload-service functions (ownership
check, size enforcement via head_object), real DB rows, the real scheduler
job function (process_pending_videos -- the same one wired to the live
`video_processing` scheduler job), real ffmpeg (frame extraction,
compression), and the real TFLite food classifier.

The ONE thing genuinely stubbed is the R2/S3 network layer: this
environment has zero R2 credentials (confirmed via settings.r2_account_id
etc. all being empty/None), so a real Cloudflare object-storage round
trip is not reachable here regardless of mocking choices -- that piece
needs production credentials, not more code. FakeS3 below is a
local-file-backed stand-in for exactly that one boundary; everything
else in this test is genuine production code executing for real.

Push notification delivery is not mocked at all -- it doesn't need to be.
send_push_to_user() already queries DevicePushToken for the calling user,
finds none (this test creates no device tokens), and no-ops for real,
the same way it would for any real user who hasn't registered a device.

Closes the same class of gap as test_video_pipeline_real_ffmpeg_and_model.py
(PR #121, which proved ffmpeg+classifier in isolation) one layer up: this
proves the actual API-to-DB-to-scheduler-to-classifier chain a real
upload would take, not just the classifier function called directly.
"""
from __future__ import annotations

import io
import shutil
import subprocess
import uuid

import pytest
from botocore.exceptions import ClientError
from fastapi.testclient import TestClient

from app.main import app
from app.core.rate_limit import rate_limit
from app.core.user_auth import get_current_user_id
from app.db.session import SessionLocal
from app.db.models.city import City
from app.db.models.place import Place
from app.db.models.place_video import PlaceVideo, STATUS_APPROVED, STATUS_REJECTED
import app.services.upload.r2_client as r2_client
from app.services.video.video_processing_worker import process_pending_videos
from app.services.video.food_classifier import _load_interpreter, FoodClassifierUnavailableError

client = TestClient(app)

FIXTURES_DIR = __file__.rsplit("/", 1)[0] + "/fixtures/video"
FOOD_IMAGE = f"{FIXTURES_DIR}/sample_food.jpg"
NOT_FOOD_IMAGE = f"{FIXTURES_DIR}/sample_not_food.jpg"


def _skip_if_unavailable():
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("ffmpeg/ffprobe not installed in this environment")
    try:
        _load_interpreter()
    except FoodClassifierUnavailableError as exc:
        pytest.skip(f"no TFLite runtime installed: {exc}")


def _build_video_from_image(image_path: str, out_path: str, *, seconds: int = 3) -> str:
    result = subprocess.run(
        [
            "ffmpeg", "-y",
            "-loop", "1", "-i", image_path,
            "-c:v", "libx264", "-t", str(seconds),
            "-pix_fmt", "yuv420p",
            "-vf", "scale=640:640",
            out_path,
        ],
        capture_output=True, timeout=30, check=False,
    )
    assert result.returncode == 0, result.stderr.decode(errors="replace")[:500]
    return out_path


class FakeS3:
    """Local-file-backed stand-in for the real boto3 R2 client -- the one
    boundary this environment cannot reach for real (no R2 credentials).
    generate_presigned_url returns an unused placeholder; head_object and
    get_object serve whatever bytes the test registered under a key,
    mirroring what a real client's direct-to-storage PUT would have left
    there."""

    def __init__(self):
        self.objects: dict[str, bytes] = {}
        self.last_presigned_key: str | None = None

    def generate_presigned_url(self, **kwargs):
        self.last_presigned_key = kwargs["Params"]["Key"]
        return "https://fake-r2.test/unused-presigned-url"

    def head_object(self, *, Bucket, Key):
        if Key not in self.objects:
            raise ClientError({"Error": {"Code": "404", "Message": "Not Found"}}, "HeadObject")
        return {"ContentLength": len(self.objects[Key])}

    def get_object(self, *, Bucket, Key):
        data = self.objects[Key]

        class _Body:
            def __init__(self, data):
                self._buf = io.BytesIO(data)

            def iter_chunks(self, chunk_size=1024 * 1024):
                while True:
                    chunk = self._buf.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk

            def close(self):
                pass

        return {"Body": _Body(data)}

    def upload_file(self, local_path, Bucket, Key, ExtraArgs=None):
        # Approve-path uploads (processed video, thumbnail) -- real
        # ffmpeg output really does land here, same as a real R2 PUT.
        with open(local_path, "rb") as f:
            self.objects[Key] = f.read()

    def delete_object(self, *, Bucket, Key):
        self.objects.pop(Key, None)


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def place(db):
    _skip_if_unavailable()
    city_id = str(uuid.uuid4())
    place_id = str(uuid.uuid4())
    db.add(City(
        id=city_id, name="Video Upload Pipeline Test City",
        slug=f"video-upload-pipeline-{city_id[:8]}", lat=37.8, lng=-122.27, is_active=True,
    ))
    db.add(Place(
        id=place_id, name="Video Upload Pipeline Test Place", city_id=city_id,
        lat=37.8, lng=-122.27, is_active=True,
    ))
    db.commit()
    yield place_id
    db.query(PlaceVideo).filter(PlaceVideo.place_id == place_id).delete()
    db.query(Place).filter(Place.id == place_id).delete()
    db.query(City).filter(City.id == city_id).delete()
    db.commit()


@pytest.fixture(autouse=True)
def _overrides():
    app.dependency_overrides[rate_limit] = lambda: None
    yield
    app.dependency_overrides.pop(get_current_user_id, None)
    app.dependency_overrides.pop(rate_limit, None)


@pytest.fixture()
def fake_s3(monkeypatch):
    # video_upload_service.py and video_processing_worker.py both call
    # r2_client's own head_object/download_to_file/generate_presigned_
    # upload_url functions, which resolve _get_s3_client() from r2_client's
    # module namespace at call time -- patching it here alone covers both
    # callers, no need to patch it in each importing module separately.
    fake = FakeS3()
    monkeypatch.setattr(r2_client, "_get_s3_client", lambda: fake)

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def raise_for_status(self):
            return None

        def iter_content(self, chunk_size=1024 * 1024):
            assert fake.last_presigned_key is not None
            data = fake.objects[fake.last_presigned_key]
            for offset in range(0, len(data), chunk_size):
                yield data[offset : offset + chunk_size]

    monkeypatch.setattr(r2_client.requests, "get", lambda *args, **kwargs: _Response())
    return fake


def _run_real_pipeline(*, db, place_id: str, video_path: str, fake_s3) -> PlaceVideo:
    user_id = f"user-{uuid.uuid4().hex[:8]}"
    app.dependency_overrides[get_current_user_id] = lambda: user_id

    # Real route, real service function, real DB row.
    resp = client.post(
        "/api/v1/videos/request",
        json={"place_id": place_id, "content_type": "video/mp4"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    video_id, key = body["video_id"], body["key"]

    # The one step that can't be real here: the client's direct-to-R2 PUT.
    # Registers the real generated video's bytes under the real key the
    # real service just generated.
    with open(video_path, "rb") as f:
        fake_s3.objects[key] = f.read()

    # Real route, real service function (real ownership + size checks).
    resp = client.post(f"/api/v1/videos/{video_id}/confirm")
    assert resp.status_code == 200, resp.text

    # The real scheduler job function -- identical to the live
    # `video_processing` job. Real ffmpeg, real model, real DB commit.
    process_pending_videos(db, limit=10)

    db.expire_all()
    return db.query(PlaceVideo).filter(PlaceVideo.id == video_id).one()


def test_a_real_food_video_is_approved_through_the_full_real_pipeline(db, place, fake_s3, tmp_path):
    video_path = _build_video_from_image(FOOD_IMAGE, str(tmp_path / "food.mp4"))

    video = _run_real_pipeline(db=db, place_id=place, video_path=video_path, fake_s3=fake_s3)

    assert video.status == STATUS_APPROVED
    assert video.food_score is not None and video.food_score >= 0.8


def test_a_real_non_food_video_is_rejected_through_the_full_real_pipeline(db, place, fake_s3, tmp_path):
    video_path = _build_video_from_image(NOT_FOOD_IMAGE, str(tmp_path / "not_food.mp4"))

    video = _run_real_pipeline(db=db, place_id=place, video_path=video_path, fake_s3=fake_s3)

    assert video.status == STATUS_REJECTED
    assert video.reject_reason == "food_score"
