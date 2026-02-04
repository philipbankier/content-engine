from abc import ABC, abstractmethod


class BasePublisher(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    async def publish(self, content: dict) -> dict:
        """Publish content and return {"platform_post_id": ..., "platform_url": ...}."""
        ...

    @abstractmethod
    async def get_metrics(self, post_id: str) -> dict:
        """Return engagement metrics for a published post."""
        ...
