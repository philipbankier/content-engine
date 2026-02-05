"""Provider factory for selecting LLM, image, and video providers based on config."""

import logging

from config import settings
from providers.llm.base import LLMProvider
from providers.image.base import ImageProvider
from providers.video.base import VideoProvider

logger = logging.getLogger(__name__)

# Cache provider instances
_llm_provider: LLMProvider | None = None
_image_provider: ImageProvider | None = None
_video_provider: VideoProvider | None = None


def get_llm_provider(force_new: bool = False) -> LLMProvider:
    """Get the configured LLM provider.

    Supports:
    - bedrock: AWS Bedrock with Claude models (default)
    - ollama: Local Ollama server
    - openai_compat: OpenAI-compatible API (vLLM, LM Studio, etc.)

    Args:
        force_new: If True, create a new instance instead of using cached.

    Returns:
        Configured LLMProvider instance.
    """
    global _llm_provider

    if _llm_provider is not None and not force_new:
        return _llm_provider

    provider_type = settings.llm_provider.lower()

    if provider_type == "ollama":
        from providers.llm.ollama import OllamaProvider

        _llm_provider = OllamaProvider(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
        )
        logger.info("Using Ollama LLM provider: %s", settings.ollama_model)

    elif provider_type == "openai_compat":
        from providers.llm.openai_compat import OpenAICompatProvider

        _llm_provider = OpenAICompatProvider(
            base_url=settings.openai_compat_base_url,
            model=settings.openai_compat_model,
            api_key=settings.openai_compat_api_key or None,
        )
        logger.info("Using OpenAI-compatible LLM provider: %s", settings.openai_compat_model)

    else:
        # Default to Bedrock
        from providers.llm.bedrock import BedrockProvider

        _llm_provider = BedrockProvider(model_id=settings.bedrock_model_id)
        logger.info("Using Bedrock LLM provider: %s", settings.bedrock_model_id)

    return _llm_provider


def get_image_provider(force_new: bool = False) -> ImageProvider:
    """Get the configured image generation provider.

    Supports:
    - fal: fal.ai cloud API (default)
    - comfyui: Local ComfyUI server
    - sdwebui: Local Stable Diffusion WebUI

    Args:
        force_new: If True, create a new instance instead of using cached.

    Returns:
        Configured ImageProvider instance.
    """
    global _image_provider

    if _image_provider is not None and not force_new:
        return _image_provider

    provider_type = settings.image_provider.lower()

    if provider_type == "comfyui":
        from providers.image.comfyui import ComfyUIProvider

        _image_provider = ComfyUIProvider(
            base_url=settings.comfyui_base_url,
            output_dir=settings.image_output_dir or None,
        )
        logger.info("Using ComfyUI image provider: %s", settings.comfyui_base_url)

    elif provider_type == "sdwebui":
        from providers.image.sdwebui import SDWebUIProvider

        _image_provider = SDWebUIProvider(
            base_url=settings.sdwebui_base_url,
            output_dir=settings.image_output_dir or None,
        )
        logger.info("Using SD WebUI image provider: %s", settings.sdwebui_base_url)

    else:
        # Default to fal.ai
        from providers.image.fal import FalProvider

        _image_provider = FalProvider(api_key=settings.fal_key)
        logger.info("Using fal.ai image provider")

    return _image_provider


def get_video_provider(force_new: bool = False) -> VideoProvider:
    """Get the configured video generation provider.

    Supports:
    - heygen: HeyGen cloud API (default, best quality)
    - cogvideo: Local CogVideoX (experimental)

    Args:
        force_new: If True, create a new instance instead of using cached.

    Returns:
        Configured VideoProvider instance.
    """
    global _video_provider

    if _video_provider is not None and not force_new:
        return _video_provider

    provider_type = settings.video_provider.lower()

    if provider_type == "cogvideo":
        from providers.video.cogvideo import CogVideoProvider

        _video_provider = CogVideoProvider(
            base_url=settings.cogvideo_base_url,
            output_dir=settings.video_output_dir or None,
        )
        logger.info("Using CogVideoX video provider: %s", settings.cogvideo_base_url)

    else:
        # Default to HeyGen
        from providers.video.heygen import HeyGenProvider

        _video_provider = HeyGenProvider(
            api_key=settings.heygen_api_key,
            avatar_id_founder=settings.heygen_avatar_id_founder,
            avatar_id_professional=settings.heygen_avatar_id_professional,
        )
        logger.info("Using HeyGen video provider")

    return _video_provider


async def check_all_providers() -> dict[str, bool]:
    """Run health checks on all configured providers.

    Returns:
        Dictionary mapping provider type to health status.
    """
    results = {}

    try:
        llm = get_llm_provider()
        results["llm"] = await llm.health_check()
        results["llm_provider"] = llm.provider_name
    except Exception as e:
        logger.error("LLM provider health check failed: %s", e)
        results["llm"] = False

    try:
        image = get_image_provider()
        results["image"] = await image.health_check()
        results["image_provider"] = image.provider_name
    except Exception as e:
        logger.error("Image provider health check failed: %s", e)
        results["image"] = False

    try:
        video = get_video_provider()
        results["video"] = await video.health_check()
        results["video_provider"] = video.provider_name
    except Exception as e:
        logger.error("Video provider health check failed: %s", e)
        results["video"] = False

    return results


def reset_providers():
    """Reset all cached provider instances.

    Useful for testing or when configuration changes.
    """
    global _llm_provider, _image_provider, _video_provider
    _llm_provider = None
    _image_provider = None
    _video_provider = None
