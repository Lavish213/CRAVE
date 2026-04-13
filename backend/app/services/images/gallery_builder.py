from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional


logger = logging.getLogger(__name__)


MAX_GALLERY_IMAGES = 9
MAX_BACKUP_IMAGES = 3

# 🔥 HARD FALLBACK (prevents empty UI cards)
FALLBACK_IMAGE_URL = "https://via.placeholder.com/800x600?text=No+Image"


class GalleryBuilder:
    """
    Builds the canonical gallery payload used by the image materializer.

    Guarantees
    ----------
    - exactly one primary image (never None in final output)
    - deterministic ordering
    - deduped urls
    - size limits enforced
    - safe fallback if no images exist
    """

    def build(
        self,
        *,
        place,
        candidates: List[dict],
    ) -> Dict[str, Any]:

        place_id = getattr(place, "id", None)

        try:

            primary: Optional[Dict[str, Any]] = None
            gallery: List[Dict[str, Any]] = []
            backup: List[Dict[str, Any]] = []

            seen_urls = set()

            # ---------------------------------------------------------
            # Build gallery
            # ---------------------------------------------------------

            for candidate in candidates or []:

                try:

                    url = self._clean_url(candidate.get("url"))

                    if not url or url in seen_urls:
                        continue

                    seen_urls.add(url)

                    entry = self._build_entry(candidate, url=url)

                    if not primary and candidate.get("is_primary"):
                        primary = entry

                    if len(gallery) < MAX_GALLERY_IMAGES:
                        gallery.append(entry)
                    elif len(backup) < MAX_BACKUP_IMAGES:
                        backup.append(entry)

                except Exception as exc:
                    logger.debug(
                        "gallery_candidate_failed place_id=%s error=%s",
                        place_id,
                        exc,
                    )

            # ---------------------------------------------------------
            # Primary resolution
            # ---------------------------------------------------------

            if not primary and gallery:
                primary = gallery[0]

            # 🔥 HARD FALLBACK (CRITICAL)
            if not primary:
                primary = self._fallback_entry()

                # ensure at least 1 image exists
                if not gallery:
                    gallery = [primary]

            # ensure primary is first
            gallery = self._ensure_primary_first(
                primary=primary,
                gallery=gallery,
            )

            logger.info(
                "gallery_complete place_id=%s gallery=%s backup=%s",
                place_id,
                len(gallery),
                len(backup),
            )

            return {
                "primary": primary,
                "gallery": gallery,
                "backup": backup,
                "total_candidates": len(seen_urls),
            }

        except Exception as exc:

            logger.error(
                "gallery_builder_failed place_id=%s error=%s",
                place_id,
                exc,
            )

            fallback = self._fallback_entry()

            return {
                "primary": fallback,
                "gallery": [fallback],
                "backup": [],
                "total_candidates": 0,
            }

    # ---------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------

    def _clean_url(self, url: Any) -> Optional[str]:
        if not url:
            return None

        try:
            url = str(url).strip()
        except Exception:
            return None

        return url or None

    def _ensure_primary_first(
        self,
        *,
        primary: Dict[str, Any],
        gallery: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:

        primary_url = primary.get("url")

        ordered: List[Dict[str, Any]] = [primary]

        for entry in gallery:
            if entry.get("url") == primary_url:
                continue
            ordered.append(entry)

        return ordered[:MAX_GALLERY_IMAGES]

    def _fallback_entry(self) -> Dict[str, Any]:
        return {
            "url": FALLBACK_IMAGE_URL,
            "source": "fallback",
            "width": None,
            "height": None,
            "score": 0.0,
            "context": "fallback",
            "metadata": {},
        }

    # ---------------------------------------------------------
    # Entry normalization
    # ---------------------------------------------------------

    def _build_entry(
        self,
        candidate: Dict,
        *,
        url: str,
    ) -> Dict[str, Any]:

        metadata = candidate.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}

        return {
            "url": url,
            "source": candidate.get("source"),
            "width": candidate.get("width"),
            "height": candidate.get("height"),
            "score": float(candidate.get("score") or 0.0),
            "context": candidate.get("context"),
            "metadata": metadata,
        }