from __future__ import annotations

from datetime import datetime
from typing import Optional

from .base import Skill
from .manager import SkillManager


class SkillSynthesizer:
    """Analyze outcome patterns and propose new or updated skills."""

    def __init__(self, skill_manager: SkillManager) -> None:
        self._manager = skill_manager

    def analyze_patterns(self, metrics: list[dict]) -> list[dict]:
        """Find correlations between skill usage and outcomes.

        Each metric dict is expected to have at least:
          - skill_name: str
          - score: float
          - context: dict (optional extra info)

        Returns a list of pattern descriptions.
        """
        if not metrics:
            return []

        # Group scores by skill
        skill_scores: dict[str, list[float]] = {}
        for m in metrics:
            name = m.get("skill_name", "")
            score = m.get("score", 0.0)
            skill_scores.setdefault(name, []).append(score)

        patterns: list[dict] = []

        for name, scores in skill_scores.items():
            if not scores:
                continue

            avg = sum(scores) / len(scores)
            skill = self._manager.get_skill(name)

            if avg >= 0.8 and len(scores) >= 3:
                patterns.append(
                    {
                        "type": "high_performer",
                        "skill_name": name,
                        "avg_score": round(avg, 3),
                        "sample_size": len(scores),
                        "description": f"Skill '{name}' consistently performs well (avg {avg:.2f} over {len(scores)} uses)",
                    }
                )
            elif avg <= 0.3 and len(scores) >= 3:
                patterns.append(
                    {
                        "type": "underperformer",
                        "skill_name": name,
                        "avg_score": round(avg, 3),
                        "sample_size": len(scores),
                        "description": f"Skill '{name}' consistently underperforms (avg {avg:.2f} over {len(scores)} uses)",
                    }
                )

            # Detect trend shifts
            if len(scores) >= 6:
                first_half = scores[: len(scores) // 2]
                second_half = scores[len(scores) // 2 :]
                first_avg = sum(first_half) / len(first_half)
                second_avg = sum(second_half) / len(second_half)
                delta = second_avg - first_avg

                if abs(delta) > 0.15:
                    direction = "improving" if delta > 0 else "declining"
                    patterns.append(
                        {
                            "type": "trend_shift",
                            "skill_name": name,
                            "direction": direction,
                            "delta": round(delta, 3),
                            "description": f"Skill '{name}' is {direction} (delta {delta:+.2f})",
                        }
                    )

        return patterns

    def generate_skill(
        self, pattern: dict, existing_skills: list[Skill]
    ) -> str:
        """Generate new skill markdown content based on an observed pattern.

        Returns a markdown string. The actual LLM call for richer generation
        would happen in the agent layer; this provides a structured template.
        """
        pattern_type = pattern.get("type", "unknown")
        skill_name = pattern.get("skill_name", "unnamed")
        description = pattern.get("description", "")

        existing_names = {s.name for s in existing_skills}
        base_name = f"derived-from-{skill_name}"
        new_name = base_name
        counter = 2
        while new_name in existing_names:
            new_name = f"{base_name}-{counter}"
            counter += 1

        lines = [
            f"# {new_name}",
            "",
            f"Derived from pattern: {description}",
            "",
            "## Context",
            "",
            f"- Pattern type: {pattern_type}",
            f"- Source skill: {skill_name}",
            f"- Average score: {pattern.get('avg_score', 'N/A')}",
            f"- Sample size: {pattern.get('sample_size', 'N/A')}",
            "",
            "## Guidelines",
            "",
            "<!-- Replace with specific guidelines once validated -->",
            "",
            "1. Apply the successful patterns observed in the source skill.",
            "2. Monitor performance closely during the first 10 uses.",
            "3. Validate against real outcomes before promoting to ACTIVE.",
            "",
        ]
        return "\n".join(lines)

    def propose_updates(
        self, skill: Skill, outcomes: list[dict]
    ) -> Optional[dict]:
        """Propose content updates if outcomes show a consistent pattern.

        Each outcome dict should contain at least:
          - score: float
          - feedback: str (optional)

        Returns a proposal dict or None.
        """
        if len(outcomes) < 3:
            return None

        scores = [o.get("score", 0.0) for o in outcomes]
        avg = sum(scores) / len(scores)
        feedbacks = [o.get("feedback", "") for o in outcomes if o.get("feedback")]

        # Only propose if there is a clear signal
        if 0.3 <= avg <= 0.7 and not feedbacks:
            return None

        proposal: dict = {
            "skill_name": skill.name,
            "current_version": skill.version,
            "proposed_at": datetime.now().isoformat(),
            "avg_score": round(avg, 3),
            "sample_size": len(outcomes),
        }

        if avg < 0.3:
            proposal["action"] = "major_revision"
            proposal["reason"] = (
                f"Consistently low scores (avg {avg:.2f} over {len(outcomes)} outcomes)"
            )
            proposal["suggested_changes"] = [
                "Review core assumptions in skill content",
                "Cross-reference with high-performing skills in the same category",
                "Consider retiring if no improvement path is clear",
            ]
        elif avg >= 0.8:
            proposal["action"] = "minor_refinement"
            proposal["reason"] = (
                f"Strong performance (avg {avg:.2f}); refine to capture what works"
            )
            proposal["suggested_changes"] = [
                "Document the specific conditions where this skill excels",
                "Tighten guidelines to codify successful patterns",
            ]
        else:
            proposal["action"] = "targeted_update"
            proposal["reason"] = (
                f"Mixed results (avg {avg:.2f}); targeted improvements needed"
            )
            proposal["suggested_changes"] = [
                "Identify which contexts produce good vs poor results",
                "Add conditional guidance for different scenarios",
            ]

        if feedbacks:
            proposal["feedback_summary"] = feedbacks[:5]

        return proposal
