"""Feedback loop — ties pattern analysis, experiments, and skill updates together."""

import logging
from datetime import datetime, timezone

from sqlalchemy import select

from db import async_session
from learning.experiment_runner import ExperimentRunner
from learning.failure_patterns import get_failure_tracker
from learning.pattern_analyzer import PatternAnalyzer
from models import SkillMetric
from skills.evaluator import SkillEvaluator
from skills.manager import SkillManager
from skills.synthesizer import SkillSynthesizer

logger = logging.getLogger(__name__)


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

        # Step 7 — Apply winners
        applied = 0
        for exp in experiment_results:
            if exp.get("winner") == "B":
                try:
                    self.skill_manager.create_version(
                        exp["skill_name"],
                        new_content=exp.get("variant_description", ""),
                        change_reason=f"Experiment winner (confidence: {exp.get('confidence', 0)})",
                    )
                    actions.append(
                        f"Promoted variant for skill '{exp['skill_name']}'"
                    )
                    applied += 1
                except Exception:
                    logger.exception(
                        "Failed to promote variant for skill '%s'",
                        exp["skill_name"],
                    )

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

    async def _update_skill_confidence(self) -> dict[str, float]:
        """Recompute confidence for each skill based on recent SkillMetric records."""
        async with async_session() as session:
            result = await session.execute(select(SkillMetric))
            rows = result.scalars().all()

        from collections import defaultdict

        grouped: dict[str, list[float]] = defaultdict(list)
        for row in rows:
            grouped[row.skill_name].append(row.score)

        updates: dict[str, float] = {}
        for skill_name, scores in grouped.items():
            confidence = round(sum(scores) / len(scores), 3)
            updates[skill_name] = confidence

        return updates

    async def _run_synthesizer(self) -> dict:
        """Run the skill synthesizer to analyze patterns and propose updates.

        Returns:
            dict with 'patterns' and 'proposals' keys
        """
        # Fetch recent metrics for analysis
        async with async_session() as session:
            result = await session.execute(select(SkillMetric))
            rows = result.scalars().all()

        # Convert to dict format expected by synthesizer
        metrics = [
            {
                "skill_name": row.skill_name,
                "score": row.score,
                "context": row.context or {},
            }
            for row in rows
        ]

        # Analyze patterns
        patterns = self.synthesizer.analyze_patterns(metrics)

        # Log significant patterns
        for pattern in patterns:
            if pattern.get("type") == "high_performer":
                logger.info(
                    "HIGH PERFORMER: %s (avg %.2f over %d uses)",
                    pattern["skill_name"],
                    pattern.get("avg_score", 0),
                    pattern.get("sample_size", 0),
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

            # Get outcomes for this skill
            skill_metrics = [m for m in metrics if m["skill_name"] == skill_name]
            outcomes = [{"score": m["score"], "feedback": ""} for m in skill_metrics]

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
        from models import ContentExperiment

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
