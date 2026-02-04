"""Video generation via Veo3 on fal.ai queue API."""

import asyncio
import logging
import httpx
from config import settings

logger = logging.getLogger(__name__)

MAX_POLL_DURATION = 600  # 10 minutes
POLL_INTERVAL = 10  # seconds

FAL_QUEUE_BASE = "https://queue.fal.run/fal-ai/veo3"


class Veo3VideoGenerator:
    def __init__(self):
        self.headers = {
            "Authorization": f"Key {settings.fal_key}",
            "Content-Type": "application/json",
        }

    async def generate(
        self,
        prompt: str,
        duration_seconds: int = 8,
    ) -> dict:
        """Generate a video using Veo3 via fal.ai queue API.

        Returns {"video_url": url} or {"error": msg}.
        """
        body = {
            "prompt": prompt,
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                # Submit to fal.ai queue
                resp = await client.post(
                    FAL_QUEUE_BASE,
                    headers=self.headers,
                    json=body,
                )
                resp.raise_for_status()
                data = resp.json()

                request_id = data.get("request_id")
                if not request_id:
                    # Synchronous response — result returned directly
                    video_url = self._extract_video_url(data)
                    if video_url:
                        return {"video_url": video_url}
                    return {"error": f"No request_id in response: {data}"}

                # Poll for completion
                status_url = f"{FAL_QUEUE_BASE}/requests/{request_id}/status"
                result_url = f"{FAL_QUEUE_BASE}/requests/{request_id}"
                elapsed = 0

                while elapsed < MAX_POLL_DURATION:
                    await asyncio.sleep(POLL_INTERVAL)
                    elapsed += POLL_INTERVAL

                    poll_resp = await client.get(
                        status_url,
                        headers=self.headers,
                    )
                    poll_resp.raise_for_status()
                    poll_data = poll_resp.json()

                    status = poll_data.get("status")
                    if status == "COMPLETED":
                        # Fetch the result
                        result_resp = await client.get(
                            result_url,
                            headers=self.headers,
                        )
                        result_resp.raise_for_status()
                        result_data = result_resp.json()
                        video_url = self._extract_video_url(result_data)
                        if video_url:
                            return {"video_url": video_url}
                        return {"error": f"Completed but no video URL: {result_data}"}
                    elif status == "FAILED":
                        error = poll_data.get("error", "Unknown error")
                        return {"error": f"Veo3 generation failed: {error}"}

                    logger.debug("Veo3 request %s status: %s (%ds)", request_id, status, elapsed)

                return {"error": f"Veo3 generation timed out after {MAX_POLL_DURATION}s"}

        except httpx.HTTPStatusError as e:
            error_msg = f"Veo3/fal.ai API error {e.response.status_code}: {e.response.text}"
            logger.error("Veo3 video generation failed: %s", error_msg)
            return {"error": error_msg}
        except Exception as e:
            logger.error("Veo3 video generation failed: %s", e)
            return {"error": str(e)}

    @staticmethod
    def _extract_video_url(data: dict) -> str | None:
        """Extract video URL from fal.ai response data."""
        # fal.ai typically returns {"video": {"url": "..."}}
        video = data.get("video")
        if isinstance(video, dict):
            return video.get("url")

        # Also check for direct url field
        if data.get("video_url"):
            return data["video_url"]

        # Check output list format
        output = data.get("output", [])
        if output and isinstance(output, list) and isinstance(output[0], dict):
            return output[0].get("url")

        return None
