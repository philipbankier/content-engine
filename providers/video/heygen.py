"""HeyGen video generation provider."""

import asyncio
import logging
import time

import httpx

from config import settings
from providers.video.base import VideoProvider, VideoResult

logger = logging.getLogger(__name__)

MAX_POLL_DURATION = 1200  # 20 minutes — HeyGen video gen takes 10-20 min
POLL_INTERVAL = 10  # seconds


class HeyGenProvider(VideoProvider):
    """HeyGen provider for AI avatar video generation.

    Creates videos with AI avatars speaking provided scripts.
    Best quality option but requires cloud API.

    Usage:
        provider = HeyGenProvider()
        result = await provider.generate("Hello, welcome to our demo!", avatar_type="founder")
    """

    def __init__(
        self,
        api_key: str | None = None,
        avatar_id_founder: str | None = None,
        avatar_id_professional: str | None = None,
    ):
        self.api_key = api_key or settings.heygen_api_key
        self.avatar_id_founder = avatar_id_founder or settings.heygen_avatar_id_founder
        self.avatar_id_professional = avatar_id_professional or settings.heygen_avatar_id_professional
        self.base_url = "https://api.heygen.com"

    @property
    def provider_name(self) -> str:
        return "heygen"

    def _get_headers(self) -> dict:
        return {
            "X-Api-Key": self.api_key,
            "Content-Type": "application/json",
        }

    def _get_avatar_id(self, avatar_type: str) -> str:
        if avatar_type == "professional":
            return self.avatar_id_professional
        return self.avatar_id_founder

    async def _resolve_voice_id(
        self, avatar_id: str, voice_id: str | None,
    ) -> str | None:
        """Resolve voice_id: explicit > config > avatar default."""
        if voice_id:
            return voice_id
        if settings.heygen_voice_id:
            return settings.heygen_voice_id
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{self.base_url}/v2/avatars",
                    headers=self._get_headers(),
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
        **kwargs,
    ) -> VideoResult:
        """Generate a video with a HeyGen avatar speaking the script."""
        start_ms = time.time() * 1000

        avatar_id = self._get_avatar_id(avatar_type)
        if not avatar_id:
            return VideoResult(
                video_url=None,
                local_path=None,
                video_id=None,
                error=f"No avatar ID configured for type: {avatar_type}",
                provider=self.provider_name,
                cost_usd=0.0,
            )

        resolved_voice = await self._resolve_voice_id(avatar_id, voice_id)
        if not resolved_voice:
            return VideoResult(
                video_url=None,
                local_path=None,
                video_id=None,
                error="No voice_id available — set HEYGEN_VOICE_ID or ensure avatar has a default voice",
                provider=self.provider_name,
                cost_usd=0.0,
            )

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

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                # Submit video generation request
                resp = await client.post(
                    f"{self.base_url}/v2/video/generate",
                    headers=self._get_headers(),
                    json=body,
                )
                resp.raise_for_status()
                data = resp.json()

                video_id = data.get("data", {}).get("video_id")
                if not video_id:
                    return VideoResult(
                        video_url=None,
                        local_path=None,
                        video_id=None,
                        error=f"No video_id in response: {data}",
                        provider=self.provider_name,
                        cost_usd=0.0,
                    )

                # Poll for completion
                elapsed = 0
                while elapsed < MAX_POLL_DURATION:
                    await asyncio.sleep(POLL_INTERVAL)
                    elapsed += POLL_INTERVAL

                    status_resp = await client.get(
                        f"{self.base_url}/v1/video_status.get",
                        params={"video_id": video_id},
                        headers=self._get_headers(),
                    )
                    status_resp.raise_for_status()
                    status_data = status_resp.json()

                    status = status_data.get("data", {}).get("status")
                    if status == "completed":
                        video_url = status_data["data"].get("video_url")
                        duration = status_data["data"].get("duration")
                        generation_time_ms = time.time() * 1000 - start_ms

                        # HeyGen pricing is roughly $0.10-0.50 per video depending on length
                        cost_usd = 0.25

                        return VideoResult(
                            video_url=video_url,
                            local_path=None,
                            video_id=video_id,
                            error=None,
                            provider=self.provider_name,
                            cost_usd=cost_usd,
                            duration_seconds=duration,
                            width=1080,
                            height=1920,
                            generation_time_ms=generation_time_ms,
                        )
                    elif status == "failed":
                        error = status_data["data"].get("error", "Unknown error")
                        return VideoResult(
                            video_url=None,
                            local_path=None,
                            video_id=video_id,
                            error=f"Video generation failed: {error}",
                            provider=self.provider_name,
                            cost_usd=0.0,
                        )

                    logger.debug("HeyGen video %s status: %s (%ds)", video_id, status, elapsed)

                return VideoResult(
                    video_url=None,
                    local_path=None,
                    video_id=video_id,
                    error=f"Video generation timed out after {MAX_POLL_DURATION}s",
                    provider=self.provider_name,
                    cost_usd=0.0,
                )

        except httpx.HTTPStatusError as e:
            error_msg = f"HeyGen API error {e.response.status_code}: {e.response.text}"
            logger.error("Video generation failed: %s", error_msg)
            return VideoResult(
                video_url=None,
                local_path=None,
                video_id=None,
                error=error_msg,
                provider=self.provider_name,
                cost_usd=0.0,
            )
        except Exception as e:
            logger.error("Video generation failed: %s", e)
            return VideoResult(
                video_url=None,
                local_path=None,
                video_id=None,
                error=str(e),
                provider=self.provider_name,
                cost_usd=0.0,
            )

    async def health_check(self) -> bool:
        """Check if HeyGen API is accessible."""
        if not self.api_key:
            logger.warning("HeyGen API key not configured")
            return False

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                # Check API by listing avatars
                response = await client.get(
                    f"{self.base_url}/v2/avatars",
                    headers=self._get_headers(),
                )
                return response.status_code == 200
        except Exception as e:
            logger.warning("HeyGen health check failed: %s", e)
            return False
