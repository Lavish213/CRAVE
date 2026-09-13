"""
Universal-link (https://crave.app/...) support.

Mounted at the domain root in app/main.py (no /api prefix) -- both the two
platform verification files and the human-facing fallback pages must live
at exactly the paths iOS/Android expect, not under an API version prefix.

Three responsibilities:
  1. Serve the two files iOS/Android fetch once (at app-install time, not
     per-link-tap) to verify this domain is allowed to open the app:
     GET /.well-known/apple-app-site-association
     GET /.well-known/assetlinks.json
  2. Serve a real HTML page at the same paths app.json's associatedDomains/
     intentFilters declare (/place/{id}, /rank/{id}, /user/{id}), for the
     one case universal links can't route around: the recipient doesn't
     have the app installed, so the OS opens the URL as a plain web page
     instead. Without this, that's a 404 -- the whole reason PR #225's
     share-link work was flagged as "does nothing for anyone without the
     app already installed."
  3. Never leak data the app itself won't show. /user/{id} reuses the
     same is_public gate profile.py's own public-profile endpoint uses --
     a private profile gets the same generic branded page as a bad id,
     not a data leak through a back door this session's own privacy
     retirement (PR #266) didn't anticipate.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models.place import Place
from app.services.query.place_image_visibility_query import get_primary_image_urls_bulk
from app.services.profile.profile_service import get_profile

router = APIRouter()

# --- iOS / Android app-verification identifiers ---------------------------
#
# Both of these are placeholders. Until they're replaced with the real
# values, the two files below are served but iOS/Android will silently
# refuse to verify this domain -- a tapped https://crave.app/place/... link
# opens Safari/Chrome to the fallback page below instead of the app, with
# no visible error anywhere. Real values:
#   iOS Team ID:  Apple Developer > Membership, or `eas credentials -p ios`
#   Android SHA-256: `cd frontend && eas credentials --platform android`
#     (use the Play Console "App signing key certificate" fingerprint, not
#     the upload-key one, once Play App Signing is enabled)
_APPLE_TEAM_ID = "REPLACE_WITH_APPLE_TEAM_ID"
_IOS_APP_ID = f"{_APPLE_TEAM_ID}.com.crave.app"
_ANDROID_PACKAGE = "com.crave.app"
_ANDROID_SHA256_FINGERPRINT = "REPLACE_WITH_ANDROID_SHA256_FINGERPRINT"

# Paths app.json's associatedDomains/intentFilters already declare -- keep
# these two lists in sync with that file.
_ASSOCIATED_PATHS = ["/place/*", "/rank/*", "/user/*"]


@router.get("/.well-known/apple-app-site-association")
def apple_app_site_association() -> dict:
    return {
        "applinks": {
            "apps": [],
            "details": [
                {
                    "appID": _IOS_APP_ID,
                    "paths": _ASSOCIATED_PATHS,
                }
            ],
        }
    }


@router.get("/.well-known/assetlinks.json")
def android_asset_links() -> list[dict]:
    return [
        {
            "relation": ["delegate_permission/common.handle_all_urls"],
            "target": {
                "namespace": "android_app",
                "package_name": _ANDROID_PACKAGE,
                "sha256_cert_fingerprints": [_ANDROID_SHA256_FINGERPRINT],
            },
        }
    ]


def _render_landing_page(title: str, subtitle: str, image_url: str | None) -> str:
    image_tag = (
        f'<img src="{image_url}" alt="" style="width:100%;max-width:420px;'
        f'border-radius:16px;margin-top:24px;object-fit:cover;" />'
        if image_url
        else ""
    )
    og_image = f'<meta property="og:image" content="{image_url}" />' if image_url else ""
    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{title} — CRAVE</title>
<meta property="og:title" content="{title}" />
<meta property="og:description" content="{subtitle}" />
{og_image}
<style>
  body {{
    background: #050807; color: #FFF8EF;
    font-family: -apple-system, system-ui, sans-serif;
    display: flex; flex-direction: column; align-items: center;
    justify-content: center; min-height: 100vh; margin: 0; padding: 24px;
    text-align: center;
  }}
  h1 {{ color: #F4A845; letter-spacing: 2px; font-size: 28px; margin-bottom: 4px; }}
  h2 {{ font-size: 20px; margin: 8px 0 4px; }}
  p {{ color: #B8B0A6; font-size: 15px; max-width: 320px; }}
</style>
</head>
<body>
  <h1>CRAVE</h1>
  <h2>{title}</h2>
  <p>{subtitle}</p>
  {image_tag}
  <p style="margin-top:32px;">CRAVE is coming soon. Open this link on a device with the app installed to jump right in.</p>
</body>
</html>"""


def _place_preview(db: Session, place_id: str) -> tuple[str, str | None]:
    """(subtitle-safe name, image url) for a place, or a generic fallback."""
    place = (
        db.query(Place.id, Place.name)
        .filter(Place.id == place_id, Place.is_active.is_(True))
        .first()
    )
    if place is None:
        return "This link may be out of date.", None
    image_urls = get_primary_image_urls_bulk(db, place_ids=[place.id])
    return place.name, image_urls.get(place.id)


@router.get("/place/{place_id}", response_class=HTMLResponse)
def place_landing_page(place_id: str, db: Session = Depends(get_db)) -> HTMLResponse:
    name, image_url = _place_preview(db, place_id)
    return HTMLResponse(_render_landing_page(name, "See this place on CRAVE.", image_url))


@router.get("/rank/{place_id}", response_class=HTMLResponse)
def rank_landing_page(place_id: str, db: Session = Depends(get_db)) -> HTMLResponse:
    name, image_url = _place_preview(db, place_id)
    return HTMLResponse(_render_landing_page(name, "Rank this place on CRAVE.", image_url))


@router.get("/user/{user_id}", response_class=HTMLResponse)
def user_landing_page(user_id: str, db: Session = Depends(get_db)) -> HTMLResponse:
    # Same is_public gate as profile.py's own get_public_profile -- a
    # private profile gets the identical generic page as a bad id. This
    # page has no session/API-key context to check "is this the owner
    # viewing their own profile" the way that endpoint does, so it can
    # only ever show the public case, never the owner-viewing-self case --
    # correct here, since a stranger clicking a shared link is never the
    # owner.
    profile = get_profile(db, user_id)
    if profile is None or not profile.is_public:
        return HTMLResponse(_render_landing_page("CRAVE profile", "This link may be out of date.", None))
    name = profile.display_name or "A CRAVE user"
    return HTMLResponse(_render_landing_page(name, f"See {name}'s CRAVE profile.", profile.avatar_url))
