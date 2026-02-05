"""Approval queue — routes content by risk level with quality gating."""

import logging
import re
from datetime import datetime, timezone

from sqlalchemy import select

from approval.risk_assessor import RiskAssessor
from db import async_session
from models import ContentCreation

logger = logging.getLogger(__name__)

# Quality thresholds
QUALITY_AUTO_REJECT_THRESHOLD = 0.4
QUALITY_WARNING_THRESHOLD = 0.6

# Platform-specific quality profiles with comprehensive checks
PLATFORM_QUALITY_PROFILES = {
    "linkedin": {
        "min_length": 150,
        "ideal_length": (300, 1500),
        "max_length": 3000,
        "requires_paragraphs": True,
        "ideal_sentence_length": (12, 25),
        "banned_words": ["revolutionary", "game-changing", "excited to announce", "synergy", "leverage"],
        "requires_cta": False,
        "hook_max_length": 200,
        "max_exclamations": 1,
        "max_emojis": 3,
    },
    "twitter": {
        "min_length": 20,
        "ideal_length": (100, 250),
        "max_length": 280,
        "requires_paragraphs": False,
        "ideal_sentence_length": (5, 15),
        "banned_words": ["revolutionary"],
        "requires_cta": False,
        "hook_max_length": 100,
        "max_exclamations": 2,
        "max_emojis": 5,
    },
    "youtube": {
        "min_length": 100,
        "ideal_length": (200, 500),
        "max_length": 1000,
        "requires_paragraphs": False,
        "requires_hook": True,
        "hook_max_length": 50,  # First line spoken aloud - keep it punchy
        "requires_pacing": True,  # Needs [pause], [emphasis] markers for video
        "ideal_sentence_length": (8, 18),
        "banned_words": ["click below", "smash that like"],
        "max_exclamations": 2,
        "max_emojis": 2,
    },
    "tiktok": {
        "min_length": 20,
        "ideal_length": (50, 200),
        "max_length": 300,
        "requires_paragraphs": False,
        "ideal_sentence_length": (5, 12),
        "banned_words": [],
        "requires_cta": False,
        "hook_max_length": 40,  # Very short hook for fast scrolling
        "max_exclamations": 3,
        "max_emojis": 8,
    },
    "medium": {
        "min_length": 500,
        "ideal_length": (1200, 4000),
        "max_length": 10000,
        "requires_paragraphs": True,
        "ideal_sentence_length": (15, 30),
        "banned_words": ["revolutionary", "game-changing"],
        "requires_cta": False,
        "requires_sections": True,  # Should have ## headers
        "hook_max_length": 250,
        "max_exclamations": 2,
        "max_emojis": 1,
    },
}

# Legacy format for backward compatibility
PLATFORM_LENGTH_RANGES = {
    platform: {
        "min": profile["min_length"],
        "max": profile["max_length"],
        "ideal_min": profile["ideal_length"][0],
        "ideal_max": profile["ideal_length"][1],
    }
    for platform, profile in PLATFORM_QUALITY_PROFILES.items()
}


class QualityChecker:
    """Pre-approval quality gate for content.

    Evaluates content on multiple dimensions before risk assessment.
    Uses platform-specific quality profiles for appropriate thresholds.
    Content scoring below QUALITY_AUTO_REJECT_THRESHOLD (0.4) is auto-rejected.
    """

    def check(self, content: ContentCreation) -> dict:
        """Evaluate content quality using platform-specific profiles.

        Returns:
            dict with keys:
                - score: float 0-1 (higher is better)
                - passed: bool (True if score >= threshold)
                - issues: list of identified problems
                - metrics: detailed breakdown
        """
        body = content.body or ""
        title = content.title or ""
        platform = content.platform or "linkedin"

        # Get platform-specific profile
        profile = PLATFORM_QUALITY_PROFILES.get(platform, PLATFORM_QUALITY_PROFILES["linkedin"])

        issues = []
        metrics = {}

        # Pre-check: Fail immediately on placeholder content
        placeholder_patterns = [r"\[.*?\]", r"\{.*?\}", r"TODO", r"PLACEHOLDER"]
        for pattern in placeholder_patterns:
            if re.search(pattern, body):
                issues.append("Contains placeholder text (auto-reject)")
                return {
                    "score": 0.1,
                    "passed": False,
                    "warning": False,
                    "issues": issues,
                    "metrics": {"placeholder_detected": True},
                }

        # 1. Length score (platform-specific)
        length_score, length_issues = self._check_length_with_profile(body, platform, profile)
        metrics["length"] = length_score
        issues.extend(length_issues)

        # 2. Readability score (sentence structure, word complexity)
        readability_score, readability_issues = self._check_readability_with_profile(body, profile)
        metrics["readability"] = readability_score
        issues.extend(readability_issues)

        # 3. Structure score (paragraphs, formatting)
        structure_score, structure_issues = self._check_structure_with_profile(body, platform, profile)
        metrics["structure"] = structure_score
        issues.extend(structure_issues)

        # 4. Title quality
        title_score, title_issues = self._check_title(title, platform)
        metrics["title"] = title_score
        issues.extend(title_issues)

        # 5. Content substance (not just filler/fluff)
        substance_score, substance_issues = self._check_substance_with_profile(body, profile)
        metrics["substance"] = substance_score
        issues.extend(substance_issues)

        # 6. Hook quality (platform-specific)
        hook_score, hook_issues = self._check_hook(body, profile)
        metrics["hook"] = hook_score
        issues.extend(hook_issues)

        # Weighted average with platform-aware weighting
        if platform in ("twitter", "tiktok"):
            # Short-form: hook matters more, structure matters less
            weights = {
                "length": 0.15,
                "readability": 0.15,
                "structure": 0.10,
                "title": 0.10,
                "substance": 0.25,
                "hook": 0.25,
            }
        elif platform == "medium":
            # Long-form: structure and substance matter more
            weights = {
                "length": 0.15,
                "readability": 0.20,
                "structure": 0.20,
                "title": 0.15,
                "substance": 0.20,
                "hook": 0.10,
            }
        else:
            # Default (LinkedIn, YouTube)
            weights = {
                "length": 0.15,
                "readability": 0.15,
                "structure": 0.15,
                "title": 0.10,
                "substance": 0.25,
                "hook": 0.20,
            }

        overall_score = sum(metrics[k] * weights[k] for k in weights)

        passed = overall_score >= QUALITY_AUTO_REJECT_THRESHOLD
        warning = overall_score < QUALITY_WARNING_THRESHOLD

        return {
            "score": round(overall_score, 3),
            "passed": passed,
            "warning": warning and passed,
            "issues": issues,
            "metrics": {k: round(v, 3) for k, v in metrics.items()},
            "platform_profile": platform,
        }

    def _check_length(self, body: str, platform: str) -> tuple[float, list[str]]:
        """Check if content length is appropriate for platform (legacy method)."""
        profile = PLATFORM_QUALITY_PROFILES.get(platform, PLATFORM_QUALITY_PROFILES["linkedin"])
        return self._check_length_with_profile(body, platform, profile)

    def _check_length_with_profile(self, body: str, platform: str, profile: dict) -> tuple[float, list[str]]:
        """Check if content length is appropriate using platform profile."""
        issues = []
        length = len(body)

        min_len = profile["min_length"]
        max_len = profile["max_length"]
        ideal_min, ideal_max = profile["ideal_length"]

        if length < min_len:
            issues.append(f"Content too short for {platform} ({length} chars, min {min_len})")
            return 0.0, issues
        if length > max_len:
            issues.append(f"Content too long for {platform} ({length} chars, max {max_len})")
            return 0.3, issues

        # Score based on ideal range
        if ideal_min <= length <= ideal_max:
            return 1.0, issues
        elif length < ideal_min:
            # Scale between min and ideal_min
            ratio = (length - min_len) / (ideal_min - min_len) if ideal_min > min_len else 1.0
            return 0.5 + 0.5 * ratio, issues
        else:
            # Scale between ideal_max and max
            ratio = (max_len - length) / (max_len - ideal_max) if max_len > ideal_max else 1.0
            return 0.5 + 0.5 * ratio, issues

    def _check_readability(self, body: str) -> tuple[float, list[str]]:
        """Check readability using simple heuristics (legacy method)."""
        profile = PLATFORM_QUALITY_PROFILES.get("linkedin", PLATFORM_QUALITY_PROFILES["linkedin"])
        return self._check_readability_with_profile(body, profile)

    def _check_readability_with_profile(self, body: str, profile: dict) -> tuple[float, list[str]]:
        """Check readability using platform-specific profile."""
        issues = []

        if not body.strip():
            return 0.0, ["Empty content"]

        sentences = re.split(r'[.!?]+', body)
        sentences = [s.strip() for s in sentences if s.strip()]

        if not sentences:
            return 0.2, ["No complete sentences found"]

        # Platform-specific ideal sentence length
        ideal_min, ideal_max = profile.get("ideal_sentence_length", (12, 25))

        word_counts = [len(s.split()) for s in sentences]
        avg_sentence_length = sum(word_counts) / len(word_counts)

        # Score based on platform's ideal range
        if ideal_min <= avg_sentence_length <= ideal_max:
            sentence_score = 1.0
        elif avg_sentence_length > ideal_max * 1.5:
            issues.append(f"Sentences too long (avg {avg_sentence_length:.0f} words, ideal {ideal_min}-{ideal_max})")
            sentence_score = 0.3
        elif avg_sentence_length > ideal_max:
            issues.append(f"Sentences somewhat long (avg {avg_sentence_length:.0f} words)")
            sentence_score = 0.6
        elif avg_sentence_length < ideal_min * 0.5:
            issues.append(f"Sentences too short (avg {avg_sentence_length:.0f} words)")
            sentence_score = 0.5
        else:
            sentence_score = 0.8

        # Check for all caps (shouting)
        caps_ratio = sum(1 for c in body if c.isupper()) / max(len(body), 1)
        if caps_ratio > 0.3:
            issues.append("Too much CAPS ({:.0%})".format(caps_ratio))
            caps_score = 0.3
        else:
            caps_score = 1.0

        # Check for excessive exclamation marks
        max_exclamations = profile.get("max_exclamations", 2)
        exclamation_count = body.count("!")
        if exclamation_count > max_exclamations:
            issues.append(f"Too many exclamation marks ({exclamation_count}, max {max_exclamations})")
            exclamation_score = 0.5
        else:
            exclamation_score = 1.0

        return (sentence_score * 0.6 + caps_score * 0.2 + exclamation_score * 0.2), issues

    def _check_structure(self, body: str, platform: str) -> tuple[float, list[str]]:
        """Check content structure and formatting (legacy method)."""
        profile = PLATFORM_QUALITY_PROFILES.get(platform, PLATFORM_QUALITY_PROFILES["linkedin"])
        return self._check_structure_with_profile(body, platform, profile)

    def _check_structure_with_profile(self, body: str, platform: str, profile: dict) -> tuple[float, list[str]]:
        """Check content structure using platform-specific profile."""
        issues = []
        score = 1.0

        # Check for paragraph breaks if required
        if profile.get("requires_paragraphs", False):
            paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
            min_len = profile["min_length"]
            if len(paragraphs) == 1 and len(body) > min_len * 2:
                issues.append(f"Single large paragraph on {platform} - needs breaks")
                score = min(score, 0.4)

        # Check for sections/headers if required (Medium long-form)
        if profile.get("requires_sections", False):
            has_headers = bool(re.search(r'^#{1,3}\s', body, re.MULTILINE))
            if len(body) > 1000 and not has_headers:
                issues.append("Long-form content missing section headers")
                score = min(score, 0.6)

        # Check for bullet points / lists in long-form content
        has_lists = bool(re.search(r'^[\-\*•]\s', body, re.MULTILINE))
        ideal_max = profile["ideal_length"][1]
        if profile.get("requires_paragraphs", False) and len(body) > ideal_max and not has_lists:
            # Not a hard penalty, just slightly lower score
            score = min(score, 0.7)

        # Check for pacing markers if required (YouTube scripts)
        if profile.get("requires_pacing", False):
            has_pacing = bool(re.search(r'\[(pause|emphasis|beat)\]', body, re.IGNORECASE))
            if not has_pacing:
                # Mild suggestion, not a hard fail
                pass  # Could add soft guidance here

        return score, issues

    def _check_title(self, title: str, platform: str) -> tuple[float, list[str]]:
        """Check title quality."""
        issues = []

        if not title:
            if platform in ["linkedin", "medium", "youtube"]:
                issues.append("Missing title")
                return 0.3, issues
            return 0.8, issues  # Twitter/TikTok don't need titles

        if len(title) < 10:
            issues.append("Title too short")
            return 0.5, issues

        if len(title) > 150:
            issues.append("Title too long")
            return 0.6, issues

        # Check for clickbait patterns (optional warning)
        clickbait_patterns = [
            r"you won't believe",
            r"shocking",
            r"\d+ things",
            r"this one trick",
        ]
        for pattern in clickbait_patterns:
            if re.search(pattern, title, re.IGNORECASE):
                issues.append("Potential clickbait title")
                return 0.7, issues

        return 1.0, issues

    def _check_substance(self, body: str) -> tuple[float, list[str]]:
        """Check if content has substance vs just filler (legacy method)."""
        profile = PLATFORM_QUALITY_PROFILES.get("linkedin", PLATFORM_QUALITY_PROFILES["linkedin"])
        return self._check_substance_with_profile(body, profile)

    def _check_substance_with_profile(self, body: str, profile: dict) -> tuple[float, list[str]]:
        """Check if content has substance using platform-specific profile."""
        issues = []

        if not body.strip():
            return 0.0, ["No content"]

        words = body.lower().split()
        if len(words) < 10:
            return 0.3, ["Too few words to evaluate substance"]

        # Check for excessive filler words
        filler_words = {
            "very", "really", "just", "actually", "basically", "literally",
            "honestly", "simply", "absolutely", "definitely", "totally",
        }
        filler_count = sum(1 for w in words if w in filler_words)
        filler_ratio = filler_count / len(words)

        if filler_ratio > 0.1:
            issues.append("Too many filler words ({:.0%})".format(filler_ratio))
            filler_score = 0.4
        elif filler_ratio > 0.05:
            filler_score = 0.7
        else:
            filler_score = 1.0

        # Check for banned words (platform-specific)
        banned_words = profile.get("banned_words", [])
        body_lower = body.lower()
        found_banned = [w for w in banned_words if w.lower() in body_lower]
        if found_banned:
            issues.append(f"Contains banned phrases: {', '.join(found_banned[:3])}")
            banned_score = 0.5
        else:
            banned_score = 1.0

        # Check for repetition (same word repeated excessively)
        word_freq = {}
        for w in words:
            if len(w) > 4:  # Only check longer words
                word_freq[w] = word_freq.get(w, 0) + 1

        max_repeat = max(word_freq.values()) if word_freq else 0
        repeat_ratio = max_repeat / len(words) if words else 0

        if repeat_ratio > 0.1:
            issues.append("Excessive word repetition")
            repeat_score = 0.5
        else:
            repeat_score = 1.0

        # Check for placeholder/template markers
        placeholder_patterns = [r"\[.*?\]", r"\{.*?\}", r"TODO", r"PLACEHOLDER"]
        for pattern in placeholder_patterns:
            if re.search(pattern, body):
                issues.append("Contains placeholder text")
                return 0.2, issues

        return (filler_score * 0.4 + repeat_score * 0.3 + banned_score * 0.3), issues

    def _check_hook(self, body: str, profile: dict) -> tuple[float, list[str]]:
        """Check the quality of the opening hook."""
        issues = []

        if not body.strip():
            return 0.0, []

        # Get first line as the hook
        first_line = body.split("\n")[0].strip()
        hook_max_length = profile.get("hook_max_length", 200)

        # Check hook length
        if len(first_line) < 15:
            issues.append("Hook too short to capture attention")
            return 0.4, issues

        if len(first_line) > hook_max_length:
            issues.append(f"Hook too long ({len(first_line)} chars, max {hook_max_length})")
            return 0.6, issues

        score = 1.0

        # Penalize self-focused hooks
        if first_line.startswith(("I ", "We ", "Our ", "My ")):
            issues.append("Self-focused hook (starts with I/We/Our)")
            score = min(score, 0.6)

        # Penalize exclamation-heavy hooks
        if first_line.endswith("!"):
            issues.append("Hook ends with exclamation mark")
            score = min(score, 0.7)

        # Penalize hyperbolic language
        hyperbolic = ["excited", "thrilled", "amazing", "incredible", "revolutionary", "game-changing"]
        if any(word in first_line.lower() for word in hyperbolic):
            issues.append("Hook contains hyperbolic language")
            score = min(score, 0.5)

        # Bonus for question hooks (engagement driver)
        if "?" in first_line:
            score = min(1.0, score + 0.1)

        return score, issues


class ApprovalQueue:
    """Route content through approval based on quality gating and risk assessment.

    Pipeline:
    1. Quality Check (auto-reject if score < 0.4)
    2. Risk Assessment (block high-risk content)
    3. Variant routing (A/B tests → human review)
    4. Auto-approval for low-risk content
    """

    def __init__(self):
        self.risk_assessor = RiskAssessor()
        self.quality_checker = QualityChecker()

    async def process(self, creation_id: int, at: datetime | None = None) -> dict:
        """Assess and route a content creation through approval.

        Quality gating runs first - content with quality score < 0.4 is auto-rejected
        before risk assessment even runs.
        """
        now = at or datetime.now(timezone.utc)

        async with async_session() as session:
            result = await session.execute(
                select(ContentCreation).where(ContentCreation.id == creation_id)
            )
            creation = result.scalar_one_or_none()
            if not creation:
                return {"status": "error", "message": "Creation not found"}

            # Step 1: Quality gating (runs before risk assessment)
            quality = self.quality_checker.check(creation)

            if not quality["passed"]:
                creation.approval_status = "quality_rejected"
                creation.quality_score = quality["score"]
                creation.quality_issues = quality["issues"]
                await session.commit()

                logger.warning(
                    "Content %d QUALITY REJECTED: score=%.2f, issues=%s",
                    creation_id, quality["score"], quality["issues"]
                )
                return {
                    "decision": "quality_rejected",
                    "quality": quality,
                    "risk": None,
                }

            # Store quality metrics even for passing content
            creation.quality_score = quality["score"]
            creation.quality_issues = quality["issues"] if quality["issues"] else None

            # Step 2: Risk assessment
            assessment = self.risk_assessor.assess(creation.body, creation.title or "")
            creation.risk_score = assessment["score"]
            creation.risk_flags = assessment["flags"]

            # Step 3: Routing decision
            if assessment["risk_level"] == "high":
                creation.approval_status = "rejected"
                decision = "blocked"
            elif creation.variant_group:
                # Variant groups always go to human review
                creation.approval_status = "pending_review"
                decision = "pending_review"
            elif assessment["risk_level"] == "low":
                # Quality warning bumps to human review
                if quality.get("warning"):
                    creation.approval_status = "pending_review"
                    decision = "pending_review"
                    logger.info(
                        "Content %d: quality warning (%.2f), sending to review",
                        creation_id, quality["score"]
                    )
                else:
                    creation.approval_status = "auto_approved"
                    creation.approved_at = now
                    decision = "auto_approved"
            else:
                creation.approval_status = "pending"
                decision = "pending_review"

            await session.commit()

        logger.info(
            "Content %d: quality=%.2f, risk=%s, decision=%s",
            creation_id, quality["score"], assessment["risk_level"], decision
        )
        return {"decision": decision, "quality": quality, "risk": assessment}

    async def process_pending(
        self, at: datetime | None = None, skip_video: bool = False
    ) -> list[dict]:
        """Process all pending content creations.

        Args:
            at: Timestamp to use for approval
            skip_video: If True, video generation will be skipped for cost savings.
                       This flag is passed through for downstream processing.
        """
        async with async_session() as session:
            result = await session.execute(
                select(ContentCreation).where(ContentCreation.approval_status == "pending")
            )
            creations = result.scalars().all()

        if skip_video:
            logger.info("Video generation disabled for this batch (cost-saving mode)")

        results = []
        for creation in creations:
            r = await self.process(creation.id, at=at)
            r["skip_video"] = skip_video
            results.append({"creation_id": creation.id, **r})
        return results
