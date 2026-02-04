"""SQLAlchemy models — 9 tables for the content autopilot system."""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    JSON,
)
from sqlalchemy.orm import DeclarativeBase


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class ContentDiscovery(Base):
    """Raw items discovered from source platforms."""

    __tablename__ = "content_discoveries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(64), nullable=False, index=True)
    source_id = Column(String(256), nullable=True)
    title = Column(Text, nullable=False)
    url = Column(Text, nullable=True)
    content_hash = Column(String(64), nullable=False, unique=True, index=True)
    raw_score = Column(Float, default=0.0)
    relevance_score = Column(Float, nullable=True)
    velocity_score = Column(Float, nullable=True)
    risk_level = Column(String(16), nullable=True)  # low / medium / high
    platform_fit = Column(JSON, nullable=True)  # {"linkedin": 0.9, "twitter": 0.7, ...}
    suggested_formats = Column(JSON, nullable=True)
    status = Column(String(32), default="new", index=True)  # new / analyzed / queued / published / skipped
    raw_data = Column(JSON, nullable=True)
    discovered_at = Column(DateTime, default=_utcnow, nullable=False)
    analyzed_at = Column(DateTime, nullable=True)


class ContentCreation(Base):
    """Generated content pieces (text, image refs, video refs)."""

    __tablename__ = "content_creations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    discovery_id = Column(Integer, nullable=False, index=True)
    platform = Column(String(32), nullable=False, index=True)
    format = Column(String(32), nullable=False)  # post / thread / short / article / carousel
    title = Column(Text, nullable=True)
    body = Column(Text, nullable=False)
    media_urls = Column(JSON, nullable=True)  # list of asset URLs
    skills_used = Column(JSON, nullable=True)  # list of skill names
    risk_score = Column(Float, nullable=True)
    risk_flags = Column(JSON, nullable=True)
    quality_score = Column(Float, nullable=True)  # 0-1 quality score from QualityChecker
    quality_issues = Column(JSON, nullable=True)  # list of quality issues found
    video_script = Column(Text, nullable=True)  # stored for deferred video generation
    variant_group = Column(String(64), nullable=True, index=True)
    variant_label = Column(String(8), nullable=True)  # A, B, C
    approval_status = Column(String(32), default="pending")  # pending / pending_review / approved / rejected / auto_approved / quality_rejected
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    approved_at = Column(DateTime, nullable=True)


class ContentPublication(Base):
    """Published posts with platform IDs and arbitrage tracking."""

    __tablename__ = "content_publications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    creation_id = Column(Integer, nullable=False, index=True)
    platform = Column(String(32), nullable=False, index=True)
    platform_post_id = Column(String(256), nullable=True)
    platform_url = Column(Text, nullable=True)
    arbitrage_window_minutes = Column(Integer, nullable=True)  # how early vs mainstream
    published_at = Column(DateTime, default=_utcnow, nullable=False)


class ContentMetric(Base):
    """Engagement snapshots at intervals (1h, 6h, 24h, 48h, 7d)."""

    __tablename__ = "content_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    publication_id = Column(Integer, nullable=False, index=True)
    interval = Column(String(8), nullable=False)  # 1h / 6h / 24h / 48h / 7d
    views = Column(Integer, default=0)
    likes = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    shares = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    followers_gained = Column(Integer, default=0)
    engagement_rate = Column(Float, default=0.0)
    collected_at = Column(DateTime, default=_utcnow, nullable=False)


class ContentPlaybook(Base):
    """Brand configuration — voice, topics, competitors."""

    __tablename__ = "content_playbook"

    id = Column(Integer, primary_key=True, autoincrement=True)
    brand_name = Column(String(128), nullable=False, default="Autopilot by Kairox AI")
    voice_guide = Column(Text, nullable=True)
    topics = Column(JSON, nullable=True)  # list of topic strings
    avoid_topics = Column(JSON, nullable=True)
    competitors = Column(JSON, nullable=True)
    updated_at = Column(DateTime, default=_utcnow, nullable=False)


class ContentExperiment(Base):
    """A/B test definitions and results."""

    __tablename__ = "content_experiments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    skill_name = Column(String(128), nullable=False, index=True)
    variant_a = Column(Text, nullable=False)  # description / content hash
    variant_b = Column(Text, nullable=False)
    metric_target = Column(String(64), nullable=False)  # engagement_rate / clicks / shares
    sample_size = Column(Integer, default=0)
    variant_a_score = Column(Float, default=0.0)
    variant_b_score = Column(Float, default=0.0)
    winner = Column(String(1), nullable=True)  # A / B / None
    status = Column(String(32), default="running")  # running / completed / cancelled
    started_at = Column(DateTime, default=_utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)


class ContentAgentRun(Base):
    """Agent execution logs with cost tracking."""

    __tablename__ = "content_agent_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent = Column(String(64), nullable=False, index=True)
    task = Column(String(128), nullable=True)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    estimated_cost_usd = Column(Float, default=0.0)
    duration_seconds = Column(Float, default=0.0)
    status = Column(String(32), default="completed")  # completed / failed / timeout
    error = Column(Text, nullable=True)
    started_at = Column(DateTime, default=_utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)


class SkillRecord(Base):
    """Skill metadata, confidence, health, version pointers."""

    __tablename__ = "skill_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False, unique=True, index=True)
    category = Column(String(32), nullable=False, index=True)
    platform = Column(String(32), nullable=True)
    confidence = Column(Float, default=0.5)
    status = Column(String(32), default="active")  # active / stale / under_review / retired
    version = Column(Integer, default=1)
    total_uses = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    failure_streak = Column(Integer, default=0)
    tags = Column(JSON, nullable=True)
    file_path = Column(Text, nullable=True)
    last_used_at = Column(DateTime, nullable=True)
    last_validated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    updated_at = Column(DateTime, default=_utcnow, nullable=False)


class SkillMetric(Base):
    """Individual skill usage outcomes — feeds back into confidence."""

    __tablename__ = "skill_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    skill_name = Column(String(128), nullable=False, index=True)
    agent = Column(String(64), nullable=False)
    task = Column(String(128), nullable=True)
    outcome = Column(String(32), nullable=False)  # success / partial / failure
    score = Column(Float, default=0.0)
    context = Column(JSON, nullable=True)  # extra metadata
    recorded_at = Column(DateTime, default=_utcnow, nullable=False)
