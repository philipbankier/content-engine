"""Stable Diffusion WebUI (AUTOMATIC1111) image generation provider."""

import base64
import logging
import os
import time
import uuid
from pathlib import Path

import httpx

from providers.image.base import ImageProvider, ImageResult

logger = logging.getLogger(__name__)


class SDWebUIProvider(ImageProvider):
    """Stable Diffusion WebUI (AUTOMATIC1111) provider for local image generation.

    Recommended for RTX 3060 (12GB VRAM):
    - SDXL models (~8GB)
    - SD 1.5 models (~4GB)

    Usage:
        provider = SDWebUIProvider(base_url="http://localhost:7860")
        result = await provider.generate("A beautiful landscape")
    """

    def __init__(
        self,
        base_url: str = "http://localhost:7860",
        output_dir: str | None = None,
        default_model: str | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.output_dir = output_dir or os.path.join(os.getcwd(), "generated_images")
        self.default_model = default_model

        # Ensure output directory exists
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)

    @property
    def provider_name(self) -> str:
        return "sdwebui"

    def _parse_size(self, size: str) -> tuple[int, int]:
        """Parse size string to width, height tuple."""
        size_map = {
            "1024x1024": (1024, 1024),
            "square": (512, 512),
            "landscape_4_3": (768, 576),
            "landscape_16_9": (768, 432),
            "portrait_3_4": (576, 768),
            "portrait_9_16": (432, 768),
        }
        if size in size_map:
            return size_map[size]

        # Try to parse "WxH" format
        if "x" in size:
            try:
                w, h = size.lower().split("x")
                return int(w), int(h)
            except ValueError:
                pass

        return 512, 512  # Default for SD 1.5

    async def generate(
        self,
        prompt: str,
        size: str = "512x512",
        style: str | None = None,
    ) -> ImageResult:
        """Generate an image using SD WebUI's txt2img API."""
        start_ms = time.time() * 1000

        # Apply style if provided
        full_prompt = f"{style} style, {prompt}" if style else prompt

        width, height = self._parse_size(size)

        payload = {
            "prompt": full_prompt,
            "negative_prompt": "blurry, low quality, distorted, deformed",
            "width": width,
            "height": height,
            "steps": 20,
            "cfg_scale": 7.0,
            "sampler_name": "DPM++ 2M Karras",
            "batch_size": 1,
            "n_iter": 1,
        }

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(
                    f"{self.base_url}/sdapi/v1/txt2img",
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()

            generation_time_ms = time.time() * 1000 - start_ms

            images = data.get("images", [])
            if not images:
                return ImageResult(
                    url=None,
                    local_path=None,
                    error="No images returned from SD WebUI",
                    provider=self.provider_name,
                    cost_usd=0.0,
                )

            # Decode base64 image and save to disk
            image_b64 = images[0]
            # Remove potential data URI prefix
            if "," in image_b64:
                image_b64 = image_b64.split(",", 1)[1]

            image_data = base64.b64decode(image_b64)
            local_filename = f"{uuid.uuid4().hex}.png"
            local_path = os.path.join(self.output_dir, local_filename)

            with open(local_path, "wb") as f:
                f.write(image_data)

            return ImageResult(
                url=None,
                local_path=local_path,
                error=None,
                provider=self.provider_name,
                cost_usd=0.0,  # Local = free
                width=width,
                height=height,
                generation_time_ms=generation_time_ms,
            )

        except httpx.ConnectError:
            logger.error("Cannot connect to SD WebUI at %s. Is it running?", self.base_url)
            return ImageResult(
                url=None,
                local_path=None,
                error=f"Cannot connect to SD WebUI at {self.base_url}",
                provider=self.provider_name,
                cost_usd=0.0,
            )
        except Exception as e:
            logger.error("SD WebUI generation failed: %s", e)
            return ImageResult(
                url=None,
                local_path=None,
                error=str(e),
                provider=self.provider_name,
                cost_usd=0.0,
            )

    async def health_check(self) -> bool:
        """Check if SD WebUI is running."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(f"{self.base_url}/sdapi/v1/sd-models")
                return response.status_code == 200
        except Exception as e:
            logger.warning("SD WebUI health check failed: %s", e)
            return False

    async def get_models(self) -> list[str]:
        """Get list of available models."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(f"{self.base_url}/sdapi/v1/sd-models")
                response.raise_for_status()
                data = response.json()
                return [m.get("model_name", m.get("title", "")) for m in data]
        except Exception as e:
            logger.warning("Failed to get SD WebUI models: %s", e)
            return []

    async def set_model(self, model_name: str) -> bool:
        """Set the active model."""
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    f"{self.base_url}/sdapi/v1/options",
                    json={"sd_model_checkpoint": model_name},
                )
                return response.status_code == 200
        except Exception as e:
            logger.warning("Failed to set SD WebUI model: %s", e)
            return False
