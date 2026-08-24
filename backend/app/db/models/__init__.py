from __future__ import annotations

# ---------------------------------------------------------
# SQLAlchemy Base
# ---------------------------------------------------------

from .base import Base


# ---------------------------------------------------------
# MODEL REGISTRY LOADER (PRODUCTION LOCKED)
# ---------------------------------------------------------

# ----- Core Domain -----
from .city import City
from .category import Category
from .place import Place
from .place_categories import place_categories

# ----- Media Layer -----
from .place_image import PlaceImage
from .place_image_fetch_log import PlaceImageFetchLog

# ----- Truth & Claims Layer -----
from .place_claim import PlaceClaim
from .place_truth import PlaceTruth

# ----- Discovery Layer -----
from .discovery_candidate import DiscoveryCandidate

# ----- Menu Layer -----
from .menu_item import MenuItem
from .menu_source import MenuSource
from .menu_snapshot import MenuSnapshot
from .menu_submission import MenuSubmission

# ----- Signals / Jobs Layer -----
from .place_signal import PlaceSignal
from .enrichment_job import EnrichmentJob

# ----- Feed Layer -----
from .place_feed_snapshot import PlaceFeedSnapshot

# ----- Ranking Layer -----
from .city_place_ranking import CityPlaceRanking

# ----- Hit List Layer -----
from .hitlist_save import HitlistSave
from .hitlist_suggestion import HitlistSuggestion
from .hitlist_dedup_key import HitlistDedupKey

# ----- Share-to-CRAVE Layer -----
from .crave_item import CraveItem

# ----- Ops / Observability Layer -----
from .job_run import JobRun

# ----- Social / Identity Layer -----
from .user_profile import UserProfile
from .user_follow import UserFollow
from .user_block import UserBlock
from .place_ranking import PlaceRanking
from .activity_event import ActivityEvent
from .user_streak import UserStreak

# ----- Moderation Layer -----
from .image_report import ImageReport
from .video_report import VideoReport

# ----- Video Layer -----
from .video_template import VideoTemplate
from .place_video import PlaceVideo

# ----- Notifications Layer -----
from .device_push_token import DevicePushToken


# ---------------------------------------------------------
# EXPORTS (STRICT + COMPLETE)
# ---------------------------------------------------------

__all__ = [
    "Base",

    # Core
    "City",
    "Category",
    "Place",
    "place_categories",

    # Media
    "PlaceImage",
    "PlaceImageFetchLog",

    # Truth
    "PlaceClaim",
    "PlaceTruth",

    # Discovery
    "DiscoveryCandidate",

    # Menu
    "MenuItem",
    "MenuSource",
    "MenuSnapshot",
    "MenuSubmission",

    # Signals / Jobs
    "PlaceSignal",
    "EnrichmentJob",

    # Feed
    "PlaceFeedSnapshot",

    # Ranking
    "CityPlaceRanking",

    # Hit List
    "HitlistSave",
    "HitlistSuggestion",
    "HitlistDedupKey",

    # Share-to-CRAVE
    "CraveItem",

    # Ops / Observability
    "JobRun",

    # Social / Identity
    "UserProfile",
    "UserFollow",
    "PlaceRanking",
    "ActivityEvent",

    # Moderation
    "ImageReport",
    "VideoReport",

    # Notifications
    "DevicePushToken",
]