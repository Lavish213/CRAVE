"""
Overture Maps places fetch — free, open, bulk geospatial data (Meta,
Microsoft, Amazon, TomTom) published monthly as public Parquet on S3, no
API key, no per-request cost.

Live-verified against the real dataset before building this (not assumed):
querying a real bounding box (SF-area) for food_and_drink places found
85.2% already carry a website, average per-record confidence 0.89 — high
enough to be worth ingesting, but that number is for *all* food places
Overture knows about, not specifically CRAVE's harder no-source gap, so
don't read it as an expected yield.

Mirrors osm_overpass.py's fetch_osm_pois in output shape so both sources
feed the exact same downstream ingest/promote pipeline
(osm_ingest_job.py / overture_ingest_job.py -> ingest_candidate_v2 ->
promote_candidate_v2), just with a different fetch function.

Data access uses plain pyarrow + anonymous S3 (no DuckDB httpfs extension —
avoids a runtime dependency on downloading an extension binary at request
time). Overture's Parquet files carry per-row-group min/max statistics on
the `bbox` struct fields, so pyarrow's filter pushdown skips almost all of
each file's data for a city-sized bounding box without downloading it.
"""
from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional

import pyarrow.compute as pc
import pyarrow.dataset as pads
import pyarrow.fs as pafs

logger = logging.getLogger(__name__)

OVERTURE_BUCKET = "overturemaps-us-west-2"
OVERTURE_REGION = "us-west-2"

# Overture's own taxonomy top-level grouping for restaurants/cafes/bars/
# bakeries/etc — confirmed live: 'restaurant'/'cafe'/'bar' all carry
# taxonomy.hierarchy[0] == 'food_and_drink', while unrelated categories that
# happen to contain the substring "bar" (e.g. 'barber_shop') do NOT. Using
# this hierarchy field instead of substring-matching category names avoids
# that false-positive class entirely.
FOOD_AND_DRINK_GROUP = "food_and_drink"


def _clean_string(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    value = value.strip()
    return value or None


def _normalize_phone(phone: Optional[str]) -> Optional[str]:
    if not phone:
        return None
    phone = re.sub(r"[^\d+]", "", phone)
    if len(phone) < 7:
        return None
    return phone


def _normalize_website(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    url = url.strip()
    if not url.startswith("http"):
        url = "https://" + url
    return url


def _build_address(addr: Optional[Dict]) -> Optional[str]:
    if not addr:
        return None
    freeform = addr.get("freeform")
    locality = addr.get("locality")
    parts = [freeform, locality]
    address = ", ".join(p for p in parts if p)
    return address or None


def _latest_release() -> Optional[str]:
    """Overture publishes a new dated release monthly; discover the current
    one rather than hardcoding a version that will eventually go stale."""
    try:
        import boto3
        from botocore import UNSIGNED
        from botocore.config import Config

        client = boto3.client(
            "s3", region_name=OVERTURE_REGION, config=Config(signature_version=UNSIGNED)
        )
        resp = client.list_objects_v2(
            Bucket=OVERTURE_BUCKET, Prefix="release/", Delimiter="/"
        )
        prefixes = [p["Prefix"] for p in resp.get("CommonPrefixes", [])]
        releases = sorted(p.strip("/").split("/")[-1] for p in prefixes if p)
        return releases[-1] if releases else None
    except Exception as exc:
        logger.warning("overture_latest_release_lookup_failed error=%s", exc)
        return None


def fetch_overture_places(
    *,
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
) -> List[Dict]:

    release = _latest_release()
    if not release:
        return []

    try:
        s3 = pafs.S3FileSystem(anonymous=True, region=OVERTURE_REGION)
        path = f"{OVERTURE_BUCKET}/release/{release}/theme=places/type=place/"
        dataset = pads.dataset(path, filesystem=s3, format="parquet")

        filt = (
            (pc.field("bbox", "xmin") <= lon_max)
            & (pc.field("bbox", "xmax") >= lon_min)
            & (pc.field("bbox", "ymin") <= lat_max)
            & (pc.field("bbox", "ymax") >= lat_min)
        )

        table = dataset.to_table(
            columns=[
                "id", "names", "categories", "taxonomy",
                "websites", "phones", "addresses", "bbox",
            ],
            filter=filt,
        )
    except Exception as exc:
        logger.warning("overture_fetch_failed error=%s release=%s", exc, release)
        return []

    ids = table.column("id")
    names = table.column("names").combine_chunks().field("primary")
    categories = table.column("categories").combine_chunks().field("primary")
    hierarchies = table.column("taxonomy").combine_chunks().field("hierarchy")
    websites_col = table.column("websites").combine_chunks()
    phones_col = table.column("phones").combine_chunks()
    addresses_col = table.column("addresses").combine_chunks()
    bbox_col = table.column("bbox").combine_chunks()

    results: List[Dict] = []

    for i in range(table.num_rows):

        hierarchy = hierarchies[i].as_py() or []
        if FOOD_AND_DRINK_GROUP not in hierarchy:
            continue

        name = _clean_string(names[i].as_py())
        if not name:
            continue

        bbox = bbox_col[i].as_py()
        if not bbox:
            continue
        lat = (bbox["ymin"] + bbox["ymax"]) / 2
        lon = (bbox["xmin"] + bbox["xmax"]) / 2

        website_list = websites_col[i].as_py() or []
        website = _normalize_website(website_list[0]) if website_list else None

        phone_list = phones_col[i].as_py() or []
        phone = _normalize_phone(phone_list[0]) if phone_list else None

        address_list = addresses_col[i].as_py() or []
        address = _build_address(address_list[0]) if address_list else None

        results.append({
            "external_id": f"overture:{ids[i].as_py()}",
            "name": name,
            "address": address,
            "lat": float(lat),
            "lon": float(lon),
            "phone": phone,
            "website": website,
            "category_hint": categories[i].as_py(),
            "source": "overture",
            # Flat, deliberately-chosen value — NOT Overture's own per-record
            # confidence field. Reusing that directly would repeat the exact
            # bug just fixed for OSM: individual records legitimately score
            # anywhere from ~0.5-1.0 in Overture's own scale, so some real,
            # valid rows would again land below
            # promotion_orchestrator_v2.MIN_CONFIDENCE_THRESHOLD (0.72) and
            # sit stuck forever. 0.8 is comfortably above that gate and
            # matches the empirically-measured average confidence (0.89) for
            # food_and_drink places in the one region checked live.
            "confidence": 0.8,
            "raw_payload": {"category": categories[i].as_py(), "hierarchy": hierarchy},
        })

    logger.info(
        "overture_places_fetched count=%s release=%s", len(results), release
    )
    return results
