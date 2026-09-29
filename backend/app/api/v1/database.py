from fastapi import APIRouter
from sqlalchemy import text

from app.core.database import AsyncSessionLocal


router = APIRouter(
    prefix="/database",
    tags=["Database"],
)


@router.get("/health")
async def database_health() -> dict[str, str]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("SELECT 1"))
        value = result.scalar_one()

    if value == 1:
        return {
            "status": "ok",
            "database": "PostgreSQL",
        }

    return {
        "status": "error",
        "database": "PostgreSQL",
    }