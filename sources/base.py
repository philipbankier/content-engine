import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class DiscoveryItem:
    source: str
    source_id: str
    title: str
    url: str
    raw_score: float
    raw_data: dict = field(default_factory=dict)
    discovered_at: datetime = field(default_factory=datetime.utcnow)


def content_hash(title: str, url: str) -> str:
    return hashlib.sha256(f"{title}|{url}".encode()).hexdigest()


class BaseSource(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    async def fetch(self) -> list[DiscoveryItem]: ...
