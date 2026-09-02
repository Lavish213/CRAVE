from __future__ import annotations

import os
from typing import Tuple

import boto3
import requests
from botocore.client import Config


R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID")
R2_ACCESS_KEY = os.getenv("R2_ACCESS_KEY")
R2_SECRET_KEY = os.getenv("R2_SECRET_KEY")
R2_BUCKET = os.getenv("R2_BUCKET")

R2_ENDPOINT = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"

# The bucket's actual public-serving domain — a Public Development URL
# (bucket Settings -> Public Development URL, "https://pub-<hash>.r2.dev")
# or a custom domain mapped to the bucket. Deliberately NOT derived from
# R2_ENDPOINT above: that's the S3 API host, which always requires
# SigV4-signed requests no matter what a bucket's public-access setting
# is, so a URL built from it can never be loaded directly by a client —
# every URL generate_public_url() returned before this env var existed
# was unreachable from the app regardless of any Railway config.
R2_PUBLIC_BASE_URL = os.getenv("R2_PUBLIC_BASE_URL", "").rstrip("/")


def _get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=R2_ENDPOINT,
        aws_access_key_id=R2_ACCESS_KEY,
        aws_secret_access_key=R2_SECRET_KEY,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


def generate_presigned_upload_url(
    *,
    key: str,
    content_type: str,
    expires_in: int = 600,
) -> str:
    """
    Generate presigned PUT URL for direct upload to R2
    """

    client = _get_s3_client()

    url = client.generate_presigned_url(
        ClientMethod="put_object",
        Params={
            "Bucket": R2_BUCKET,
            "Key": key,
            "ContentType": content_type,
        },
        ExpiresIn=expires_in,
    )

    return url


def generate_public_url(key: str) -> str:
    """
    Build the publicly-loadable URL for an object in this bucket.

    Raises if R2_PUBLIC_BASE_URL isn't configured rather than falling back
    to the S3 API endpoint — that fallback is what silently produced
    unreachable URLs before, and callers here already treat a raised
    exception as "this upload didn't work" (see StaleImageRefresher,
    which wraps this in the same try/except as the upload call and fails
    closed).
    """
    if not R2_PUBLIC_BASE_URL:
        raise RuntimeError("R2_PUBLIC_BASE_URL is not configured")

    return f"{R2_PUBLIC_BASE_URL}/{key}"


def upload_bytes(*, key: str, data: bytes, content_type: str) -> None:
    """
    Server-side upload — for content the backend downloads itself (e.g. a
    Google Places photo) rather than a client-presigned direct upload.
    Raises on failure; callers that need fail-open behavior (an ingestion
    worker shouldn't die because R2 hiccuped) must catch around this
    themselves, same as every other outbound call in this codebase.
    """

    client = _get_s3_client()
    client.put_object(
        Bucket=R2_BUCKET,
        Key=key,
        Body=data,
        ContentType=content_type,
    )


def head_object(key: str) -> dict:
    """
    Metadata (notably ContentLength) for an object already in the bucket,
    without downloading its body. Used by the video upload flow to
    actually enforce a max-size cap after the client's direct-to-storage
    PUT finishes — a presigned PUT URL has no built-in size limit, so this
    is the real enforcement point, same lesson as the confirm_upload fix
    in app/services/upload/upload_service.py. Raises (botocore's
    ClientError, 404 on a missing key) rather than returning None — the
    caller already needs to distinguish "not uploaded yet" from "uploaded,
    too large" and a raised exception makes that an explicit branch
    instead of a silent falsy value.
    """
    client = _get_s3_client()
    return client.head_object(Bucket=R2_BUCKET, Key=key)


def download_to_file(key: str, dest_path: str) -> None:
    """
    Streams an object's body straight to a local file rather than loading
    it into memory — video files are large enough that reading a whole
    one into a Python bytes object before writing it out would waste real
    memory for no benefit, unlike the small photo payloads upload_bytes()
    above is sized for.
    """
    client = _get_s3_client()
    # Do not stream through botocore's ``StreamingBody.iter_chunks`` here.
    # The standalone Railway scheduler reproduced a recursion failure in that
    # path twice for a real uploaded video, even though the same exact object
    # could be fetched from a one-shot process.  A short-lived signed GET keeps
    # authorization server-side while letting requests perform the bounded,
    # boring HTTP stream independently of botocore's response wrapper.
    url = client.generate_presigned_url(
        ClientMethod="get_object",
        Params={"Bucket": R2_BUCKET, "Key": key},
        ExpiresIn=300,
    )
    with requests.get(url, stream=True, timeout=(10, 120)) as response:
        response.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)


def upload_file(
    *,
    key: str,
    local_path: str,
    content_type: str,
    cache_control: str | None = None,
) -> None:
    """
    File-based counterpart to upload_bytes() — for content already on
    local disk (e.g. a worker's ffmpeg output) rather than in memory.
    """
    client = _get_s3_client()
    extra_args = {"ContentType": content_type}
    if cache_control:
        extra_args["CacheControl"] = cache_control
    client.upload_file(local_path, R2_BUCKET, key, ExtraArgs=extra_args)


def delete_object(key: str) -> None:
    client = _get_s3_client()
    client.delete_object(Bucket=R2_BUCKET, Key=key)
