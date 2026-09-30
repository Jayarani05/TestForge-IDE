from fastapi import APIRouter
from app.api.v1.context import router as context_router
from app.api.v1.database import router as database_router
from app.api.v1.health import router as health_router
from app.api.v1.repository import router as repository_router
from app.api.v1.context_retrieval import (
    router as context_retrieval_router,
)

from app.api.v1.agents import (
    router as agents_router,
)

from app.api.v1.hybrid_context import (
    router as hybrid_context_router,
)
from app.api.v1.context_assembly import (
    router as context_assembly_router,
)
from app.api.v1.providers import (
    router as providers_router,
)

from app.api.v1.test_generation import router as test_generation_router
from app.api.v1.execution import router as execution_router
from app.api.v1.failure_analysis import (
    router as failure_analysis_router,
)
from app.api.v1.self_healing import (
    router as self_healing_router,
)

from app.api.v1.analytics import router as analytics_router
api_router = APIRouter()

from app.api.v1.intelligent_testing import (
    router as intelligent_testing_router,
)

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
api_router.include_router(
    agents_router
)

api_router.include_router(
    providers_router
)

api_router.include_router(
    test_generation_router
)

api_router.include_router(execution_router)

api_router.include_router(
    failure_analysis_router
)

api_router.include_router(
    self_healing_router
)

api_router.include_router(analytics_router)

api_router.include_router(intelligent_testing_router)