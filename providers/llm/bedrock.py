"""AWS Bedrock LLM provider using Claude models."""

import logging
import os
import time

from config import settings
from providers.llm.base import LLMProvider, LLMResponse

logger = logging.getLogger(__name__)


def _make_boto3_client():
    """Create a boto3 bedrock-runtime client with bearer token auth."""
    import boto3

    os.environ["AWS_BEARER_TOKEN_BEDROCK"] = settings.aws_bearer_token_bedrock
    # Clear IAM keys from env so boto3 picks up the bearer token instead
    for key in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_PROFILE", "AWS_SESSION_TOKEN"):
        os.environ.pop(key, None)
    return boto3.client("bedrock-runtime", region_name=settings.aws_region)


def _make_anthropic_client():
    """Create an AnthropicBedrock client for SigV4 (IAM key) auth."""
    from anthropic import AnthropicBedrock

    if settings.aws_access_key_id and settings.aws_secret_access_key:
        return AnthropicBedrock(
            aws_region=settings.aws_region,
            aws_access_key=settings.aws_access_key_id,
            aws_secret_key=settings.aws_secret_access_key,
        )
    return AnthropicBedrock(aws_region=settings.aws_region)


class BedrockProvider(LLMProvider):
    """AWS Bedrock provider for Claude models.

    Supports two authentication methods:
    - Bearer token auth (via boto3 converse API)
    - IAM key auth (via AnthropicBedrock SDK)
    """

    def __init__(self, model_id: str | None = None):
        self.model_id = model_id or settings.bedrock_model_id

    @property
    def provider_name(self) -> str:
        return "bedrock"

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4096,
        json_mode: bool = False,
    ) -> LLMResponse:
        """Generate a completion using AWS Bedrock."""
        start_ms = time.time() * 1000

        try:
            if settings.aws_bearer_token_bedrock:
                # Bearer token auth — use boto3 converse API
                content_text, input_tokens, output_tokens = self._call_via_boto3(
                    system_prompt, user_prompt, max_tokens
                )
            else:
                # IAM key auth — use AnthropicBedrock SDK
                content_text, input_tokens, output_tokens = self._call_via_anthropic(
                    system_prompt, user_prompt, max_tokens
                )

            latency_ms = time.time() * 1000 - start_ms

            # Estimate cost (Claude Sonnet via Bedrock ballpark)
            # Input: $3/M tokens, Output: $15/M tokens
            cost_usd = (input_tokens * 3.0 + output_tokens * 15.0) / 1_000_000

            return LLMResponse(
                text=content_text,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                model=self.model_id,
                provider=self.provider_name,
                latency_ms=latency_ms,
                cost_usd=cost_usd,
            )

        except Exception as e:
            logger.error("Bedrock call failed: %s", e)
            raise

    def _call_via_boto3(
        self, system_prompt: str, user_prompt: str, max_tokens: int
    ) -> tuple[str, int, int]:
        """Call Bedrock using boto3 converse API (supports bearer token auth)."""
        client = _make_boto3_client()
        response = client.converse(
            modelId=self.model_id,
            system=[{"text": system_prompt}],
            messages=[{"role": "user", "content": [{"text": user_prompt}]}],
            inferenceConfig={"maxTokens": max_tokens},
        )
        content_text = response["output"]["message"]["content"][0]["text"]
        usage = response.get("usage", {})
        input_tokens = usage.get("inputTokens", 0)
        output_tokens = usage.get("outputTokens", 0)
        return content_text, input_tokens, output_tokens

    def _call_via_anthropic(
        self, system_prompt: str, user_prompt: str, max_tokens: int
    ) -> tuple[str, int, int]:
        """Call Bedrock using AnthropicBedrock SDK (SigV4 / IAM key auth)."""
        client = _make_anthropic_client()
        response = client.messages.create(
            model=self.model_id,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        content_text = response.content[0].text if response.content else ""
        return content_text, response.usage.input_tokens, response.usage.output_tokens

    async def health_check(self) -> bool:
        """Check if Bedrock is accessible with a minimal completion request."""
        try:
            response = await self.complete(
                system_prompt="You are a health check assistant.",
                user_prompt="Reply with just 'OK'.",
                max_tokens=10,
            )
            return bool(response.text)
        except Exception as e:
            logger.warning("Bedrock health check failed: %s", e)
            return False
