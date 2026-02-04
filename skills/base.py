from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class SkillStatus(Enum):
    ACTIVE = "active"
    STALE = "stale"
    UNDER_REVIEW = "under_review"
    RETIRED = "retired"
    SUPERSEDED = "superseded"


class SkillCategory(Enum):
    SOURCES = "sources"
    CREATION = "creation"
    PLATFORM = "platform"
    TOOLS = "tools"
    ENGAGEMENT = "engagement"
    TIMING = "timing"


@dataclass
class Skill:
    name: str
    category: SkillCategory
    platform: Optional[str] = None
    confidence: float = 0.5
    status: SkillStatus = SkillStatus.ACTIVE
    version: int = 1
    content: str = ""
    tags: list[str] = field(default_factory=list)
    file_path: str = ""
    total_uses: int = 0
    success_count: int = 0
    failure_streak: int = 0
    last_used_at: Optional[datetime] = None
    last_validated_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
