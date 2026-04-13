from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Optional

from app.services.entity.normalize_name import normalize_name
from app.services.entity.normalize_address import normalize_address


logger = logging.getLogger(__name__)


MAX_CANDIDATES = 5000


class CandidateBuilder:
    """
    Converts raw discovery records into normalized restaurant candidates.

    Sources may include:
        - OSM
        - permits
        - inspections
        - openaddresses
        - schema.org website data
    """

    # -----------------------------------------------------
    # Public API
    # -----------------------------------------------------

    def build_candidates(
        self,
        records: Iterable[Dict[str, Any]],
        *,
        source: Optional[str] = None,
    ) -> List[Dict[str, Any]]:

        candidates: List[Dict[str, Any]] = []

        for record in records:

            try:

                candidate = self._build_candidate(record, source=source)

                if not candidate:
                    continue

                candidates.append(candidate)

            except Exception as exc:

                logger.debug(
                    "candidate_build_failed source=%s error=%s",
                    source,
                    exc,
                )

            if len(candidates) >= MAX_CANDIDATES:
                break

        logger.info(
            "candidates_built count=%s source=%s",
            len(candidates),
            source,
        )

        return candidates

    # -----------------------------------------------------
    # Candidate construction
    # -----------------------------------------------------

    def _build_candidate(
        self,
        record: Dict[str, Any],
        *,
        source: Optional[str],
    ) -> Optional[Dict[str, Any]]:

        name = record.get("name")
        address = record.get("address")

        if not name:
            return None

        normalized_name = normalize_name(name)

        normalized_address = normalize_address(address)

        lat = record.get("lat") or record.get("latitude")
        lon = record.get("lon") or record.get("lng") or record.get("longitude")

        candidate = {
            "name": name,
            "normalized_name": normalized_name,
            "address": address,
            "normalized_address": normalized_address,
            "lat": lat,
            "lon": lon,
            "phone": record.get("phone"),
            "website": record.get("website"),
            "source": source,
            "raw": record,
        }

        return candidate