# app/services/account/account_deletion_service.py
"""
Account deletion for CRAVE.

A deletion request must remove data that is still associated with the user
from CRAVE's database, remove user-uploaded media objects from R2, and delete
the Supabase Auth identity. The operation is intentionally retryable:

- R2 object deletion happens first. If it fails, database/auth deletion does
  not proceed, so the request can be retried without falsely reporting
  completion. R2 DELETE is idempotent, so partially deleted object sets are
  safe to retry.
- App-side rows are then deleted in one database transaction.
- Supabase Auth deletion happens last. If that upstream call fails, the route
  reports failure and keeps the session alive so the user can retry; app-side
  deletion is idempotent, so a later retry can safely finish the auth half.

Public place facts that no longer contain a user identifier are not swept just
because they originated from a user contribution. For example, an approved
menu submission may have materialized anonymous PlaceClaim facts; those rows
are not personal data once they no longer carry the deleted account id.
"""
from __future__ import annotations

import logging
import os
from typing import Dict, Iterable

import requests
from sqlalchemy.orm import Session

from app.db.models.activity_event import ActivityEvent
from app.db.models.crave_item import CraveItem
from app.db.models.device_push_token import DevicePushToken
from app.db.models.hitlist_dedup_key import HitlistDedupKey
from app.db.models.hitlist_save import HitlistSave
from app.db.models.hitlist_suggestion import HitlistSuggestion
from app.db.models.image_report import ImageReport
from app.db.models.menu_submission import MenuSubmission
from app.db.models.place_image import PlaceImage
from app.db.models.place_ranking import PlaceRanking
from app.db.models.place_video import PlaceVideo
from app.db.models.recommendation_event import RecommendationEvent
from app.db.models.user_block import UserBlock
from app.db.models.user_follow import UserFollow
from app.db.models.user_profile import UserProfile
from app.db.models.user_streak import UserStreak
from app.db.models.video_report import VideoReport
from app.services.upload.r2_client import delete_object

logger = logging.getLogger(__name__)

_TIMEOUT = 15


def _delete_supabase_auth_user(user_id: str) -> bool:
    """Delete the Supabase Auth identity, returning False on upstream failure."""
    base_url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()

    if not base_url or not service_key:
        logger.error(
            "account_deletion_supabase_not_configured user_id=%s",
            user_id,
        )
        return False

    try:
        resp = requests.delete(
            f"{base_url}/auth/v1/admin/users/{user_id}",
            headers={
                "apikey": service_key,
                "Authorization": f"Bearer {service_key}",
            },
            timeout=_TIMEOUT,
        )
    except Exception as exc:
        logger.error(
            "account_deletion_supabase_request_failed user_id=%s error=%s",
            user_id,
            exc,
        )
        return False

    if resp.status_code not in (200, 204):
        logger.error(
            "account_deletion_supabase_upstream_error user_id=%s status=%s",
            user_id,
            resp.status_code,
        )
        return False

    return True


def _media_keys(images: Iterable[PlaceImage], videos: Iterable[PlaceVideo]) -> list[str]:
    keys: list[str] = []
    for media in [*images, *videos]:
        for key in (media.orig_key, media.processed_key, media.thumb_key):
            if key:
                keys.append(key)
    return list(dict.fromkeys(keys))


def _delete_r2_objects(keys: Iterable[str], user_id: str) -> bool:
    """Delete all owned R2 objects. Fail closed so callers can retry safely."""
    try:
        for key in keys:
            delete_object(key)
    except Exception as exc:
        logger.error(
            "account_deletion_storage_failed user_id=%s key=%s error=%s",
            user_id,
            key,
            exc,
        )
        return False
    return True


def delete_account(db: Session, user_id: str) -> Dict[str, bool]:
    """Delete all user-associated CRAVE data and the Supabase Auth identity."""
    owned_images = db.query(PlaceImage).filter(PlaceImage.uploaded_by == user_id).all()
    owned_videos = db.query(PlaceVideo).filter(PlaceVideo.uploaded_by == user_id).all()

    storage_deleted = _delete_r2_objects(_media_keys(owned_images, owned_videos), user_id)
    if not storage_deleted:
        return {
            "app_data_deleted": False,
            "storage_deleted": False,
            "supabase_account_deleted": False,
            "complete": False,
        }

    image_ids = [row.id for row in owned_images]
    video_ids = [row.id for row in owned_videos]

    try:
        # Reports authored by this user are personal activity. Reports against
        # the user's own media are also removed before the media rows themselves
        # so behavior does not depend on DB-specific FK cascade settings.
        image_report_filter = ImageReport.reporter_id == user_id
        if image_ids:
            image_report_filter = image_report_filter | ImageReport.image_id.in_(image_ids)
        db.query(ImageReport).filter(image_report_filter).delete(synchronize_session=False)

        video_report_filter = VideoReport.reporter_id == user_id
        if video_ids:
            video_report_filter = video_report_filter | VideoReport.video_id.in_(video_ids)
        db.query(VideoReport).filter(video_report_filter).delete(synchronize_session=False)

        db.query(ActivityEvent).filter(
            (ActivityEvent.user_id == user_id) | (ActivityEvent.target_user_id == user_id)
        ).delete(synchronize_session=False)
        db.query(RecommendationEvent).filter(
            RecommendationEvent.user_id == user_id
        ).delete(synchronize_session=False)
        db.query(PlaceRanking).filter(PlaceRanking.user_id == user_id).delete(
            synchronize_session=False
        )
        db.query(HitlistSave).filter(HitlistSave.user_id == user_id).delete(
            synchronize_session=False
        )
        db.query(HitlistSuggestion).filter(HitlistSuggestion.user_id == user_id).delete(
            synchronize_session=False
        )
        db.query(HitlistDedupKey).filter(HitlistDedupKey.user_id == user_id).delete(
            synchronize_session=False
        )
        db.query(CraveItem).filter(CraveItem.submitted_by == user_id).delete(
            synchronize_session=False
        )
        db.query(MenuSubmission).filter(MenuSubmission.submitted_by == user_id).delete(
            synchronize_session=False
        )
        db.query(DevicePushToken).filter(DevicePushToken.user_id == user_id).delete(
            synchronize_session=False
        )
        db.query(UserStreak).filter(UserStreak.user_id == user_id).delete(
            synchronize_session=False
        )

        # Remove owned media rows after storage/report cleanup. Also anonymize
        # moderation-review references where the deleted account was a reviewer.
        db.query(PlaceImage).filter(PlaceImage.reviewed_by == user_id).update(
            {PlaceImage.reviewed_by: None}, synchronize_session=False
        )
        db.query(PlaceVideo).filter(PlaceVideo.reviewed_by == user_id).update(
            {PlaceVideo.reviewed_by: None}, synchronize_session=False
        )
        db.query(MenuSubmission).filter(MenuSubmission.reviewed_by == user_id).update(
            {MenuSubmission.reviewed_by: None}, synchronize_session=False
        )
        db.query(PlaceImage).filter(PlaceImage.uploaded_by == user_id).delete(
            synchronize_session=False
        )
        db.query(PlaceVideo).filter(PlaceVideo.uploaded_by == user_id).delete(
            synchronize_session=False
        )

        db.query(UserFollow).filter(
            (UserFollow.follower_id == user_id) | (UserFollow.followee_id == user_id)
        ).delete(synchronize_session=False)
        db.query(UserBlock).filter(
            (UserBlock.blocker_id == user_id) | (UserBlock.blocked_id == user_id)
        ).delete(synchronize_session=False)
        db.query(UserProfile).filter(UserProfile.id == user_id).delete(
            synchronize_session=False
        )

        db.commit()
    except Exception:
        db.rollback()
        logger.exception("account_deletion_database_failed user_id=%s", user_id)
        return {
            "app_data_deleted": False,
            "storage_deleted": True,
            "supabase_account_deleted": False,
            "complete": False,
        }

    supabase_account_deleted = _delete_supabase_auth_user(user_id)
    complete = supabase_account_deleted

    logger.info(
        "account_deletion_complete user_id=%s app_data_deleted=true "
        "storage_deleted=true supabase_account_deleted=%s complete=%s",
        user_id,
        supabase_account_deleted,
        complete,
    )

    return {
        "app_data_deleted": True,
        "storage_deleted": True,
        "supabase_account_deleted": supabase_account_deleted,
        "complete": complete,
    }
