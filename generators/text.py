"""Text content generation via Claude on AWS Bedrock."""

import logging
from anthropic import AnthropicBedrock
from config import settings

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
    def __init__(self):
        self.client = AnthropicBedrock(
            aws_region=settings.aws_region,
            aws_access_key=settings.aws_access_key_id,
            aws_secret_key=settings.aws_secret_access_key,
        )
        self.model = settings.bedrock_model_id

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 4096,
        skills_context: str = "",
    ) -> dict:
        """Generate text content. Returns {"text": ..., "input_tokens": ..., "output_tokens": ...}."""
        system = system_prompt or f"You are a content creator for Autopilot by Kairox AI.\n\n{BRAND_VOICE}"
        if skills_context:
            system += f"\n\n## Relevant Skills\n{skills_context}"

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text if response.content else ""
            return {
                "text": text,
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            }
        except Exception as e:
            logger.error("Text generation failed: %s", e)
            return {"text": "", "input_tokens": 0, "output_tokens": 0, "error": str(e)}
