import logging
import time
import traceback
from datetime import datetime, timezone

from db import async_session
from models import ContentAgentRun
from providers.factory import get_llm_provider
from providers.llm.base import LLMProvider
from skills.manager import SkillManager

# Module-level SkillManager so skills are loaded once and shared
_skill_manager: SkillManager | None = None


def _get_skill_manager() -> SkillManager:
    global _skill_manager
    if _skill_manager is None:
        _skill_manager = SkillManager()
        _skill_manager.load_all()
    return _skill_manager


class BaseAgent:
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"agent.{name}")
        self._llm_provider: LLMProvider | None = None

    @property
    def llm_provider(self) -> LLMProvider:
        """Get the configured LLM provider (lazy initialization)."""
        if self._llm_provider is None:
            self._llm_provider = get_llm_provider()
        return self._llm_provider

    def select_skills(self, task_type: str, platform: str | None = None) -> list:
        return _get_skill_manager().get_for_task(task_type=task_type, platform=platform)

    async def call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        skills: list | None = None,
        max_tokens: int = 4096,
    ) -> str:
        """Call the configured LLM provider and return the response text.

        Also logs the run to DB with cost tracking.
        """
        # Inject skills into system prompt
        full_system = system_prompt
        if skills:
            skills_section = self.format_skills_for_prompt(skills)
            full_system = f"{system_prompt}\n\n{skills_section}"

        start = time.time()
        try:
            response = await self.llm_provider.complete(
                system_prompt=full_system,
                user_prompt=user_prompt,
                max_tokens=max_tokens,
            )

            duration = time.time() - start

            # Log to content_agent_runs table
            try:
                async with async_session() as session:
                    run = ContentAgentRun(
                        agent=self.name,
                        task=None,
                        input_tokens=response.input_tokens,
                        output_tokens=response.output_tokens,
                        estimated_cost_usd=response.cost_usd,
                        duration_seconds=round(duration, 2),
                        status="completed",
                        provider=response.provider,
                        started_at=datetime.now(timezone.utc),
                        completed_at=datetime.now(timezone.utc),
                    )
                    session.add(run)
                    await session.commit()
            except Exception:
                self.logger.warning("Failed to log agent run to database", exc_info=True)

            return response.text

        except Exception as e:
            self.logger.error("LLM call failed: %s\n%s", e, traceback.format_exc())
            raise

    async def call_bedrock(
        self,
        system_prompt: str,
        user_prompt: str,
        skills: list | None = None,
        max_tokens: int = 4096,
    ) -> str:
        """Call the LLM provider (deprecated, use call_llm instead).

        This method is kept for backwards compatibility.
        """
        return await self.call_llm(system_prompt, user_prompt, skills, max_tokens)

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
