"""ScoutAgent: discovers content from all sources, normalizes, deduplicates, stores."""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta

from sqlalchemy import select

from agents.base import BaseAgent
from db import async_session
from models import ContentDiscovery
from sources import ALL_SOURCES
from sources.base import content_hash

logger = logging.getLogger(__name__)

# Health tracking thresholds
FAILURE_THRESHOLD_REDUCED = 3  # After 3 failures, reduce frequency
FAILURE_THRESHOLD_SKIP = 5     # After 5 failures, skip temporarily
MAX_BACKOFF_HOURS = 24         # Maximum backoff time


@dataclass
class SourceHealth:
    """Tracks health status of a content source."""
    consecutive_failures: int = 0
    total_failures: int = 0
    total_successes: int = 0
    last_failure_at: datetime | None = None
    last_success_at: datetime | None = None
    backoff_until: datetime | None = None

    @property
    def is_healthy(self) -> bool:
        return self.consecutive_failures < FAILURE_THRESHOLD_REDUCED

    @property
    def should_skip(self) -> bool:
        if self.backoff_until and datetime.now(timezone.utc) < self.backoff_until:
            return True
        return self.consecutive_failures >= FAILURE_THRESHOLD_SKIP

    @property
    def success_rate(self) -> float:
        total = self.total_successes + self.total_failures
        return self.total_successes / total if total > 0 else 1.0

    def record_success(self) -> None:
        self.consecutive_failures = 0
        self.total_successes += 1
        self.last_success_at = datetime.now(timezone.utc)
        self.backoff_until = None

    def record_failure(self) -> None:
        self.consecutive_failures += 1
        self.total_failures += 1
        self.last_failure_at = datetime.now(timezone.utc)

        # Apply exponential backoff after threshold
        if self.consecutive_failures >= FAILURE_THRESHOLD_SKIP:
            backoff_hours = min(2 ** (self.consecutive_failures - FAILURE_THRESHOLD_SKIP), MAX_BACKOFF_HOURS)
            self.backoff_until = datetime.now(timezone.utc) + timedelta(hours=backoff_hours)
            logger.warning(
                "Source entering backoff: %d hours (consecutive failures: %d)",
                backoff_hours, self.consecutive_failures
            )


# Module-level health tracker (persists across scout runs)
_source_health: dict[str, SourceHealth] = {}


def get_source_health(source_name: str) -> SourceHealth:
    """Get or create health tracker for a source."""
    if source_name not in _source_health:
        _source_health[source_name] = SourceHealth()
    return _source_health[source_name]


class ScoutAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="scout")

    async def run(self, at: datetime | None = None) -> dict:
        """Run all sources concurrently, deduplicate, store new discoveries.

        Implements source health monitoring:
        - Tracks consecutive failures per source
        - After 3 failures: logs warning, continues with reduced confidence
        - After 5 failures: skips source with exponential backoff
        - Backoff doubles each time: 1h, 2h, 4h, ... up to 24h max
        """
        now = at or datetime.now(timezone.utc)

        # Filter sources based on health
        active_sources = []
        skipped_sources = []
        for src in ALL_SOURCES:
            health = get_source_health(src.name)
            if health.should_skip:
                skipped_sources.append(src.name)
                logger.info(
                    "Skipping %s (backoff until %s, failures: %d)",
                    src.name,
                    health.backoff_until.isoformat() if health.backoff_until else "N/A",
                    health.consecutive_failures
                )
            else:
                active_sources.append(src)

        if skipped_sources:
            logger.warning("Sources in backoff: %s", skipped_sources)

        # Fetch from active sources
        results = await asyncio.gather(
            *[self._fetch_source(src) for src in active_sources],
            return_exceptions=True,
        )

        all_items = []
        source_stats = {}

        # Initialize stats for skipped sources
        for src_name in skipped_sources:
            health = get_source_health(src_name)
            source_stats[src_name] = {
                "status": "skipped",
                "count": 0,
                "consecutive_failures": health.consecutive_failures,
                "backoff_until": health.backoff_until.isoformat() if health.backoff_until else None,
            }

        # Process results from active sources
        for src, result in zip(active_sources, results):
            health = get_source_health(src.name)

            if isinstance(result, Exception):
                logger.error("Source %s failed: %s", src.name, result)
                health.record_failure()
                source_stats[src.name] = {
                    "status": "error",
                    "count": 0,
                    "consecutive_failures": health.consecutive_failures,
                    "error": str(result),
                }

                if health.consecutive_failures == FAILURE_THRESHOLD_REDUCED:
                    logger.warning(
                        "Source %s has failed %d times - monitoring closely",
                        src.name, health.consecutive_failures
                    )
                elif health.consecutive_failures == FAILURE_THRESHOLD_SKIP:
                    logger.warning(
                        "Source %s has failed %d times - entering backoff",
                        src.name, health.consecutive_failures
                    )
                continue

            # Success - reset failure counter
            health.record_success()
            all_items.extend(result)
            source_stats[src.name] = {
                "status": "ok",
                "count": len(result),
                "success_rate": round(health.success_rate, 3),
            }

        # Deduplicate and store
        new_count = 0
        async with async_session() as session:
            for item in all_items:
                chash = content_hash(item.title, item.url)
                existing = await session.execute(
                    select(ContentDiscovery).where(ContentDiscovery.content_hash == chash)
                )
                if existing.scalar_one_or_none():
                    continue

                discovery = ContentDiscovery(
                    source=item.source,
                    source_id=item.source_id,
                    title=item.title,
                    url=item.url,
                    content_hash=chash,
                    raw_score=item.raw_score,
                    raw_data=item.raw_data,
                    status="new",
                    discovered_at=item.discovered_at or now,
                )
                session.add(discovery)
                new_count += 1
            await session.commit()

        logger.info(
            "Scout complete: %d new discoveries from %d/%d sources (%d skipped)",
            new_count, len(active_sources), len(ALL_SOURCES), len(skipped_sources)
        )
        return {
            "new_discoveries": new_count,
            "sources": source_stats,
            "active_sources": len(active_sources),
            "skipped_sources": skipped_sources,
        }

    async def _fetch_source(self, source):
        try:
            return await source.fetch()
        except Exception as e:
            logger.error("Failed to fetch from %s: %s", source.name, e)
            return []

    def get_source_health_summary(self) -> dict:
        """Get health summary for all sources (for API exposure)."""
        summary = {}
        for src in ALL_SOURCES:
            health = get_source_health(src.name)
            summary[src.name] = {
                "healthy": health.is_healthy,
                "should_skip": health.should_skip,
                "consecutive_failures": health.consecutive_failures,
                "total_failures": health.total_failures,
                "total_successes": health.total_successes,
                "success_rate": round(health.success_rate, 3),
                "last_failure_at": health.last_failure_at.isoformat() if health.last_failure_at else None,
                "last_success_at": health.last_success_at.isoformat() if health.last_success_at else None,
                "backoff_until": health.backoff_until.isoformat() if health.backoff_until else None,
            }
        return summary

    def reset_source_health(self, source_name: str) -> bool:
        """Manually reset health for a source (recover from backoff)."""
        if source_name in _source_health:
            _source_health[source_name] = SourceHealth()
            logger.info("Reset health for source: %s", source_name)
            return True
        return False
