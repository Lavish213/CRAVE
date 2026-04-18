from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.routes.places import router as places_router
from app.api.v1.routes.search import router as search_router
from app.api.v1.routes.map import router as map_router
from app.api.v1.routes.place_detail_router import router as place_detail_router
from app.api.v1.routes.categories import router as categories_router
from app.api.v1.routes.cities import router as cities_router
from app.api.routes.menus import router as menus_router
from app.api.v1.routes.hitlist import router as hitlist_router
from app.api.v1.routes.trending import router as trending_router
from app.api.v1.routes.signals import router as signals_router
from app.api.v1.routes.enrichment import router as enrichment_router
from app.api.v1.routes.enrichment import router_coverage as coverage_router
from app.api.v1.routes.share import router as share_router
from app.api.v1.routes.craves import router as craves_router
from app.api.v1.routes.image import router as image_router
from app.api.v1.routes.saves import router as saves_router

router = APIRouter()

router.include_router(image_router)
router.include_router(saves_router)
router.include_router(places_router)
router.include_router(menus_router)
router.include_router(search_router)
router.include_router(map_router)
router.include_router(place_detail_router)
router.include_router(categories_router)
router.include_router(cities_router)
router.include_router(hitlist_router)
router.include_router(trending_router)
router.include_router(signals_router)
router.include_router(enrichment_router)
router.include_router(coverage_router)
router.include_router(share_router)
router.include_router(craves_router)