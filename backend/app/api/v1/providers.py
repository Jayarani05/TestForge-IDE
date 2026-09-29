from fastapi import APIRouter

from app.agents import LLMOrchestrator


router = APIRouter(
    prefix="/providers",
    tags=["Providers"],
)


orchestrator = LLMOrchestrator()


@router.get("/status")
async def provider_status() -> dict[str, object]:
    """
    Return the currently available TestForge
    LLM providers.
    """

    return {
        "providers": (
            orchestrator.provider_status()
        )
    }