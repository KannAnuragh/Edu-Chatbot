"""
API v1 — Main Router.

Aggregates all v1 route modules.
"""

from fastapi import APIRouter
from api.v1.auth import router as auth_router
from api.v1.courses import router as courses_router
from api.v1.documents import router as documents_router
from api.v1.chat import router as chat_router
from api.v1.stats import router as stats_router

router = APIRouter(prefix="/api/v1")

router.include_router(auth_router)
router.include_router(courses_router)
router.include_router(documents_router)
router.include_router(chat_router)
router.include_router(stats_router)

