"""Failure pattern tracking — learn what NOT to do from low-engagement content."""

import logging
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select

from db import async_session
from models import ContentCreation, ContentMetric, ContentPublication

logger = logging.getLogger(__name__)

# Threshold below which content is considered "failed"
FAILURE_ENGAGEMENT_THRESHOLD = 0.02  # 2% engagement rate
MIN_SAMPLES_FOR_PATTERN = 3  # Minimum failed content pieces to establish a pattern


class FailurePatternTracker:
    """Analyzes failed content to extract patterns to avoid.

    Tracks:
    - Hook patterns that underperform (first sentence/line characteristics)
    - Content length issues (too long/short for platform)
    - Posting time failures (wrong day/hour combinations)
    - Format mismatches (wrong format for content type)
    - Skill combinations that fail together
    """

    def __init__(self):
        self._cached_patterns: dict = {}
        self._last_analysis: datetime | None = None

    async def analyze_failures(
        self, lookback_days: int = 14, min_metrics: int = 3
    ) -> dict:
        """Analyze failed content from the past N days.

        Returns patterns organized by category:
        - hook_patterns: Opening line characteristics to avoid
        - length_patterns: Length issues by platform
        - timing_patterns: Bad posting times
        - format_patterns: Format/platform mismatches
        - skill_patterns: Skills associated with failures
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)

        async with async_session() as session:
            # Get publications with metrics
            result = await session.execute(
                select(ContentPublication, ContentMetric)
                .join(
                    ContentMetric,
                    ContentPublication.id == ContentMetric.publication_id
                )
                .where(ContentPublication.published_at >= cutoff)
                .where(ContentMetric.interval == "24h")  # Use 24h metrics as baseline
            )
            rows = result.all()

            # Get associated creations
            pub_ids = [row.ContentPublication.creation_id for row in rows]
            creation_result = await session.execute(
                select(ContentCreation).where(ContentCreation.id.in_(pub_ids))
            )
            creations = {c.id: c for c in creation_result.scalars().all()}

        # Filter to failed content
        failures = []
        for pub, metric in rows:
            if metric.engagement_rate < FAILURE_ENGAGEMENT_THRESHOLD:
                creation = creations.get(pub.creation_id)
                if creation:
                    failures.append({
                        "publication": pub,
                        "metric": metric,
                        "creation": creation,
                    })

        if len(failures) < MIN_SAMPLES_FOR_PATTERN:
            logger.info(
                "Not enough failures to establish patterns (%d < %d)",
                len(failures), MIN_SAMPLES_FOR_PATTERN
            )
            return {"patterns": {}, "failure_count": len(failures)}

        # Analyze patterns
        patterns = {
            "hook_patterns": self._analyze_hooks(failures),
            "length_patterns": self._analyze_length(failures),
            "timing_patterns": self._analyze_timing(failures),
            "format_patterns": self._analyze_formats(failures),
            "skill_patterns": self._analyze_skills(failures),
        }

        # Cache results
        self._cached_patterns = patterns
        self._last_analysis = datetime.now(timezone.utc)

        logger.info(
            "Analyzed %d failures, found patterns: %s",
            len(failures),
            {k: len(v) for k, v in patterns.items() if v}
        )

        return {
            "patterns": patterns,
            "failure_count": len(failures),
            "analysis_timestamp": self._last_analysis.isoformat(),
        }

    def get_avoid_patterns_for_prompt(
        self, platform: str, fmt: str | None = None
    ) -> str:
        """Get formatted avoid patterns for injection into creator prompts.

        Returns a markdown-formatted string of patterns to avoid.
        """
        if not self._cached_patterns:
            return ""

        lines = ["## CAUTION: Patterns to AVOID (from failed content)"]
        lines.append("The following patterns have led to poor engagement:\n")

        # Hook patterns
        hooks = self._cached_patterns.get("hook_patterns", [])
        if hooks:
            lines.append("### Hook Patterns to Avoid")
            for pattern in hooks[:5]:
                lines.append(f"- {pattern['description']} (failure rate: {pattern['failure_rate']:.0%})")
            lines.append("")

        # Length patterns for this platform
        length = self._cached_patterns.get("length_patterns", {}).get(platform, [])
        if length:
            lines.append(f"### Length Issues on {platform.title()}")
            for pattern in length:
                lines.append(f"- {pattern['description']}")
            lines.append("")

        # Timing patterns
        timing = self._cached_patterns.get("timing_patterns", {}).get(platform, [])
        if timing:
            lines.append(f"### Bad Posting Times for {platform.title()}")
            for pattern in timing[:3]:
                lines.append(f"- {pattern['description']}")
            lines.append("")

        # Skill patterns
        skills = self._cached_patterns.get("skill_patterns", [])
        if skills:
            underperforming = [s for s in skills if s.get("failure_rate", 0) > 0.5]
            if underperforming:
                lines.append("### Skill Patterns to Use Cautiously")
                for pattern in underperforming[:3]:
                    lines.append(
                        f"- Skill '{pattern['skill_name']}' has "
                        f"{pattern['failure_rate']:.0%} failure rate"
                    )
                lines.append("")

        if len(lines) <= 2:
            return ""  # No significant patterns

        return "\n".join(lines)

    def _analyze_hooks(self, failures: list[dict]) -> list[dict]:
        """Analyze opening lines of failed content."""
        hook_issues = defaultdict(int)
        total = len(failures)

        for f in failures:
            body = f["creation"].body or ""
            first_line = body.split("\n")[0].strip()

            # Check for common hook issues
            if len(first_line) < 20:
                hook_issues["too_short_hook"] += 1
            if first_line.endswith("!"):
                hook_issues["exclamation_hook"] += 1
            if first_line.startswith(("I ", "We ", "Our ")):
                hook_issues["self_focused_hook"] += 1
            if re.match(r"^\d+\.", first_line):
                hook_issues["numbered_list_start"] += 1
            if "?" not in first_line and len(first_line) > 50:
                hook_issues["long_statement_no_question"] += 1
            if any(word in first_line.lower() for word in ["excited", "thrilled", "amazing", "incredible"]):
                hook_issues["hyperbolic_hook"] += 1

        patterns = []
        for issue, count in hook_issues.items():
            rate = count / total
            if rate >= 0.3:  # Pattern appears in 30%+ of failures
                description = {
                    "too_short_hook": "Very short opening lines (<20 chars)",
                    "exclamation_hook": "Opening lines ending with exclamation marks",
                    "self_focused_hook": "Self-focused openings (I/We/Our)",
                    "numbered_list_start": "Starting with numbered list format",
                    "long_statement_no_question": "Long declarative statements without questions",
                    "hyperbolic_hook": "Hyperbolic language (excited, amazing, incredible)",
                }.get(issue, issue)

                patterns.append({
                    "type": issue,
                    "description": description,
                    "count": count,
                    "failure_rate": rate,
                })

        return sorted(patterns, key=lambda x: x["failure_rate"], reverse=True)

    def _analyze_length(self, failures: list[dict]) -> dict[str, list[dict]]:
        """Analyze content length issues by platform."""
        platform_issues = defaultdict(lambda: defaultdict(int))
        platform_totals = defaultdict(int)

        for f in failures:
            platform = f["creation"].platform
            body_len = len(f["creation"].body or "")
            platform_totals[platform] += 1

            if platform == "linkedin":
                if body_len < 100:
                    platform_issues[platform]["too_short"] += 1
                elif body_len > 2500:
                    platform_issues[platform]["too_long"] += 1
            elif platform == "twitter":
                if body_len > 250:
                    platform_issues[platform]["too_long"] += 1
            elif platform in ("youtube", "tiktok"):
                if body_len < 50:
                    platform_issues[platform]["too_short"] += 1

        result = {}
        for platform, issues in platform_issues.items():
            patterns = []
            total = platform_totals[platform]
            for issue, count in issues.items():
                rate = count / total
                if rate >= 0.25:
                    patterns.append({
                        "type": issue,
                        "description": f"Content {issue.replace('_', ' ')} for {platform}",
                        "count": count,
                        "failure_rate": rate,
                    })
            if patterns:
                result[platform] = patterns

        return result

    def _analyze_timing(self, failures: list[dict]) -> dict[str, list[dict]]:
        """Analyze posting time patterns."""
        platform_timing = defaultdict(lambda: defaultdict(int))
        platform_totals = defaultdict(int)

        for f in failures:
            platform = f["creation"].platform
            pub_time = f["publication"].published_at
            if not pub_time:
                continue

            platform_totals[platform] += 1

            # Day of week
            day = pub_time.strftime("%A")
            platform_timing[platform][f"day_{day}"] += 1

            # Hour bucket
            hour = pub_time.hour
            if hour < 6:
                platform_timing[platform]["late_night"] += 1
            elif hour > 20:
                platform_timing[platform]["evening"] += 1
            elif 12 <= hour <= 13:
                platform_timing[platform]["lunch_hour"] += 1

        result = {}
        for platform, timing in platform_timing.items():
            patterns = []
            total = platform_totals[platform]
            for key, count in timing.items():
                rate = count / total
                if rate >= 0.3 and count >= 2:
                    if key.startswith("day_"):
                        day = key.replace("day_", "")
                        desc = f"Posts on {day} tend to underperform"
                    else:
                        desc = {
                            "late_night": "Late night posts (before 6am)",
                            "evening": "Late evening posts (after 8pm)",
                            "lunch_hour": "Lunch hour posts (12-1pm)",
                        }.get(key, key)
                    patterns.append({
                        "type": key,
                        "description": desc,
                        "count": count,
                        "failure_rate": rate,
                    })
            if patterns:
                result[platform] = patterns

        return result

    def _analyze_formats(self, failures: list[dict]) -> list[dict]:
        """Analyze format/platform mismatches."""
        format_platform = defaultdict(int)
        total_by_combo = defaultdict(int)

        for f in failures:
            combo = f"{f['creation'].platform}_{f['creation'].format}"
            format_platform[combo] += 1

        # This needs comparison against successes to be meaningful
        # For now, just identify heavily-used failing combos
        patterns = []
        for combo, count in format_platform.items():
            if count >= 3:
                platform, fmt = combo.split("_", 1)
                patterns.append({
                    "platform": platform,
                    "format": fmt,
                    "description": f"{fmt.title()} format on {platform.title()} has {count} failures",
                    "count": count,
                })

        return patterns

    def _analyze_skills(self, failures: list[dict]) -> list[dict]:
        """Analyze which skills are associated with failures."""
        skill_failures = defaultdict(int)
        skill_totals = defaultdict(int)

        for f in failures:
            skills = f["creation"].skills_used or []
            for skill in skills:
                skill_failures[skill] += 1
                skill_totals[skill] += 1

        patterns = []
        for skill, failures_count in skill_failures.items():
            total = skill_totals[skill]
            rate = failures_count / total if total > 0 else 0
            if total >= 2:  # Need minimum sample
                patterns.append({
                    "skill_name": skill,
                    "failure_count": failures_count,
                    "total_uses_in_failed": total,
                    "failure_rate": rate,
                })

        return sorted(patterns, key=lambda x: x["failure_rate"], reverse=True)


# Module-level singleton for easy access
_tracker: Optional[FailurePatternTracker] = None


def get_failure_tracker() -> FailurePatternTracker:
    """Get or create the failure pattern tracker singleton."""
    global _tracker
    if _tracker is None:
        _tracker = FailurePatternTracker()
    return _tracker
