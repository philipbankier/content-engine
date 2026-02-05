#!/usr/bin/env python3
"""Test script to verify local provider setup.

Run this script to check if your local providers are configured correctly:

    python scripts/test_local_setup.py

The script will:
1. Check which providers are configured
2. Run health checks on each provider
3. Optionally run test generations to verify everything works
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import settings


async def check_llm_provider():
    """Check LLM provider configuration and health."""
    print("\n" + "=" * 50)
    print("LLM PROVIDER CHECK")
    print("=" * 50)

    print(f"Configured provider: {settings.llm_provider}")

    if settings.llm_provider == "ollama":
        print(f"  Base URL: {settings.ollama_base_url}")
        print(f"  Model: {settings.ollama_model}")
    elif settings.llm_provider == "openai_compat":
        print(f"  Base URL: {settings.openai_compat_base_url}")
        print(f"  Model: {settings.openai_compat_model}")
    else:
        print(f"  Model: {settings.bedrock_model_id}")
        print(f"  Region: {settings.aws_region}")

    from providers.factory import get_llm_provider

    try:
        provider = get_llm_provider()
        print(f"\n  Provider instance: {provider.__class__.__name__}")

        print("  Running health check...", end=" ")
        healthy = await provider.health_check()
        if healthy:
            print("✓ HEALTHY")
        else:
            print("✗ UNHEALTHY")
            return False

        # Test a simple completion
        print("  Testing completion...", end=" ")
        response = await provider.complete(
            system_prompt="You are a helpful assistant.",
            user_prompt="Say 'Hello, World!' and nothing else.",
            max_tokens=20,
        )
        if response.text and "hello" in response.text.lower():
            print("✓ WORKS")
            print(f"    Response: {response.text[:50]}...")
            print(f"    Tokens: {response.input_tokens} in, {response.output_tokens} out")
            print(f"    Cost: ${response.cost_usd:.6f}")
            print(f"    Latency: {response.latency_ms:.0f}ms")
        else:
            print("✗ UNEXPECTED RESPONSE")
            print(f"    Got: {response.text}")
            return False

        return True

    except Exception as e:
        print(f"✗ ERROR: {e}")
        return False


async def check_image_provider():
    """Check image provider configuration and health."""
    print("\n" + "=" * 50)
    print("IMAGE PROVIDER CHECK")
    print("=" * 50)

    print(f"Configured provider: {settings.image_provider}")

    if settings.image_provider == "comfyui":
        print(f"  Base URL: {settings.comfyui_base_url}")
    elif settings.image_provider == "sdwebui":
        print(f"  Base URL: {settings.sdwebui_base_url}")
    else:
        print(f"  Using fal.ai cloud API")
        if not settings.fal_key:
            print("  ⚠ Warning: FAL_KEY not set")

    from providers.factory import get_image_provider

    try:
        provider = get_image_provider()
        print(f"\n  Provider instance: {provider.__class__.__name__}")

        print("  Running health check...", end=" ")
        healthy = await provider.health_check()
        if healthy:
            print("✓ HEALTHY")
        else:
            print("✗ UNHEALTHY")
            return False

        return True

    except Exception as e:
        print(f"✗ ERROR: {e}")
        return False


async def check_video_provider():
    """Check video provider configuration and health."""
    print("\n" + "=" * 50)
    print("VIDEO PROVIDER CHECK")
    print("=" * 50)

    print(f"Configured provider: {settings.video_provider}")

    if settings.video_provider == "cogvideo":
        print(f"  Base URL: {settings.cogvideo_base_url}")
    else:
        print(f"  Using HeyGen cloud API")
        if not settings.heygen_api_key:
            print("  ⚠ Warning: HEYGEN_API_KEY not set")

    from providers.factory import get_video_provider

    try:
        provider = get_video_provider()
        print(f"\n  Provider instance: {provider.__class__.__name__}")

        print("  Running health check...", end=" ")
        healthy = await provider.health_check()
        if healthy:
            print("✓ HEALTHY")
        else:
            print("✗ UNHEALTHY")
            return False

        return True

    except Exception as e:
        print(f"✗ ERROR: {e}")
        return False


async def run_image_test():
    """Generate a test image."""
    print("\n" + "=" * 50)
    print("IMAGE GENERATION TEST")
    print("=" * 50)

    from generators.image import ImageGenerator

    generator = ImageGenerator()
    print(f"  Provider: {generator.provider.provider_name}")
    print("  Generating test image...", end=" ", flush=True)

    result = await generator.generate(
        prompt="A simple blue circle on white background, minimalist",
        size="512x512",
        style="simple",
    )

    if result["error"]:
        print(f"✗ ERROR: {result['error']}")
        return False

    print("✓ SUCCESS")
    if result["url"]:
        print(f"    URL: {result['url'][:60]}...")
    if result["local_path"]:
        print(f"    Local path: {result['local_path']}")
    print(f"    Cost: ${result['cost_usd']:.4f}")

    return True


async def main():
    """Run all provider checks."""
    print("=" * 50)
    print("LOCAL PROVIDER SETUP TEST")
    print("=" * 50)
    print(f"\nConfiguration from: .env")
    print(f"LLM Provider: {settings.llm_provider}")
    print(f"Image Provider: {settings.image_provider}")
    print(f"Video Provider: {settings.video_provider}")

    results = {}

    # Check LLM
    results["llm"] = await check_llm_provider()

    # Check Image
    results["image"] = await check_image_provider()

    # Check Video
    results["video"] = await check_video_provider()

    # Summary
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)

    all_passed = True
    for name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {name.upper()}: {status}")
        if not passed:
            all_passed = False

    if all_passed:
        print("\n✓ All providers configured correctly!")

        # Ask if user wants to run generation tests
        print("\nWould you like to run generation tests? (y/n): ", end="")
        try:
            response = input()
            if response.lower() == "y":
                await run_image_test()
        except EOFError:
            pass

        return 0
    else:
        print("\n✗ Some providers are not configured correctly.")
        print("\nTroubleshooting:")
        if not results.get("llm"):
            if settings.llm_provider == "ollama":
                print("  - Ollama: Is 'ollama serve' running? Is the model pulled?")
                print(f"    Run: ollama pull {settings.ollama_model}")
            elif settings.llm_provider == "openai_compat":
                print("  - OpenAI-compat: Is the server running at the configured URL?")
            else:
                print("  - Bedrock: Check AWS credentials and model ID")

        if not results.get("image"):
            if settings.image_provider == "comfyui":
                print("  - ComfyUI: Is it running at the configured URL?")
            elif settings.image_provider == "sdwebui":
                print("  - SD WebUI: Is it running with --api flag?")
            else:
                print("  - fal.ai: Check FAL_KEY in .env")

        if not results.get("video"):
            if settings.video_provider == "cogvideo":
                print("  - CogVideoX: Is the server running?")
            else:
                print("  - HeyGen: Check HEYGEN_API_KEY in .env")

        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
