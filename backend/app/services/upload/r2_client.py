from __future__ import annotations

import os
from typing import Tuple

import boto3
from botocore.client import Config


R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID")
R2_ACCESS_KEY = os.getenv("R2_ACCESS_KEY")
R2_SECRET_KEY = os.getenv("R2_SECRET_KEY")
R2_BUCKET = os.getenv("R2_BUCKET")

R2_ENDPOINT = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"


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
    Build CDN/public URL (no DB hardcoding)
    """

    return f"https://{R2_BUCKET}.{R2_ACCOUNT_ID}.r2.cloudflarestorage.com/{key}"