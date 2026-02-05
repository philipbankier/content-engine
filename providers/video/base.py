"""Abstract base class for video generation providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class VideoResult:
    """Standardized result from any video provider."""

    video_url: str | None  # Remote URL (for cloud providers)
    local_path: str | None  # Local file path (for local providers)
    video_id: str | None  # Provider-specific ID for status tracking
    error: str | None
    provider: str
    cost_usd: float  # 0.0 for local providers
    duration_seconds: float | None = None
    width: int | None = None
    height: int | None = None
    generation_time_ms: float | None = None


class VideoProvider(ABC):
    """Abstract base class for video generation providers.

    Implementations: HeyGenProvider, CogVideoProvider, Veo3Provider
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name for logging/tracking."""
        ...

    @abstractmethod
    async def generate(
        self,
        script: str,
        avatar_type: str = "founder",
        voice_id: str | None = None,
        **kwargs,
    ) -> VideoResult:
        """Generate a video from a script.

        Args:
            script: The text/script for the video.
            avatar_type: Type of avatar to use (provider-specific).
            voice_id: Optional voice ID for TTS.
            **kwargs: Provider-specific options.

        Returns:
            VideoResult with URL/path, error status, and metadata.
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the provider is available and responding.

        Returns:
            True if the provider is healthy, False otherwise.
        """
        ...
