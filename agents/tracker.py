"""TrackerAgent: collects engagement metrics from published content."""

import logging
from collections import defaultdict
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, func

from agents.base import BaseAgent
from db import async_session
from models import ContentPublication, ContentMetric, ContentCreation, SkillMetric, SkillInteraction
from skills.manager import SkillManager
from itertools import combinations

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

# Platform-specific engagement benchmarks for composite scoring
PLATFORM_BENCHMARKS = {
    "linkedin": {
        "engagement_rate": 0.05,  # 5% is excellent
        "share_rate": 0.01,       # 1% share rate is good
        "save_rate": 0.02,        # 2% save rate is good
        "comment_rate": 0.005,    # 0.5% comment rate is good
        "click_rate": 0.02,       # 2% CTR is good
    },
    "twitter": {
        "engagement_rate": 0.03,
        "share_rate": 0.02,
        "save_rate": 0.01,
        "comment_rate": 0.003,
        "click_rate": 0.015,
    },
    "youtube": {
        "engagement_rate": 0.08,
        "share_rate": 0.005,
        "save_rate": 0.03,
        "comment_rate": 0.01,
        "click_rate": 0.03,
    },
    "tiktok": {
        "engagement_rate": 0.10,
        "share_rate": 0.03,
        "save_rate": 0.05,
        "comment_rate": 0.02,
        "click_rate": 0.02,
    },
    "medium": {
        "engagement_rate": 0.04,
        "share_rate": 0.01,
        "save_rate": 0.02,
        "comment_rate": 0.005,
        "click_rate": 0.03,
    },
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
                            saves=metrics.get("saves", 0),  # Bookmarks/saves
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
            if publication.platform_post_id:
                return await publisher.get_metrics(publication.platform_post_id)
        else:
            publisher = UploadPostPublisher()
            if publication.platform_post_id or publication.platform_url:
                # Pass platform_url to enable real metrics scraping
                return await publisher.get_metrics(
                    post_id=publication.platform_post_id or "",
                    platform=publication.platform,
                    platform_url=publication.platform_url,
                )

        # Return empty metrics if no publisher or no post ID
        return {"views": 0, "likes": 0, "comments": 0, "shares": 0, "clicks": 0}

    async def _update_skill_outcomes_from_metrics(
        self, publication: ContentPublication, metrics: dict, now: datetime
    ) -> int:
        """Update skill outcomes based on actual engagement metrics with weighted attribution.

        This is the critical link that connects real performance back to skills.
        Uses multi-signal composite scoring and weighted skill attribution based on
        historical baselines to properly attribute success/failure to individual skills.

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

        platform = publication.platform or "linkedin"

        # Calculate composite score from multiple engagement signals
        composite_score = self._calculate_composite_score(metrics, platform)

        # Get historical baselines for each skill used
        skill_baselines = await self._get_skill_baselines(skills_used)

        # Calculate expected performance given the skill mix
        if skill_baselines:
            expected_score = sum(skill_baselines.values()) / len(skill_baselines)
        else:
            expected_score = 0.5  # Default expectation

        # Record outcome for each skill with weighted attribution
        skill_manager = _get_skill_manager()
        updated = 0

        for skill_name in skills_used:
            baseline = skill_baselines.get(skill_name, 0.5)

            # Attribute contribution based on deviation from baseline
            if composite_score >= expected_score:
                # Success: skills that historically underperform get credit for lifting
                # (they contributed more than expected)
                if expected_score > 0:
                    contribution = baseline / expected_score
                else:
                    contribution = 1.0
                # Bound contribution factor
                contribution = max(0.5, min(1.5, contribution))
            else:
                # Failure: skills that historically overperform get penalized more
                # (they failed to deliver their expected value)
                if baseline > 0:
                    shortfall = expected_score - composite_score
                    contribution = 1 + (baseline - 0.5) * (shortfall / 0.5)
                else:
                    contribution = 1.0
                # Bound contribution factor
                contribution = max(0.5, min(1.5, contribution))

            # Calculate attributed score
            attributed_score = composite_score * contribution
            attributed_score = max(0.0, min(1.0, attributed_score))

            # Determine outcome based on attributed score
            if attributed_score >= 0.6:
                outcome = "success"
            elif attributed_score >= 0.3:
                outcome = "partial"
            else:
                outcome = "failure"

            skill_manager.record_outcome(
                skill_name=skill_name,
                outcome=outcome,
                score=attributed_score,
                at=now,
                agent="tracker",
                task="engagement_feedback",
                context={
                    "publication_id": publication.id,
                    "creation_id": creation.id,
                    "platform": platform,
                    "raw_composite_score": composite_score,
                    "skill_baseline": baseline,
                    "expected_score": expected_score,
                    "contribution_factor": contribution,
                    "engagement_rate": metrics.get("engagement_rate", 0.0),
                    "views": metrics.get("views", 0),
                    "likes": metrics.get("likes", 0),
                    "comments": metrics.get("comments", 0),
                    "shares": metrics.get("shares", 0),
                },
            )
            updated += 1
            logger.info(
                "Skill '%s' outcome: %.3f (baseline: %.3f, contribution: %.2fx) from %s",
                skill_name, attributed_score, baseline, contribution, platform
            )

        # Track skill interactions (combinations of 2+ skills)
        if len(skills_used) >= 2:
            await self._update_skill_interactions(
                skills_used, composite_score, skill_baselines, now
            )

        return updated

    async def _update_skill_interactions(
        self,
        skills_used: list[str],
        composite_score: float,
        skill_baselines: dict[str, float],
        now: datetime,
    ) -> None:
        """Track skill co-occurrence outcomes to discover synergies and conflicts.

        For each pair of skills used together, calculates a synergy score:
        - Positive synergy: skills amplify each other (combined > individual averages)
        - Negative synergy: skills conflict (combined < individual averages)
        """
        # Generate all pairs of skills
        skill_pairs = list(combinations(sorted(skills_used), 2))

        async with async_session() as session:
            for skill_a, skill_b in skill_pairs:
                # Calculate expected score based on individual baselines
                baseline_a = skill_baselines.get(skill_a, 0.5)
                baseline_b = skill_baselines.get(skill_b, 0.5)
                expected_combined = (baseline_a + baseline_b) / 2

                # Synergy = actual combined - expected combined
                # Positive = they work better together than individually
                # Negative = they conflict
                synergy = composite_score - expected_combined

                # Find or create interaction record
                result = await session.execute(
                    select(SkillInteraction).where(
                        SkillInteraction.skill_a == skill_a,
                        SkillInteraction.skill_b == skill_b,
                    )
                )
                interaction = result.scalar_one_or_none()

                if interaction is None:
                    # Create new interaction record
                    interaction = SkillInteraction(
                        skill_a=skill_a,
                        skill_b=skill_b,
                        co_occurrence_count=1,
                        avg_combined_score=composite_score,
                        synergy_score=synergy,
                        last_used_at=now,
                        updated_at=now,
                    )
                    session.add(interaction)
                else:
                    # Update existing record with rolling average
                    n = interaction.co_occurrence_count
                    interaction.avg_combined_score = (
                        interaction.avg_combined_score * n + composite_score
                    ) / (n + 1)
                    interaction.synergy_score = (
                        interaction.synergy_score * n + synergy
                    ) / (n + 1)
                    interaction.co_occurrence_count = n + 1
                    interaction.last_used_at = now
                    interaction.updated_at = now

                # Log significant synergies
                if abs(interaction.synergy_score) > 0.1 and interaction.co_occurrence_count >= 3:
                    if interaction.synergy_score > 0:
                        logger.info(
                            "SYNERGY: %s + %s = +%.2f (n=%d)",
                            skill_a, skill_b, interaction.synergy_score,
                            interaction.co_occurrence_count
                        )
                    else:
                        logger.warning(
                            "CONFLICT: %s + %s = %.2f (n=%d)",
                            skill_a, skill_b, interaction.synergy_score,
                            interaction.co_occurrence_count
                        )

            await session.commit()

    def _calculate_composite_score(self, metrics: dict, platform: str) -> float:
        """Calculate weighted composite score from multiple engagement signals.

        Uses platform-specific benchmarks to normalize each signal and weights
        them to produce a single 0-1 score.
        """
        benchmarks = PLATFORM_BENCHMARKS.get(platform, PLATFORM_BENCHMARKS["linkedin"])

        views = max(metrics.get("views", 1), 1)  # Avoid division by zero
        engagement_rate = metrics.get("engagement_rate", 0.0)
        shares = metrics.get("shares", 0)
        saves = metrics.get("saves", 0)  # May not be available for all platforms
        comments = metrics.get("comments", 0)
        clicks = metrics.get("clicks", 0)

        # Calculate individual rates
        share_rate = shares / views
        save_rate = saves / views
        comment_rate = comments / views
        click_rate = clicks / views

        # Define signal weights
        weights = {
            "engagement_rate": 0.30,  # Overall engagement still matters
            "share_rate": 0.25,       # Shares indicate viral potential
            "save_rate": 0.20,        # Saves indicate value/usefulness
            "comment_rate": 0.15,     # Comments indicate discussion quality
            "click_rate": 0.10,       # Clicks indicate interest
        }

        signals = {
            "engagement_rate": engagement_rate,
            "share_rate": share_rate,
            "save_rate": save_rate,
            "comment_rate": comment_rate,
            "click_rate": click_rate,
        }

        composite = 0.0
        for signal_name, value in signals.items():
            benchmark = benchmarks.get(signal_name, 0.01)
            # Normalize: benchmark = 1.0 score, double benchmark = 1.0 (capped)
            normalized = min(1.0, value / benchmark) if benchmark > 0 else 0.0
            weight = weights.get(signal_name, 0.1)
            composite += normalized * weight

        return min(1.0, composite)

    async def _get_skill_baselines(self, skill_names: list[str]) -> dict[str, float]:
        """Get historical success rate (baseline) for each skill.

        Returns a dict mapping skill_name -> average score from recent outcomes.
        Skills with no history default to 0.5.
        """
        baselines = {}
        lookback_days = 30

        async with async_session() as session:
            cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)

            for skill_name in skill_names:
                result = await session.execute(
                    select(func.avg(SkillMetric.score))
                    .where(SkillMetric.skill_name == skill_name)
                    .where(SkillMetric.recorded_at >= cutoff)
                    .where(SkillMetric.agent == "tracker")  # Only engagement-based metrics
                )
                avg_score = result.scalar()

                if avg_score is not None:
                    baselines[skill_name] = float(avg_score)
                else:
                    # No historical data - check skill's current confidence
                    skill_manager = _get_skill_manager()
                    skill = skill_manager.get_skill(skill_name)
                    if skill:
                        baselines[skill_name] = skill.confidence
                    else:
                        baselines[skill_name] = 0.5

        return baselines
