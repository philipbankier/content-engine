"""OpenAI-compatible LLM provider for vLLM, LM Studio, text-generation-webui, etc."""

import logging
import time

import httpx

from providers.llm.base import LLMProvider, LLMResponse

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 300  # 5 minutes


class OpenAICompatProvider(LLMProvider):
    """OpenAI-compatible API provider.

    Works with:
    - vLLM (recommended for production)
    - LM Studio
    - text-generation-webui with OpenAI extension
    - LocalAI
    - Any server implementing OpenAI's /v1/chat/completions endpoint

    Usage:
        provider = OpenAICompatProvider(
            base_url="http://localhost:8000/v1",
            model="qwen2.5-14b",
            api_key="token-if-needed"
        )
        response = await provider.complete("You are helpful.", "Hello!")
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000/v1",
        model: str = "qwen2.5-14b",
        api_key: str | None = None,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout

    @property
    def provider_name(self) -> str:
        return "openai_compat"

    def _get_headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4096,
        json_mode: bool = False,
    ) -> LLMResponse:
        """Generate a completion using the OpenAI-compatible API."""
        start_ms = time.time() * 1000

        payload: dict = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens,
            "stream": False,
        }

        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self._get_headers(),
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()

            latency_ms = time.time() * 1000 - start_ms

            # Extract response text
            choices = data.get("choices", [])
            text = choices[0]["message"]["content"] if choices else ""

            # Extract token usage
            usage = data.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)

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
            logger.error(
                "OpenAI-compat API error %d: %s",
                e.response.status_code,
                e.response.text,
            )
            raise
        except httpx.ConnectError:
            logger.error("Cannot connect to API at %s. Is the server running?", self.base_url)
            raise
        except Exception as e:
            logger.error("OpenAI-compat call failed: %s", e)
            raise

    async def health_check(self) -> bool:
        """Check if the API server is running and responding."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                # Try the models endpoint (standard OpenAI endpoint)
                response = await client.get(
                    f"{self.base_url}/models",
                    headers=self._get_headers(),
                )
                response.raise_for_status()
                data = response.json()

                # Check if our model is available
                models = [m.get("id", "") for m in data.get("data", [])]
                if self.model in models:
                    return True

                # Some servers don't list models, just check if endpoint works
                if response.status_code == 200:
                    logger.info(
                        "API responding but model %s not in list. Available: %s",
                        self.model,
                        ", ".join(models) if models else "unknown",
                    )
                    return True

                return False

        except Exception as e:
            logger.warning("OpenAI-compat health check failed: %s", e)
            return False
