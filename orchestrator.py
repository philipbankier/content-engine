"""Main orchestrator — schedules all agents on cadence."""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from enum import Enum

from agents.scout import ScoutAgent
from agents.analyst import AnalystAgent
from agents.creator import CreatorAgent
from agents.engagement import EngagementAgent
from agents.tracker import TrackerAgent
from agents.reviewer import ReviewerAgent
from approval.queue import ApprovalQueue
from learning.feedback_loop import FeedbackLoop
from learning.pattern_analyzer import PatternAnalyzer
from learning.experiment_runner import ExperimentRunner
from skills.manager import SkillManager
from config import settings
from db import async_session
from sqlalchemy import select, func
from models import ContentAgentRun

logger = logging.getLogger(__name__)


class OperationMode(Enum):
    """Degradation modes for cost management.

    FULL: All agents running, video generation enabled
    REDUCED: Skip video generation, limit content creation to 3 per cycle
    MINIMAL: Scout + tracker only, no content creation
    PAUSED: Nothing runs, wait for cost reset
    """
    FULL = "full"
    REDUCED = "reduced"
    MINIMAL = "minimal"
    PAUSED = "paused"


# Cost thresholds as percentages of daily limit
COST_THRESHOLDS = {
    OperationMode.FULL: 0.0,       # 0-70% of limit
    OperationMode.REDUCED: 0.70,   # 70-85% of limit
    OperationMode.MINIMAL: 0.85,   # 85-95% of limit
    OperationMode.PAUSED: 0.95,    # 95%+ of limit
}


class Orchestrator:
    """Autonomous content pipeline orchestrator with graceful degradation."""

    def __init__(self):
        self.scout = ScoutAgent()
        self.analyst = AnalystAgent()
        self.creator = CreatorAgent()
        self.engagement = EngagementAgent()
        self.tracker = TrackerAgent()
        self.reviewer = ReviewerAgent()
        self.approval = ApprovalQueue()
        self.skill_manager = SkillManager()
        self.pattern_analyzer = PatternAnalyzer()
        self.experiment_runner = ExperimentRunner()
        self.feedback_loop = FeedbackLoop(
            self.skill_manager, self.pattern_analyzer, self.experiment_runner
        )
        self._running = False
        self._tasks: list[asyncio.Task] = []
        self.last_run: dict[str, str] = {}
        self._operation_mode = OperationMode.FULL
        self._mode_changed_at: datetime | None = None

    async def start(self, demo_mode: bool = False):
        """Start all scheduled loops. If demo_mode=True, skip automatic scheduling."""
        self._running = True
        self.skill_manager.load_all()
        logger.info("Orchestrator starting — %d skills loaded", len(self.skill_manager.all_skills()))

        if demo_mode:
            logger.info("DEMO MODE: Agent scheduling DISABLED")
            logger.info("Use POST /discover to manually trigger scout")
            logger.info("All other agents can be triggered via API endpoints")
            return  # Don't start background loops

        # Production mode: start all agent loops
        logger.info("PRODUCTION MODE: Starting agent loops...")
        self._tasks = [
            asyncio.create_task(self._loop("scout", self._scout_cycle, interval=settings.scout_interval)),
            asyncio.create_task(self._loop("tracker", self._tracker_cycle, interval=settings.tracker_interval)),
            asyncio.create_task(self._loop("engagement", self._engagement_cycle, interval=settings.engagement_interval)),
            asyncio.create_task(self._loop("feedback", self._feedback_cycle, interval=settings.feedback_interval)),
            asyncio.create_task(self._loop("reviewer", self._review_cycle, interval=settings.reviewer_interval)),
        ]
        logger.info("Orchestrator started with %d scheduled loops", len(self._tasks))

    async def stop(self):
        """Stop all scheduled loops."""
        self._running = False
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        logger.info("Orchestrator stopped")

    async def _loop(self, name: str, func, interval: int):
        """Run a function on a fixed interval. Checks cost limits and applies degradation."""
        while self._running:
            try:
                # Update operation mode based on cost
                if settings.daily_cost_limit > 0:
                    await self._update_operation_mode()

                    # Check if this task should run in current mode
                    if not self._should_run_task(name):
                        logger.debug(
                            "Skipping %s in %s mode", name, self._operation_mode.value
                        )
                        await asyncio.sleep(interval)
                        continue

                logger.info("Running scheduled task: %s (mode: %s)", name, self._operation_mode.value)
                await func()
                self.last_run[name] = datetime.now(timezone.utc).isoformat()
            except Exception as e:
                logger.error("Scheduled task %s failed: %s", name, e)
            await asyncio.sleep(interval)

    async def _update_operation_mode(self) -> None:
        """Update operation mode based on current daily cost."""
        cost_today = await self._get_cost_today()
        cost_ratio = cost_today / settings.daily_cost_limit if settings.daily_cost_limit > 0 else 0

        old_mode = self._operation_mode

        # Determine new mode based on thresholds
        if cost_ratio >= COST_THRESHOLDS[OperationMode.PAUSED]:
            new_mode = OperationMode.PAUSED
        elif cost_ratio >= COST_THRESHOLDS[OperationMode.MINIMAL]:
            new_mode = OperationMode.MINIMAL
        elif cost_ratio >= COST_THRESHOLDS[OperationMode.REDUCED]:
            new_mode = OperationMode.REDUCED
        else:
            new_mode = OperationMode.FULL

        if new_mode != old_mode:
            self._operation_mode = new_mode
            self._mode_changed_at = datetime.now(timezone.utc)
            logger.warning(
                "OPERATION MODE CHANGE: %s → %s (cost: $%.2f / $%.2f = %.1f%%)",
                old_mode.value, new_mode.value,
                cost_today, settings.daily_cost_limit, cost_ratio * 100
            )

    def _should_run_task(self, task_name: str) -> bool:
        """Determine if a task should run in the current operation mode."""
        mode = self._operation_mode

        if mode == OperationMode.PAUSED:
            # In PAUSED mode, nothing runs
            return False

        if mode == OperationMode.MINIMAL:
            # In MINIMAL mode, only scout and tracker run
            return task_name in ("scout", "tracker", "feedback")

        if mode == OperationMode.REDUCED:
            # In REDUCED mode, skip engagement (less critical)
            return task_name != "engagement"

        # FULL mode - everything runs
        return True

    async def _get_cost_today(self) -> float:
        """Get total cost for today (UTC)."""
        try:
            today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            async with async_session() as db:
                result = await db.execute(
                    select(func.coalesce(func.sum(ContentAgentRun.estimated_cost_usd), 0.0))
                    .where(ContentAgentRun.started_at >= today_start)
                )
                return result.scalar() or 0.0
        except Exception as e:
            logger.error("Failed to get today's cost: %s", e)
            return 0.0

    async def _scout_cycle(self):
        """Scout → Analyst → Creator → Approval pipeline.

        Respects operation mode:
        - FULL: Full pipeline with all features
        - REDUCED: Limit content creation to 3 items, skip video
        - MINIMAL: Scout only (discovery + analysis, no creation)
        """
        mode = self._operation_mode

        # 1. Discover (always runs)
        scout_result = await self.scout.run()
        logger.info("Scout: %s", scout_result)

        # 2. Analyze (always runs)
        analyst_result = await self.analyst.run()
        logger.info("Analyst: %s", analyst_result)

        # 3. Create content (skip in MINIMAL mode)
        if mode == OperationMode.MINIMAL:
            logger.info("Creator: SKIPPED (minimal mode)")
            return

        # Limit creation in REDUCED mode
        creation_limit = 3 if mode == OperationMode.REDUCED else 10
        creator_result = await self.creator.run(limit=creation_limit)
        logger.info("Creator: %s (limit=%d)", creator_result, creation_limit)

        # 4. Run approval on new creations
        # In REDUCED mode, skip video generation by setting a flag
        skip_video = mode == OperationMode.REDUCED
        approved = await self.approval.process_pending(skip_video=skip_video)
        logger.info("Approval: processed %d items (skip_video=%s)", len(approved), skip_video)

    async def _tracker_cycle(self):
        """Collect metrics from published content and trigger learning if enough data."""
        result = await self.tracker.run()
        logger.info("Tracker: %s", result)

        # Auto-trigger feedback loop if we collected meaningful data
        # This ensures the system learns from every batch of new metrics
        skills_updated = result.get("skills_updated", 0)
        if skills_updated >= 3:
            logger.info("Tracker collected %d skill updates — triggering feedback loop", skills_updated)
            await self._feedback_cycle(triggered_by="tracker_metrics")

    async def _engagement_cycle(self):
        """Run engagement agent."""
        result = await self.engagement.run()
        logger.info("Engagement: %s", result)

    async def _feedback_cycle(self, triggered_by: str = "scheduled"):
        """Run learning feedback loop."""
        logger.info("Starting feedback cycle (triggered by: %s)", triggered_by)
        result = await self.feedback_loop.run_cycle()
        logger.info("Feedback loop: %s", result)
        return result

    async def _review_cycle(self):
        """Run weekly review."""
        result = await self.reviewer.run()
        logger.info("Weekly review: %s", result)

    async def trigger_scout(self) -> dict:
        """Manually trigger a scout cycle. Used by API."""
        await self._scout_cycle()
        return {"status": "completed", "timestamp": datetime.now(timezone.utc).isoformat()}

    def get_status(self) -> dict:
        """Return current orchestrator status."""
        return {
            "running": self._running,
            "demo_mode": settings.demo_mode,
            "active_loops": len(self._tasks),
            "last_runs": self.last_run,
            "skills_loaded": len(self.skill_manager.all_skills()),
            "daily_cost_limit": settings.daily_cost_limit,
            "operation_mode": self._operation_mode.value,
            "mode_changed_at": self._mode_changed_at.isoformat() if self._mode_changed_at else None,
            "mode_description": self._get_mode_description(),
        }

    def _get_mode_description(self) -> str:
        """Human-readable description of current operation mode."""
        descriptions = {
            OperationMode.FULL: "All agents running, full features enabled",
            OperationMode.REDUCED: "Limited creation (3/cycle), video generation skipped",
            OperationMode.MINIMAL: "Scout + tracker only, no content creation",
            OperationMode.PAUSED: "All operations paused, waiting for cost reset",
        }
        return descriptions.get(self._operation_mode, "Unknown mode")
