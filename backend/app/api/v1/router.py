from fastapi import APIRouter

from app.api.v1.database import router as database_router
from app.api.v1.health import router as health_router
from app.api.v1.repository import router as repository_router


api_router = APIRouter()

api_router.include_router(health_router)
api_router.include_router(database_router)
api_router.include_router(repository_router)