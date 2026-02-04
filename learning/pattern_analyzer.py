"""Analyze skill and content metrics to find performance patterns."""

import logging
from collections import defaultdict

from sqlalchemy import select

from db import async_session
from models import ContentCreation, ContentMetric, ContentPublication, SkillMetric

logger = logging.getLogger(__name__)


class PatternAnalyzer:
    """Discover which skills and content strategies drive engagement."""

    async def analyze(self) -> list[dict]:
        """Analyze metrics and return a list of pattern insights.

        Each pattern dict has:
            pattern: str description
            strength: float 0-1
            skills: list[str]
            recommendation: str
        """
        patterns: list[dict] = []

        # --- Skill performance from SkillMetric ---
        skill_stats = await self._aggregate_skill_metrics()

        # --- Engagement correlated with skills ---
        skill_engagement = await self._correlate_skills_with_engagement()

        # Find high-performing skills
        for skill_name, stats in skill_stats.items():
            if stats["avg_score"] >= 0.7 and stats["sample_size"] >= 5:
                patterns.append({
                    "pattern": f"Skill '{skill_name}' consistently scores well",
                    "strength": round(min(stats["avg_score"], 1.0), 2),
                    "skills": [skill_name],
                    "recommendation": f"Continue using '{skill_name}'; consider increasing weight.",
                })

        # Find skills correlated with high engagement
        for skill_name, eng in skill_engagement.items():
            if eng["avg_engagement"] >= 0.6 and eng["sample_size"] >= 3:
                patterns.append({
                    "pattern": f"Content using '{skill_name}' gets above-average engagement",
                    "strength": round(min(eng["avg_engagement"], 1.0), 2),
                    "skills": [skill_name],
                    "recommendation": f"Prioritize '{skill_name}' in content creation.",
                })

        # Find underperforming skills
        for skill_name, stats in skill_stats.items():
            if stats["avg_score"] < 0.3 and stats["sample_size"] >= 5:
                patterns.append({
                    "pattern": f"Skill '{skill_name}' is underperforming",
                    "strength": round(1.0 - stats["avg_score"], 2),
                    "skills": [skill_name],
                    "recommendation": f"Consider revising or replacing '{skill_name}'.",
                })

        logger.info("Pattern analysis found %d patterns", len(patterns))
        return patterns

    def correlate_skill_outcomes(self, metrics: list[dict]) -> dict:
        """Group metrics by skill and compute trend information.

        Args:
            metrics: list of dicts with at least 'skill_name' and 'score' keys.

        Returns:
            {skill_name: {"avg_score": float, "trend": str, "sample_size": int}}
        """
        grouped: dict[str, list[float]] = defaultdict(list)
        for m in metrics:
            grouped[m["skill_name"]].append(m["score"])

        result = {}
        for skill_name, scores in grouped.items():
            avg = sum(scores) / len(scores)
            trend = self._compute_trend(scores)
            result[skill_name] = {
                "avg_score": round(avg, 3),
                "trend": trend,
                "sample_size": len(scores),
            }
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _aggregate_skill_metrics(self) -> dict:
        """Return {skill_name: {"avg_score": float, "sample_size": int}}."""
        async with async_session() as session:
            result = await session.execute(select(SkillMetric))
            rows = result.scalars().all()

        grouped: dict[str, list[float]] = defaultdict(list)
        for row in rows:
            grouped[row.skill_name].append(row.score)

        return {
            name: {
                "avg_score": round(sum(scores) / len(scores), 3),
                "sample_size": len(scores),
            }
            for name, scores in grouped.items()
        }

    async def _correlate_skills_with_engagement(self) -> dict:
        """Correlate skills_used on ContentCreation with engagement from ContentMetric.

        Join path: ContentCreation → ContentPublication (via creation_id) → ContentMetric (via publication_id).
        """
        async with async_session() as session:
            result = await session.execute(
                select(ContentCreation, ContentMetric)
                .join(ContentPublication, ContentCreation.id == ContentPublication.creation_id)
                .join(ContentMetric, ContentPublication.id == ContentMetric.publication_id)
            )
            rows = result.all()

        skill_engagement: dict[str, list[float]] = defaultdict(list)
        for creation, metric in rows:
            skills = creation.skills_used or []
            rate = metric.engagement_rate or 0.0
            for skill in skills:
                skill_engagement[skill].append(rate)

        return {
            name: {
                "avg_engagement": round(sum(rates) / len(rates), 3),
                "sample_size": len(rates),
            }
            for name, rates in skill_engagement.items()
        }

    @staticmethod
    def _compute_trend(scores: list[float]) -> str:
        """Determine trend direction from a list of chronological scores."""
        if len(scores) < 3:
            return "stable"
        first_half = scores[: len(scores) // 2]
        second_half = scores[len(scores) // 2 :]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        diff = avg_second - avg_first
        if diff > 0.05:
            return "improving"
        elif diff < -0.05:
            return "degrading"
        return "stable"
