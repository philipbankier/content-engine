import asyncio
import logging
from datetime import datetime

import httpx

from sources.base import BaseSource, DiscoveryItem

logger = logging.getLogger(__name__)

SUBREDDITS = [
    "MachineLearning",
    "artificial",
    "LocalLLaMA",
    "singularity",
    "ChatGPT",
    "automation",
    "SaaS",
]

HEADERS = {"User-Agent": "content-autopilot/0.1"}


class RedditSource(BaseSource):
    @property
    def name(self) -> str:
        return "reddit"

    async def fetch(self) -> list[DiscoveryItem]:
        try:
            async with httpx.AsyncClient(timeout=30.0, headers=HEADERS) as client:
                tasks = [self._fetch_subreddit(client, sub) for sub in SUBREDDITS]
                results = await asyncio.gather(*tasks, return_exceptions=True)

            items: list[DiscoveryItem] = []
            for result in results:
                if isinstance(result, Exception):
                    logger.warning("Reddit subreddit fetch failed: %s", result)
                    continue
                items.extend(result)

            logger.info("Reddit: fetched %d items across %d subreddits", len(items), len(SUBREDDITS))
            return items

        except Exception:
            logger.exception("Reddit fetch failed")
            return []

    async def _fetch_subreddit(self, client: httpx.AsyncClient, subreddit: str) -> list[DiscoveryItem]:
        resp = await client.get(
            f"https://www.reddit.com/r/{subreddit}/hot.json",
            params={"limit": 10},
        )
        resp.raise_for_status()
        data = resp.json()

        items: list[DiscoveryItem] = []
        for child in data.get("data", {}).get("children", []):
            post = child.get("data", {})
            score = post.get("score", 0)
            if score < 100:
                continue

            permalink = post.get("permalink", "")
            url = f"https://www.reddit.com{permalink}" if permalink else post.get("url", "")

            items.append(
                DiscoveryItem(
                    source="reddit",
                    source_id=post.get("id", ""),
                    title=post.get("title", ""),
                    url=url,
                    raw_score=float(score),
                    raw_data=post,
                    discovered_at=datetime.utcnow(),
                )
            )

        return items
