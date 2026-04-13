from __future__ import annotations
from typing import Dict, Optional, List

"""
Health dataset configuration registry.
PRODUCTION READY — ArcGIS VERIFIED
"""

# ---------------------------------------------------------
# Defaults
# ---------------------------------------------------------

DEFAULT_HEALTH_CONFIDENCE = 0.85
DEFAULT_PAGE_LIMIT = 1000  # ✅ proper ArcGIS safe max
DEFAULT_CATEGORY = "restaurant"

SUPPORTED_DATASET_TYPES = {"socrata", "arcgis"}


# ---------------------------------------------------------
# Dataset Config Structure
# ---------------------------------------------------------

class HealthDatasetConfig:

    def __init__(
        self,
        *,
        city_slug: str,
        dataset_type: str = "socrata",

        domain: Optional[str] = None,
        dataset_id: Optional[str] = None,
        arcgis_url: Optional[str] = None,

        name_field: str,
        lat_field: Optional[str],
        lng_field: Optional[str],

        address_field: Optional[str] = None,
        phone_field: Optional[str] = None,
        website_field: Optional[str] = None,

        permit_id_field: Optional[str] = None,
        facility_id_field: Optional[str] = None,

        status_field: Optional[str] = None,
        status_active_values: Optional[List[str]] = None,

        where: Optional[str] = None,
        select: Optional[str] = None,

        category_field: Optional[str] = None,
        facility_type_field: Optional[str] = None,
        permit_type_field: Optional[str] = None,

        category_hint: str = DEFAULT_CATEGORY,
        confidence: float = DEFAULT_HEALTH_CONFIDENCE,

        page_limit: int = DEFAULT_PAGE_LIMIT,
        source_priority: int = 50,

        allow_address_only: bool = True,
        allow_geocode_fallback: bool = True,

        dataset_tags: Optional[List[str]] = None,
    ):

        self.city_slug = city_slug.lower().strip()
        self.dataset_type = dataset_type.lower().strip()

        self.domain = domain.strip() if isinstance(domain, str) else domain
        self.dataset_id = dataset_id.strip() if isinstance(dataset_id, str) else dataset_id
        self.arcgis_url = arcgis_url.strip() if isinstance(arcgis_url, str) else arcgis_url

        self.name_field = name_field
        self.lat_field = lat_field
        self.lng_field = lng_field

        self.address_field = address_field
        self.phone_field = phone_field
        self.website_field = website_field

        self.permit_id_field = permit_id_field
        self.facility_id_field = facility_id_field

        self.category_field = category_field
        self.facility_type_field = facility_type_field
        self.permit_type_field = permit_type_field

        self.status_field = status_field
        self.status_active_values = status_active_values

        self.where = where
        self.select = select

        self.category_hint = category_hint
        self.confidence = max(0.0, min(confidence, 1.0))

        self.page_limit = page_limit
        self.source_priority = source_priority

        self.allow_address_only = allow_address_only
        self.allow_geocode_fallback = allow_geocode_fallback

        self.dataset_tags = dataset_tags or ["health"]

        self._validate()

    def _validate(self) -> None:
        if not self.city_slug:
            raise ValueError("city_slug required")

        if self.dataset_type not in SUPPORTED_DATASET_TYPES:
            raise ValueError(f"{self.city_slug}: unsupported dataset_type")

        if self.dataset_type == "socrata":
            if not self.domain or not self.dataset_id:
                raise ValueError(f"{self.city_slug}: invalid socrata config")

        if self.dataset_type == "arcgis":
            if not self.arcgis_url:
                raise ValueError(f"{self.city_slug}: arcgis_url required")

        if not self.name_field:
            raise ValueError(f"{self.city_slug}: name_field required")

        if self.page_limit <= 0:
            raise ValueError(f"{self.city_slug}: page_limit must be > 0")

    def to_dict(self) -> Dict[str, object]:
        return self.__dict__


# ---------------------------------------------------------
# Registry
# ---------------------------------------------------------

HEALTH_DATASETS: Dict[str, HealthDatasetConfig] = {}


def register_health_dataset(config: HealthDatasetConfig) -> None:
    if config.city_slug in HEALTH_DATASETS:
        raise RuntimeError(f"Duplicate dataset config: {config.city_slug}")
    HEALTH_DATASETS[config.city_slug] = config


# ---------------------------------------------------------
# Oakland (FINAL FIXED)
# ---------------------------------------------------------

register_health_dataset(
    HealthDatasetConfig(
        city_slug="oakland",
        dataset_type="arcgis",

        arcgis_url="https://services5.arcgis.com/ROBnTHSNjoZ2Wm1P/arcgis/rest/services/Restaurant_Inspections/FeatureServer/0/query",

        name_field="Facility_Name",
        lat_field="Latitude",
        lng_field="Longitude",

        address_field="Address",
        facility_id_field="Facility_ID",

        status_field=None,

        category_hint="restaurant",
        confidence=0.92,
        source_priority=80,

        dataset_tags=["health", "alameda", "oakland"],
    )
)


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def get_health_dataset(city_slug: str) -> HealthDatasetConfig:
    slug = city_slug.lower().strip()

    if slug not in HEALTH_DATASETS:
        raise ValueError(f"No dataset for {slug}")

    return HEALTH_DATASETS[slug]


def list_health_datasets() -> List[str]:
    return sorted(HEALTH_DATASETS.keys())