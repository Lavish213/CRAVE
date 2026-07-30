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

# Google's Nearby Search `type` param is a loose OR-match, and Google tags
# many non-restaurant venues with a secondary "food" or "store" type because
# they sell food/drink items (dollar stores, gas stations, pharmacies,
# supermarkets). That's how "Dollar General" and "Super King" (a grocery
# chain) ended up in the catalog as if they were restaurants — nothing
# rejected a result just because it wasn't actually a place to eat AT.
# Any place whose `types` includes one of these is dropped outright,
# regardless of what else is in its types list.
_NON_RESTAURANT_TYPES = frozenset({
    "grocery_or_supermarket",
    "supermarket",
    "convenience_store",
    "department_store",
    "discount_store",
    "variety_store",
    "general_contractor",
    "gas_station",
    "pharmacy",
    "drugstore",
    "liquor_store",
    "grocery_store",
    "wholesaler",
    "warehouse",
    "hardware_store",
    "home_goods_store",
    "supermarket_chain",
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


class GoogleQuotaExhausted(RuntimeError):
    """
    Raised when Google Places reports OVER_QUERY_LIMIT after retries, or a
    hard REQUEST_DENIED / INVALID_REQUEST (bad/missing key, billing disabled,
    API not enabled, malformed request). Callers should stop scanning
    immediately rather than burning the rest of the grid — every remaining
    cell/type request would fail identically and (in the OVER_QUERY_LIMIT
    case) each failed call still costs a request against the quota.

    Before this existed, `_scan_cell` only checked the HTTP status code.
    Google Places returns HTTP 200 with a JSON `status` field for quota and
    auth errors, so a dead API key or exhausted quota silently produced zero
    results for the entire grid with no error, log line, or way to tell that
    apart from "there are just no restaurants here".
    """


# Non-fatal statuses: proceed as normal (OK) or move on (no results for this
# page/type, not an error).
_OK_STATUSES = frozenset({"OK", "ZERO_RESULTS"})

# Transient — worth a bounded retry with backoff.
_RETRYABLE_STATUSES = frozenset({"OVER_QUERY_LIMIT", "UNKNOWN_ERROR"})

# Fatal — every subsequent call this run will fail the same way; stop now.
_FATAL_STATUSES = frozenset({"REQUEST_DENIED", "INVALID_REQUEST", "NOT_FOUND"})


class GooglePlacesIngest:

    SEARCH_TYPES = [
        "restaurant",
        "cafe",
        "meal_takeaway",
        # "food" deliberately removed — it's Google's broadest catch-all
        # type and matches grocery stores, gas stations, dollar stores,
        # pharmacies, etc. (anything that sells food items), not just
        # restaurants. _NON_RESTAURANT_TYPES below is a second, independent
        # layer of defense against the same problem for whatever these
        # three narrower types still let through.
    ]

    MAX_RESULTS_PER_CELL = 60
    PAGE_DELAY_SECONDS = 2

    # Backoff for OVER_QUERY_LIMIT — Google recommends a short pause and
    # retry since quota buckets often free up within seconds, but we cap
    # attempts hard so one bad key/billing issue can't spin forever.
    MAX_QUOTA_RETRIES = 3
    QUOTA_BACKOFF_BASE_SECONDS = 2.0

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def search_nearby(self, *, lat: float, lng: float, radius_m: int = 150) -> List[Dict]:
        """
        Single, unpaginated Nearby Search centered on an exact point — for
        live "what's around me right now" lookups (e.g. a user confirming a
        new spot from their GPS location), as opposed to scan_grid()'s
        multi-cell, multi-page city-wide sweep. A 150m radius is small
        enough that pagination essentially never applies.

        Returns the same record shape as scan_grid() (via _convert_place),
        deduplicated by external_id (Google place_id) across the searched
        types.
        """
        results: List[Dict] = []
        seen_ids: Set[str] = set()

        for place_type in self.SEARCH_TYPES:
            try:
                params: Dict = {
                    "location": f"{lat},{lng}",
                    "radius": radius_m,
                    "type": place_type,
                    "key": self.api_key,
                }
                response = fetch(GOOGLE_PLACES_URL, method="GET", params=params)

                if response.status_code != 200:
                    continue

                data = response.json()
                status = data.get("status", "UNKNOWN_ERROR")

                if status in _FATAL_STATUSES:
                    raise GoogleQuotaExhausted(
                        f"google_places status={status} "
                        f"error_message={data.get('error_message')!r}"
                    )

                if status not in _OK_STATUSES:
                    continue

                for place in data.get("results", []):
                    record = self._convert_place(place)
                    if not record:
                        continue
                    ext_id = record.get("external_id")
                    if ext_id and ext_id in seen_ids:
                        continue
                    if ext_id:
                        seen_ids.add(ext_id)
                    results.append(record)

            except GoogleQuotaExhausted:
                raise
            except Exception as exc:
                logger.debug(
                    "google_places_nearby_failed lat=%s lng=%s type=%s error=%s",
                    lat, lng, place_type, exc,
                )

        return results

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
            except GoogleQuotaExhausted as exc:
                # Fatal for the whole run, not just this cell — every
                # remaining cell would fail identically (bad key, billing
                # disabled, or quota exhausted). Stop scanning immediately
                # instead of burning the rest of the grid on calls that are
                # guaranteed to fail.
                logger.error(
                    "google_places_scan_aborted lat=%s lon=%s reason=%s "
                    "cells_scanned=%s cells_total=%s records_so_far=%s",
                    cell["lat"], cell["lon"], exc,
                    cells.index(cell), len(cells), len(records),
                )
                break
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
                quota_retries = 0

                while True:
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
                        status = data.get("status", "UNKNOWN_ERROR")

                        if status in _FATAL_STATUSES:
                            raise GoogleQuotaExhausted(
                                f"google_places status={status} "
                                f"error_message={data.get('error_message')!r}"
                            )

                        if status in _RETRYABLE_STATUSES:
                            quota_retries += 1
                            if quota_retries > self.MAX_QUOTA_RETRIES:
                                raise GoogleQuotaExhausted(
                                    f"google_places status={status} "
                                    f"after {quota_retries - 1} retries "
                                    f"error_message={data.get('error_message')!r}"
                                )
                            backoff = self.QUOTA_BACKOFF_BASE_SECONDS * (2 ** (quota_retries - 1))
                            logger.warning(
                                "google_places_quota_retry lat=%s lon=%s type=%s "
                                "status=%s attempt=%s backoff=%s",
                                lat, lon, place_type, status, quota_retries, backoff,
                            )
                            time.sleep(backoff)
                            continue  # retry the same page/token, not a new page

                        if status not in _OK_STATUSES:
                            # Unrecognized status — log once and treat this
                            # page as empty rather than guessing.
                            logger.debug(
                                "google_places_unknown_status lat=%s lon=%s status=%s",
                                lat, lon, status,
                            )

                        for place in data.get("results", []):
                            record = self._convert_place(place)
                            if record:
                                all_results.append(record)

                        next_page_token = data.get("next_page_token")
                        break  # move to next page (or stop, below)

                    except GoogleQuotaExhausted:
                        raise
                    except Exception as exc:
                        logger.debug(
                            "google_places_query_failed lat=%s lon=%s error=%s",
                            lat, lon, exc,
                        )
                        next_page_token = None
                        break

                if not next_page_token:
                    break

                time.sleep(self.PAGE_DELAY_SECONDS)

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

            if _NON_RESTAURANT_TYPES.intersection(types):
                return None

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
