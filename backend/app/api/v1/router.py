from fastapi import APIRouter
from app.api.v1.context import router as context_router
from app.api.v1.database import router as database_router
from app.api.v1.health import router as health_router
from app.api.v1.repository import router as repository_router
from app.api.v1.context_retrieval import (
    router as context_retrieval_router,
)

from app.api.v1.hybrid_context import (
    router as hybrid_context_router,
)
from app.api.v1.context_assembly import (
    router as context_assembly_router,
)
api_router = APIRouter()

api_router.include_router(health_router)
api_router.include_router(database_router)
api_router.include_router(repository_router)
api_router.include_router(context_router)
api_router.include_router(
    context_retrieval_router
)
api_router.include_router(
    hybrid_context_router
)
api_router.include_router(
    context_assembly_router
)