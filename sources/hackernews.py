import logging
from datetime import datetime

import httpx

from sources.base import BaseSource, DiscoveryItem

logger = logging.getLogger(__name__)


class HackerNewsSource(BaseSource):
    @property
    def name(self) -> str:
        return "hackernews"

    async def fetch(self) -> list[DiscoveryItem]:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(
                    "https://hn.algolia.com/api/v1/search",
                    params={"tags": "front_page", "hitsPerPage": 20},
                )
                resp.raise_for_status()
                data = resp.json()

            items: list[DiscoveryItem] = []
            for hit in data.get("hits", []):
                points = hit.get("points", 0) or 0
                if points < 50:
                    continue

                url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit['objectID']}"
                items.append(
                    DiscoveryItem(
                        source="hackernews",
                        source_id=str(hit["objectID"]),
                        title=hit.get("title", ""),
                        url=url,
                        raw_score=float(points),
                        raw_data=hit,
                        discovered_at=datetime.utcnow(),
                    )
                )

            logger.info("HackerNews: fetched %d items (filtered from %d)", len(items), len(data.get("hits", [])))
            return items

        except Exception:
            logger.exception("HackerNews fetch failed")
            return []
