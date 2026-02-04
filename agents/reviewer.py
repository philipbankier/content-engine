"""ReviewerAgent: weekly strategy review, skill evolution, learning reports."""

import json
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, func

from agents.base import BaseAgent
from db import async_session
from models import ContentPublication, ContentMetric, ContentCreation, SkillMetric, SkillRecord
from skills.manager import SkillManager
from skills.evaluator import SkillEvaluator

logger = logging.getLogger(__name__)


class ReviewerAgent(BaseAgent):
    """Weekly review: performance analysis, skill health, strategic recommendations."""

    def __init__(self):
        super().__init__(name="reviewer")
        self.skill_manager = SkillManager()
        self.skill_evaluator = SkillEvaluator()

    async def run(self, at: datetime | None = None) -> dict:
        """Run weekly review cycle."""
        now = at or datetime.now(timezone.utc)
        week_ago = now - timedelta(days=7)

        # Load current skills
        self.skill_manager.load_all()

        # 1. Gather week's performance data
        performance = await self._gather_performance(week_ago, now)

        # 2. Review skill health
        skill_health = self._review_skill_health()

        # 3. Generate strategic recommendations via LLM
        recommendations = await self._generate_recommendations(performance, skill_health)

        # 4. Flag skills for retirement or update
        actions_taken = await self._take_actions(skill_health, now)

        report = {
            "period": {"start": week_ago.isoformat(), "end": now.isoformat()},
            "performance": performance,
            "skill_health": skill_health,
            "recommendations": recommendations,
            "actions_taken": actions_taken,
        }

        logger.info("Weekly review complete: %d recommendations, %d actions", len(recommendations), len(actions_taken))
        return report

    async def _gather_performance(self, start: datetime, end: datetime) -> dict:
        """Gather performance metrics for the review period."""
        async with async_session() as session:
            # Count publications
            pub_result = await session.execute(
                select(func.count(ContentPublication.id)).where(
                    ContentPublication.published_at >= start,
                    ContentPublication.published_at <= end,
                )
            )
            pub_count = pub_result.scalar() or 0

            # Count creations
            creation_result = await session.execute(
                select(func.count(ContentCreation.id)).where(
                    ContentCreation.created_at >= start,
                    ContentCreation.created_at <= end,
                )
            )
            creation_count = creation_result.scalar() or 0

            # Average engagement
            metrics_result = await session.execute(
                select(
                    func.avg(ContentMetric.engagement_rate),
                    func.sum(ContentMetric.views),
                    func.sum(ContentMetric.likes),
                ).where(
                    ContentMetric.collected_at >= start,
                    ContentMetric.collected_at <= end,
                )
            )
            row = metrics_result.one()
            avg_engagement = row[0] or 0.0
            total_views = row[1] or 0
            total_likes = row[2] or 0

        return {
            "publications": pub_count,
            "creations": creation_count,
            "avg_engagement_rate": round(avg_engagement, 4),
            "total_views": total_views,
            "total_likes": total_likes,
        }

    def _review_skill_health(self) -> list[dict]:
        """Check health of all skills."""
        results = []
        for skill in self.skill_manager.all_skills():
            health = self.skill_evaluator.check_health(skill)
            is_stale = self.skill_evaluator.detect_staleness(skill)
            results.append({
                "name": skill.name,
                "confidence": skill.confidence,
                "health": health["status"],
                "stale": is_stale,
                "reasons": health.get("reasons", []),
            })
        return results

    async def _generate_recommendations(self, performance: dict, skill_health: list[dict]) -> list[str]:
        """Use LLM to generate strategic recommendations."""
        skills = self.select_skills("source_scoring")  # Use general skills
        skills_text = self.format_skills_for_prompt(skills)

        system = (
            "You are a content strategy reviewer for Autopilot by Kairox AI. "
            "Analyze the week's performance data and skill health, then provide "
            "3-5 concise strategic recommendations. Be specific and actionable.\n\n"
            f"## Relevant Skills\n{skills_text}"
        )
        user = (
            f"Weekly Performance:\n{performance}\n\n"
            f"Skill Health Summary:\n"
            + "\n".join(f"- {s['name']}: confidence={s['confidence']}, health={s['health']}, stale={s['stale']}" for s in skill_health)
            + "\n\nProvide 3-5 strategic recommendations as a JSON array of strings."
        )

        content = await self.call_bedrock(system, user, max_tokens=1024)

        # Try to parse JSON, fall back to splitting by newlines
        try:
            # Handle potential markdown code fences
            if "```" in content:
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            return json.loads(content)
        except (json.JSONDecodeError, IndexError):
            return [line.strip("- ") for line in content.strip().split("\n") if line.strip()]

    async def _take_actions(self, skill_health: list[dict], now: datetime) -> list[str]:
        """Take automated actions based on skill health."""
        actions = []
        for sh in skill_health:
            if sh["stale"] and sh["confidence"] < 0.2:
                self.skill_manager.mark_stale(sh["name"])
                actions.append(f"Marked '{sh['name']}' as stale (confidence={sh['confidence']})")
            elif sh["health"] == "critical":
                self.skill_manager.mark_stale(sh["name"])
                actions.append(f"Flagged '{sh['name']}' for review (critical health)")
        return actions
