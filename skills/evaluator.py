from __future__ import annotations

from datetime import datetime, timedelta

from .base import Skill


class SkillEvaluator:
    """Assess skill health, staleness, and performance trends."""

    STALE_THRESHOLD_DAYS: int = 7
    WARNING_CONFIDENCE: float = 0.3
    CRITICAL_CONFIDENCE: float = 0.15
    WARNING_FAILURE_STREAK: int = 3
    CRITICAL_FAILURE_STREAK: int = 5

    def check_health(self, skill: Skill) -> dict:
        """Return a health report: status is healthy, warning, or critical."""
        reasons: list[str] = []
        status = "healthy"

        # Critical checks
        if skill.confidence < self.CRITICAL_CONFIDENCE:
            reasons.append(
                f"Confidence critically low ({skill.confidence:.2f} < {self.CRITICAL_CONFIDENCE})"
            )
            status = "critical"

        if skill.failure_streak > self.CRITICAL_FAILURE_STREAK:
            reasons.append(
                f"Failure streak critically high ({skill.failure_streak} > {self.CRITICAL_FAILURE_STREAK})"
            )
            status = "critical"

        # Warning checks (only upgrade to warning, never downgrade from critical)
        if status != "critical":
            if skill.confidence < self.WARNING_CONFIDENCE:
                reasons.append(
                    f"Confidence low ({skill.confidence:.2f} < {self.WARNING_CONFIDENCE})"
                )
                status = "warning"

            if skill.failure_streak > self.WARNING_FAILURE_STREAK:
                reasons.append(
                    f"Failure streak high ({skill.failure_streak} > {self.WARNING_FAILURE_STREAK})"
                )
                status = "warning"

            if self._not_validated_recently(skill):
                reasons.append(
                    f"Not validated in the last {self.STALE_THRESHOLD_DAYS} days"
                )
                if status == "healthy":
                    status = "warning"

        return {"status": status, "reasons": reasons}

    def detect_staleness(self, skill: Skill) -> bool:
        """Return True if the skill should be considered stale."""
        if skill.last_validated_at is None:
            return True

        if self._not_validated_recently(skill):
            return True

        if skill.confidence < 0.2:
            return True

        return False

    def compute_trend(self, skill: Skill, recent_outcomes: list[float]) -> str:
        """Compute whether performance is improving, degrading, or stable.

        Compares the average of the last 5 outcomes against the previous 5.
        """
        if len(recent_outcomes) < 2:
            return "stable"

        last_5 = recent_outcomes[-5:]
        previous_5 = recent_outcomes[-10:-5] if len(recent_outcomes) > 5 else []

        if not previous_5:
            return "stable"

        last_avg = sum(last_5) / len(last_5)
        prev_avg = sum(previous_5) / len(previous_5)

        if last_avg > prev_avg:
            return "improving"
        elif last_avg < prev_avg:
            return "degrading"
        return "stable"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _not_validated_recently(self, skill: Skill) -> bool:
        if skill.last_validated_at is None:
            return True
        return (datetime.now() - skill.last_validated_at) > timedelta(
            days=self.STALE_THRESHOLD_DAYS
        )
