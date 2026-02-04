import logging
from datetime import datetime

import httpx

from sources.base import BaseSource, DiscoveryItem

logger = logging.getLogger(__name__)


class LobstersSource(BaseSource):
    @property
    def name(self) -> str:
        return "lobsters"

    async def fetch(self) -> list[DiscoveryItem]:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get("https://lobste.rs/hottest.json")
                resp.raise_for_status()
                data = resp.json()

            items: list[DiscoveryItem] = []
            for story in data[:15]:
                score = story.get("score", 0)
                if score < 20:
                    continue

                items.append(
                    DiscoveryItem(
                        source="lobsters",
                        source_id=story.get("short_id", ""),
                        title=story.get("title", ""),
                        url=story.get("url") or story.get("comments_url", ""),
                        raw_score=float(score),
                        raw_data=story,
                        discovered_at=datetime.utcnow(),
                    )
                )

            logger.info("Lobsters: fetched %d items", len(items))
            return items

        except Exception:
            logger.exception("Lobsters fetch failed")
            return []
