from abc import ABC, abstractmethod

from pydantic import BaseModel


class LLMRequest(BaseModel):
    prompt: str
    system_prompt: str | None = None
    model: str | None = None
    temperature: float = 0.2
    max_tokens: int = 2048


class LLMResponse(BaseModel):
    provider: str
    model: str
    content: str
    input_tokens: int | None = None
    output_tokens: int | None = None


class LLMProvider(ABC):
    """Base interface for all LLM providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def default_model(self) -> str:
        raise NotImplementedError

    @abstractmethod
    async def generate(
        self,
        request: LLMRequest,
    ) -> LLMResponse:
        raise NotImplementedError