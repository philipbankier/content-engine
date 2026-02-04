"""Image generation via fal.ai REST API."""

import logging
import httpx
from config import settings

logger = logging.getLogger(__name__)


class ImageGenerator:
    def __init__(self):
        self.api_url = "https://fal.run/fal-ai/flux/dev"
        self.headers = {
            "Authorization": f"Key {settings.fal_key}",
            "Content-Type": "application/json",
        }

    async def generate(
        self,
        prompt: str,
        size: str = "landscape_4_3",
        style: str = "professional",
    ) -> dict:
        """Generate an image from a text prompt.

        Returns {"url": image_url, "error": None} or {"url": None, "error": error_msg}.
        """
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
                    headers=self.headers,
                    json=body,
                )
                response.raise_for_status()
                data = response.json()

                images = data.get("images", [])
                if images:
                    image_url = images[0].get("url") or images[0].get("uri")
                    return {"url": image_url, "error": None}

                return {"url": None, "error": "No images returned from fal.ai"}

        except httpx.HTTPStatusError as e:
            error_msg = f"fal.ai API error {e.response.status_code}: {e.response.text}"
            logger.error("Image generation failed: %s", error_msg)
            return {"url": None, "error": error_msg}
        except Exception as e:
            logger.error("Image generation failed: %s", e)
            return {"url": None, "error": str(e)}
