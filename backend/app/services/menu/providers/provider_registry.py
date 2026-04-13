from __future__ import annotations

import logging
import time
from typing import Callable, Dict, List, Optional

from app.services.menu.contracts import ExtractedMenuItem
from app.services.menu.providers.provider_normalizer import normalize_items


# =========================================================
# IMPORT EXTRACTORS
# =========================================================

from app.services.menu.providers.toast_direct_extractor import extract_toast_direct
from app.services.menu.providers.clover_direct_extractor import extract_clover_direct
from app.services.menu.providers.popmenu_direct_extractor import extract_popmenu_direct

from app.services.menu.providers.toast_extractor import extract_toast_menu
from app.services.menu.providers.square_extractor import extract_square_menu
from app.services.menu.providers.popmenu_extractor import extract_popmenu_menu
from app.services.menu.providers.clover_extractor import extract_clover_menu
from app.services.menu.providers.chownow_extractor import extract_chownow_menu
from app.services.menu.providers.olo_extractor import extract_olo_menu


logger = logging.getLogger(__name__)


ProviderExtractor = Callable[[str, Optional[str]], List[ExtractedMenuItem]]


# =========================================================
# CONFIG
# =========================================================

MAX_ITEMS = 1500
MAX_EXTRACTOR_TIME = 5.0
MIN_VALID_ITEMS = 2


# =========================================================
# REGISTRY (ORDER = PRIORITY)
# =========================================================

_PROVIDER_REGISTRY: Dict[str, List[ProviderExtractor]] = {
    "toast": [
        extract_toast_direct,
        extract_toast_menu,
    ],
    "clover": [
        extract_clover_direct,
        extract_clover_menu,
    ],
    "popmenu": [
        extract_popmenu_direct,
        extract_popmenu_menu,
    ],
    "square": [
        extract_square_menu,
    ],
    "chownow": [
        extract_chownow_menu,
    ],
    "olo": [
        extract_olo_menu,
    ],
}


# =========================================================
# HELPERS
# =========================================================

def _normalize_provider(provider: Optional[str]) -> str:
    if not provider:
        return ""
    return provider.strip().lower()


def _is_valid_result(items: List[ExtractedMenuItem]) -> bool:
    return bool(items) and len(items) >= MIN_VALID_ITEMS


# =========================================================
# PUBLIC API
# =========================================================

def get_provider_extractors(provider: Optional[str]) -> List[ProviderExtractor]:

    provider_key = _normalize_provider(provider)

    if not provider_key:
        return []

    return _PROVIDER_REGISTRY.get(provider_key, [])


def extract_with_fallback(
    provider: Optional[str],
    url: str,
    html: Optional[str] = None,
) -> List[ExtractedMenuItem]:

    provider_key = _normalize_provider(provider)

    if not provider_key:
        return []

    extractors = _PROVIDER_REGISTRY.get(provider_key, [])

    if not extractors:
        logger.debug("no_provider_extractors provider=%s", provider_key)
        return []

    best_result: List[ExtractedMenuItem] = []
    best_count = 0

    for extractor in extractors:

        extractor_name = getattr(extractor, "__name__", "unknown")
        start = time.time()

        try:

            result = extractor(url, html)

            elapsed = time.time() - start

            if elapsed > MAX_EXTRACTOR_TIME:
                logger.warning(
                    "provider_extractor_slow provider=%s extractor=%s time=%s",
                    provider_key,
                    extractor_name,
                    round(elapsed, 2),
                )

            if not result:
                continue

            normalized = normalize_items(result, provider=provider_key)

            if not _is_valid_result(normalized):
                continue

            count = len(normalized)

            logger.info(
                "provider_extractor_result provider=%s extractor=%s count=%s",
                provider_key,
                extractor_name,
                count,
            )

            # -------------------------------------------------
            # BEST RESULT SELECTION (not just first success)
            # -------------------------------------------------

            if count > best_count:
                best_result = normalized
                best_count = count

            # early exit if very strong result
            if count >= 20:
                break

        except Exception as exc:
            logger.debug(
                "provider_extractor_failed provider=%s extractor=%s error=%s",
                provider_key,
                extractor_name,
                exc,
            )
            continue

    if best_result:
        logger.info(
            "provider_final_selection provider=%s count=%s",
            provider_key,
            len(best_result),
        )
        return best_result[:MAX_ITEMS]

    logger.debug("provider_all_extractors_failed provider=%s", provider_key)
    return []


def has_provider_extractor(provider: Optional[str]) -> bool:
    return len(get_provider_extractors(provider)) > 0


def list_supported_providers() -> List[str]:
    return sorted(_PROVIDER_REGISTRY.keys())