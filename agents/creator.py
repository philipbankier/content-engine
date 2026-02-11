"""CreatorAgent: generates platform-specific content from top analyzed discoveries."""

import json
import logging
import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from agents.base import BaseAgent
from db import async_session
from generators.video_types import VideoType, should_generate_video, CONTENT_VIDEO_DEFAULTS
from models import ContentCreation, ContentDiscovery

logger = logging.getLogger(__name__)

PLATFORM_FIT_THRESHOLD = 0.6

CREATOR_SYSTEM_PROMPT_TEMPLATE = """You are a content creator for Autopilot by Kairox AI.

Brand Voice: Calm, confident, technical, grounded. Builder-to-builder, operator-to-operator.
Core message: "This is how work actually gets done."

Style rules:
- Short paragraphs, declarative statements, minimal adjectives
- No buzzwords ("revolutionary", "game-changing", "leverage AI")
- No exclamation points
- No sales CTAs
- No overly anthropomorphic AI language

Create {format} content for {platform} based on the following source material."""


class CreatorAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="creator")

    async def run(self, limit: int = 10, at: datetime | None = None) -> dict:
        """Create content for top analyzed discoveries across qualifying platforms."""
        now = at or datetime.now(timezone.utc)
        created_count = 0
        error_count = 0
        discovery_count = 0

        async with async_session() as session:
            result = await session.execute(
                select(ContentDiscovery)
                .where(ContentDiscovery.status == "analyzed")
                .order_by(
                    (ContentDiscovery.relevance_score + ContentDiscovery.velocity_score).desc()
                )
                .limit(limit)
            )
            discoveries = list(result.scalars().all())

        if not discoveries:
            logger.info("Creator: no analyzed discoveries to process")
            return {"discoveries_processed": 0, "content_created": 0, "errors": 0}

        for discovery in discoveries:
            discovery_count += 1
            platforms = self._select_platforms(discovery)
            if not platforms:
                logger.info(
                    "No platforms above threshold for discovery %s", discovery.source_id
                )
                continue

            formats = discovery.suggested_formats or ["post"]

            for platform in platforms:
                fmt = self._best_format_for_platform(platform, formats)
                variant_group = str(uuid.uuid4())[:8]
                variant_labels = ["A", "B"]  # Generate 2 variants per platform

                for label in variant_labels:
                    try:
                        creation = await self._create_content(
                            discovery, platform, fmt, now,
                            variant_group=variant_group,
                            variant_label=label,
                        )
                        if creation:
                            created_count += 1
                    except Exception as e:
                        logger.error(
                            "Error creating %s/%s variant %s for discovery %s: %s",
                            platform,
                            fmt,
                            label,
                            discovery.source_id,
                            e,
                        )
                        error_count += 1

            # Update discovery status
            async with async_session() as session:
                discovery.status = "queued"
                session.add(discovery)
                await session.commit()

        logger.info(
            "Creator complete: %d content pieces from %d discoveries, %d errors",
            created_count,
            discovery_count,
            error_count,
        )
        return {
            "discoveries_processed": discovery_count,
            "content_created": created_count,
            "errors": error_count,
        }

    def _select_platforms(self, discovery: ContentDiscovery) -> list[str]:
        """Return platforms whose fit score exceeds the threshold."""
        platform_fit = discovery.platform_fit or {}
        if isinstance(platform_fit, str):
            try:
                platform_fit = json.loads(platform_fit)
            except (json.JSONDecodeError, TypeError):
                return []

        return [
            platform
            for platform, score in platform_fit.items()
            if float(score) >= PLATFORM_FIT_THRESHOLD
        ]

    @staticmethod
    def _best_format_for_platform(platform: str, formats: list[str]) -> str:
        """Pick the best format for a given platform from suggested formats."""
        platform_format_prefs = {
            "linkedin": ["post", "carousel", "article"],
            "twitter": ["thread", "post"],
            "youtube": ["short", "article"],
            "tiktok": ["short", "post"],
        }
        prefs = platform_format_prefs.get(platform, ["post"])
        for pref in prefs:
            if pref in formats:
                return pref
        return formats[0] if formats else "post"

    async def _create_content(
        self,
        discovery: ContentDiscovery,
        platform: str,
        fmt: str,
        now: datetime,
        variant_group: str | None = None,
        variant_label: str | None = None,
    ) -> ContentCreation | None:
        """Generate content for a single platform/format via Bedrock."""
        # Load skills for this creation task
        task_key = f"content_creation_{platform}"
        skills = self.select_skills("content_creation", platform=platform)
        skills_text = self.format_skills_for_prompt(skills)

        system_prompt = CREATOR_SYSTEM_PROMPT_TEMPLATE.format(
            format=fmt, platform=platform
        )

        # Add priority patterns from high-confidence skills
        priority_guidance = self._build_priority_guidance(skills)
        if priority_guidance:
            system_prompt += f"\n\n{priority_guidance}"

        # Add failure patterns to avoid (from low-engagement content analysis)
        avoid_guidance = self._build_avoid_guidance(platform, fmt)
        if avoid_guidance:
            system_prompt += f"\n\n{avoid_guidance}"

        if skills_text:
            system_prompt += f"\n\nAvailable skills:\n{skills_text}"

        user_prompt = (
            f"Source title: {discovery.title}\n"
            f"Source URL: {discovery.url}\n"
            f"Source: {discovery.source}\n"
            f"Relevance score: {discovery.relevance_score}\n"
            f"Velocity score: {discovery.velocity_score}\n"
        )
        if discovery.raw_data:
            raw = discovery.raw_data
            if isinstance(raw, str):
                try:
                    raw = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    pass
            if isinstance(raw, dict):
                summary = raw.get("summary") or raw.get("description") or raw.get("text", "")
                if summary:
                    user_prompt += f"Summary: {summary}\n"

        user_prompt += f"\nCreate a {fmt} for {platform}. "
        if variant_label:
            style_hints = {
                "A": "Use a bold, provocative hook. Lead with a surprising insight or contrarian take.",
                "B": "Use a question-based hook. Lead with curiosity and build to the insight gradually.",
                "C": "Use a story-based hook. Open with a brief anecdote or concrete example.",
            }
            hint = style_hints.get(variant_label, "")
            user_prompt += f"This is variant {variant_label}. {hint} "
        # Determine if this content should have video
        wants_video = should_generate_video(fmt, platform)

        user_prompt += "Return JSON with keys: title, body, image_prompt"
        if wants_video:
            # Load video format selection skill for the LLM to reason about video type
            video_skills = self.select_skills("video_format_selection")
            video_skills_text = self.format_skills_for_prompt(video_skills)
            if video_skills_text:
                system_prompt += f"\n\n{video_skills_text}"

            user_prompt += (
                ", video_type (one of: avatar_talking_head, avatar_agent, "
                "motion_graphics, hybrid_avatar_broll, kinetic_text, "
                "cinematic_broll, image_to_video, multi_shot_narrative — "
                "choose the best format for this content and platform), "
                "video_type_rationale (1-sentence explanation of your choice)"
            )
            user_prompt += (
                ". Then include the fields needed for your chosen video_type: "
                "if avatar_talking_head → video_script (30-60s spoken script, 75-150 words, conversational); "
                "if avatar_agent → video_prompt (rich description of desired video); "
                "if motion_graphics → video_prompt (cinematic visual description); "
                "if hybrid_avatar_broll → video_composition (list of segment objects with "
                "type 'avatar' or 'broll', plus 'script' or 'prompt' and 'duration' in seconds); "
                "if kinetic_text → video_prompt (the text content + style description); "
                "if cinematic_broll → video_prompt (cinematic scene with specific camera movements and physics); "
                "if image_to_video → video_prompt (how to animate the generated image — describe motion, not scene); "
                "if multi_shot_narrative → video_composition (list of 2-6 shot objects with 'prompt' and 'duration' in seconds)"
            )

        raw_response = await self.call_bedrock(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        # Parse response
        content_data = self._parse_content_response(raw_response)
        if not content_data:
            logger.warning(
                "Could not parse creator response for %s/%s", platform, fmt
            )
            return None

        skills_used = [s.name if hasattr(s, "name") else str(s) for s in skills]

        # --- Stage 1: generate images only (cheap). Video deferred to after approval. ---
        media_urls = await self._generate_images(content_data, platform, fmt)

        # Extract video fields — the LLM now decides video_type for all video-capable content
        video_script = None
        video_type = None
        video_type_rationale = None
        video_prompt = None
        video_composition = None

        if wants_video:
            video_type_raw = content_data.get("video_type")
            if video_type_raw:
                video_type = VideoType.from_string(video_type_raw).value
            else:
                # Fallback: infer from content category
                video_type = self._infer_video_type(discovery, platform)
            video_type_rationale = content_data.get("video_type_rationale")
            video_script = content_data.get("video_script")
            video_prompt = content_data.get("video_prompt")
            video_composition = content_data.get("video_composition")

        async with async_session() as session:
            creation = ContentCreation(
                discovery_id=discovery.id,
                platform=platform,
                format=fmt,
                title=content_data.get("title", discovery.title),
                body=content_data.get("body", ""),
                media_urls=media_urls or None,
                video_script=video_script,
                video_type=video_type,
                video_type_rationale=video_type_rationale,
                video_prompt=video_prompt,
                video_composition=video_composition,
                skills_used=skills_used,
                variant_group=variant_group,
                variant_label=variant_label,
                approval_status="pending_review" if variant_group else "pending",
                created_at=now,
            )
            session.add(creation)
            await session.commit()

        # Record initial skill usage (actual score will be updated by TrackerAgent
        # when 24h engagement metrics come in)
        self.record_outcome(
            skills_used,
            outcome="success",
            score=0.5,  # Neutral initial score - real score comes from engagement
            task=f"create_{platform}_{fmt}",
            context={
                "discovery_id": discovery.id,
                "platform": platform,
                "format": fmt,
                "variant_label": variant_label,
            },
        )

        return creation

    async def _generate_images(
        self, content_data: dict, platform: str, fmt: str
    ) -> list[dict]:
        """Generate image assets only. Video generation is deferred to after approval."""
        from config import settings

        media_urls: list[dict] = []

        image_prompt = content_data.get("image_prompt")
        if image_prompt and settings.fal_key:
            try:
                from generators.image import ImageGenerator

                img_result = await ImageGenerator().generate(prompt=image_prompt)
                if img_result.get("url"):
                    media_urls.append({"type": "image", "url": img_result["url"]})
                    logger.info("Image generated for %s/%s", platform, fmt)
                elif img_result.get("error"):
                    logger.warning("Image generation failed: %s", img_result["error"])
            except Exception as e:
                logger.warning("Image generation error: %s", e)

        return media_urls

    @staticmethod
    def _parse_content_response(text: str) -> dict | None:
        """Extract JSON content from Bedrock response, handling code fences."""
        # Strip markdown code fences if present
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        cleaned = match.group(1).strip() if match else text.strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            logger.error("Failed to parse creator response as JSON")
            return None

    def _build_priority_guidance(self, skills: list) -> str:
        """Build priority guidance from high-confidence skills.

        Skills with confidence >= 0.7 are considered "proven" and their
        patterns are emphasized. Skills with confidence <= 0.3 are flagged
        as patterns to avoid.

        This creates a feedback loop: successful content patterns get
        reinforced in future content generation.
        """
        HIGH_CONFIDENCE_THRESHOLD = 0.7
        LOW_CONFIDENCE_THRESHOLD = 0.3

        high_confidence = []
        low_confidence = []

        for skill in skills:
            confidence = getattr(skill, "confidence", 0.5)
            name = getattr(skill, "name", str(skill))
            content = getattr(skill, "content", "")

            if confidence >= HIGH_CONFIDENCE_THRESHOLD:
                high_confidence.append({
                    "name": name,
                    "confidence": confidence,
                    "content": content,
                })
            elif confidence <= LOW_CONFIDENCE_THRESHOLD:
                low_confidence.append({
                    "name": name,
                    "confidence": confidence,
                })

        if not high_confidence and not low_confidence:
            return ""

        lines = []

        if high_confidence:
            lines.append("## PRIORITY: Proven Patterns (High Confidence)")
            lines.append("These patterns have been validated through engagement data. Follow them closely:")
            lines.append("")
            for skill in sorted(high_confidence, key=lambda x: x["confidence"], reverse=True):
                lines.append(f"### {skill['name']} (confidence: {skill['confidence']:.0%})")
                # Extract key points from skill content (first 500 chars)
                if skill["content"]:
                    # Get the "Core Patterns" or similar section if present
                    content = skill["content"]
                    if "## Core Patterns" in content:
                        start = content.find("## Core Patterns")
                        end = content.find("##", start + 1)
                        if end == -1:
                            end = len(content)
                        excerpt = content[start:end].strip()[:500]
                    else:
                        excerpt = content[:500]
                    lines.append(excerpt)
                lines.append("")

        if low_confidence:
            lines.append("## CAUTION: Underperforming Patterns")
            lines.append("These patterns have shown poor engagement. Use with caution or avoid:")
            lines.append("")
            for skill in low_confidence:
                lines.append(f"- {skill['name']} (confidence: {skill['confidence']:.0%})")
            lines.append("")

        if high_confidence:
            logger.info(
                "Creator using %d high-confidence skills: %s",
                len(high_confidence),
                [s["name"] for s in high_confidence]
            )

        return "\n".join(lines)

    def _build_avoid_guidance(self, platform: str, fmt: str) -> str:
        """Build avoid guidance from failure pattern analysis.

        This injects patterns learned from low-engagement content into the
        prompt, helping the system avoid repeating mistakes.
        """
        try:
            from learning.failure_patterns import get_failure_tracker

            tracker = get_failure_tracker()
            avoid_text = tracker.get_avoid_patterns_for_prompt(platform, fmt)

            if avoid_text:
                logger.info(
                    "Creator injecting avoid patterns for %s/%s",
                    platform, fmt
                )

            return avoid_text
        except Exception as e:
            logger.warning("Failed to build avoid guidance: %s", e)
            return ""

    @staticmethod
    def _infer_video_type(discovery: ContentDiscovery, platform: str) -> str:
        """Fallback: infer video type from content signals when LLM doesn't decide."""
        from generators.video_types import CONTENT_VIDEO_DEFAULTS, PLATFORM_VIDEO_PREFERENCES

        # Try matching discovery suggested_formats to content keywords
        formats = discovery.suggested_formats or []
        if isinstance(formats, str):
            try:
                formats = json.loads(formats)
            except (json.JSONDecodeError, TypeError):
                formats = []

        for fmt_hint in formats:
            if fmt_hint in CONTENT_VIDEO_DEFAULTS:
                return CONTENT_VIDEO_DEFAULTS[fmt_hint].value

        # Fall back to platform default
        prefs = PLATFORM_VIDEO_PREFERENCES.get(platform, [])
        if prefs:
            return prefs[0].value

        return VideoType.AVATAR_AGENT.value
