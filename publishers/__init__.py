"""Publishers for distributing content to platforms."""

from publishers.base import BasePublisher
from publishers.upload_post import UploadPostPublisher
from publishers.tiktok import TikTokPublisher
from publishers.medium import MediumPublisher

__all__ = ["BasePublisher", "UploadPostPublisher", "TikTokPublisher", "MediumPublisher"]


def get_publisher(platform: str) -> BasePublisher:
    """Get the appropriate publisher for a platform."""
    publishers = {
        "linkedin": UploadPostPublisher(),
        "x": UploadPostPublisher(),
        "twitter": UploadPostPublisher(),
        "youtube": UploadPostPublisher(),
        "tiktok": TikTokPublisher(),
        "medium": MediumPublisher(),
    }
    return publishers.get(platform.lower())
