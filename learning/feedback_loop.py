"""Feedback loop — ties pattern analysis, experiments, and skill updates together."""

import logging
from collections import defaultdict
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, desc, func

from db import async_session
from learning.experiment_runner import ExperimentRunner
from learning.failure_patterns import get_failure_tracker
from learning.pattern_analyzer import PatternAnalyzer
from models import SkillMetric, ContentExperiment
from skills.evaluator import SkillEvaluator
from skills.manager import SkillManager
from skills.synthesizer import SkillSynthesizer

logger = logging.getLogger(__name__)

# Default lookback window for analysis
DEFAULT_LOOKBACK_DAYS = 14

# Required experiment wins before skill promotion
REQUIRED_WINS_FOR_PROMOTION = 2

# Performance drop threshold for rollback consideration
ROLLBACK_THRESHOLD = 0.15  # 15% drop triggers rollback check


class FeedbackLoop:
    """Orchestrate the learning cycle: analyze, experiment, adapt."""

    def __init__(
        self,
        skill_manager: SkillManager,
        pattern_analyzer: PatternAnalyzer,
        experiment_runner: ExperimentRunner,
    ):
        self.skill_manager = skill_manager
        self.pattern_analyzer = pattern_analyzer
        self.experiment_runner = experiment_runner
        self.evaluator = SkillEvaluator()
        self.synthesizer = SkillSynthesizer(skill_manager)

    async def run_cycle(self, at: datetime | None = None) -> dict:
        """Execute one full feedback cycle.

        Steps:
            1. Collect patterns from pattern_analyzer.
            2. Update skill confidence from recent SkillMetric records.
            3. Check for stale skills via SkillEvaluator.
            4. Run SkillSynthesizer to analyze patterns and propose updates.
            5. Check active experiments for winners.
            6. Apply experiment winners to skill versions.

        Returns a summary dict of all actions taken.
        """
        now = at or datetime.now(timezone.utc)
        actions: list[str] = []

        # Step 1 — Analyze patterns
        patterns = await self.pattern_analyzer.analyze()
        actions.append(f"Analyzed patterns: {len(patterns)} found")

        # Step 2 — Update skill confidence from recent metrics
        confidence_updates = await self._update_skill_confidence()
        actions.append(f"Updated confidence for {len(confidence_updates)} skills")

        # Step 3 — Detect stale skills
        stale_skills = []
        for skill in self.skill_manager.all_skills():
            if self.evaluator.detect_staleness(skill):
                stale_skills.append(skill.name)
        if stale_skills:
            actions.append(f"Stale skills detected: {stale_skills}")
        else:
            actions.append("No stale skills detected")

        # Step 4 — Run SkillSynthesizer to find patterns and propose updates
        synthesizer_results = await self._run_synthesizer()
        actions.append(f"Synthesizer: {len(synthesizer_results.get('patterns', []))} patterns, {len(synthesizer_results.get('proposals', []))} proposals")

        # Step 5 — Analyze failure patterns from low-engagement content
        failure_analysis = await self._analyze_failure_patterns()
        actions.append(
            f"Failure patterns: {failure_analysis['failure_count']} failures analyzed, "
            f"{sum(len(v) for v in failure_analysis['patterns'].values() if isinstance(v, list))} patterns found"
        )

        # Step 6 — Check experiments for winners
        experiment_results = await self._check_experiments()
        actions.append(f"Checked experiments: {len(experiment_results)} evaluated")

        # Step 7 — Apply winners (with progressive promotion)
        applied = 0
        for exp in experiment_results:
            if exp.get("winner") == "B":
                try:
                    promoted = await self._apply_experiment_winner(exp)
                    if promoted:
                        actions.append(
                            f"Promoted variant for skill '{exp['skill_name']}'"
                        )
                        applied += 1
                    else:
                        actions.append(
                            f"Skill '{exp['skill_name']}' won but needs more wins for promotion"
                        )
                except Exception:
                    logger.exception(
                        "Failed to process experiment winner for skill '%s'",
                        exp["skill_name"],
                    )

        # Step 8 — Check for skills that need rollback
        rollback_results = await self._check_version_health()
        if rollback_results:
            actions.append(f"Rollback checks: {len(rollback_results)} skills evaluated")

        summary = {
            "timestamp": now.isoformat(),
            "patterns_found": len(patterns),
            "confidence_updates": len(confidence_updates),
            "stale_skills": stale_skills,
            "synthesizer_patterns": len(synthesizer_results.get("patterns", [])),
            "synthesizer_proposals": len(synthesizer_results.get("proposals", [])),
            "failure_patterns": {
                "failures_analyzed": failure_analysis["failure_count"],
                "patterns_by_category": {
                    k: len(v) for k, v in failure_analysis["patterns"].items()
                    if isinstance(v, list)
                },
            },
            "experiments_checked": len(experiment_results),
            "variants_promoted": applied,
            "actions": actions,
        }
        logger.info("Feedback cycle complete: %s", summary)
        return summary

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _update_skill_confidence(
        self, lookback_days: int = DEFAULT_LOOKBACK_DAYS
    ) -> dict[str, float]:
        """Recompute confidence for each skill based on time-windowed SkillMetric records.

        Uses recency weighting: recent outcomes count more than older ones.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)

        async with async_session() as session:
            result = await session.execute(
                select(SkillMetric)
                .where(SkillMetric.recorded_at >= cutoff)
                .order_by(desc(SkillMetric.recorded_at))
            )
            rows = result.scalars().all()

        # Group by skill with recency weighting
        grouped: dict[str, list[tuple[float, float]]] = defaultdict(list)  # skill -> [(score, weight)]
        now = datetime.now(timezone.utc)

        for row in rows:
            days_ago = (now - row.recorded_at).days
            # Linear decay: today = 1.0, lookback_days ago = 0.3
            recency_weight = 1.0 - (days_ago / lookback_days) * 0.7
            recency_weight = max(0.3, recency_weight)
            grouped[row.skill_name].append((row.score, recency_weight))

        updates: dict[str, float] = {}
        for skill_name, score_weights in grouped.items():
            if not score_weights:
                continue

            # Weighted average
            total_weight = sum(w for _, w in score_weights)
            weighted_sum = sum(s * w for s, w in score_weights)
            confidence = weighted_sum / total_weight if total_weight > 0 else 0.5
            updates[skill_name] = round(confidence, 3)

            logger.debug(
                "Skill '%s' confidence from %d samples: %.3f (weighted)",
                skill_name, len(score_weights), confidence
            )

        return updates

    async def _run_synthesizer(
        self, lookback_days: int = DEFAULT_LOOKBACK_DAYS
    ) -> dict:
        """Run the skill synthesizer with time-windowed data.

        Uses recency weighting to prioritize recent patterns over old ones.

        Returns:
            dict with 'patterns' and 'proposals' keys
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
        now = datetime.now(timezone.utc)

        # Fetch recent metrics for analysis
        async with async_session() as session:
            result = await session.execute(
                select(SkillMetric)
                .where(SkillMetric.recorded_at >= cutoff)
                .order_by(desc(SkillMetric.recorded_at))
            )
            rows = result.scalars().all()

        # Convert to dict format with recency weighting
        metrics = []
        for row in rows:
            days_ago = (now - row.recorded_at).days
            recency_weight = 1.0 - (days_ago / lookback_days) * 0.7
            recency_weight = max(0.3, recency_weight)

            metrics.append({
                "skill_name": row.skill_name,
                "score": row.score * recency_weight,  # Weighted score for analysis
                "raw_score": row.score,
                "recency_weight": recency_weight,
                "context": row.context or {},
                "recorded_at": row.recorded_at.isoformat(),
            })

        # Analyze patterns
        patterns = self.synthesizer.analyze_patterns(metrics)

        # Log significant patterns
        for pattern in patterns:
            if pattern.get("type") == "high_performer":
                logger.info(
                    "HIGH PERFORMER: %s (avg %.2f over %d uses, last %d days)",
                    pattern["skill_name"],
                    pattern.get("avg_score", 0),
                    pattern.get("sample_size", 0),
                    lookback_days,
                )
            elif pattern.get("type") == "underperformer":
                logger.warning(
                    "UNDERPERFORMER: %s (avg %.2f over %d uses) — consider revision",
                    pattern["skill_name"],
                    pattern.get("avg_score", 0),
                    pattern.get("sample_size", 0),
                )
            elif pattern.get("type") == "trend_shift":
                logger.info(
                    "TREND SHIFT: %s is %s (delta %+.2f)",
                    pattern["skill_name"],
                    pattern.get("direction", "unknown"),
                    pattern.get("delta", 0),
                )

        # Generate update proposals for skills with clear patterns
        proposals = []
        for pattern in patterns:
            skill_name = pattern.get("skill_name")
            skill = self.skill_manager.get_skill(skill_name)
            if not skill:
                continue

            # Get outcomes for this skill (use raw scores for proposals)
            skill_metrics = [m for m in metrics if m["skill_name"] == skill_name]
            outcomes = [{"score": m["raw_score"], "feedback": ""} for m in skill_metrics]

            proposal = self.synthesizer.propose_updates(skill, outcomes)
            if proposal:
                proposals.append(proposal)
                logger.info(
                    "SKILL PROPOSAL: %s — %s (reason: %s)",
                    proposal["skill_name"],
                    proposal.get("action", "unknown"),
                    proposal.get("reason", ""),
                )

        return {
            "patterns": patterns,
            "proposals": proposals,
            "lookback_days": lookback_days,
            "metrics_analyzed": len(metrics),
        }

    async def _analyze_failure_patterns(self) -> dict:
        """Analyze failed content to extract patterns to avoid.

        This populates the failure pattern tracker cache, which is then
        used by the CreatorAgent to inject "avoid" guidance into prompts.
        """
        tracker = get_failure_tracker()
        result = await tracker.analyze_failures(lookback_days=14)

        # Log significant findings
        patterns = result.get("patterns", {})
        for category, items in patterns.items():
            if isinstance(items, list) and items:
                logger.info(
                    "Failure pattern category '%s': %d patterns found",
                    category, len(items)
                )
                for item in items[:2]:  # Log top 2 per category
                    if "description" in item:
                        logger.info("  - %s", item["description"])

        return result

    async def _check_experiments(self) -> list[dict]:
        """Check all active experiments and return results."""
        async with async_session() as session:
            result = await session.execute(
                select(ContentExperiment).where(
                    ContentExperiment.status == "running"
                )
            )
            experiments = result.scalars().all()

        results = []
        for exp in experiments:
            outcome = await self.experiment_runner.check_winner(exp.id)
            results.append({
                "experiment_id": exp.id,
                "skill_name": exp.skill_name,
                "variant_description": exp.variant_b,
                **outcome,
            })
        return results

    async def _apply_experiment_winner(self, exp: dict) -> bool:
        """Apply experiment winner with progressive promotion.

        Requires REQUIRED_WINS_FOR_PROMOTION experiment wins before actually
        promoting a skill variant. This prevents premature promotion based on
        a single lucky experiment.

        Returns True if the skill was actually promoted, False if more wins needed.
        """
        skill_name = exp["skill_name"]
        variant_description = exp.get("variant_description", "")

        # Count prior wins for this skill with similar variant
        prior_wins = await self._count_prior_experiment_wins(skill_name, variant_description)

        total_wins = prior_wins + 1  # Including current win

        if total_wins >= REQUIRED_WINS_FOR_PROMOTION:
            # Enough wins - promote the skill
            self.skill_manager.create_version(
                skill_name,
                new_content=variant_description,
                change_reason=f"Experiment winner ({total_wins} wins, confidence: {exp.get('confidence', 0):.2f})",
            )
            logger.info(
                "Promoted skill '%s' after %d experiment wins",
                skill_name, total_wins
            )
            return True
        else:
            # Not enough wins yet
            logger.info(
                "Skill '%s' won experiment but needs %d more wins for promotion (has %d/%d)",
                skill_name, REQUIRED_WINS_FOR_PROMOTION - total_wins, total_wins, REQUIRED_WINS_FOR_PROMOTION
            )
            return False

    async def _count_prior_experiment_wins(
        self, skill_name: str, variant_description: str
    ) -> int:
        """Count prior experiment wins for a skill with similar variant."""
        async with async_session() as session:
            # Look for completed experiments where this skill won with variant B
            result = await session.execute(
                select(func.count(ContentExperiment.id))
                .where(ContentExperiment.skill_name == skill_name)
                .where(ContentExperiment.winner == "B")
                .where(ContentExperiment.status == "completed")
                # Only count if variant_b matches (or is similar enough)
                .where(ContentExperiment.variant_b == variant_description)
            )
            exact_matches = result.scalar() or 0

            # Also check for semantically similar wins (variant contains same keywords)
            # This is a simple heuristic - in production you'd use embedding similarity
            if exact_matches == 0 and variant_description:
                # Fall back to any B wins for this skill (less strict)
                result = await session.execute(
                    select(func.count(ContentExperiment.id))
                    .where(ContentExperiment.skill_name == skill_name)
                    .where(ContentExperiment.winner == "B")
                    .where(ContentExperiment.status == "completed")
                )
                any_b_wins = result.scalar() or 0
                return any_b_wins

            return exact_matches

    async def _check_version_health(self) -> list[dict]:
        """Check if any recently updated skills are underperforming and need rollback.

        Compares recent performance (last 10 outcomes) against pre-version performance
        to detect skills that got worse after being updated.

        Returns list of skills checked with their health status.
        """
        results = []

        for skill in self.skill_manager.all_skills():
            if skill.version < 2:
                continue  # No previous version to rollback to

            # Get recent outcomes (last 10)
            recent_avg = await self._get_recent_score_avg(skill.name, limit=10)
            if recent_avg is None:
                continue  # Not enough data

            # Get pre-version performance
            previous_avg = await self._get_score_avg_before_version(skill.name, skill.version)
            if previous_avg is None:
                continue  # No historical data

            performance_drop = previous_avg - recent_avg

            result = {
                "skill_name": skill.name,
                "version": skill.version,
                "recent_avg": recent_avg,
                "previous_avg": previous_avg,
                "performance_drop": performance_drop,
                "needs_rollback": performance_drop > ROLLBACK_THRESHOLD,
            }
            results.append(result)

            if performance_drop > ROLLBACK_THRESHOLD:
                logger.warning(
                    "Skill '%s' v%d underperforming by %.1f%% (%.3f → %.3f). Consider rollback.",
                    skill.name, skill.version, performance_drop * 100,
                    previous_avg, recent_avg
                )
                # Auto-rollback is risky - log warning but don't auto-execute
                # In production, this would trigger human review or A/B test

        return results

    async def _get_recent_score_avg(self, skill_name: str, limit: int = 10) -> float | None:
        """Get average score from the most recent N outcomes for a skill."""
        async with async_session() as session:
            result = await session.execute(
                select(SkillMetric.score)
                .where(SkillMetric.skill_name == skill_name)
                .where(SkillMetric.agent == "tracker")  # Only engagement-based
                .order_by(desc(SkillMetric.recorded_at))
                .limit(limit)
            )
            scores = [row[0] for row in result.all()]

        if len(scores) < 5:  # Need minimum sample
            return None

        return sum(scores) / len(scores)

    async def _get_score_avg_before_version(
        self, skill_name: str, current_version: int
    ) -> float | None:
        """Get average score from before the current version was applied.

        Uses the skill's updated_at timestamp to determine when the version changed.
        """
        skill = self.skill_manager.get_skill(skill_name)
        if not skill or not skill.updated_at:
            return None

        # Assume version was updated at skill.updated_at
        # Get scores from before that time
        async with async_session() as session:
            result = await session.execute(
                select(func.avg(SkillMetric.score))
                .where(SkillMetric.skill_name == skill_name)
                .where(SkillMetric.agent == "tracker")
                .where(SkillMetric.recorded_at < skill.updated_at)
            )
            avg_score = result.scalar()

        return float(avg_score) if avg_score is not None else None
