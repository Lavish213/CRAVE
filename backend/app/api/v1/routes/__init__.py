from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.routes.places import router as places_router
from app.api.v1.routes.search import router as search_router
from app.api.v1.routes.map import router as map_router
from app.api.v1.routes.place_detail_router import router as place_detail_router
from app.api.routes.menus import router as menus_router

router = APIRouter()



router.include_router(places_router)
router.include_router(menus_router)
router.include_router(search_router)
router.include_router(map_router)
router.include_router(place_detail_router)