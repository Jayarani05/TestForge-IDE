from app.agents.provider_registry import (
    LLMProviderRegistry,
    create_default_registry,
)
from app.agents.providers import (
    LLMRequest,
    LLMResponse,
)


class LLMOrchestrator:
    """
    Coordinate LLM requests across registered providers.
    """

    def __init__(
        self,
        registry: LLMProviderRegistry | None = None,
    ) -> None:
        self.registry = (
            registry
            or create_default_registry()
        )

    async def generate(
        self,
        request: LLMRequest,
        provider_name: str = "auto",
        fallback_providers: list[str] | None = None,
    ) -> LLMResponse:
        """
        Generate an LLM response using the selected provider.

        If provider_name is "auto", the first available
        provider is selected automatically.
        """

        if provider_name.lower() == "auto":
            available = self.available_providers()

            if not available:
                raise RuntimeError(
                    "No LLM providers are available."
                )

            provider_name = available[0]

        providers = [
            provider_name
        ]

        if fallback_providers:
            providers.extend(
                fallback_providers
            )

        errors: list[str] = []

        for name in providers:
            try:
                provider = self.registry.get(
                    name
                )

                return await provider.generate(
                    request
                )

            except Exception as exc:
                errors.append(
                    f"{name}: {exc}"
                )

        raise RuntimeError(
            "All configured LLM providers failed. "
            + " | ".join(errors)
        )

    def available_providers(self) -> list[str]:
        return self.registry.list_providers()

    def provider_status(
        self,
    ) -> list[dict[str, object]]:
        return self.registry.provider_status()