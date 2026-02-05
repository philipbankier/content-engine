"""Image generation via configurable provider (fal.ai, ComfyUI, SD WebUI)."""

import logging

from providers.factory import get_image_provider
from providers.image.base import ImageProvider

logger = logging.getLogger(__name__)


class ImageGenerator:
    def __init__(self, provider: ImageProvider | None = None):
        self._provider = provider

    @property
    def provider(self) -> ImageProvider:
        if self._provider is None:
            self._provider = get_image_provider()
        return self._provider

    async def generate(
        self,
        prompt: str,
        size: str = "landscape_4_3",
        style: str = "professional",
    ) -> dict:
        """Generate an image from a text prompt.

        Returns:
            dict with keys: url, local_path, error, provider, cost_usd
            - url: Remote URL (for cloud providers like fal.ai)
            - local_path: Local file path (for local providers like ComfyUI)
            - error: Error message if generation failed, None otherwise
        """
        try:
            result = await self.provider.generate(
                prompt=prompt,
                size=size,
                style=style,
            )

            return {
                "url": result.url,
                "local_path": result.local_path,
                "error": result.error,
                "provider": result.provider,
                "cost_usd": result.cost_usd,
                "width": result.width,
                "height": result.height,
            }

        except Exception as e:
            logger.error("Image generation failed: %s", e)
            return {
                "url": None,
                "local_path": None,
                "error": str(e),
                "provider": self.provider.provider_name,
                "cost_usd": 0.0,
            }
