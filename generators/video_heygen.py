"""Video generation via HeyGen API."""

import asyncio
import logging
import httpx
from config import settings

logger = logging.getLogger(__name__)

MAX_POLL_DURATION = 1200  # 20 minutes — HeyGen video gen takes 10-20 min
POLL_INTERVAL = 10  # seconds


class HeyGenVideoGenerator:
    def __init__(self):
        self.base_url = "https://api.heygen.com"
        self.headers = {
            "X-Api-Key": settings.heygen_api_key,
            "Content-Type": "application/json",
        }

    def _get_avatar_id(self, avatar_type: str) -> str:
        if avatar_type == "professional":
            return settings.heygen_avatar_id_professional
        return settings.heygen_avatar_id_founder

    async def _resolve_voice_id(
        self, avatar_id: str, voice_id: str | None,
    ) -> str | None:
        """Resolve voice_id: explicit > config > avatar default."""
        if voice_id:
            return voice_id
        if settings.heygen_voice_id:
            return settings.heygen_voice_id
        # Fetch avatar's default voice
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{self.base_url}/v2/avatars",
                    headers=self.headers,
                )
                resp.raise_for_status()
                for av in resp.json().get("data", {}).get("avatars", []):
                    if av.get("avatar_id") == avatar_id:
                        vid = av.get("default_voice_id")
                        if vid:
                            logger.info("Using avatar default voice: %s", vid)
                            return vid
        except Exception as e:
            logger.warning("Could not fetch avatar default voice: %s", e)
        return None

    async def generate(
        self,
        script: str,
        avatar_type: str = "founder",
        voice_id: str | None = None,
        test_mode: bool = False,
    ) -> dict:
        """Generate a video with a HeyGen avatar speaking the given script.

        Args:
            test_mode: If True, pass "test": true to HeyGen — produces
                       watermarked output at zero credit cost.

        Returns {"video_url": url, "video_id": id} or {"error": msg}.
        """
        avatar_id = self._get_avatar_id(avatar_type)
        resolved_voice = await self._resolve_voice_id(avatar_id, voice_id)
        if not resolved_voice:
            return {"error": "No voice_id available — set HEYGEN_VOICE_ID or ensure avatar has a default voice"}

        voice_config: dict = {
            "type": "text",
            "input_text": script,
            "voice_id": resolved_voice,
        }

        body = {
            "video_inputs": [
                {
                    "character": {
                        "type": "avatar",
                        "avatar_id": avatar_id,
                    },
                    "voice": voice_config,
                }
            ],
            "dimension": {
                "width": 720,
                "height": 1280,
            },
        }

        if test_mode:
            body["test"] = True
            logger.info("HeyGen v2: test_mode=True — watermarked output, zero credits")

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                # Submit video generation request
                resp = await client.post(
                    f"{self.base_url}/v2/video/generate",
                    headers=self.headers,
                    json=body,
                )
                resp.raise_for_status()
                data = resp.json()

                video_id = data.get("data", {}).get("video_id")
                if not video_id:
                    return {"error": f"No video_id in response: {data}"}

                # Poll for completion
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
                        return {"error": f"Video generation failed: {error}"}

                    logger.debug("HeyGen video %s status: %s (%ds)", video_id, status, elapsed)

                return {"error": f"Video generation timed out after {MAX_POLL_DURATION}s"}

        except httpx.HTTPStatusError as e:
            error_msg = f"HeyGen API error {e.response.status_code}: {e.response.text}"
            logger.error("Video generation failed: %s", error_msg)
            return {"error": error_msg}
        except Exception as e:
            logger.error("Video generation failed: %s", e)
            return {"error": str(e)}
