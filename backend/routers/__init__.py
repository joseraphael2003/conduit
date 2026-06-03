from fastapi import APIRouter
from routers.projects import projects_router
from routers.characters import characters_router
from routers.segments import segments_router
from routers.images import images_router

router = APIRouter(prefix="/api/v1")
router.include_router(projects_router)
router.include_router(characters_router)
router.include_router(segments_router)
router.include_router(images_router)
