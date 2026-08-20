from __future__ import annotations

from fastapi import APIRouter

# -------------------------
# Core Routes
# -------------------------
from app.api.v1.routes.places import router as places_router
from app.api.v1.routes.search import router as search_router
from app.api.v1.routes.map import router as map_router
from app.api.v1.routes.place_detail_router import router as place_detail_router
from app.api.v1.routes.categories import router as categories_router
from app.api.v1.routes.cities import router as cities_router
from app.api.v1.routes.hitlist import router as hitlist_router
from app.api.v1.routes.trending import router as trending_router
from app.api.v1.routes.signals import router as signals_router

# -------------------------
# User content (were fully built + JWT-secured but never registered here —
# the frontend has been calling /api/v1/saves (saves.ts) and /api/v1/craves
# (crave.ts) since before this fix, so those two were live 404s in prod)
# -------------------------
from app.api.v1.routes.saves import router as saves_router
from app.api.v1.routes.craves import router as craves_router
from app.api.v1.routes.share import router as share_router
from app.api.v1.routes.image import router as image_router
from app.api.v1.routes.nearby import router as nearby_router

# -------------------------
# Enrichment
# -------------------------
from app.api.v1.routes.enrichment import router as enrichment_router
from app.api.v1.routes.enrichment import router_coverage as coverage_router

# -------------------------
# Upload (REQUIRED)
# -------------------------
from app.api.v1.endpoints.upload import router as upload_router

# -------------------------
# Social / Identity / Ranking
# -------------------------
from app.api.v1.routes.profile import router as profile_router
from app.api.v1.routes.account import router as account_router
from app.api.v1.routes.follows import router as follows_router
from app.api.v1.routes.blocks import router as blocks_router
from app.api.v1.routes.rankings import router as rankings_router
from app.api.v1.routes.feed_social import router as feed_social_router
from app.api.v1.routes.leaderboard import router as leaderboard_router
from app.api.v1.routes.moderation import router as moderation_router
from app.api.v1.routes.menu_submissions import (
    router as menu_submissions_router,
    router_moderation as menu_submissions_moderation_router,
)
from app.api.v1.routes.debug import router as debug_router


# -------------------------
# API Router
# -------------------------
router = APIRouter()


# -------------------------
# Register Routes
# -------------------------
router.include_router(places_router)
router.include_router(search_router)
router.include_router(map_router)
router.include_router(place_detail_router)
router.include_router(categories_router)
router.include_router(cities_router)

router.include_router(hitlist_router)
router.include_router(trending_router)
router.include_router(signals_router)

router.include_router(saves_router)
router.include_router(craves_router)
router.include_router(share_router)
router.include_router(image_router)
router.include_router(nearby_router)

router.include_router(enrichment_router)
router.include_router(coverage_router)

# 🔥 THIS WAS MISSING
router.include_router(upload_router)

router.include_router(profile_router)
router.include_router(account_router)
router.include_router(follows_router)
router.include_router(blocks_router)
router.include_router(rankings_router)
router.include_router(feed_social_router)
router.include_router(leaderboard_router)
router.include_router(moderation_router)
router.include_router(menu_submissions_router)
router.include_router(menu_submissions_moderation_router)
router.include_router(debug_router)