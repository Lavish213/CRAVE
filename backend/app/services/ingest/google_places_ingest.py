from __future__ import annotations

import logging
import time
from typing import Dict, List, Set

from app.services.network.http_fetcher import fetch


logger = logging.getLogger(__name__)

GOOGLE_PLACES_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"


class GooglePlacesIngest:

    SEARCH_TYPES = [
        "restaurant",
        "cafe",
        "meal_takeaway",
        "food",
    ]

    MAX_RESULTS_PER_CELL = 60
    PAGE_DELAY_SECONDS = 2  # required by Google API

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    # ---------------------------------------------------------
    # ENTRY
    # ---------------------------------------------------------

    def scan_grid(
        self,
        *,
        lat_min: float,
        lat_max: float,
        lon_min: float,
        lon_max: float,
        step_km: float = 1.5,
    ) -> List[Dict]:

        cells = self._generate_grid(
            lat_min=lat_min,
            lat_max=lat_max,
            lon_min=lon_min,
            lon_max=lon_max,
            step_km=step_km,
        )

        records: List[Dict] = []
        seen_ids: Set[str] = set()

        for cell in cells:

            try:

                results = self._scan_cell(
                    lat=cell["lat"],
                    lon=cell["lon"],
                )

                for r in results:
                    ext_id = r.get("external_id")

                    if not ext_id or ext_id in seen_ids:
                        continue

                    seen_ids.add(ext_id)
                    records.append(r)

            except Exception as exc:

                logger.debug(
                    "google_places_cell_failed lat=%s lon=%s error=%s",
                    cell["lat"],
                    cell["lon"],
                    exc,
                )

        logger.info(
            "google_places_scan_complete cells=%s unique_records=%s",
            len(cells),
            len(records),
        )

        return records

    # ---------------------------------------------------------
    # GRID
    # ---------------------------------------------------------

    def _generate_grid(
        self,
        *,
        lat_min: float,
        lat_max: float,
        lon_min: float,
        lon_max: float,
        step_km: float,
    ) -> List[Dict]:

        step_deg = step_km / 111

        cells: List[Dict] = []

        lat = lat_min

        while lat <= lat_max:

            lon = lon_min

            while lon <= lon_max:

                cells.append({"lat": lat, "lon": lon})

                lon += step_deg

            lat += step_deg

        return cells

    # ---------------------------------------------------------
    # CELL SCAN (WITH PAGINATION 🔥)
    # ---------------------------------------------------------

    def _scan_cell(
        self,
        *,
        lat: float,
        lon: float,
    ) -> List[Dict]:

        all_results: List[Dict] = []

        for place_type in self.SEARCH_TYPES:

            next_page_token = None

            for page in range(3):  # max 3 pages (~60 results)

                try:

                    params = {
                        "location": f"{lat},{lon}",
                        "radius": 1500,
                        "type": place_type,
                        "key": self.api_key,
                    }

                    if next_page_token:
                        params = {
                            "pagetoken": next_page_token,
                            "key": self.api_key,
                        }

                    response = fetch(
                        GOOGLE_PLACES_URL,
                        method="GET",
                        params=params,
                    )

                    if response.status_code != 200:
                        break

                    data = response.json()

                    for place in data.get("results", []):

                        record = self._convert_place(place)

                        if record:
                            all_results.append(record)

                    next_page_token = data.get("next_page_token")

                    if not next_page_token:
                        break

                    time.sleep(self.PAGE_DELAY_SECONDS)

                except Exception as exc:

                    logger.debug(
                        "google_places_query_failed lat=%s lon=%s error=%s",
                        lat,
                        lon,
                        exc,
                    )
                    break

        return all_results

    # ---------------------------------------------------------
    # CONVERT
    # ---------------------------------------------------------

    def _convert_place(
        self,
        place: Dict,
    ) -> Dict | None:

        try:

            name = place.get("name")
            location = place.get("geometry", {}).get("location", {})

            lat = location.get("lat")
            lng = location.get("lng")

            if not name or lat is None or lng is None:
                return None

            return {
                "external_id": place.get("place_id"),
                "name": name,
                "address": place.get("vicinity"),
                "lat": float(lat),
                "lng": float(lng),  # 🔥 FIXED (was "lon")
                "phone": None,
                "website": None,
                "source": "google_places",
                "raw_payload": place,
            }

        except Exception:
            return None