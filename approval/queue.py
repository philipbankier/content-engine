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

# Platform-specific length expectations
PLATFORM_LENGTH_RANGES = {
    "linkedin": {"min": 100, "max": 3000, "ideal_min": 200, "ideal_max": 1500},
    "twitter": {"min": 10, "max": 280, "ideal_min": 50, "ideal_max": 250},
    "youtube": {"min": 50, "max": 5000, "ideal_min": 100, "ideal_max": 2000},
    "tiktok": {"min": 20, "max": 500, "ideal_min": 50, "ideal_max": 300},
    "medium": {"min": 300, "max": 10000, "ideal_min": 800, "ideal_max": 5000},
}


class QualityChecker:
    """Pre-approval quality gate for content.

    Evaluates content on multiple dimensions before risk assessment.
    Content scoring below QUALITY_AUTO_REJECT_THRESHOLD (0.4) is auto-rejected.
    """

    def check(self, content: ContentCreation) -> dict:
        """Evaluate content quality.

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

        # 1. Length score
        length_score, length_issues = self._check_length(body, platform)
        metrics["length"] = length_score
        issues.extend(length_issues)

        # 2. Readability score (sentence structure, word complexity)
        readability_score, readability_issues = self._check_readability(body)
        metrics["readability"] = readability_score
        issues.extend(readability_issues)

        # 3. Structure score (paragraphs, formatting)
        structure_score, structure_issues = self._check_structure(body, platform)
        metrics["structure"] = structure_score
        issues.extend(structure_issues)

        # 4. Title quality
        title_score, title_issues = self._check_title(title, platform)
        metrics["title"] = title_score
        issues.extend(title_issues)

        # 5. Content substance (not just filler/fluff)
        substance_score, substance_issues = self._check_substance(body)
        metrics["substance"] = substance_score
        issues.extend(substance_issues)

        # Weighted average
        weights = {
            "length": 0.15,
            "readability": 0.20,
            "structure": 0.15,
            "title": 0.15,
            "substance": 0.35,
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
        }

    def _check_length(self, body: str, platform: str) -> tuple[float, list[str]]:
        """Check if content length is appropriate for platform."""
        issues = []
        length = len(body)
        ranges = PLATFORM_LENGTH_RANGES.get(platform, PLATFORM_LENGTH_RANGES["linkedin"])

        if length < ranges["min"]:
            issues.append(f"Content too short ({length} chars, min {ranges['min']})")
            return 0.0, issues
        if length > ranges["max"]:
            issues.append(f"Content too long ({length} chars, max {ranges['max']})")
            return 0.3, issues

        # Score based on ideal range
        if ranges["ideal_min"] <= length <= ranges["ideal_max"]:
            return 1.0, issues
        elif length < ranges["ideal_min"]:
            # Scale between min and ideal_min
            ratio = (length - ranges["min"]) / (ranges["ideal_min"] - ranges["min"])
            return 0.5 + 0.5 * ratio, issues
        else:
            # Scale between ideal_max and max
            ratio = (ranges["max"] - length) / (ranges["max"] - ranges["ideal_max"])
            return 0.5 + 0.5 * ratio, issues

    def _check_readability(self, body: str) -> tuple[float, list[str]]:
        """Check readability using simple heuristics."""
        issues = []

        if not body.strip():
            return 0.0, ["Empty content"]

        sentences = re.split(r'[.!?]+', body)
        sentences = [s.strip() for s in sentences if s.strip()]

        if not sentences:
            return 0.2, ["No complete sentences found"]

        # Average sentence length (aim for 15-25 words)
        word_counts = [len(s.split()) for s in sentences]
        avg_sentence_length = sum(word_counts) / len(word_counts)

        if avg_sentence_length > 40:
            issues.append("Sentences too long (avg {:.0f} words)".format(avg_sentence_length))
            sentence_score = 0.3
        elif avg_sentence_length > 30:
            issues.append("Sentences somewhat long (avg {:.0f} words)".format(avg_sentence_length))
            sentence_score = 0.6
        elif avg_sentence_length < 5:
            issues.append("Sentences too short (avg {:.0f} words)".format(avg_sentence_length))
            sentence_score = 0.5
        else:
            sentence_score = 1.0

        # Check for all caps (shouting)
        caps_ratio = sum(1 for c in body if c.isupper()) / max(len(body), 1)
        if caps_ratio > 0.3:
            issues.append("Too much CAPS ({:.0%})".format(caps_ratio))
            caps_score = 0.3
        else:
            caps_score = 1.0

        return (sentence_score * 0.7 + caps_score * 0.3), issues

    def _check_structure(self, body: str, platform: str) -> tuple[float, list[str]]:
        """Check content structure and formatting."""
        issues = []

        # Check for paragraph breaks (except Twitter which is short)
        if platform not in ["twitter", "tiktok"]:
            paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
            if len(paragraphs) == 1 and len(body) > 500:
                issues.append("Single large paragraph - needs breaks")
                return 0.4, issues

        # Check for bullet points / lists in long-form content
        has_lists = bool(re.search(r'^[\-\*•]\s', body, re.MULTILINE))
        if platform in ["linkedin", "medium"] and len(body) > 800 and not has_lists:
            # Not a hard penalty, just slightly lower score
            return 0.7, issues

        return 1.0, issues

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
        """Check if content has substance vs just filler."""
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

        return (filler_score * 0.5 + repeat_score * 0.5), issues


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
