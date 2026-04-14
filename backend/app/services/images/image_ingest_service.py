from __future__ import annotations

import logging
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.db.models.place import Place
from app.db.models.place_image import PlaceImage

from app.services.images.image_reader import ImageReader
from app.services.images.image_matcher import ImageMatcher
from app.services.images.image_deduper import ImageDeduper
from app.services.images.image_scorer import ImageScorer
from app.services.images.image_ranker import ImageRanker
from app.services.images.image_selector import ImageSelector
from app.services.images.gallery_builder import GalleryBuilder
from app.services.images.materialize_image_truth import MaterializeImageTruth


logger = logging.getLogger(__name__)


MAX_INPUT_IMAGES = 50
MAX_GALLERY_IMAGES = 10


class ImageIngestService:
    """
    Orchestrates the full image pipeline for a place.

    Flow
    ----
    place
      ↓
    read image candidates
      ↓
    normalize / match
      ↓
    dedupe
      ↓
    score
      ↓
    rank
      ↓
    select primary + gallery
      ↓
    materialize to place_images
    """

    def __init__(
        self,
        *,
        reader: Optional[ImageReader] = None,
        matcher: Optional[ImageMatcher] = None,
        deduper: Optional[ImageDeduper] = None,
        scorer: Optional[ImageScorer] = None,
        ranker: Optional[ImageRanker] = None,
        selector: Optional[ImageSelector] = None,
        gallery_builder: Optional[GalleryBuilder] = None,
        materializer: Optional[MaterializeImageTruth] = None,
    ) -> None:
        self.reader = reader or ImageReader()
        self.matcher = matcher or ImageMatcher()
        self.deduper = deduper or ImageDeduper()
        self.scorer = scorer or ImageScorer()
        self.ranker = ranker or ImageRanker()
        self.selector = selector or ImageSelector()
        self.gallery_builder = gallery_builder or GalleryBuilder()
        self.materializer = materializer or MaterializeImageTruth()

    def ingest_place_images(
        self,
        *,
        db: Session,
        place: Place,
        force_refresh: bool = False,
    ) -> List[PlaceImage]:

        place_id = getattr(place, "id", None)

        if not place_id:
            raise ValueError("place.id is required")

        if not force_refresh and self._has_existing_images(place):
            logger.debug(
                "image_ingest_skip_existing place_id=%s",
                place_id,
            )
            return list(getattr(place, "images", []) or [])

        logger.info(
            "image_ingest_start place_id=%s place_name=%s",
            place_id,
            getattr(place, "name", None),
        )

        raw_candidates = self._read_candidates(db=db, place=place)

        if not raw_candidates:
            logger.info(
                "image_ingest_no_candidates place_id=%s",
                place_id,
            )
            return []

        matched_candidates = self._match_candidates(
            place=place,
            candidates=raw_candidates,
        )

        if not matched_candidates:
            logger.info(
                "image_ingest_no_matched_candidates place_id=%s raw=%s",
                place_id,
                len(raw_candidates),
            )
            return []

        deduped_candidates = self._dedupe_candidates(
            place=place,
            candidates=matched_candidates,
        )

        if not deduped_candidates:
            logger.info(
                "image_ingest_no_deduped_candidates place_id=%s matched=%s",
                place_id,
                len(matched_candidates),
            )
            return []

        scored_candidates = self._score_candidates(
            place=place,
            candidates=deduped_candidates,
        )

        if not scored_candidates:
            logger.info(
                "image_ingest_no_scored_candidates place_id=%s deduped=%s",
                place_id,
                len(deduped_candidates),
            )
            return []

        ranked_candidates = self._rank_candidates(
            place=place,
            candidates=scored_candidates,
        )

        if not ranked_candidates:
            logger.info(
                "image_ingest_no_ranked_candidates place_id=%s scored=%s",
                place_id,
                len(scored_candidates),
            )
            return []

        selected_candidates = self._select_candidates(
            place=place,
            candidates=ranked_candidates,
        )

        if not selected_candidates:
            logger.info(
                "image_ingest_no_selected_candidates place_id=%s ranked=%s",
                place_id,
                len(ranked_candidates),
            )
            return []

        gallery_payload = self._build_gallery(
            place=place,
            candidates=selected_candidates,
        )

        images = self._materialize(
            db=db,
            place=place,
            gallery_payload=gallery_payload,
            force_refresh=force_refresh,
        )

        logger.info(
            "image_ingest_complete place_id=%s raw=%s matched=%s deduped=%s scored=%s ranked=%s selected=%s written=%s",
            place_id,
            len(raw_candidates),
            len(matched_candidates),
            len(deduped_candidates),
            len(scored_candidates),
            len(ranked_candidates),
            len(selected_candidates),
            len(images),
        )

        return images

    def ingest_places(
        self,
        *,
        db: Session,
        places: List[Place],
        force_refresh: bool = False,
    ) -> Dict[str, int]:

        processed = 0
        succeeded = 0
        failed = 0
        written = 0

        for place in places:
            processed += 1

            try:
                images = self.ingest_place_images(
                    db=db,
                    place=place,
                    force_refresh=force_refresh,
                )
                written += len(images)
                succeeded += 1

            except Exception as exc:
                failed += 1
                logger.exception(
                    "image_ingest_place_failed place_id=%s error=%s",
                    getattr(place, "id", None),
                    exc,
                )

        summary = {
            "processed": processed,
            "succeeded": succeeded,
            "failed": failed,
            "written": written,
        }

        logger.info(
            "image_ingest_batch_complete processed=%s succeeded=%s failed=%s written=%s",
            processed,
            succeeded,
            failed,
            written,
        )

        return summary

    # ---------------------------------------------------------
    # Internal stages
    # ---------------------------------------------------------

    def _has_existing_images(
        self,
        place: Place,
    ) -> bool:
        images = getattr(place, "images", None)
        return bool(images)

    def _read_candidates(
        self,
        *,
        place: Place,
        db=None,
    ) -> List[dict]:

        candidates = self.reader.read(place=place, db=db)

        if not candidates:
            return []

        return candidates[:MAX_INPUT_IMAGES]

    def _match_candidates(
        self,
        *,
        place: Place,
        candidates: List[dict],
    ) -> List[dict]:

        matched = self.matcher.match(
            place=place,
            candidates=candidates,
        )

        return matched or []

    def _dedupe_candidates(
        self,
        *,
        place: Place,
        candidates: List[dict],
    ) -> List[dict]:

        deduped = self.deduper.dedupe(
            place=place,
            candidates=candidates,
        )

        return deduped or []

    def _score_candidates(
        self,
        *,
        place: Place,
        candidates: List[dict],
    ) -> List[dict]:

        scored = self.scorer.score(
            place=place,
            candidates=candidates,
        )

        return scored or []

    def _rank_candidates(
        self,
        *,
        place: Place,
        candidates: List[dict],
    ) -> List[dict]:

        ranked = self.ranker.rank(
            place=place,
            candidates=candidates,
        )

        return ranked or []

    def _select_candidates(
        self,
        *,
        place: Place,
        candidates: List[dict],
    ) -> List[dict]:

        selected = self.selector.select(
            place=place,
            candidates=candidates,
            max_gallery_images=MAX_GALLERY_IMAGES,
        )

        return selected or []

    def _build_gallery(
        self,
        *,
        place: Place,
        candidates: List[dict],
    ) -> Dict[str, object]:

        gallery_payload = self.gallery_builder.build(
            place=place,
            candidates=candidates,
        )

        if not isinstance(gallery_payload, dict):
            raise RuntimeError("gallery_builder must return dict")

        return gallery_payload

    def _materialize(
        self,
        *,
        db: Session,
        place: Place,
        gallery_payload: Dict[str, object],
        force_refresh: bool,
    ) -> List[PlaceImage]:

        images = self.materializer.write(
            db=db,
            place=place,
            gallery_payload=gallery_payload,
            force_refresh=force_refresh,
        )

        return images or [] 