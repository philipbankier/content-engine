"""Ollama LLM provider for local model inference."""

import logging
import time

import httpx

from providers.llm.base import LLMProvider, LLMResponse

logger = logging.getLogger(__name__)

# Ollama can take a while for first inference (model loading)
DEFAULT_TIMEOUT = 300  # 5 minutes


class OllamaProvider(LLMProvider):
    """Ollama provider for local LLM inference.

    Recommended models for RTX 3060 (12GB VRAM):
    - qwen2.5:14b (Q4) - ~8GB, good quality
    - mistral:7b-v0.3 - ~5GB, fast
    - llama3.2:8b - ~6GB, balanced

    Usage:
        provider = OllamaProvider(base_url="http://localhost:11434", model="qwen2.5:14b")
        response = await provider.complete("You are helpful.", "Hello!")
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "qwen2.5:14b",
        timeout: int = DEFAULT_TIMEOUT,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    @property
    def provider_name(self) -> str:
        return "ollama"

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4096,
        json_mode: bool = False,
    ) -> LLMResponse:
        """Generate a completion using Ollama's chat API."""
        start_ms = time.time() * 1000

        payload: dict = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "options": {
                "num_predict": max_tokens,
            },
        }

        if json_mode:
            payload["format"] = "json"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()

            latency_ms = time.time() * 1000 - start_ms

            # Extract response text
            text = data.get("message", {}).get("content", "")

            # Ollama provides token counts in the response
            input_tokens = data.get("prompt_eval_count", 0)
            output_tokens = data.get("eval_count", 0)

            return LLMResponse(
                text=text,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                model=self.model,
                provider=self.provider_name,
                latency_ms=latency_ms,
                cost_usd=0.0,  # Local = free
            )

        except httpx.HTTPStatusError as e:
            logger.error("Ollama API error %d: %s", e.response.status_code, e.response.text)
            raise
        except httpx.ConnectError:
            logger.error("Cannot connect to Ollama at %s. Is it running?", self.base_url)
            raise
        except Exception as e:
            logger.error("Ollama call failed: %s", e)
            raise

    async def health_check(self) -> bool:
        """Check if Ollama is running and the model is available."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                # Check if Ollama is running
                response = await client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
                data = response.json()

                # Check if our model is available
                models = [m.get("name", "") for m in data.get("models", [])]
                model_base = self.model.split(":")[0]

                # Check for exact match or base name match
                for m in models:
                    if m == self.model or m.startswith(f"{model_base}:"):
                        return True

                logger.warning(
                    "Model %s not found in Ollama. Available: %s",
                    self.model,
                    ", ".join(models) if models else "none",
                )
                return False

        except Exception as e:
            logger.warning("Ollama health check failed: %s", e)
            return False

    async def pull_model(self) -> bool:
        """Pull the configured model if not already available."""
        try:
            async with httpx.AsyncClient(timeout=600) as client:  # 10 min for large models
                logger.info("Pulling model %s...", self.model)
                response = await client.post(
                    f"{self.base_url}/api/pull",
                    json={"name": self.model, "stream": False},
                )
                response.raise_for_status()
                logger.info("Model %s pulled successfully", self.model)
                return True
        except Exception as e:
            logger.error("Failed to pull model %s: %s", self.model, e)
            return False
