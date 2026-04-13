from __future__ import annotations

from enum import Enum
from typing import Optional


class MenuSourceType(str, Enum):

    # Structured provider APIs (Toast, Square, Olo, etc.)
    PROVIDER_API = "provider_api"

    # Official restaurant website HTML
    OFFICIAL_HTML = "official_html"

    # HTML discovered through scraping or heuristics
    SCRAPED_HTML = "scraped_html"

    # PDF menu
    PDF = "pdf"


    # -----------------------------------------------------
    # Internal constants
    # -----------------------------------------------------

    _PRIORITY_MAP = {
        PROVIDER_API: 100,
        OFFICIAL_HTML: 80,
        SCRAPED_HTML: 60,
        PDF: 40,
    }

    _ALIASES = {
        "provider": PROVIDER_API,
        "providerapi": PROVIDER_API,
        "official": OFFICIAL_HTML,
        "html": OFFICIAL_HTML,
        "scraped": SCRAPED_HTML,
        "pdfmenu": PDF,
    }


    # -----------------------------------------------------
    # Parsing helpers
    # -----------------------------------------------------

    @classmethod
    def from_str(cls, value: Optional[str]) -> Optional["MenuSourceType"]:
        """
        Safely convert string → enum.
        """

        if not value:
            return None

        value = value.strip().lower()

        # direct match
        for member in cls:
            if member.value == value:
                return member

        # alias match
        if value in cls._ALIASES:
            return cls._ALIASES[value]

        return None


    # -----------------------------------------------------
    # Type helpers
    # -----------------------------------------------------

    def is_html(self) -> bool:
        return self in {
            MenuSourceType.OFFICIAL_HTML,
            MenuSourceType.SCRAPED_HTML,
        }

    def is_provider(self) -> bool:
        return self == MenuSourceType.PROVIDER_API

    def is_pdf(self) -> bool:
        return self == MenuSourceType.PDF

    def is_structured(self) -> bool:
        """
        Structured sources are typically higher quality.
        """

        return self in {
            MenuSourceType.PROVIDER_API,
        }


    # -----------------------------------------------------
    # Ranking priority
    # -----------------------------------------------------

    def priority(self) -> int:
        """
        Higher = better source for menu extraction.
        """

        return self._PRIORITY_MAP.get(self, 0)


    # -----------------------------------------------------
    # Logging helper
    # -----------------------------------------------------

    def __str__(self) -> str:
        return self.value