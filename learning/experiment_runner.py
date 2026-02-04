"""Run A/B experiments on content skills and strategies."""

import logging
import math
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select

from db import async_session
from models import ContentExperiment, ContentCreation, ContentMetric, ContentPublication

logger = logging.getLogger(__name__)

# Try to import scipy for statistical testing
try:
    from scipy import stats as scipy_stats
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    logger.info("scipy not available - using fallback statistical methods")


class ExperimentRunner:
    """Create, record, and evaluate A/B experiments."""

    async def create_experiment(
        self,
        skill_name: str,
        variant_description: str,
        metric_target: str = "engagement_rate",
        at: datetime | None = None,
    ) -> int:
        """Create a new experiment comparing the original skill with a variant.

        Returns the experiment ID.
        """
        now = at or datetime.now(timezone.utc)

        async with async_session() as session:
            experiment = ContentExperiment(
                skill_name=skill_name,
                variant_a="original",
                variant_b=variant_description,
                metric_target=metric_target,
                variant_a_score=0.0,
                variant_b_score=0.0,
                sample_size=0,
                status="running",
                winner=None,
                started_at=now,
            )
            session.add(experiment)
            await session.commit()
            await session.refresh(experiment)
            experiment_id = experiment.id

        logger.info(
            "Created experiment %d for skill '%s': original vs '%s'",
            experiment_id, skill_name, variant_description,
        )
        return experiment_id

    async def record_result(
        self, experiment_id: int, variant: str, score: float
    ) -> None:
        """Record a result for a variant in an experiment.

        Args:
            experiment_id: ID of the experiment.
            variant: "A" or "B".
            score: The metric score for this observation.
        """
        async with async_session() as session:
            result = await session.execute(
                select(ContentExperiment).where(ContentExperiment.id == experiment_id)
            )
            experiment = result.scalar_one_or_none()
            if experiment is None:
                logger.warning("Experiment %d not found", experiment_id)
                return

            # Running average update
            n = experiment.sample_size or 0
            if variant.upper() == "A":
                old = experiment.variant_a_score or 0.0
                experiment.variant_a_score = round(
                    (old * n + score) / (n + 1), 4
                )
            elif variant.upper() == "B":
                old = experiment.variant_b_score or 0.0
                experiment.variant_b_score = round(
                    (old * n + score) / (n + 1), 4
                )
            else:
                logger.warning("Unknown variant '%s' for experiment %d", variant, experiment_id)
                return

            experiment.sample_size = n + 1
            await session.commit()

        logger.info(
            "Recorded %s=%.4f for experiment %d (n=%d)",
            variant, score, experiment_id, n + 1,
        )

    async def check_winner(
        self, experiment_id: int, min_samples: int = 10, p_threshold: float = 0.05
    ) -> dict:
        """Check whether an experiment has a statistically significant winner.

        Uses Mann-Whitney U test (if scipy available) or Welch's t-test approximation
        to determine if there's a statistically significant difference between variants.

        Args:
            experiment_id: ID of the experiment
            min_samples: Minimum samples per variant required
            p_threshold: p-value threshold for significance (default 0.05)

        Returns:
            {
                "winner": "A"|"B"|None,
                "confidence": float (1 - p_value),
                "p_value": float,
                "effect_size": float,
                "complete": bool,
                "method": str
            }
        """
        async with async_session() as session:
            result = await session.execute(
                select(ContentExperiment).where(ContentExperiment.id == experiment_id)
            )
            experiment = result.scalar_one_or_none()
            if experiment is None:
                return {"winner": None, "confidence": 0.0, "p_value": 1.0, "complete": False}

            # Get individual observations for each variant
            observations_a, observations_b = await self._get_variant_observations(
                experiment.skill_name, experiment.started_at
            )

            n_a, n_b = len(observations_a), len(observations_b)

            # Check minimum sample size
            if n_a < min_samples or n_b < min_samples:
                return {
                    "winner": None,
                    "confidence": 0.0,
                    "p_value": 1.0,
                    "effect_size": 0.0,
                    "complete": False,
                    "method": "insufficient_data",
                    "samples_a": n_a,
                    "samples_b": n_b,
                }

            # Run statistical test
            test_result = self._run_statistical_test(observations_a, observations_b)

            p_value = test_result["p_value"]
            effect_size = test_result["effect_size"]
            method = test_result["method"]

            # Determine winner
            mean_a = sum(observations_a) / n_a
            mean_b = sum(observations_b) / n_b

            if p_value > p_threshold:
                # No statistically significant difference
                winner = None
                logger.info(
                    "Experiment %d: no significant difference (p=%.4f > %.2f)",
                    experiment_id, p_value, p_threshold
                )
            elif mean_a > mean_b:
                winner = "A"
            else:
                winner = "B"

            confidence = round(1.0 - p_value, 4)

            # Update experiment
            experiment.status = "completed"
            experiment.winner = winner
            experiment.variant_a_score = round(mean_a, 4)
            experiment.variant_b_score = round(mean_b, 4)
            experiment.sample_size = n_a + n_b
            experiment.completed_at = datetime.now(timezone.utc)
            await session.commit()

        logger.info(
            "Experiment %d complete: winner=%s, p=%.4f, effect=%.3f, method=%s",
            experiment_id, winner, p_value, effect_size, method
        )
        return {
            "winner": winner,
            "confidence": confidence,
            "p_value": round(p_value, 4),
            "effect_size": round(effect_size, 3),
            "complete": True,
            "method": method,
            "mean_a": round(mean_a, 4),
            "mean_b": round(mean_b, 4),
            "samples_a": n_a,
            "samples_b": n_b,
        }

    async def _get_variant_observations(
        self, skill_name: str, started_at: datetime
    ) -> tuple[list[float], list[float]]:
        """Get individual engagement observations for each variant.

        Pulls from ContentCreation → ContentPublication → ContentMetric chain,
        grouping by variant_label (A vs B).
        """
        async with async_session() as session:
            # Get creations with variant labels for this skill since experiment started
            result = await session.execute(
                select(ContentCreation, ContentMetric)
                .join(ContentPublication, ContentCreation.id == ContentPublication.creation_id)
                .join(ContentMetric, ContentPublication.id == ContentMetric.publication_id)
                .where(ContentCreation.created_at >= started_at)
                .where(ContentMetric.interval == "24h")  # Use 24h metrics
            )
            rows = result.all()

        observations_a: list[float] = []
        observations_b: list[float] = []

        for creation, metric in rows:
            # Check if this creation used the skill we're testing
            skills_used = creation.skills_used or []
            if skill_name not in skills_used:
                continue

            engagement = metric.engagement_rate or 0.0

            if creation.variant_label == "A":
                observations_a.append(engagement)
            elif creation.variant_label == "B":
                observations_b.append(engagement)

        return observations_a, observations_b

    def _run_statistical_test(
        self, group_a: list[float], group_b: list[float]
    ) -> dict:
        """Run statistical test to compare two groups.

        Uses Mann-Whitney U test if scipy is available (non-parametric, robust),
        otherwise falls back to Welch's t-test approximation.
        """
        if SCIPY_AVAILABLE:
            return self._mann_whitney_test(group_a, group_b)
        else:
            return self._welch_t_test_approximation(group_a, group_b)

    def _mann_whitney_test(
        self, group_a: list[float], group_b: list[float]
    ) -> dict:
        """Mann-Whitney U test using scipy."""
        try:
            statistic, p_value = scipy_stats.mannwhitneyu(
                group_a, group_b, alternative="two-sided"
            )
            # Calculate effect size (rank-biserial correlation)
            n1, n2 = len(group_a), len(group_b)
            effect_size = 1 - (2 * statistic) / (n1 * n2)

            return {
                "p_value": p_value,
                "effect_size": abs(effect_size),
                "statistic": statistic,
                "method": "mann_whitney_u",
            }
        except Exception as e:
            logger.warning("Mann-Whitney test failed: %s, falling back", e)
            return self._welch_t_test_approximation(group_a, group_b)

    def _welch_t_test_approximation(
        self, group_a: list[float], group_b: list[float]
    ) -> dict:
        """Welch's t-test approximation without scipy.

        Uses the Welch-Satterthwaite approximation for degrees of freedom.
        """
        n1, n2 = len(group_a), len(group_b)
        mean1 = sum(group_a) / n1
        mean2 = sum(group_b) / n2

        # Calculate variances
        var1 = sum((x - mean1) ** 2 for x in group_a) / (n1 - 1) if n1 > 1 else 0
        var2 = sum((x - mean2) ** 2 for x in group_b) / (n2 - 1) if n2 > 1 else 0

        # Pooled standard error
        se = math.sqrt(var1 / n1 + var2 / n2) if (var1 / n1 + var2 / n2) > 0 else 0.001

        # t-statistic
        t_stat = (mean1 - mean2) / se if se > 0 else 0

        # Welch-Satterthwaite degrees of freedom
        num = (var1 / n1 + var2 / n2) ** 2
        denom = ((var1 / n1) ** 2 / (n1 - 1) + (var2 / n2) ** 2 / (n2 - 1)) if n1 > 1 and n2 > 1 else 1
        df = num / denom if denom > 0 else min(n1, n2) - 1

        # Approximate p-value using normal distribution (valid for large df)
        # For small df, this is an approximation
        p_value = 2 * (1 - self._normal_cdf(abs(t_stat)))

        # Cohen's d effect size
        pooled_std = math.sqrt(((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2)) if (n1 + n2 - 2) > 0 else 1
        effect_size = abs(mean1 - mean2) / pooled_std if pooled_std > 0 else 0

        return {
            "p_value": min(max(p_value, 0.0001), 1.0),  # Clamp to valid range
            "effect_size": effect_size,
            "t_statistic": t_stat,
            "df": df,
            "method": "welch_t_approx",
        }

    @staticmethod
    def _normal_cdf(x: float) -> float:
        """Approximate normal CDF using error function approximation."""
        # Abramowitz and Stegun approximation
        a1, a2, a3, a4, a5 = 0.254829592, -0.284496736, 1.421413741, -1.453152027, 1.061405429
        p = 0.3275911
        sign = 1 if x >= 0 else -1
        x = abs(x) / math.sqrt(2)
        t = 1.0 / (1.0 + p * x)
        y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(-x * x)
        return 0.5 * (1.0 + sign * y)
