from __future__ import annotations

import logging
import time
from typing import Dict, List, Optional, Set

from app.services.network.http_fetcher import fetch


logger = logging.getLogger(__name__)

GOOGLE_PLACES_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"

_GENERIC_TYPES = frozenset({
    "point_of_interest",
    "establishment",
    "premise",
    "food",
    "store",
    "health",
    "locality",
    "political",
    "geocode",
})

_TYPE_TO_HINT: Dict[str, str] = {
    "restaurant": "restaurant",
    "cafe": "cafe",
    "bar": "bar",
    "bakery": "bakery",
    "meal_takeaway": "fast food",
    "meal_delivery": "fast food",
    "night_club": "bar",
    "ice_cream_shop": "desserts",
    "dessert_shop": "desserts",
    "sandwich_shop": "american",
    "pizza_restaurant": "pizza",
    "seafood_restaurant": "seafood",
    "sushi_restaurant": "japanese",
    "ramen_restaurant": "japanese",
    "mexican_restaurant": "mexican",
    "italian_restaurant": "italian",
    "chinese_restaurant": "chinese",
    "japanese_restaurant": "japanese",
    "korean_restaurant": "korean",
    "thai_restaurant": "thai",
    "indian_restaurant": "indian",
    "mediterranean_restaurant": "mediterranean",
    "barbecue_restaurant": "bbq",
    "american_restaurant": "american",
    "breakfast_restaurant": "breakfast",
    "brunch_restaurant": "breakfast",
    "fast_food_restaurant": "fast food",
    "coffee_shop": "coffee",
    "tea_house": "coffee",
    "wine_bar": "bar",
    "sports_bar": "bar",
    "pub": "bar",
    "food_court": "restaurant",
    "diner": "american",
    "steakhouse": "american",
    "vegetarian_restaurant": "vegan",
    "vegan_restaurant": "vegan",
}


def _best_type_hint(types: List[str]) -> Optional[str]:
    if not types:
        return None
    for t in types:
        mapped = _TYPE_TO_HINT.get(t)
        if mapped:
            return mapped
    for t in types:
        if t not in _GENERIC_TYPES:
            return t.replace("_", " ")
    return None


class GooglePlacesIngest:

    SEARCH_TYPES = [
        "restaurant",
        "cafe",
        "meal_takeaway",
        "food",
    ]

    MAX_RESULTS_PER_CELL = 60
    PAGE_DELAY_SECONDS = 2

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

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
                results = self._scan_cell(lat=cell["lat"], lon=cell["lon"])
                for r in results:
                    ext_id = r.get("external_id")
                    if not ext_id or ext_id in seen_ids:
                        continue
                    seen_ids.add(ext_id)
                    records.append(r)
            except Exception as exc:
                logger.debug(
                    "google_places_cell_failed lat=%s lon=%s error=%s",
                    cell["lat"], cell["lon"], exc,
                )

        logger.info(
            "google_places_scan_complete cells=%s unique_records=%s",
            len(cells), len(records),
        )

        return records

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

    def _scan_cell(self, *, lat: float, lon: float) -> List[Dict]:

        all_results: List[Dict] = []

        for place_type in self.SEARCH_TYPES:
            next_page_token = None

            for _page in range(3):
                try:
                    params: Dict = {
                        "location": f"{lat},{lon}",
                        "radius": 1500,
                        "type": place_type,
                        "key": self.api_key,
                    }

                    if next_page_token:
                        params = {"pagetoken": next_page_token, "key": self.api_key}

                    response = fetch(GOOGLE_PLACES_URL, method="GET", params=params)

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
                        lat, lon, exc,
                    )
                    break

        return all_results

    def _convert_place(self, place: Dict) -> Optional[Dict]:
        try:
            name = place.get("name")
            location = place.get("geometry", {}).get("location", {})
            lat = location.get("lat")
            lng = location.get("lng")

            if not name or lat is None or lng is None:
                return None

            types: List[str] = place.get("types") or []
            category_hint = _best_type_hint(types)

            return {
                "external_id": place.get("place_id"),
                "name": name,
                "address": place.get("vicinity"),
                "lat": float(lat),
                "lng": float(lng),
                "phone": None,
                "website": place.get("website"),
                "category_hint": category_hint,
                "source": "google_places",
                "raw_payload": place,
            }

        except Exception:
            return None
