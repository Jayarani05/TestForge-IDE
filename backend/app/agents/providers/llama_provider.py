from groq import AsyncGroq

from app.agents.providers.base import (
    LLMProvider,
    LLMRequest,
    LLMResponse,
)
from app.core.config import settings


class LlamaProvider(LLMProvider):
    """Llama implementation using the Groq API."""

    @property
    def provider_name(self) -> str:
        return "llama"

    @property
    def default_model(self) -> str:
        return (
            settings.llama_model
            or "llama-3.3-70b-versatile"
        )

    def __init__(self) -> None:
        if not settings.groq_api_key:
            raise ValueError(
                "GROQ_API_KEY is not configured."
            )

        self.client = AsyncGroq(
            api_key=settings.groq_api_key,
        )

    async def generate(
        self,
        request: LLMRequest,
    ) -> LLMResponse:
        model = (
            request.model
            or self.default_model
        )

        messages = []

        if request.system_prompt:
            messages.append(
                {
                    "role": "system",
                    "content": request.system_prompt,
                }
            )

        messages.append(
            {
                "role": "user",
                "content": request.prompt,
            }
        )

        response = (
            await self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            )
        )

        content = (
            response.choices[0].message.content
            or ""
        )

        usage = response.usage

        return LLMResponse(
            provider=self.provider_name,
            model=model,
            content=content,
            input_tokens=(
                usage.prompt_tokens
                if usage
                else None
            ),
            output_tokens=(
                usage.completion_tokens
                if usage
                else None
            ),
        )