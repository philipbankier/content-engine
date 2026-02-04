"""Collect engagement metrics from published content at timed intervals."""

import logging
from datetime import datetime, timezone

from sqlalchemy import select

from db import async_session
from models import ContentMetric, ContentPublication

logger = logging.getLogger(__name__)

# Intervals at which to collect metrics (label → hours since publication)
COLLECTION_INTERVALS = {
    "1h": 1,
    "6h": 6,
    "24h": 24,
    "48h": 48,
    "7d": 168,
}


class MetricsCollector:
    """Fetch and store engagement metrics for published content."""

    async def collect(self, at: datetime | None = None) -> dict:
        """Collect metrics for all publications at their appropriate intervals.

        Returns a summary with counts of metrics collected and skipped.
        """
        now = at or datetime.now(timezone.utc)
        collected = 0
        skipped = 0
        errors = 0

        async with async_session() as session:
            result = await session.execute(select(ContentPublication))
            publications = result.scalars().all()

        for pub in publications:
            age = now - pub.published_at
            age_hours = age.total_seconds() / 3600

            for interval_label, interval_hours in COLLECTION_INTERVALS.items():
                if age_hours < interval_hours:
                    continue

                # Check if we already collected this interval
                async with async_session() as session:
                    existing = await session.execute(
                        select(ContentMetric).where(
                            ContentMetric.publication_id == pub.id,
                            ContentMetric.interval == interval_label,
                        )
                    )
                    if existing.scalar_one_or_none() is not None:
                        skipped += 1
                        continue

                # Fetch metrics from the publisher
                try:
                    metrics_data = await self._fetch_platform_metrics(pub)

                    async with async_session() as session:
                        metric = ContentMetric(
                            publication_id=pub.id,
                            interval=interval_label,
                            views=metrics_data.get("views", 0),
                            likes=metrics_data.get("likes", 0),
                            comments=metrics_data.get("comments", 0),
                            shares=metrics_data.get("shares", 0),
                            clicks=metrics_data.get("clicks", 0),
                            followers_gained=metrics_data.get("followers_gained", 0),
                            engagement_rate=metrics_data.get("engagement_rate", 0.0),
                            collected_at=now,
                        )
                        session.add(metric)
                        await session.commit()

                    collected += 1
                    logger.info(
                        "Collected %s metrics for publication %d on %s",
                        interval_label, pub.id, pub.platform,
                    )
                except Exception:
                    logger.exception("Failed to collect metrics for publication %d", pub.id)
                    errors += 1

        summary = {"collected": collected, "skipped": skipped, "errors": errors}
        logger.info("Metrics collection complete: %s", summary)
        return summary

    async def _fetch_platform_metrics(self, publication) -> dict:
        """Fetch metrics from the appropriate platform publisher."""
        from publishers.upload_post import UploadPostPublisher
        from publishers.tiktok import TikTokPublisher

        if publication.platform == "tiktok":
            publisher = TikTokPublisher()
        else:
            publisher = UploadPostPublisher()

        if publication.platform_post_id:
            return await publisher.get_metrics(publication.platform_post_id)

        return {"views": 0, "likes": 0, "comments": 0, "shares": 0, "clicks": 0}
