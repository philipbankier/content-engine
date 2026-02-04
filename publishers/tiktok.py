"""TikTok publishing stub — requires browser automation for actual posting."""

import logging
from publishers.base import BasePublisher

logger = logging.getLogger(__name__)


class TikTokPublisher(BasePublisher):
    name = "tiktok"

    async def publish(self, content: dict) -> dict:
        """Publish content to TikTok.

        TikTok does not offer a simple public posting API.
        This stub queues content for manual upload or browser automation
        via Stagehand.

        Args:
            content: {
                "video_url": str,
                "caption": str,
                "tags": list[str] (optional),
            }

        Returns:
            Status dict indicating manual upload is required.
        """
        video_url = content.get("video_url", "")
        caption = content.get("caption", "")
        tags = content.get("tags", [])

        logger.info(
            "TikTok publish queued for manual upload: caption=%s, video=%s, tags=%s",
            caption[:50],
            video_url[:80] if video_url else "none",
            tags,
        )

        return {
            "platform_post_id": "pending_manual",
            "platform_url": None,
            "note": "TikTok requires browser automation - queued for manual upload",
            "queued_content": {
                "video_url": video_url,
                "caption": caption,
                "tags": tags,
            },
        }

    async def get_metrics(self, post_id: str) -> dict:
        """Get metrics for a TikTok post.

        Returns empty metrics stub since automated access is not available.
        """
        return {
            "views": 0,
            "likes": 0,
            "comments": 0,
            "shares": 0,
            "note": "TikTok metrics require browser automation or manual lookup",
        }
