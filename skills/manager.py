from __future__ import annotations

import asyncio
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import frontmatter

from .base import Skill, SkillCategory, SkillStatus

logger = logging.getLogger(__name__)


_TASK_TYPE_TO_CATEGORY: dict[str, SkillCategory] = {
    "source_scoring": SkillCategory.SOURCES,
    "content_creation": SkillCategory.CREATION,
    "platform_optimization": SkillCategory.PLATFORM,
    "engagement": SkillCategory.ENGAGEMENT,
    "timing": SkillCategory.TIMING,
    "tool_usage": SkillCategory.TOOLS,
}


class SkillManager:
    """Loads, indexes, and maintains the skill library."""

    def __init__(self, library_path: Optional[str | Path] = None) -> None:
        if library_path is None:
            self._library_path = Path(__file__).parent / "library"
        else:
            self._library_path = Path(library_path)

        self._skills: dict[str, Skill] = {}

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load_all(self) -> list[Skill]:
        """Scan library_path recursively for .md files and parse them."""
        self._skills.clear()

        if not self._library_path.exists():
            return []

        for md_file in sorted(self._library_path.rglob("*.md")):
            skill = self._parse_skill_file(md_file)
            if skill is not None:
                self._skills[skill.name] = skill

        return list(self._skills.values())

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    def get_for_task(
        self, task_type: str, platform: Optional[str] = None
    ) -> list[Skill]:
        """Return skills that match the given task type and optional platform."""
        category = _TASK_TYPE_TO_CATEGORY.get(task_type)

        results: list[Skill] = []
        for skill in self._skills.values():
            if skill.status != SkillStatus.ACTIVE:
                continue

            matches = False
            if category and skill.category == category:
                matches = True
            if task_type in skill.tags:
                matches = True
            if not matches:
                continue

            if platform and skill.platform and skill.platform != platform:
                continue

            results.append(skill)

        results.sort(key=lambda s: s.confidence, reverse=True)
        return results

    def get_skill(self, name: str) -> Optional[Skill]:
        return self._skills.get(name)

    def all_skills(self) -> list[Skill]:
        return list(self._skills.values())

    # ------------------------------------------------------------------
    # Outcome tracking
    # ------------------------------------------------------------------

    # Confidence bounds to prevent extreme values
    CONFIDENCE_FLOOR = 0.2
    CONFIDENCE_CEILING = 0.95

    # Time decay settings
    DECAY_RATE_PER_DAY = 0.005  # 0.5% decay per day of inactivity
    MAX_DECAY = 0.3  # Maximum 30% total decay

    def record_outcome(
        self,
        skill_name: str,
        outcome: str,
        score: float,
        at: Optional[datetime] = None,
        agent: str = "unknown",
        task: Optional[str] = None,
        context: Optional[dict] = None,
    ) -> None:
        skill = self._skills.get(skill_name)
        if skill is None:
            return

        now = at or datetime.now(timezone.utc)
        old_confidence = skill.confidence

        # Step 1: Apply time decay before updating (if skill was previously used)
        if skill.last_used_at:
            days_since = (now - skill.last_used_at).days
            if days_since > 0:
                decay = min(days_since * self.DECAY_RATE_PER_DAY, self.MAX_DECAY)
                skill.confidence = max(self.CONFIDENCE_FLOOR, skill.confidence - decay)
                if decay > 0.01:
                    logger.debug(
                        "Skill '%s' decayed by %.3f (%.0f days inactive)",
                        skill_name, decay, days_since
                    )

        # Step 2: Adaptive weighting based on skill maturity
        # New skills adapt faster to feedback, mature skills are more stable
        if skill.total_uses < 5:
            weight_new = 0.5  # New skills adapt faster
        elif skill.total_uses < 15:
            weight_new = 0.4  # Building maturity
        elif skill.total_uses < 30:
            weight_new = 0.35  # Moderately stable
        else:
            weight_new = 0.3  # Mature skills more stable

        weight_old = 1 - weight_new

        # Step 3: Update confidence with weighted rolling average
        skill.confidence = weight_old * skill.confidence + weight_new * score

        # Step 4: Apply confidence bounds
        skill.confidence = max(self.CONFIDENCE_FLOOR, min(self.CONFIDENCE_CEILING, skill.confidence))

        skill.total_uses += 1
        skill.last_used_at = now
        skill.updated_at = now

        if outcome == "success":
            skill.success_count += 1
            skill.failure_streak = 0
        else:
            skill.failure_streak += 1

        # Log confidence change for visibility
        confidence_delta = skill.confidence - old_confidence
        if abs(confidence_delta) > 0.01:
            logger.info(
                "Skill '%s' confidence: %.3f → %.3f (%+.3f) from %s [uses=%d, weight=%.0f%%]",
                skill_name, old_confidence, skill.confidence, confidence_delta,
                outcome, skill.total_uses, weight_new * 100
            )

        # Record to SkillMetric table (async in background)
        self._record_metric_to_db(
            skill_name=skill_name,
            agent=agent,
            task=task,
            outcome=outcome,
            score=score,
            context=context,
            recorded_at=now,
        )

        # Persist skill state to SkillRecord table
        self._persist_skill_to_db(skill)

    def apply_decay_to_all(self, at: Optional[datetime] = None) -> dict[str, float]:
        """Apply time decay to all skills that haven't been used recently.

        This should be called periodically (e.g., weekly) to ensure unused
        skills don't maintain artificially high confidence.

        Returns a dict of skill_name -> decay_amount for skills that decayed.
        """
        now = at or datetime.now(timezone.utc)
        decayed = {}

        for skill_name, skill in self._skills.items():
            if skill.last_used_at is None:
                continue

            days_since = (now - skill.last_used_at).days
            if days_since < 7:  # Only decay if inactive for 7+ days
                continue

            old_confidence = skill.confidence
            decay = min(days_since * self.DECAY_RATE_PER_DAY, self.MAX_DECAY)
            skill.confidence = max(self.CONFIDENCE_FLOOR, skill.confidence - decay)

            if old_confidence != skill.confidence:
                decayed[skill_name] = old_confidence - skill.confidence
                skill.updated_at = now
                self._persist_skill_to_db(skill)
                logger.info(
                    "Skill '%s' decayed: %.3f → %.3f (%.0f days inactive)",
                    skill_name, old_confidence, skill.confidence, days_since
                )

        return decayed

    def _record_metric_to_db(
        self,
        skill_name: str,
        agent: str,
        task: Optional[str],
        outcome: str,
        score: float,
        context: Optional[dict],
        recorded_at: datetime,
    ) -> None:
        """Insert a SkillMetric row to the database (fire-and-forget async).

        This is designed to be non-blocking:
        - In async context: schedules as a background task
        - In sync context: skips DB write (logged at debug level)

        The TrackerAgent and FeedbackLoop handle the authoritative DB writes
        when running in proper async context.
        """
        try:
            loop = asyncio.get_running_loop()
            # We're in async context - schedule as background task
            loop.create_task(self._insert_skill_metric(
                skill_name, agent, task, outcome, score, context, recorded_at
            ))
        except RuntimeError:
            # No running loop - we're in sync context
            # Skip DB write to avoid blocking; the in-memory update is sufficient
            # TrackerAgent will write authoritative metrics when it runs
            logger.debug(
                "Skipping SkillMetric DB write (no event loop) for '%s'",
                skill_name
            )

    async def _insert_skill_metric(
        self,
        skill_name: str,
        agent: str,
        task: Optional[str],
        outcome: str,
        score: float,
        context: Optional[dict],
        recorded_at: datetime,
    ) -> None:
        """Actually insert the SkillMetric row."""
        try:
            from db import async_session
            from models import SkillMetric

            async with async_session() as session:
                metric = SkillMetric(
                    skill_name=skill_name,
                    agent=agent,
                    task=task,
                    outcome=outcome,
                    score=score,
                    context=context,
                    recorded_at=recorded_at,
                )
                session.add(metric)
                await session.commit()
                logger.debug("Recorded SkillMetric for '%s': score=%.3f", skill_name, score)
        except Exception as e:
            logger.warning("Failed to insert SkillMetric: %s", e)

    def _persist_skill_to_db(self, skill: Skill) -> None:
        """Upsert skill state to SkillRecord table (fire-and-forget async).

        Non-blocking by design - skips in sync context to avoid hanging.
        """
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._upsert_skill_record(skill))
        except RuntimeError:
            # No running loop - skip DB write
            logger.debug(
                "Skipping SkillRecord DB write (no event loop) for '%s'",
                skill.name
            )

    async def _upsert_skill_record(self, skill: Skill) -> None:
        """Upsert the skill state to SkillRecord table."""
        try:
            from sqlalchemy import select

            from db import async_session
            from models import SkillRecord

            async with async_session() as session:
                # Check if record exists
                result = await session.execute(
                    select(SkillRecord).where(SkillRecord.name == skill.name)
                )
                record = result.scalar_one_or_none()

                if record is None:
                    # Insert new record
                    record = SkillRecord(
                        name=skill.name,
                        category=skill.category.value,
                        platform=skill.platform,
                        confidence=skill.confidence,
                        status=skill.status.value,
                        version=skill.version,
                        total_uses=skill.total_uses,
                        success_count=skill.success_count,
                        failure_streak=skill.failure_streak,
                        tags=skill.tags,
                        file_path=skill.file_path,
                        last_used_at=skill.last_used_at,
                        last_validated_at=skill.last_validated_at,
                        created_at=skill.created_at,
                        updated_at=skill.updated_at,
                    )
                    session.add(record)
                else:
                    # Update existing record
                    record.confidence = skill.confidence
                    record.status = skill.status.value
                    record.version = skill.version
                    record.total_uses = skill.total_uses
                    record.success_count = skill.success_count
                    record.failure_streak = skill.failure_streak
                    record.last_used_at = skill.last_used_at
                    record.updated_at = skill.updated_at

                await session.commit()
                logger.debug("Persisted SkillRecord for '%s': confidence=%.3f", skill.name, skill.confidence)
        except Exception as e:
            logger.warning("Failed to upsert SkillRecord: %s", e)

    def update_confidence(self, skill_name: str, new_score: float) -> None:
        skill = self._skills.get(skill_name)
        if skill is None:
            return
        skill.confidence = 0.7 * skill.confidence + 0.3 * new_score
        skill.updated_at = datetime.now()

    def mark_stale(self, skill_name: str) -> None:
        skill = self._skills.get(skill_name)
        if skill is None:
            return
        skill.status = SkillStatus.STALE
        skill.failure_streak += 1
        skill.updated_at = datetime.now()

    # ------------------------------------------------------------------
    # Versioning
    # ------------------------------------------------------------------

    def create_version(
        self,
        skill_name: str,
        new_content: str,
        change_reason: str,
        at: Optional[datetime] = None,
    ) -> None:
        skill = self._skills.get(skill_name)
        if skill is None:
            return

        now = at or datetime.now()
        skill_file = Path(skill.file_path)

        # Archive old version
        versions_dir = self._library_path.parent / "versions"
        versions_dir.mkdir(parents=True, exist_ok=True)

        timestamp = now.strftime("%Y%m%d_%H%M%S")
        archive_name = f"{skill.name}_v{skill.version}_{timestamp}.md"
        if skill_file.exists():
            shutil.copy2(skill_file, versions_dir / archive_name)

        # Update the skill
        skill.version += 1
        skill.content = new_content
        skill.updated_at = now

        # Rewrite the file
        self._write_skill_file(skill, change_reason)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _parse_skill_file(self, path: Path) -> Optional[Skill]:
        try:
            post = frontmatter.load(str(path))
        except Exception:
            return None

        meta = post.metadata
        name = meta.get("name", path.stem)
        category_str = meta.get("category", "tools")
        try:
            category = SkillCategory(category_str)
        except ValueError:
            category = SkillCategory.TOOLS

        status_str = meta.get("status", "active")
        try:
            status = SkillStatus(status_str)
        except ValueError:
            status = SkillStatus.ACTIVE

        def _parse_dt(val: object) -> Optional[datetime]:
            if val is None:
                return None
            if isinstance(val, datetime):
                return val
            try:
                return datetime.fromisoformat(str(val))
            except (ValueError, TypeError):
                return None

        now = datetime.now()
        return Skill(
            name=name,
            category=category,
            platform=meta.get("platform"),
            confidence=float(meta.get("confidence", 0.5)),
            status=status,
            version=int(meta.get("version", 1)),
            content=post.content,
            tags=meta.get("tags", []),
            file_path=str(path),
            total_uses=int(meta.get("total_uses", 0)),
            success_count=int(meta.get("success_count", 0)),
            failure_streak=int(meta.get("failure_streak", 0)),
            last_used_at=_parse_dt(meta.get("last_used_at")),
            last_validated_at=_parse_dt(meta.get("last_validated_at")),
            created_at=_parse_dt(meta.get("created_at")) or now,
            updated_at=_parse_dt(meta.get("updated_at")) or now,
        )

    def _write_skill_file(self, skill: Skill, change_reason: str = "") -> None:
        path = Path(skill.file_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        metadata: dict = {
            "name": skill.name,
            "category": skill.category.value,
            "status": skill.status.value,
            "version": skill.version,
            "confidence": round(skill.confidence, 4),
            "tags": skill.tags,
            "total_uses": skill.total_uses,
            "success_count": skill.success_count,
            "failure_streak": skill.failure_streak,
            "created_at": skill.created_at.isoformat(),
            "updated_at": skill.updated_at.isoformat(),
        }
        if skill.platform:
            metadata["platform"] = skill.platform
        if skill.last_used_at:
            metadata["last_used_at"] = skill.last_used_at.isoformat()
        if skill.last_validated_at:
            metadata["last_validated_at"] = skill.last_validated_at.isoformat()
        if change_reason:
            metadata["change_reason"] = change_reason

        post = frontmatter.Post(skill.content, **metadata)
        path.write_text(frontmatter.dumps(post) + "\n", encoding="utf-8")
