import logging
import os
import time
import traceback
from datetime import datetime, timezone

from config import settings
from db import async_session
from models import ContentAgentRun
from skills.manager import SkillManager

# Module-level SkillManager so skills are loaded once and shared
_skill_manager: SkillManager | None = None


def _get_skill_manager() -> SkillManager:
    global _skill_manager
    if _skill_manager is None:
        _skill_manager = SkillManager()
        _skill_manager.load_all()
    return _skill_manager


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


class BaseAgent:
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"agent.{name}")

    def select_skills(self, task_type: str, platform: str | None = None) -> list:
        return _get_skill_manager().get_for_task(task_type=task_type, platform=platform)

    async def call_bedrock(
        self,
        system_prompt: str,
        user_prompt: str,
        skills: list | None = None,
        max_tokens: int = 4096,
    ) -> str:
        """Call Bedrock and return the response text. Also logs the run to DB."""
        # Inject skills into system prompt
        full_system = system_prompt
        if skills:
            skills_section = self.format_skills_for_prompt(skills)
            full_system = f"{system_prompt}\n\n{skills_section}"

        start = time.time()
        try:
            if settings.aws_bearer_token_bedrock:
                # Bearer token auth — AnthropicBedrock doesn't support it
                # (it only does SigV4), so use boto3 converse API directly.
                content_text, input_tokens, output_tokens = self._call_via_boto3(
                    full_system, user_prompt, max_tokens
                )
            else:
                # IAM key auth — use AnthropicBedrock SDK.
                content_text, input_tokens, output_tokens = self._call_via_anthropic(
                    full_system, user_prompt, max_tokens
                )

            duration = time.time() - start

            # Estimate cost (Claude Sonnet via Bedrock ballpark)
            est_cost = (input_tokens * 3.0 + output_tokens * 15.0) / 1_000_000

            # Log to content_agent_runs table
            try:
                async with async_session() as session:
                    run = ContentAgentRun(
                        agent=self.name,
                        task=None,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        estimated_cost_usd=est_cost,
                        duration_seconds=round(duration, 2),
                        status="completed",
                        started_at=datetime.now(timezone.utc),
                        completed_at=datetime.now(timezone.utc),
                    )
                    session.add(run)
                    await session.commit()
            except Exception:
                self.logger.warning("Failed to log agent run to database", exc_info=True)

            return content_text

        except Exception as e:
            self.logger.error("Bedrock call failed: %s\n%s", e, traceback.format_exc())
            raise

    def _call_via_boto3(
        self, system_prompt: str, user_prompt: str, max_tokens: int
    ) -> tuple[str, int, int]:
        """Call Bedrock using boto3 converse API (supports bearer token auth)."""
        client = _make_boto3_client()
        response = client.converse(
            modelId=settings.bedrock_model_id,
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
            model=settings.bedrock_model_id,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        content_text = response.content[0].text if response.content else ""
        return content_text, response.usage.input_tokens, response.usage.output_tokens

    def record_outcome(
        self,
        skills_used: list[str],
        outcome: str,
        score: float,
        task: str | None = None,
        context: dict | None = None,
    ):
        manager = _get_skill_manager()
        for skill_name in skills_used:
            manager.record_outcome(
                skill_name=skill_name,
                outcome=outcome,
                score=score,
                agent=self.name,
                task=task,
                context=context,
            )

    def format_skills_for_prompt(self, skills: list) -> str:
        if not skills:
            return ""

        sections = ["## Relevant Skills\n"]
        for skill in skills:
            name = getattr(skill, "name", str(skill))
            confidence = getattr(skill, "confidence", None)
            content = getattr(skill, "content", "")
            header = f"### {name}"
            if confidence is not None:
                header += f" (confidence: {confidence:.2f})"
            sections.append(header)
            if content:
                sections.append(content)
            sections.append("")

        return "\n".join(sections)
