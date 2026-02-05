"""Unified publisher via upload-post.com — handles LinkedIn, X, YouTube."""

import logging

import httpx

from config import settings
from publishers.base import BasePublisher

logger = logging.getLogger(__name__)

BASE_URL = "https://app.upload-post.com/api"


class UploadPostPublisher(BasePublisher):
    name = "upload_post"

    def _headers(self) -> dict:
        return {
            "Authorization": f"Apikey {settings.upload_post_api_key}",
            "Accept": "application/json",
        }

    async def publish(self, content: dict) -> dict:
        """Publish content via upload-post.com.

        Args:
            content: {
                "platform": "linkedin" | "x" | "youtube",
                "text": str,              # post body (required for text/photo)
                "image_urls": list[str],   # optional photo URLs
                "video_url": str,          # required for youtube
                "title": str,             # youtube_title
                "description": str,       # youtube_description
            }
        """
        platform = content.get("platform", "")
        # Map internal names to upload-post.com platform names
        platform_map = {"twitter": "x", "linkedin": "linkedin", "x": "x", "youtube": "youtube"}
        api_platform = platform_map.get(platform, platform)

        video_url = content.get("video_url")
        image_urls = content.get("image_urls", [])
        text = content.get("text", "")

        try:
            if video_url and api_platform == "youtube":
                return await self._upload_video(content, api_platform)
            elif image_urls:
                return await self._upload_photos(text, image_urls, api_platform)
            else:
                return await self._upload_text(text, api_platform)
        except Exception as e:
            logger.error("upload-post.com publish failed for %s: %s", api_platform, e)
            return {"error": str(e)}

    async def _upload_text(self, text: str, platform: str) -> dict:
        """POST /api/upload_text — text-only post."""
        data = {
            "user": settings.upload_post_user,
            "platform[]": platform,
            "text": text,
            "async_upload": "true",
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{BASE_URL}/upload_text",
                headers=self._headers(),
                data=data,
            )
            resp.raise_for_status()
            result = resp.json()
            logger.info("upload-post.com text upload (%s): %s", platform, result)
            return self._parse_response(result, platform)

    async def _upload_photos(self, text: str, image_urls: list[str], platform: str) -> dict:
        """POST /api/upload_photos — post with images."""
        data = {
            "user": settings.upload_post_user,
            "platform[]": platform,
            "text": text,
            "async_upload": "true",
        }
        # Add each photo URL
        for url in image_urls:
            data.setdefault("photos[]", [])
            if isinstance(data["photos[]"], list):
                data["photos[]"].append(url)
            else:
                data["photos[]"] = [data["photos[]"], url]

        async with httpx.AsyncClient(timeout=30) as client:
            # httpx needs special handling for repeated keys
            params_list = [
                ("user", settings.upload_post_user),
                ("platform[]", platform),
                ("text", text),
                ("async_upload", "true"),
            ]
            for url in image_urls:
                params_list.append(("photos[]", url))

            resp = await client.post(
                f"{BASE_URL}/upload_photos",
                headers=self._headers(),
                data=params_list,
            )
            resp.raise_for_status()
            result = resp.json()
            logger.info("upload-post.com photo upload (%s): %s", platform, result)
            return self._parse_response(result, platform)

    async def _upload_video(self, content: dict, platform: str) -> dict:
        """POST /api/upload — video upload (YouTube)."""
        data = [
            ("user", settings.upload_post_user),
            ("platform[]", platform),
            ("video", content.get("video_url", "")),
            ("youtube_title", content.get("title", "")),
            ("youtube_description", content.get("description", "")),
            ("async_upload", "true"),
        ]
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{BASE_URL}/upload",
                headers=self._headers(),
                data=data,
            )
            resp.raise_for_status()
            result = resp.json()
            logger.info("upload-post.com video upload (%s): %s", platform, result)
            return self._parse_response(result, platform)

    @staticmethod
    def _parse_response(result: dict, platform: str) -> dict:
        """Normalize upload-post.com response to our standard format."""
        return {
            "platform_post_id": result.get("id") or result.get("upload_id", ""),
            "platform_url": result.get("url") or result.get("post_url"),
            "raw_response": result,
            "platform": platform,
        }

    async def get_metrics(self, post_id: str, platform: str = None, platform_url: str = None) -> dict:
        """Get engagement metrics for a published post.

        Args:
            post_id: The upload-post.com post ID
            platform: Platform name (linkedin, x, youtube)
            platform_url: Direct URL to the post on the platform

        Returns:
            Metrics dict with views, likes, comments, shares, engagement_rate
        """
        from config import settings

        # If we have a platform URL and scraping is enabled, use the real scraper
        if platform_url and settings.metrics_scrape_enabled:
            try:
                from metrics.scraper import scrape_metrics

                logger.info("Scraping real metrics for %s: %s", platform, platform_url)
                metrics = await scrape_metrics(
                    platform=platform or "linkedin",
                    url=platform_url,
                    headless=settings.playwright_headless
                )

                # Only return scraped metrics if we got something useful
                if metrics.get("views", 0) > 0 or metrics.get("likes", 0) > 0:
                    return metrics

            except ImportError:
                logger.warning("Playwright not installed - falling back to stub metrics")
            except Exception as e:
                logger.error("Metrics scraping failed: %s", e)

        # Fallback to stub metrics
        return {
            "views": 0,
            "likes": 0,
            "comments": 0,
            "shares": 0,
            "saves": 0,
            "clicks": 0,
            "followers_gained": 0,
            "engagement_rate": 0.0,
            "note": "Metrics not available via upload-post.com (no platform_url provided)",
        }
