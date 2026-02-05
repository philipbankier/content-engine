"""Text content generation via configurable LLM provider."""

import logging

from providers.factory import get_llm_provider
from providers.llm.base import LLMProvider

logger = logging.getLogger(__name__)

BRAND_VOICE = """Brand Voice: Calm, confident, technical, grounded. Builder-to-builder, operator-to-operator.
Core message: "This is how work actually gets done."
Style rules:
- Short paragraphs, declarative statements, minimal adjectives
- No buzzwords ("revolutionary", "game-changing", "leverage AI")
- No exclamation points
- No sales CTAs
- No overly anthropomorphic AI language"""


class TextGenerator:
    def __init__(self, provider: LLMProvider | None = None):
        self._provider = provider

    @property
    def provider(self) -> LLMProvider:
        if self._provider is None:
            self._provider = get_llm_provider()
        return self._provider

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 4096,
        skills_context: str = "",
    ) -> dict:
        """Generate text content.

        Returns:
            dict with keys: text, input_tokens, output_tokens, provider, cost_usd
            On error: includes "error" key
        """
        system = system_prompt or f"You are a content creator for Autopilot by Kairox AI.\n\n{BRAND_VOICE}"
        if skills_context:
            system += f"\n\n## Relevant Skills\n{skills_context}"

        try:
            response = await self.provider.complete(
                system_prompt=system,
                user_prompt=prompt,
                max_tokens=max_tokens,
            )
            return {
                "text": response.text,
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "provider": response.provider,
                "cost_usd": response.cost_usd,
            }
        except Exception as e:
            logger.error("Text generation failed: %s", e)
            return {
                "text": "",
                "input_tokens": 0,
                "output_tokens": 0,
                "provider": self.provider.provider_name,
                "cost_usd": 0.0,
                "error": str(e),
            }
