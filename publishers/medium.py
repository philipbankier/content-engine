"""Medium publisher via the Medium API.

Medium's API is simple but limited:
- POST to create posts
- No ability to edit/delete via API
- No metrics available via API (must use scraper)
- Rate limited to ~10 posts/day

API docs: https://github.com/Medium/medium-api-docs
"""

import logging
from typing import Optional

import httpx

from config import settings
from publishers.base import BasePublisher

logger = logging.getLogger(__name__)

BASE_URL = "https://api.medium.com/v1"


class MediumPublisher(BasePublisher):
    """Publisher for Medium articles via the Medium API."""

    name = "medium"

    def __init__(self):
        self._user_id: Optional[str] = None

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {settings.medium_integration_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _get_user_id(self) -> str:
        """Get the authenticated user's ID (cached)."""
        if self._user_id:
            return self._user_id

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{BASE_URL}/me",
                headers=self._headers(),
            )
            resp.raise_for_status()
            data = resp.json()
            self._user_id = data["data"]["id"]
            logger.info("Medium user ID: %s (%s)", self._user_id, data["data"].get("username", ""))
            return self._user_id

    async def publish(self, content: dict) -> dict:
        """Publish an article to Medium.

        Args:
            content: {
                "title": str,              # Article title (required)
                "body": str,               # Article body in HTML or Markdown (required)
                "content_format": str,     # "html" or "markdown" (default: markdown)
                "tags": list[str],         # Up to 5 tags (optional)
                "canonical_url": str,      # Original URL if cross-posting (optional)
                "publish_status": str,     # "public", "draft", or "unlisted" (default: public)
            }

        Returns:
            {"platform_post_id": ..., "platform_url": ..., "raw_response": ...}
        """
        if not settings.medium_integration_token:
            return {"error": "Medium integration token not configured"}

        title = content.get("title", "")
        body = content.get("body", "")

        if not title or not body:
            return {"error": "Title and body are required for Medium articles"}

        try:
            user_id = await self._get_user_id()

            # Prepare post data
            post_data = {
                "title": title,
                "contentFormat": content.get("content_format", "markdown"),
                "content": body,
                "publishStatus": content.get("publish_status", "public"),
            }

            # Add optional fields
            tags = content.get("tags", [])
            if tags:
                # Medium allows max 5 tags
                post_data["tags"] = tags[:5]

            canonical_url = content.get("canonical_url")
            if canonical_url:
                post_data["canonicalUrl"] = canonical_url

            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    f"{BASE_URL}/users/{user_id}/posts",
                    headers=self._headers(),
                    json=post_data,
                )
                resp.raise_for_status()
                result = resp.json()

            post_data_response = result.get("data", {})
            logger.info(
                "Medium article published: %s (%s)",
                post_data_response.get("title", ""),
                post_data_response.get("url", ""),
            )

            return {
                "platform_post_id": post_data_response.get("id", ""),
                "platform_url": post_data_response.get("url", ""),
                "raw_response": result,
                "platform": "medium",
            }

        except httpx.HTTPStatusError as e:
            error_msg = f"Medium API error: {e.response.status_code}"
            try:
                error_data = e.response.json()
                error_msg = f"{error_msg} - {error_data}"
            except Exception:
                pass
            logger.error("Medium publish failed: %s", error_msg)
            return {"error": error_msg}
        except Exception as e:
            logger.exception("Medium publish failed")
            return {"error": str(e)}

    async def get_metrics(self, post_id: str, platform_url: str = None) -> dict:
        """Get metrics for a Medium article.

        Medium API doesn't provide stats - use browser scraping if URL available.
        """
        if platform_url:
            try:
                from metrics.scraper import scrape_metrics

                # Medium doesn't have a dedicated scraper yet, but the
                # structure is simple enough that we could add one
                logger.info("Medium metrics scraping not yet implemented for: %s", platform_url)
            except ImportError:
                pass

        # Return empty metrics - Medium stats require browser automation
        return {
            "views": 0,
            "likes": 0,  # "claps" in Medium terms
            "comments": 0,
            "shares": 0,
            "saves": 0,
            "clicks": 0,
            "followers_gained": 0,
            "engagement_rate": 0.0,
            "note": "Medium API doesn't provide stats - manual check required",
        }


async def _test_medium_auth() -> bool:
    """Test Medium API authentication."""
    if not settings.medium_integration_token:
        logger.error("Medium integration token not configured")
        return False

    try:
        publisher = MediumPublisher()
        user_id = await publisher._get_user_id()
        logger.info("Medium auth successful - user ID: %s", user_id)
        return True
    except Exception as e:
        logger.error("Medium auth failed: %s", e)
        return False
