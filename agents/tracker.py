"""TrackerAgent: collects engagement metrics from published content."""

import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import select

from agents.base import BaseAgent
from db import async_session
from models import ContentPublication, ContentMetric, ContentCreation
from skills.manager import SkillManager

logger = logging.getLogger(__name__)

# Module-level skill manager reference (shared with BaseAgent)
_skill_manager: SkillManager | None = None


def _get_skill_manager() -> SkillManager:
    global _skill_manager
    if _skill_manager is None:
        _skill_manager = SkillManager()
        _skill_manager.load_all()
    return _skill_manager

# Intervals to collect metrics at (hours since publication)
METRIC_INTERVALS = {
    "1h": timedelta(hours=1),
    "6h": timedelta(hours=6),
    "24h": timedelta(hours=24),
    "48h": timedelta(hours=48),
    "7d": timedelta(days=7),
}


class TrackerAgent(BaseAgent):
    """Collect engagement metrics from platforms at scheduled intervals."""

    def __init__(self):
        super().__init__(name="tracker")

    async def run(self, at: datetime | None = None) -> dict:
        """Check all publications and collect metrics at appropriate intervals."""
        now = at or datetime.now(timezone.utc)
        collected = 0
        errors = 0
        skills_updated = 0

        async with async_session() as session:
            result = await session.execute(select(ContentPublication))
            publications = result.scalars().all()

        for pub in publications:
            for interval_name, interval_delta in METRIC_INTERVALS.items():
                target_time = pub.published_at + interval_delta
                # Only collect if we've passed the interval time
                if now < target_time:
                    continue

                # Check if we already collected this interval
                async with async_session() as session:
                    existing = await session.execute(
                        select(ContentMetric).where(
                            ContentMetric.publication_id == pub.id,
                            ContentMetric.interval == interval_name,
                        )
                    )
                    if existing.scalar_one_or_none():
                        continue

                # Collect metrics (in production, call publisher.get_metrics())
                try:
                    metrics = await self._collect_metrics(pub, interval_name)
                    async with async_session() as session:
                        metric = ContentMetric(
                            publication_id=pub.id,
                            interval=interval_name,
                            views=metrics.get("views", 0),
                            likes=metrics.get("likes", 0),
                            comments=metrics.get("comments", 0),
                            shares=metrics.get("shares", 0),
                            clicks=metrics.get("clicks", 0),
                            followers_gained=metrics.get("followers_gained", 0),
                            engagement_rate=metrics.get("engagement_rate", 0.0),
                            collected_at=now,
                        )
                        session.add(metric)
                        await session.commit()
                    collected += 1

                    # Update skill outcomes at 24h interval (our primary learning signal)
                    if interval_name == "24h":
                        skill_updates = await self._update_skill_outcomes_from_metrics(
                            pub, metrics, now
                        )
                        skills_updated += skill_updates

                except Exception as e:
                    logger.error("Failed to collect metrics for pub %d at %s: %s", pub.id, interval_name, e)
                    errors += 1

        logger.info("Tracker: collected %d metrics, updated %d skill outcomes, %d errors", collected, skills_updated, errors)
        return {"collected": collected, "skills_updated": skills_updated, "errors": errors}

    async def _collect_metrics(self, publication, interval: str) -> dict:
        """Fetch metrics from the appropriate platform publisher."""
        # Import publishers dynamically to avoid circular imports
        from publishers.upload_post import UploadPostPublisher
        from publishers.tiktok import TikTokPublisher

        if publication.platform == "tiktok":
            publisher = TikTokPublisher()
        else:
            publisher = UploadPostPublisher()

        if publication.platform_post_id:
            return await publisher.get_metrics(publication.platform_post_id)

        # Return empty metrics if no publisher or no post ID
        return {"views": 0, "likes": 0, "comments": 0, "shares": 0, "clicks": 0}

    async def _update_skill_outcomes_from_metrics(
        self, publication: ContentPublication, metrics: dict, now: datetime
    ) -> int:
        """Update skill outcomes based on actual engagement metrics.

        This is the critical link that connects real performance back to skills.
        We use engagement_rate as the primary signal, normalized to 0-1 scale.

        Returns the number of skills updated.
        """
        # Get the ContentCreation to find which skills were used
        async with async_session() as session:
            result = await session.execute(
                select(ContentCreation).where(ContentCreation.id == publication.creation_id)
            )
            creation = result.scalar_one_or_none()

        if not creation or not creation.skills_used:
            return 0

        skills_used = creation.skills_used
        if isinstance(skills_used, str):
            import json
            try:
                skills_used = json.loads(skills_used)
            except (json.JSONDecodeError, TypeError):
                return 0

        if not skills_used:
            return 0

        # Calculate score from engagement metrics
        # Engagement rate is typically 1-10%, so we normalize:
        # - 0-1% = poor (0.0-0.3)
        # - 1-3% = average (0.3-0.6)
        # - 3-5% = good (0.6-0.8)
        # - 5%+ = excellent (0.8-1.0)
        engagement_rate = metrics.get("engagement_rate", 0.0)

        # Normalize to 0-1 score
        if engagement_rate >= 0.05:
            score = 0.8 + min((engagement_rate - 0.05) * 4, 0.2)  # 0.8-1.0
        elif engagement_rate >= 0.03:
            score = 0.6 + (engagement_rate - 0.03) * 10  # 0.6-0.8
        elif engagement_rate >= 0.01:
            score = 0.3 + (engagement_rate - 0.01) * 15  # 0.3-0.6
        else:
            score = max(engagement_rate * 30, 0.0)  # 0.0-0.3

        # Determine outcome based on score
        if score >= 0.6:
            outcome = "success"
        elif score >= 0.3:
            outcome = "partial"
        else:
            outcome = "failure"

        # Record outcome for each skill used
        skill_manager = _get_skill_manager()
        updated = 0

        for skill_name in skills_used:
            skill_manager.record_outcome(
                skill_name=skill_name,
                outcome=outcome,
                score=score,
                at=now,
                agent="tracker",
                task="engagement_feedback",
                context={
                    "publication_id": publication.id,
                    "creation_id": creation.id,
                    "platform": publication.platform,
                    "engagement_rate": engagement_rate,
                    "views": metrics.get("views", 0),
                    "likes": metrics.get("likes", 0),
                    "comments": metrics.get("comments", 0),
                    "shares": metrics.get("shares", 0),
                },
            )
            updated += 1
            logger.info(
                "Skill '%s' outcome updated: %.3f (engagement: %.2f%%) from %s content",
                skill_name, score, engagement_rate * 100, publication.platform
            )

        return updated
