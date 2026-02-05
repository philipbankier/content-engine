"""ComfyUI image generation provider for local inference."""

import asyncio
import json
import logging
import os
import time
import uuid
from pathlib import Path

import httpx

from providers.image.base import ImageProvider, ImageResult

logger = logging.getLogger(__name__)

# Default workflow for SDXL Turbo (fast, fits in 12GB VRAM)
DEFAULT_WORKFLOW = {
    "3": {
        "class_type": "KSampler",
        "inputs": {
            "cfg": 1.0,
            "denoise": 1.0,
            "latent_image": ["5", 0],
            "model": ["4", 0],
            "negative": ["7", 0],
            "positive": ["6", 0],
            "sampler_name": "euler",
            "scheduler": "normal",
            "seed": 0,  # Will be randomized
            "steps": 4,  # SDXL Turbo uses few steps
        },
    },
    "4": {
        "class_type": "CheckpointLoaderSimple",
        "inputs": {"ckpt_name": "sd_xl_turbo_1.0_fp16.safetensors"},
    },
    "5": {
        "class_type": "EmptyLatentImage",
        "inputs": {"batch_size": 1, "height": 1024, "width": 1024},
    },
    "6": {
        "class_type": "CLIPTextEncode",
        "inputs": {"clip": ["4", 1], "text": ""},  # Prompt goes here
    },
    "7": {
        "class_type": "CLIPTextEncode",
        "inputs": {"clip": ["4", 1], "text": "blurry, low quality, distorted"},
    },
    "8": {
        "class_type": "VAEDecode",
        "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
    },
    "9": {
        "class_type": "SaveImage",
        "inputs": {"filename_prefix": "autopilot", "images": ["8", 0]},
    },
}


class ComfyUIProvider(ImageProvider):
    """ComfyUI provider for local image generation.

    Recommended for RTX 3060 (12GB VRAM):
    - SDXL Turbo (~8GB) - fast, good quality
    - SD 1.5 (~4GB) - smaller, lower quality

    Usage:
        provider = ComfyUIProvider(base_url="http://localhost:8188")
        result = await provider.generate("A beautiful landscape")
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8188",
        output_dir: str | None = None,
        workflow: dict | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.output_dir = output_dir or os.path.join(os.getcwd(), "generated_images")
        self.workflow = workflow or DEFAULT_WORKFLOW
        self.client_id = str(uuid.uuid4())

        # Ensure output directory exists
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)

    @property
    def provider_name(self) -> str:
        return "comfyui"

    def _prepare_workflow(self, prompt: str, width: int, height: int) -> dict:
        """Prepare the workflow with the given prompt and dimensions."""
        import random

        workflow = json.loads(json.dumps(self.workflow))  # Deep copy

        # Set the prompt
        workflow["6"]["inputs"]["text"] = prompt

        # Set dimensions
        workflow["5"]["inputs"]["width"] = width
        workflow["5"]["inputs"]["height"] = height

        # Randomize seed
        workflow["3"]["inputs"]["seed"] = random.randint(0, 2**32 - 1)

        return workflow

    def _parse_size(self, size: str) -> tuple[int, int]:
        """Parse size string to width, height tuple."""
        size_map = {
            "1024x1024": (1024, 1024),
            "square": (1024, 1024),
            "landscape_4_3": (1024, 768),
            "landscape_16_9": (1024, 576),
            "portrait_3_4": (768, 1024),
            "portrait_9_16": (576, 1024),
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

        return 1024, 1024  # Default

    async def generate(
        self,
        prompt: str,
        size: str = "1024x1024",
        style: str | None = None,
    ) -> ImageResult:
        """Generate an image using ComfyUI."""
        start_ms = time.time() * 1000

        # Apply style if provided
        full_prompt = f"{style} style: {prompt}" if style else prompt

        width, height = self._parse_size(size)
        workflow = self._prepare_workflow(full_prompt, width, height)

        try:
            async with httpx.AsyncClient(timeout=300) as client:
                # Queue the prompt
                response = await client.post(
                    f"{self.base_url}/prompt",
                    json={"prompt": workflow, "client_id": self.client_id},
                )
                response.raise_for_status()
                data = response.json()
                prompt_id = data.get("prompt_id")

                if not prompt_id:
                    return ImageResult(
                        url=None,
                        local_path=None,
                        error="No prompt_id returned from ComfyUI",
                        provider=self.provider_name,
                        cost_usd=0.0,
                    )

                # Poll for completion
                image_data = await self._poll_for_result(client, prompt_id)

                if image_data is None:
                    return ImageResult(
                        url=None,
                        local_path=None,
                        error="Timeout waiting for ComfyUI generation",
                        provider=self.provider_name,
                        cost_usd=0.0,
                    )

                # Download the image
                filename = image_data.get("filename")
                subfolder = image_data.get("subfolder", "")
                local_path = await self._download_image(client, filename, subfolder)

                generation_time_ms = time.time() * 1000 - start_ms

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
            logger.error("Cannot connect to ComfyUI at %s. Is it running?", self.base_url)
            return ImageResult(
                url=None,
                local_path=None,
                error=f"Cannot connect to ComfyUI at {self.base_url}",
                provider=self.provider_name,
                cost_usd=0.0,
            )
        except Exception as e:
            logger.error("ComfyUI generation failed: %s", e)
            return ImageResult(
                url=None,
                local_path=None,
                error=str(e),
                provider=self.provider_name,
                cost_usd=0.0,
            )

    async def _poll_for_result(
        self, client: httpx.AsyncClient, prompt_id: str, timeout: int = 120
    ) -> dict | None:
        """Poll the history endpoint until the prompt completes."""
        start = time.time()
        while time.time() - start < timeout:
            response = await client.get(f"{self.base_url}/history/{prompt_id}")
            if response.status_code == 200:
                data = response.json()
                if prompt_id in data:
                    outputs = data[prompt_id].get("outputs", {})
                    # Find the SaveImage node output
                    for node_id, node_output in outputs.items():
                        if "images" in node_output and node_output["images"]:
                            return node_output["images"][0]
            await asyncio.sleep(1)
        return None

    async def _download_image(
        self, client: httpx.AsyncClient, filename: str, subfolder: str
    ) -> str:
        """Download an image from ComfyUI and save locally."""
        params = {"filename": filename}
        if subfolder:
            params["subfolder"] = subfolder

        response = await client.get(f"{self.base_url}/view", params=params)
        response.raise_for_status()

        # Save to local output directory
        local_filename = f"{uuid.uuid4().hex}_{filename}"
        local_path = os.path.join(self.output_dir, local_filename)

        with open(local_path, "wb") as f:
            f.write(response.content)

        return local_path

    async def health_check(self) -> bool:
        """Check if ComfyUI is running."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(f"{self.base_url}/system_stats")
                return response.status_code == 200
        except Exception as e:
            logger.warning("ComfyUI health check failed: %s", e)
            return False
