import logging
from datetime import datetime

import feedparser
import httpx

from sources.base import BaseSource, DiscoveryItem

logger = logging.getLogger(__name__)

ARXIV_QUERY = (
    "http://export.arxiv.org/api/query?"
    "search_query=cat:cs.AI+OR+cat:cs.CL+OR+cat:cs.LG+OR+cat:cs.MA"
    "&start=0&max_results=15&sortBy=submittedDate&sortOrder=descending"
)


class ArXivSource(BaseSource):
    @property
    def name(self) -> str:
        return "arxiv"

    async def fetch(self) -> list[DiscoveryItem]:
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                resp = await client.get(ARXIV_QUERY)
                resp.raise_for_status()

            feed = feedparser.parse(resp.text)
            items: list[DiscoveryItem] = []

            for entry in feed.entries:
                title = entry.get("title", "").replace("\n", " ").strip()
                link = entry.get("link", "")
                entry_id = entry.get("id", link)

                published = entry.get("published", "")
                try:
                    discovered = datetime.fromisoformat(published.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    discovered = datetime.utcnow()

                items.append(
                    DiscoveryItem(
                        source="arxiv",
                        source_id=entry_id,
                        title=title,
                        url=link,
                        raw_score=0.0,
                        raw_data={
                            "summary": entry.get("summary", ""),
                            "authors": [a.get("name", "") for a in entry.get("authors", [])],
                            "categories": [t.get("term", "") for t in entry.get("tags", [])],
                            "published": published,
                        },
                        discovered_at=discovered,
                    )
                )

            logger.info("ArXiv: fetched %d items", len(items))
            return items

        except Exception:
            logger.exception("ArXiv fetch failed")
            return []
