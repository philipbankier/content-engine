"""Abstract base class for LLM providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMResponse:
    """Standardized response from any LLM provider."""

    text: str
    input_tokens: int
    output_tokens: int
    model: str
    provider: str
    latency_ms: float
    cost_usd: float  # 0.0 for local providers


class LLMProvider(ABC):
    """Abstract base class for LLM providers.

    Implementations: BedrockProvider, OllamaProvider, OpenAICompatProvider
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name for logging/tracking."""
        ...

    @abstractmethod
    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4096,
        json_mode: bool = False,
    ) -> LLMResponse:
        """Generate a completion from the LLM.

        Args:
            system_prompt: System instructions for the model.
            user_prompt: User message/request.
            max_tokens: Maximum tokens in the response.
            json_mode: If True, request structured JSON output (provider-specific).

        Returns:
            LLMResponse with text, token counts, cost, and metadata.
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the provider is available and responding.

        Returns:
            True if the provider is healthy, False otherwise.
        """
        ...
