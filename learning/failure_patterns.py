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

# Platform-specific failure thresholds (engagement rates below these = failure)
PLATFORM_FAILURE_THRESHOLDS = {
    "linkedin": 0.02,   # 2% engagement = failure on LinkedIn
    "twitter": 0.015,   # 1.5% on Twitter (different scale)
    "youtube": 0.03,    # 3% on YouTube (higher expectations for video)
    "tiktok": 0.04,     # 4% on TikTok (viral platform, higher bar)
    "medium": 0.01,     # 1% on Medium (long-form, lower engagement expected)
}

# Default threshold for unknown platforms
DEFAULT_FAILURE_THRESHOLD = 0.02

MIN_SAMPLES_FOR_PATTERN = 3  # Minimum failed content pieces to establish a pattern

# Detailed explanations for each pattern type (the "why" and "instead")
PATTERN_EXPLANATIONS = {
    "too_short_hook": {
        "why": "Short hooks don't create enough curiosity to stop the scroll. Users need a reason to invest attention.",
        "instead": "Use 40-80 characters that promise value or create a curiosity gap",
        "example_bad": "Quick tip:",
        "example_good": "The debugging trick that saved our team 4 hours every sprint:",
    },
    "exclamation_hook": {
        "why": "Exclamation marks in hooks read as hyperbolic or salesy, triggering skepticism",
        "instead": "Use periods or questions. Let the content be compelling, not the punctuation",
        "example_bad": "This is amazing!",
        "example_good": "This changed how we think about testing.",
    },
    "self_focused_hook": {
        "why": "Self-focused openings (I/We/Our) don't create value for the reader. They scroll past content that isn't about them.",
        "instead": "Start with reader benefit, a question, or a curiosity gap",
        "example_bad": "I'm excited to share our latest feature...",
        "example_good": "Your deploys are about to get 3x faster. Here's how:",
    },
    "numbered_list_start": {
        "why": "Starting with a numbered list signals listicle content, which has declining engagement as audiences tire of the format",
        "instead": "Lead with a compelling insight, then introduce the list if needed",
        "example_bad": "5 ways to improve your code:",
        "example_good": "Most code reviews miss the same critical issue. Here's what to look for:",
    },
    "long_statement_no_question": {
        "why": "Long declarative statements without questions feel like lectures. Questions invite engagement and curiosity.",
        "instead": "Break up with questions or make the reader feel included",
        "example_bad": "Our team has been working on improving the deployment pipeline...",
        "example_good": "Ever wonder why some deploys take 20 minutes while others take 2? We did too.",
    },
    "hyperbolic_hook": {
        "why": "Hyperbolic language (excited, amazing, incredible, revolutionary) triggers platform spam filters and erodes audience trust",
        "instead": "Use specific data or outcomes instead of superlatives",
        "example_bad": "This incredible tool will revolutionize your workflow!",
        "example_good": "This tool cut our team's review time from 4 hours to 20 minutes.",
    },
    "too_short": {
        "why": "Content too short for the platform fails to deliver enough value to justify engagement",
        "instead": "Match the platform's content depth expectations",
    },
    "too_long": {
        "why": "Content too long for the platform loses attention before delivering the key insight",
        "instead": "Front-load value and trim ruthlessly for platform fit",
    },
    "late_night": {
        "why": "Late night posts (before 6am) miss the majority of audience activity windows",
        "instead": "Schedule for peak engagement hours (typically 8-10am or 12-2pm)",
    },
    "evening": {
        "why": "Late evening posts compete with personal time and entertainment content",
        "instead": "Post during work hours when professional content is more relevant",
    },
    "lunch_hour": {
        "why": "Lunch hour posts on some platforms underperform as audiences switch contexts",
        "instead": "Test mid-morning or mid-afternoon for better engagement",
    },
}


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

        # Filter to failed content using platform-specific thresholds
        failures = []
        for pub, metric in rows:
            platform = pub.platform or "linkedin"
            threshold = PLATFORM_FAILURE_THRESHOLDS.get(platform, DEFAULT_FAILURE_THRESHOLD)

            if metric.engagement_rate < threshold:
                creation = creations.get(pub.creation_id)
                if creation:
                    failures.append({
                        "publication": pub,
                        "metric": metric,
                        "creation": creation,
                        "platform": platform,
                        "failure_threshold": threshold,
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

        Returns a markdown-formatted string of patterns to avoid, with detailed
        explanations of WHY each pattern fails and what to do INSTEAD.
        Only returns patterns relevant to the specified platform.
        """
        if not self._cached_patterns:
            return ""

        lines = [f"## AVOID: Patterns That Underperform on {platform.title()}"]
        lines.append("The following patterns have led to poor engagement. Each includes why it fails and what to do instead.\n")

        has_content = False

        # Hook patterns - now platform-specific
        hook_patterns = self._cached_patterns.get("hook_patterns", {})
        platform_hooks = hook_patterns.get(platform, [])

        if platform_hooks:
            has_content = True
            lines.append("### Hook Patterns to Avoid")
            for pattern in platform_hooks[:3]:  # Top 3 patterns
                ptype = pattern["type"]
                explanation = PATTERN_EXPLANATIONS.get(ptype, {})

                lines.append(f"\n**❌ {pattern['description']}** (failure rate: {pattern['failure_rate']:.0%})")

                if explanation.get("why"):
                    lines.append(f"  - **Why it fails:** {explanation['why']}")
                if explanation.get("instead"):
                    lines.append(f"  - **Do this instead:** {explanation['instead']}")
                if explanation.get("example_bad"):
                    lines.append(f"  - **Bad:** \"{explanation['example_bad']}\"")
                if explanation.get("example_good"):
                    lines.append(f"  - **Good:** \"{explanation['example_good']}\"")

            lines.append("")

        # Length patterns for this platform
        length = self._cached_patterns.get("length_patterns", {}).get(platform, [])
        if length:
            has_content = True
            lines.append(f"### Length Issues on {platform.title()}")
            for pattern in length:
                ptype = pattern["type"]
                explanation = PATTERN_EXPLANATIONS.get(ptype, {})

                lines.append(f"\n**❌ {pattern['description']}**")
                if explanation.get("why"):
                    lines.append(f"  - **Why it fails:** {explanation['why']}")
                if explanation.get("instead"):
                    lines.append(f"  - **Do this instead:** {explanation['instead']}")
            lines.append("")

        # Timing patterns for this platform
        timing = self._cached_patterns.get("timing_patterns", {}).get(platform, [])
        if timing:
            has_content = True
            lines.append(f"### Bad Posting Times for {platform.title()}")
            for pattern in timing[:3]:
                ptype = pattern["type"]
                # Handle timing pattern types (day_Monday, late_night, etc.)
                if ptype.startswith("day_"):
                    explanation = {}
                else:
                    explanation = PATTERN_EXPLANATIONS.get(ptype, {})

                lines.append(f"\n**❌ {pattern['description']}**")
                if explanation.get("why"):
                    lines.append(f"  - **Why it fails:** {explanation['why']}")
                if explanation.get("instead"):
                    lines.append(f"  - **Do this instead:** {explanation['instead']}")
            lines.append("")

        # Skill patterns (platform-agnostic but still useful)
        skills = self._cached_patterns.get("skill_patterns", [])
        if skills:
            # Filter to skills with high failure rate and enough data
            underperforming = [
                s for s in skills
                if s.get("failure_rate", 0) > 0.5 and s.get("total_uses_in_failed", 0) >= 3
            ]
            if underperforming:
                has_content = True
                lines.append("### Skills to Use Cautiously")
                for pattern in underperforming[:3]:
                    lines.append(
                        f"- Skill '{pattern['skill_name']}' has {pattern['failure_rate']:.0%} "
                        f"failure rate ({pattern['failure_count']}/{pattern['total_uses_in_failed']} uses)"
                    )
                lines.append("")

        if not has_content:
            return ""

        return "\n".join(lines)

    def _analyze_hooks(self, failures: list[dict]) -> dict[str, list[dict]]:
        """Analyze opening lines of failed content, organized by platform.

        Returns a dict mapping platform -> list of patterns for that platform.
        """
        hook_issues_by_platform = defaultdict(lambda: defaultdict(int))
        platform_totals = defaultdict(int)

        for f in failures:
            platform = f.get("platform", f["creation"].platform or "linkedin")
            platform_totals[platform] += 1

            body = f["creation"].body or ""
            first_line = body.split("\n")[0].strip()

            # Check for common hook issues
            if len(first_line) < 20:
                hook_issues_by_platform[platform]["too_short_hook"] += 1
            if first_line.endswith("!"):
                hook_issues_by_platform[platform]["exclamation_hook"] += 1
            if first_line.startswith(("I ", "We ", "Our ")):
                hook_issues_by_platform[platform]["self_focused_hook"] += 1
            if re.match(r"^\d+\.", first_line):
                hook_issues_by_platform[platform]["numbered_list_start"] += 1
            if "?" not in first_line and len(first_line) > 50:
                hook_issues_by_platform[platform]["long_statement_no_question"] += 1
            if any(word in first_line.lower() for word in ["excited", "thrilled", "amazing", "incredible"]):
                hook_issues_by_platform[platform]["hyperbolic_hook"] += 1

        # Build platform-specific patterns
        result = {}
        for platform, issues in hook_issues_by_platform.items():
            patterns = []
            total = platform_totals[platform]

            for issue, count in issues.items():
                rate = count / total if total > 0 else 0
                # Lower threshold for platform-specific patterns (more actionable)
                if rate >= 0.25 and count >= 2:
                    description = {
                        "too_short_hook": f"On {platform}: Very short opening lines (<20 chars)",
                        "exclamation_hook": f"On {platform}: Opening lines ending with exclamation marks",
                        "self_focused_hook": f"On {platform}: Self-focused openings (I/We/Our)",
                        "numbered_list_start": f"On {platform}: Starting with numbered list format",
                        "long_statement_no_question": f"On {platform}: Long declarative statements without questions",
                        "hyperbolic_hook": f"On {platform}: Hyperbolic language (excited, amazing, incredible)",
                    }.get(issue, issue)

                    # Calculate confidence based on sample size
                    confidence = min(0.95, rate * (total / 10))

                    patterns.append({
                        "type": issue,
                        "platform": platform,
                        "description": description,
                        "count": count,
                        "sample_size": total,
                        "failure_rate": rate,
                        "confidence": confidence,
                    })

            if patterns:
                result[platform] = sorted(patterns, key=lambda x: x["failure_rate"], reverse=True)

        return result

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
