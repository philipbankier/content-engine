"""CogVideoX local video generation provider (experimental).

CogVideoX-2B is designed to fit in 12GB VRAM (RTX 3060).
Quality is lower than HeyGen but fully local and free.

This provider assumes CogVideoX is running as a local API server.
See: https://github.com/THUDM/CogVideo
"""

import asyncio
import logging
import os
import time
import uuid
from pathlib import Path

import httpx

from providers.video.base import VideoProvider, VideoResult

logger = logging.getLogger(__name__)


class CogVideoProvider(VideoProvider):
    """CogVideoX provider for local video generation.

    Experimental: Quality is lower than cloud solutions but runs fully locally.

    Recommended for RTX 3060 (12GB VRAM):
    - CogVideoX-2B (~10GB) - fits in 12GB, slower but works

    This assumes CogVideoX is running as an API server. The default API format
    follows a simple REST interface. Adjust as needed for your setup.

    Usage:
        provider = CogVideoProvider(base_url="http://localhost:8000")
        result = await provider.generate("A cat walking on a beach")
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        output_dir: str | None = None,
        timeout: int = 600,  # 10 minutes for video generation
    ):
        self.base_url = base_url.rstrip("/")
        self.output_dir = output_dir or os.path.join(os.getcwd(), "generated_videos")
        self.timeout = timeout

        # Ensure output directory exists
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)

    @property
    def provider_name(self) -> str:
        return "cogvideo"

    async def generate(
        self,
        script: str,
        avatar_type: str = "founder",
        voice_id: str | None = None,
        **kwargs,
    ) -> VideoResult:
        """Generate a video using CogVideoX.

        Note: CogVideoX generates videos from text prompts, not from scripts
        with avatars. The 'script' is used as the video generation prompt.
        For avatar-style videos, consider using HeyGen instead.
        """
        start_ms = time.time() * 1000

        # CogVideoX uses prompts, not scripts with avatars
        # Convert script to a visual prompt
        prompt = self._script_to_prompt(script)

        payload = {
            "prompt": prompt,
            "num_frames": 49,  # ~2 seconds at 24fps
            "fps": 24,
            "guidance_scale": 6.0,
            "num_inference_steps": 50,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Submit generation request
                response = await client.post(
                    f"{self.base_url}/generate",
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()

                # Handle different response formats
                if "video_url" in data:
                    # Server returns URL to generated video
                    video_url = data["video_url"]
                    local_path = await self._download_video(client, video_url)
                elif "video_base64" in data:
                    # Server returns base64 encoded video
                    import base64
                    video_data = base64.b64decode(data["video_base64"])
                    local_path = self._save_video(video_data)
                elif "task_id" in data:
                    # Server uses async generation, poll for result
                    local_path = await self._poll_for_result(client, data["task_id"])
                    if local_path is None:
                        return VideoResult(
                            video_url=None,
                            local_path=None,
                            video_id=data["task_id"],
                            error="Timeout waiting for CogVideoX generation",
                            provider=self.provider_name,
                            cost_usd=0.0,
                        )
                else:
                    return VideoResult(
                        video_url=None,
                        local_path=None,
                        video_id=None,
                        error=f"Unexpected response format: {data}",
                        provider=self.provider_name,
                        cost_usd=0.0,
                    )

                generation_time_ms = time.time() * 1000 - start_ms

                return VideoResult(
                    video_url=None,
                    local_path=local_path,
                    video_id=None,
                    error=None,
                    provider=self.provider_name,
                    cost_usd=0.0,  # Local = free
                    duration_seconds=49 / 24,  # ~2 seconds
                    width=480,
                    height=720,
                    generation_time_ms=generation_time_ms,
                )

        except httpx.ConnectError:
            logger.error("Cannot connect to CogVideoX at %s. Is it running?", self.base_url)
            return VideoResult(
                video_url=None,
                local_path=None,
                video_id=None,
                error=f"Cannot connect to CogVideoX at {self.base_url}",
                provider=self.provider_name,
                cost_usd=0.0,
            )
        except Exception as e:
            logger.error("CogVideoX generation failed: %s", e)
            return VideoResult(
                video_url=None,
                local_path=None,
                video_id=None,
                error=str(e),
                provider=self.provider_name,
                cost_usd=0.0,
            )

    def _script_to_prompt(self, script: str) -> str:
        """Convert a speaking script to a visual video prompt.

        CogVideoX generates visual videos, not talking head videos.
        This converts the script concept to a visual prompt.
        """
        # For a talking-head style, describe the scene
        # This is a basic conversion - you may want to use an LLM for better results
        return f"Professional person speaking to camera, corporate setting, {script[:200]}"

    def _save_video(self, video_data: bytes) -> str:
        """Save video data to local file."""
        filename = f"{uuid.uuid4().hex}.mp4"
        local_path = os.path.join(self.output_dir, filename)
        with open(local_path, "wb") as f:
            f.write(video_data)
        return local_path

    async def _download_video(self, client: httpx.AsyncClient, video_url: str) -> str:
        """Download video from URL and save locally."""
        response = await client.get(video_url)
        response.raise_for_status()
        return self._save_video(response.content)

    async def _poll_for_result(
        self, client: httpx.AsyncClient, task_id: str, timeout: int = 300
    ) -> str | None:
        """Poll for async generation result."""
        start = time.time()
        while time.time() - start < timeout:
            response = await client.get(f"{self.base_url}/status/{task_id}")
            if response.status_code == 200:
                data = response.json()
                status = data.get("status")
                if status == "completed":
                    if "video_url" in data:
                        return await self._download_video(client, data["video_url"])
                    elif "video_base64" in data:
                        import base64
                        video_data = base64.b64decode(data["video_base64"])
                        return self._save_video(video_data)
                elif status == "failed":
                    logger.error("CogVideoX task %s failed: %s", task_id, data.get("error"))
                    return None
            await asyncio.sleep(5)
        return None

    async def health_check(self) -> bool:
        """Check if CogVideoX server is running."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(f"{self.base_url}/health")
                return response.status_code == 200
        except Exception as e:
            logger.warning("CogVideoX health check failed: %s", e)
            return False
