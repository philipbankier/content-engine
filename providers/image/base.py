"""Abstract base class for image generation providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ImageResult:
    """Standardized result from any image provider."""

    url: str | None  # Remote URL (for cloud providers)
    local_path: str | None  # Local file path (for local providers)
    error: str | None
    provider: str
    cost_usd: float  # 0.0 for local providers
    width: int | None = None
    height: int | None = None
    generation_time_ms: float | None = None


class ImageProvider(ABC):
    """Abstract base class for image generation providers.

    Implementations: FalProvider, ComfyUIProvider, SDWebUIProvider
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name for logging/tracking."""
        ...

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        size: str = "1024x1024",
        style: str | None = None,
    ) -> ImageResult:
        """Generate an image from a text prompt.

        Args:
            prompt: Text description of the desired image.
            size: Image dimensions (e.g., "1024x1024", "landscape_4_3").
            style: Optional style modifier.

        Returns:
            ImageResult with URL/path, error status, and metadata.
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the provider is available and responding.

        Returns:
            True if the provider is healthy, False otherwise.
        """
        ...
