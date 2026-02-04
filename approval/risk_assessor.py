"""Risk assessment for content before publishing."""

import logging
import re

logger = logging.getLogger(__name__)

# Keywords that increase risk
HIGH_RISK_KEYWORDS = [
    "competitor", "lawsuit", "fired", "scandal", "bankrupt", "fraud",
    "stolen", "leaked", "confidential", "insider", "sec filing",
]
MEDIUM_RISK_KEYWORDS = [
    "controversy", "debate", "backlash", "criticism", "failed",
    "layoff", "pivot", "struggle", "problem", "issue",
]

# Claims that need fact-checking
CLAIM_PATTERNS = [
    r"\d+[x%] (?:faster|better|cheaper|more)",  # quantitative claims
    r"first (?:ever|to|in the world)",  # superlative claims
    r"(?:always|never|every|no one)",  # absolute claims
]


class RiskAssessor:
    """Assess content risk using keyword matching and pattern detection."""

    def assess(self, content: str, title: str = "") -> dict:
        """Return {"risk_level": "low"|"medium"|"high", "score": 0.0-1.0, "flags": [...]}."""
        text = f"{title} {content}".lower()
        flags = []
        score = 0.0

        # Check high-risk keywords
        for kw in HIGH_RISK_KEYWORDS:
            if kw in text:
                flags.append(f"high_risk_keyword: {kw}")
                score += 0.3

        # Check medium-risk keywords
        for kw in MEDIUM_RISK_KEYWORDS:
            if kw in text:
                flags.append(f"medium_risk_keyword: {kw}")
                score += 0.1

        # Check claim patterns
        for pattern in CLAIM_PATTERNS:
            matches = re.findall(pattern, text)
            for match in matches:
                flags.append(f"unverified_claim: {match}")
                score += 0.15

        # Check for competitor mentions
        competitors = ["openai", "anthropic", "google", "meta", "microsoft"]
        for comp in competitors:
            if comp in text:
                flags.append(f"competitor_mention: {comp}")
                score += 0.05

        score = min(score, 1.0)

        if score >= 0.6:
            risk_level = "high"
        elif score >= 0.25:
            risk_level = "medium"
        else:
            risk_level = "low"

        return {"risk_level": risk_level, "score": round(score, 2), "flags": flags}
