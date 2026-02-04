import asyncio
import logging
from datetime import datetime

import feedparser
import httpx

from sources.base import BaseSource, DiscoveryItem

logger = logging.getLogger(__name__)

MAX_ITEMS_PER_FEED = 10

RSS_FEEDS = {
    "openai": "https://openai.com/blog/rss.xml",
    "google_ai": "https://blog.google/technology/ai/rss/",
    "deepmind": "https://deepmind.google/blog/rss.xml",
    "microsoft_ai": "https://blogs.microsoft.com/ai/feed/",
    "huggingface": "https://huggingface.co/blog/feed.xml",
}

HEADERS = {"User-Agent": "content-autopilot/0.1"}


class CompanyBlogsSource(BaseSource):
    @property
    def name(self) -> str:
        return "company_blogs"

    async def fetch(self) -> list[DiscoveryItem]:
        try:
            async with httpx.AsyncClient(timeout=30.0, headers=HEADERS, follow_redirects=True) as client:
                tasks = [self._fetch_feed(client, company, url) for company, url in RSS_FEEDS.items()]
                results = await asyncio.gather(*tasks, return_exceptions=True)

            items: list[DiscoveryItem] = []
            for result in results:
                if isinstance(result, Exception):
                    logger.warning("Company blog feed failed: %s", result)
                    continue
                items.extend(result)

            logger.info("CompanyBlogs: fetched %d items from %d feeds", len(items), len(RSS_FEEDS))
            return items

        except Exception:
            logger.exception("CompanyBlogs fetch failed")
            return []

    async def _fetch_feed(self, client: httpx.AsyncClient, company: str, feed_url: str) -> list[DiscoveryItem]:
        resp = await client.get(feed_url)
        resp.raise_for_status()

        feed = feedparser.parse(resp.text)
        items: list[DiscoveryItem] = []

        for entry in feed.entries[:MAX_ITEMS_PER_FEED]:
            title = entry.get("title", "").strip()
            link = entry.get("link", "")
            if not title or not link:
                continue

            published = entry.get("published", "") or entry.get("updated", "")
            try:
                discovered = datetime.fromisoformat(published.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                discovered = datetime.utcnow()

            items.append(
                DiscoveryItem(
                    source="company_blogs",
                    source_id=link,
                    title=title,
                    url=link,
                    raw_score=0.0,
                    raw_data={
                        "company": company,
                        "summary": entry.get("summary", ""),
                        "published": published,
                    },
                    discovered_at=discovered,
                )
            )

        return items
