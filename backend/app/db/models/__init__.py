from __future__ import annotations

from .base import Base

from .city import City
from .category import Category
from .place import Place
from .place_categories import place_categories

from .place_image import PlaceImage
from .place_image_fetch_log import PlaceImageFetchLog

from .place_claim import PlaceClaim
from .place_truth import PlaceTruth

from .discovery_candidate import DiscoveryCandidate

from .menu_item import MenuItem
from .menu_source import MenuSource
from .menu_snapshot import MenuSnapshot
from .menu_submission import MenuSubmission

from .place_signal import PlaceSignal
from .enrichment_job import EnrichmentJob

from .place_feed_snapshot import PlaceFeedSnapshot
from .city_place_ranking import CityPlaceRanking

from .hitlist_save import HitlistSave
from .hitlist_suggestion import HitlistSuggestion
from .hitlist_dedup_key import HitlistDedupKey
from .crave_item import CraveItem
from .job_run import JobRun

from .user_profile import UserProfile
from .user_follow import UserFollow
from .user_block import UserBlock
from .place_ranking import PlaceRanking
from .visit_evidence import VisitEvidence
from .activity_event import ActivityEvent
from .user_streak import UserStreak

from .image_report import ImageReport
from .video_report import VideoReport
from .place_report import PlaceReport

from .video_template import VideoTemplate
from .place_video import PlaceVideo

# Native Posting V2 orchestration. Media and visit evidence remain separate
# authorities; FoodContribution coordinates the user's explicit log/post.
from .food_contribution import FoodContribution

from .device_push_token import DevicePushToken
from .recommendation_event import RecommendationEvent


__all__ = [
    "Base",
    "City",
    "Category",
    "Place",
    "place_categories",
    "PlaceImage",
    "PlaceImageFetchLog",
    "PlaceClaim",
    "PlaceTruth",
    "DiscoveryCandidate",
    "MenuItem",
    "MenuSource",
    "MenuSnapshot",
    "MenuSubmission",
    "PlaceSignal",
    "EnrichmentJob",
    "PlaceFeedSnapshot",
    "CityPlaceRanking",
    "HitlistSave",
    "HitlistSuggestion",
    "HitlistDedupKey",
    "CraveItem",
    "JobRun",
    "UserProfile",
    "UserFollow",
    "UserBlock",
    "PlaceRanking",
    "VisitEvidence",
    "ActivityEvent",
    "UserStreak",
    "ImageReport",
    "VideoReport",
    "PlaceReport",
    "VideoTemplate",
    "PlaceVideo",
    "FoodContribution",
    "DevicePushToken",
    "RecommendationEvent",
]
