from google import genai

from app.agents.providers.base import (
    LLMProvider,
    LLMRequest,
    LLMResponse,
)
from app.core.config import settings


class GeminiProvider(LLMProvider):
    """Google Gemini implementation of the TestForge LLM provider."""

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def default_model(self) -> str:
        return (
            settings.gemini_model
            or "gemini-2.5-flash"
        )

    def __init__(self) -> None:
        if not settings.google_api_key:
            raise ValueError(
                "GOOGLE_API_KEY is not configured."
            )

        self.client = genai.Client(
            api_key=settings.google_api_key
        )

    async def generate(
        self,
        request: LLMRequest,
    ) -> LLMResponse:
        model = (
            request.model
            or self.default_model
        )

        prompt = request.prompt

        if request.system_prompt:
            prompt = (
                f"{request.system_prompt}\n\n"
                f"{request.prompt}"
            )

        response = await self.client.aio.models.generate_content(
            model=model,
            contents=prompt,
        )

        content = response.text or ""

        return LLMResponse(
            provider=self.provider_name,
            model=model,
            content=content,
        )