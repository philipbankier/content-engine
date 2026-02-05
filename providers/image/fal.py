"""fal.ai image generation provider."""

import logging
import time

import httpx

from config import settings
from providers.image.base import ImageProvider, ImageResult

logger = logging.getLogger(__name__)


class FalProvider(ImageProvider):
    """fal.ai provider for cloud-based image generation.

    Uses the Flux model by default for high-quality image generation.

    Usage:
        provider = FalProvider()
        result = await provider.generate("A futuristic city at sunset")
    """

    def __init__(
        self,
        api_key: str | None = None,
        api_url: str = "https://fal.run/fal-ai/flux/dev",
    ):
        self.api_key = api_key or settings.fal_key
        self.api_url = api_url

    @property
    def provider_name(self) -> str:
        return "fal"

    def _get_headers(self) -> dict:
        return {
            "Authorization": f"Key {self.api_key}",
            "Content-Type": "application/json",
        }

    async def generate(
        self,
        prompt: str,
        size: str = "landscape_4_3",
        style: str | None = None,
    ) -> ImageResult:
        """Generate an image using fal.ai's Flux model."""
        start_ms = time.time() * 1000

        # Apply style modifier if provided
        styled_prompt = f"{style} style: {prompt}" if style else prompt

        body = {
            "prompt": styled_prompt,
            "image_size": size,
            "num_images": 1,
        }

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    self.api_url,
                    headers=self._get_headers(),
                    json=body,
                )
                response.raise_for_status()
                data = response.json()

            generation_time_ms = time.time() * 1000 - start_ms

            images = data.get("images", [])
            if images:
                image_url = images[0].get("url") or images[0].get("uri")
                width = images[0].get("width")
                height = images[0].get("height")

                # fal.ai pricing is roughly $0.01-0.03 per image
                cost_usd = 0.02

                return ImageResult(
                    url=image_url,
                    local_path=None,
                    error=None,
                    provider=self.provider_name,
                    cost_usd=cost_usd,
                    width=width,
                    height=height,
                    generation_time_ms=generation_time_ms,
                )

            return ImageResult(
                url=None,
                local_path=None,
                error="No images returned from fal.ai",
                provider=self.provider_name,
                cost_usd=0.0,
            )

        except httpx.HTTPStatusError as e:
            error_msg = f"fal.ai API error {e.response.status_code}: {e.response.text}"
            logger.error("Image generation failed: %s", error_msg)
            return ImageResult(
                url=None,
                local_path=None,
                error=error_msg,
                provider=self.provider_name,
                cost_usd=0.0,
            )
        except Exception as e:
            logger.error("Image generation failed: %s", e)
            return ImageResult(
                url=None,
                local_path=None,
                error=str(e),
                provider=self.provider_name,
                cost_usd=0.0,
            )

    async def health_check(self) -> bool:
        """Check if fal.ai API is accessible."""
        if not self.api_key:
            logger.warning("fal.ai API key not configured")
            return False

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                # Just check auth by making a request with minimal prompt
                response = await client.post(
                    self.api_url,
                    headers=self._get_headers(),
                    json={"prompt": "test", "image_size": "square", "num_images": 0},
                )
                # 400 is OK (invalid params), 401/403 means auth issues
                return response.status_code not in (401, 403)
        except Exception as e:
            logger.warning("fal.ai health check failed: %s", e)
            return False
