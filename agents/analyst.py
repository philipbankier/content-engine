"""AnalystAgent: scores and evaluates discovered content for arbitrage potential."""

import json
import logging
import re
from datetime import datetime, timezone

from sqlalchemy import select

from agents.base import BaseAgent
from db import async_session
from models import ContentDiscovery

logger = logging.getLogger(__name__)

ANALYST_SYSTEM_PROMPT = """You are a content analyst for an autonomous publishing system. Evaluate each content item for arbitrage potential.

Score each item on:
- relevance_score (0.0-1.0): How relevant is this to AI, automation, and the future of work?
- velocity_score (0.0-1.0): How fast is this trending? Higher = faster spread.
- risk_level ("low", "medium", "high"): Brand risk assessment.
- platform_fit: {"linkedin": 0.0-1.0, "twitter": 0.0-1.0, "youtube": 0.0-1.0, "tiktok": 0.0-1.0}
- suggested_formats: list of format types like "post", "thread", "short", "article", "carousel"

Return valid JSON array with one object per item, keyed by source_id."""

BATCH_SIZE = 20


class AnalystAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="analyst")

    async def run(self, at: datetime | None = None) -> dict:
        """Score all new discoveries in batches via Bedrock."""
        now = at or datetime.now(timezone.utc)
        analyzed_count = 0
        error_count = 0

        # Load skills for source scoring
        skills = self.select_skills("source_scoring")
        skills_text = self.format_skills_for_prompt(skills)

        async with async_session() as session:
            result = await session.execute(
                select(ContentDiscovery)
                .where(ContentDiscovery.status == "new")
                .order_by(ContentDiscovery.discovered_at.desc())
            )
            discoveries = list(result.scalars().all())

        if not discoveries:
            logger.info("Analyst: no new discoveries to analyze")
            return {"analyzed": 0, "errors": 0, "total_pending": 0}

        # Process in batches
        for i in range(0, len(discoveries), BATCH_SIZE):
            batch = discoveries[i : i + BATCH_SIZE]
            try:
                batch_analyzed, batch_errors = await self._analyze_batch(
                    batch, skills_text, skills, now
                )
                analyzed_count += batch_analyzed
                error_count += batch_errors
            except Exception as e:
                logger.error("Analyst batch %d failed: %s", i // BATCH_SIZE, e)
                error_count += len(batch)

        logger.info(
            "Analyst complete: %d analyzed, %d errors from %d total",
            analyzed_count,
            error_count,
            len(discoveries),
        )
        return {
            "analyzed": analyzed_count,
            "errors": error_count,
            "total_pending": len(discoveries),
        }

    async def _analyze_batch(
        self, batch: list, skills_text: str, skills: list, now: datetime
    ) -> tuple[int, int]:
        """Analyze a batch of discoveries via Bedrock."""
        # Build user prompt with discovery details
        items_text = []
        for d in batch:
            items_text.append(
                f"- source_id: {d.source_id}\n"
                f"  title: {d.title}\n"
                f"  url: {d.url}\n"
                f"  source: {d.source}\n"
                f"  raw_score: {d.raw_score}"
            )

        system_prompt = ANALYST_SYSTEM_PROMPT
        if skills_text:
            system_prompt += f"\n\nAvailable skills:\n{skills_text}"

        user_prompt = (
            "Analyze the following content items and return a JSON array:\n\n"
            + "\n".join(items_text)
        )

        # Call Bedrock — returns response text string
        raw_response = await self.call_bedrock(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        # Parse response — handle potential markdown code fences
        cleaned = self._extract_json(raw_response)
        try:
            scores = json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse analyst response: %s", e)
            return 0, len(batch)

        # Build a lookup by source_id
        score_map = {}
        if isinstance(scores, list):
            for item in scores:
                sid = item.get("source_id")
                if sid:
                    score_map[str(sid)] = item
        elif isinstance(scores, dict):
            score_map = scores

        analyzed = 0
        errors = 0

        async with async_session() as session:
            for d in batch:
                item_scores = score_map.get(str(d.source_id))
                if not item_scores:
                    logger.warning(
                        "No scores returned for source_id=%s, title=%s",
                        d.source_id,
                        d.title,
                    )
                    errors += 1
                    continue

                try:
                    d.relevance_score = float(item_scores.get("relevance_score", 0))
                    d.velocity_score = float(item_scores.get("velocity_score", 0))
                    d.risk_level = item_scores.get("risk_level", "medium")
                    d.platform_fit = item_scores.get("platform_fit", {})
                    d.suggested_formats = item_scores.get("suggested_formats", [])
                    d.status = "analyzed"
                    d.analyzed_at = now
                    session.add(d)
                    analyzed += 1
                except Exception as e:
                    logger.error(
                        "Error updating discovery %s: %s", d.source_id, e
                    )
                    errors += 1

            await session.commit()

        # Record skill outcomes
        skill_names = [s.name if hasattr(s, "name") else str(s) for s in skills]
        self.record_outcome(
            skill_names,
            outcome="success" if analyzed > 0 else "failure",
            score=analyzed / max(len(batch), 1),
        )

        return analyzed, errors

    @staticmethod
    def _extract_json(text: str) -> str:
        """Strip markdown code fences if present."""
        # Match ```json ... ``` or ``` ... ```
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if match:
            return match.group(1).strip()
        return text.strip()
