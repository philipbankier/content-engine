import logging
import re
from datetime import datetime

import httpx
from bs4 import BeautifulSoup

from sources.base import BaseSource, DiscoveryItem

logger = logging.getLogger(__name__)

HEADERS = {"User-Agent": "content-autopilot/0.1"}

AI_KEYWORDS = re.compile(
    r"\b(ai|ml|llm|agent|model|neural|transformer|gpt|language.model|automation|"
    r"diffusion|embedding|fine.?tun|rag|vector|inference|deep.?learn|"
    r"machine.?learn|generative|prompt|chat.?bot|copilot|openai|anthropic|"
    r"langchain|hugging.?face|stable.?diffusion|llama|mistral|gemini)\b",
    re.IGNORECASE,
)

# Fetch from multiple trending pages to increase AI/ML hit rate
TRENDING_URLS = [
    "https://github.com/trending?since=daily",
]


class GitHubTrendingSource(BaseSource):
    @property
    def name(self) -> str:
        return "github_trending"

    async def fetch(self) -> list[DiscoveryItem]:
        try:
            seen_repos: set[str] = set()
            items: list[DiscoveryItem] = []

            async with httpx.AsyncClient(timeout=30.0, headers=HEADERS, follow_redirects=True) as client:
                for trending_url in TRENDING_URLS:
                    try:
                        resp = await client.get(trending_url)
                        resp.raise_for_status()
                        self._parse_page(resp.text, items, seen_repos)
                    except Exception:
                        logger.warning("GitHubTrending: failed to fetch %s", trending_url)

            logger.info("GitHubTrending: fetched %d AI/ML items", len(items))
            return items

        except Exception:
            logger.exception("GitHubTrending fetch failed")
            return []

    def _parse_page(
        self, html: str, items: list[DiscoveryItem], seen: set[str]
    ) -> None:
        soup = BeautifulSoup(html, "html.parser")

        articles = soup.find_all("article", class_="Box-row")
        if not articles:
            articles = soup.find_all("article")

        for article in articles:
            h2 = article.find("h2")
            if not h2:
                continue
            link = h2.find("a")
            if not link:
                continue

            href = link.get("href", "").strip()
            repo_name = href.lstrip("/")
            if repo_name in seen:
                continue

            url = f"https://github.com{href}"

            p = article.find("p")
            description = p.get_text(strip=True) if p else ""

            if not AI_KEYWORDS.search(description or "") and not AI_KEYWORDS.search(repo_name):
                continue

            seen.add(repo_name)

            stars_today = 0
            star_spans = article.find_all("span", class_="d-inline-block float-sm-right")
            if not star_spans:
                star_spans = article.find_all(string=re.compile(r"stars\s*(today|this)", re.I))
            for el in star_spans:
                text = el.get_text(strip=True) if hasattr(el, "get_text") else str(el)
                digits = re.findall(r"[\d,]+", text)
                if digits:
                    stars_today = int(digits[0].replace(",", ""))
                    break

            items.append(
                DiscoveryItem(
                    source="github_trending",
                    source_id=repo_name,
                    title=repo_name,
                    url=url,
                    raw_score=float(stars_today),
                    raw_data={
                        "repo": repo_name,
                        "description": description,
                        "stars_today": stars_today,
                    },
                    discovered_at=datetime.utcnow(),
                )
            )
