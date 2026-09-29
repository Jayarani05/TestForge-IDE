from app.agents.providers import (
    DeepSeekProvider,
    GeminiProvider,
    LLMProvider,
    LlamaProvider,
    MockLLMProvider,
    OpenAIProvider,
)
from app.core.config import settings


class LLMProviderRegistry:
    """Registry for available TestForge LLM providers."""

    def __init__(self) -> None:
        self._providers: dict[str, LLMProvider] = {}

    def register(
        self,
        provider: LLMProvider,
    ) -> None:
        name = provider.provider_name.lower()

        if not name:
            raise ValueError(
                "Provider name cannot be empty."
            )

        self._providers[name] = provider

    def get(
        self,
        provider_name: str,
    ) -> LLMProvider:
        name = provider_name.lower()

        provider = self._providers.get(name)

        if provider is None:
            raise ValueError(
                f"LLM provider '{provider_name}' "
                "is not available."
            )

        return provider

    def list_providers(self) -> list[str]:
        return sorted(
            self._providers.keys()
        )
    def provider_status(
        self,
    ) -> list[dict[str, object]]:
        """Return status information for registered providers."""

        providers: list[dict[str, object]] = []

        for name in self.list_providers():
            provider = self._providers[name]

            providers.append(
                {
                    "provider": name,
                    "model": provider.default_model,
                    "available": True,
                }
            )

        return providers



def create_default_registry() -> LLMProviderRegistry:
    """Create the default TestForge provider registry."""

    registry = LLMProviderRegistry()

    registry.register(
        MockLLMProvider()
    )

    if settings.openai_api_key:
        registry.register(
            OpenAIProvider()
        )

    if settings.google_api_key:
        registry.register(
            GeminiProvider()
        )

    if settings.groq_api_key:
        registry.register(
            LlamaProvider()
        )
    if settings.deepseek_api_key:
        registry.register(
            DeepSeekProvider()
        )

    return registry