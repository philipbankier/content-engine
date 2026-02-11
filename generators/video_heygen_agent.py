"""Video generation via HeyGen Video Agent API — one-shot prompt-to-video."""

import asyncio
import logging
import httpx
from config import settings

logger = logging.getLogger(__name__)

MAX_POLL_DURATION = 1200  # 20 minutes
POLL_INTERVAL = 10  # seconds


class HeyGenVideoAgentGenerator:
    """Generate videos using HeyGen's Video Agent — a single prompt produces
    a full video with avatar, script, visuals, and captions automatically."""

    def __init__(self):
        self.base_url = "https://api.heygen.com"
        self.headers = {
            "X-Api-Key": settings.heygen_api_key,
            "Content-Type": "application/json",
        }

    async def generate(
        self,
        prompt: str,
        duration_sec: int = 60,
        orientation: str = "portrait",
        avatar_id: str | None = None,
        test_mode: bool = False,
    ) -> dict:
        """Generate a video from a rich text prompt using the Video Agent.

        The Video Agent handles script writing, avatar selection, visual
        composition, voiceover, pacing, and captions automatically.

        Args:
            test_mode: If True, pass "test": true to HeyGen — produces
                       watermarked output at zero credit cost.

        Returns {"video_url": url, "video_id": id} or {"error": msg}.
        """
        body: dict = {"prompt": prompt}

        if test_mode:
            body["test"] = True
            logger.info("HeyGen Video Agent: test_mode=True — watermarked output, zero credits")

        config: dict = {}
        if duration_sec:
            config["duration_sec"] = duration_sec
        if orientation:
            config["orientation"] = orientation
        if avatar_id:
            config["avatar_id"] = avatar_id
        elif settings.heygen_avatar_id_founder:
            config["avatar_id"] = settings.heygen_avatar_id_founder

        if config:
            body["config"] = config

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{self.base_url}/v1/video_agent/generate",
                    headers=self.headers,
                    json=body,
                )
                resp.raise_for_status()
                data = resp.json()

                video_id = data.get("data", {}).get("video_id")
                if not video_id:
                    return {"error": f"No video_id in response: {data}"}

                # Poll for completion using standard status endpoint
                elapsed = 0
                while elapsed < MAX_POLL_DURATION:
                    await asyncio.sleep(POLL_INTERVAL)
                    elapsed += POLL_INTERVAL

                    status_resp = await client.get(
                        f"{self.base_url}/v1/video_status.get",
                        params={"video_id": video_id},
                        headers=self.headers,
                    )
                    status_resp.raise_for_status()
                    status_data = status_resp.json()

                    status = status_data.get("data", {}).get("status")
                    if status == "completed":
                        video_url = status_data["data"].get("video_url")
                        return {"video_url": video_url, "video_id": video_id}
                    elif status == "failed":
                        error = status_data["data"].get("error", "Unknown error")
                        return {"error": f"Video Agent generation failed: {error}"}

                    logger.debug(
                        "HeyGen Video Agent %s status: %s (%ds)",
                        video_id, status, elapsed,
                    )

                return {"error": f"Video Agent timed out after {MAX_POLL_DURATION}s"}

        except httpx.HTTPStatusError as e:
            error_msg = f"HeyGen Video Agent API error {e.response.status_code}: {e.response.text}"
            logger.error("Video Agent generation failed: %s", error_msg)
            return {"error": error_msg}
        except Exception as e:
            logger.error("Video Agent generation failed: %s", e)
            return {"error": str(e)}
