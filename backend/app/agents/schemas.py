from pydantic import BaseModel, Field

from app.agents.tasks import AgentTask


class AgentRequest(BaseModel):
    """Request sent to a TestForge AI agent."""

    task: AgentTask

    prompt: str = Field(
        ...,
        min_length=1,
    )

    provider: str = "auto"

    fallback_providers: list[str] = Field(
        default_factory=list
    )

    repository_path: str | None = None

    context: str | None = None

    temperature: float = 0.2

    max_tokens: int = 4096


class AgentResponse(BaseModel):
    """Response returned by a TestForge AI agent."""

    task: AgentTask

    provider: str

    model: str

    content: str

    input_tokens: int | None = None

    output_tokens: int | None = None