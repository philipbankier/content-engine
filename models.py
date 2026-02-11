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
    video_type = Column(String(32), nullable=True)  # VideoType enum value
    video_type_rationale = Column(Text, nullable=True)
    video_prompt = Column(Text, nullable=True)  # for non-script video types (motion_graphics, kinetic_text, avatar_agent)
    video_composition = Column(JSON, nullable=True)  # for hybrid: list of segment dicts
    video_status = Column(String(32), default="idle")  # idle / generating / done / failed
    video_url = Column(Text, nullable=True)
    video_error = Column(Text, nullable=True)
    video_started_at = Column(DateTime, nullable=True)
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
    saves = Column(Integer, default=0)  # Bookmarks/saves (indicates value)
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
    provider = Column(String(32), nullable=True, index=True)  # bedrock / ollama / openai_compat
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


class SkillInteraction(Base):
    """Track skill co-occurrence outcomes to discover synergies and conflicts.

    When two skills are used together, this table records how they perform
    relative to their individual baselines. Positive synergy_score indicates
    the combination works better than expected; negative indicates conflict.
    """

    __tablename__ = "skill_interactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    skill_a = Column(String(128), nullable=False, index=True)
    skill_b = Column(String(128), nullable=False, index=True)
    co_occurrence_count = Column(Integer, default=0)
    avg_combined_score = Column(Float, default=0.0)
    # synergy_score: combined score - (avg of individual scores)
    # positive = skills amplify each other
    # negative = skills conflict
    synergy_score = Column(Float, default=0.0)
    last_used_at = Column(DateTime, default=_utcnow, nullable=False)
    updated_at = Column(DateTime, default=_utcnow, nullable=False)


class EngagementAction(Base):
    """Track engagement actions (replies, proactive comments) for learning."""

    __tablename__ = "engagement_actions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    action_type = Column(String(32), nullable=False, index=True)  # "reply" | "proactive"
    platform = Column(String(32), nullable=False, index=True)
    target_url = Column(Text, nullable=False)  # URL of post/comment we're responding to
    target_author = Column(String(128), nullable=True)  # Author of the original content
    target_text = Column(Text, nullable=True)  # Text of original comment (for replies)
    our_text = Column(Text, nullable=False)  # Our reply/comment text
    publication_id = Column(Integer, nullable=True, index=True)  # Link to our post (for replies)
    skills_used = Column(JSON, nullable=True)
    status = Column(String(32), default="pending")  # pending / posted / failed
    posted_at = Column(DateTime, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)


class ContentSchedule(Base):
    """Scheduled content publications — approved content queued for future publish."""

    __tablename__ = "content_schedules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    creation_id = Column(Integer, nullable=False, index=True)
    platform = Column(String(32), nullable=False, index=True)
    scheduled_at = Column(DateTime, nullable=False, index=True)
    status = Column(String(32), default="scheduled", index=True)  # scheduled / published / cancelled / failed
    suggested_by = Column(String(32), default="system")  # system / user
    publication_id = Column(Integer, nullable=True)  # Set after publish
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    published_at = Column(DateTime, nullable=True)


class NewsletterDraft(Base):
    """Curated newsletter drafts with topic sections."""

    __tablename__ = "newsletter_drafts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(Text, nullable=False)
    sections = Column(JSON, nullable=True)  # [{heading, summary, discovery_ids, image_url}]
    html_body = Column(Text, nullable=True)
    header_image_url = Column(Text, nullable=True)
    status = Column(String(32), default="draft", index=True)  # draft / approved / sent
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    approved_at = Column(DateTime, nullable=True)
    sent_at = Column(DateTime, nullable=True)


class VideoCreation(Base):
    """Dedicated short-form video content (TikTok, Reels, Shorts)."""

    __tablename__ = "video_creations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    discovery_id = Column(Integer, nullable=True, index=True)
    title = Column(Text, nullable=False)
    script = Column(Text, nullable=True)
    video_type = Column(String(32), nullable=True)
    video_prompt = Column(Text, nullable=True)
    video_composition = Column(JSON, nullable=True)
    thumbnail_prompt = Column(Text, nullable=True)
    caption = Column(Text, nullable=True)
    hashtags = Column(JSON, nullable=True)
    target_platforms = Column(JSON, nullable=True)  # ["tiktok", "youtube_shorts", "reels"]
    video_url = Column(Text, nullable=True)
    thumbnail_url = Column(Text, nullable=True)
    video_status = Column(String(32), default="pending", index=True)  # pending / generating / done / failed
    approval_status = Column(String(32), default="pending", index=True)  # pending / approved / rejected
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    approved_at = Column(DateTime, nullable=True)
