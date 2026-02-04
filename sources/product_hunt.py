import logging
from datetime import datetime

import feedparser
import httpx

from sources.base import BaseSource, DiscoveryItem

logger = logging.getLogger(__name__)

HEADERS = {"User-Agent": "content-autopilot/0.1"}
PH_FEED_URL = "https://www.producthunt.com/feed"
MAX_ITEMS = 15


class ProductHuntSource(BaseSource):
    @property
    def name(self) -> str:
        return "producthunt"

    async def fetch(self) -> list[DiscoveryItem]:
        try:
            async with httpx.AsyncClient(timeout=30.0, headers=HEADERS, follow_redirects=True) as client:
                resp = await client.get(PH_FEED_URL)
                resp.raise_for_status()

            feed = feedparser.parse(resp.text)
            items: list[DiscoveryItem] = []

            for entry in feed.entries[:MAX_ITEMS]:
                title = entry.get("title", "").strip()
                link = entry.get("link", "")
                if not title or not link:
                    continue

                entry_id = entry.get("id", link)

                published = entry.get("published", "") or entry.get("updated", "")
                try:
                    discovered = datetime.fromisoformat(published.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    discovered = datetime.utcnow()

                summary = entry.get("summary", "")

                items.append(
                    DiscoveryItem(
                        source="producthunt",
                        source_id=entry_id,
                        title=title,
                        url=link,
                        raw_score=0.0,
                        raw_data={
                            "title": title,
                            "url": link,
                            "summary": summary,
                        },
                        discovered_at=discovered,
                    )
                )

            logger.info("ProductHunt: fetched %d items via Atom feed", len(items))
            return items

        except Exception:
            logger.exception("ProductHunt fetch failed")
            return []
