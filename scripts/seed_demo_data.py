#!/usr/bin/env python3
"""
Demo data seeding script for Content Autopilot.

Generates 14 days of realistic historical data showing:
- Content arbitrage timing advantages
- Skill evolution (v1→v2→v3 genealogy)
- A/B test outcomes
- Multi-platform coordination
- Cost efficiency metrics

Run with: python scripts/seed_demo_data.py
"""

import asyncio
import hashlib
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

# Add parent dir to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from db import async_session, create_tables
from models import (
    ContentAgentRun,
    ContentCreation,
    ContentDiscovery,
    ContentExperiment,
    ContentMetric,
    ContentPlaybook,
    ContentPublication,
    SkillMetric,
    SkillRecord,
)


# ============================================================================
# Configuration
# ============================================================================

DEMO_DAYS = 14
END_DATE = datetime.now(timezone.utc).replace(hour=20, minute=0, second=0, microsecond=0)
START_DATE = END_DATE - timedelta(days=DEMO_DAYS)

# Key skills that will evolve during demo period (all dates timezone-aware)
EVOLVING_SKILLS = {
    "linkedin-hook-writing": {
        "v1_end": (START_DATE + timedelta(days=4)).replace(tzinfo=timezone.utc),
        "v2_end": (START_DATE + timedelta(days=9)).replace(tzinfo=timezone.utc),
        "v1_confidence": 0.5,
        "v2_confidence": 0.67,
        "v3_confidence": 0.82,
        "insight": "Question hooks get 2.1x engagement vs statements",
    },
    "optimal-posting-windows": {
        "v1_end": (START_DATE + timedelta(days=5)).replace(tzinfo=timezone.utc),
        "v2_end": (START_DATE + timedelta(days=10)).replace(tzinfo=timezone.utc),
        "v1_confidence": 0.5,
        "v2_confidence": 0.71,
        "v3_confidence": 0.85,
        "insight": "Tuesday 9am PST crushes all other times for LinkedIn",
    },
    "hackernews-scoring": {
        "v1_end": (START_DATE + timedelta(days=6)).replace(tzinfo=timezone.utc),
        "v2_end": (START_DATE + timedelta(days=11)).replace(tzinfo=timezone.utc),
        "v1_confidence": 0.5,
        "v2_confidence": 0.69,
        "v3_confidence": 0.79,
        "insight": "'Show HN' + agent framework = 3.4x conversion",
    },
    "heygen-avatar-video": {
        "v1_end": (START_DATE + timedelta(days=7)).replace(tzinfo=timezone.utc),
        "v2_end": None,  # Only v2 created
        "v1_confidence": 0.5,
        "v2_confidence": 0.76,
        "v3_confidence": None,
        "insight": "Direct-to-camera opening = 40% retention boost",
    },
    "arxiv-mainstream-prediction": {
        "v1_end": (START_DATE + timedelta(days=8)).replace(tzinfo=timezone.utc),
        "v2_end": None,
        "v1_confidence": 0.5,
        "v2_confidence": 0.73,
        "v3_confidence": None,
        "insight": "Papers cited by 3+ bloggers in 24hrs always go mainstream",
    },
    "content-spacing": {
        "v1_end": (START_DATE + timedelta(days=5)).replace(tzinfo=timezone.utc),
        "v2_end": None,
        "v1_confidence": 0.5,
        "v2_confidence": 0.68,
        "v3_confidence": None,
        "insight": "Don't post LinkedIn within 4hrs of previous (cannibalization)",
    },
}

# Platforms and their characteristics
PLATFORMS = {
    "linkedin": {"weight": 0.40, "avg_engagement": 850, "variance": 0.4},
    "twitter": {"weight": 0.30, "avg_engagement": 1200, "variance": 0.6},
    "youtube": {"weight": 0.15, "avg_engagement": 3500, "variance": 0.8},
    "medium": {"weight": 0.10, "avg_engagement": 450, "variance": 0.3},
    "tiktok": {"weight": 0.05, "avg_engagement": 8000, "variance": 1.2},
}

# Sample discovery topics (realistic HN/Reddit content)
SAMPLE_TOPICS = [
    ("Anthropic releases Claude 3.5 Opus", "anthropic", 180),
    ("Show HN: Open-source AI agent framework", "hackernews", 240),
    ("New paper: Scaling Laws for Neural Language Models", "arxiv", 320),
    ("GPT-4 Turbo now available in API", "openai-blog", 120),
    ("Reddit discussion: AI replacing junior devs", "reddit", 420),
    ("GitHub Trending: LangChain hits 50k stars", "github", 180),
    ("Product Hunt: AI video generator launch", "producthunt", 90),
    ("Show HN: I built an AI coding assistant", "hackernews", 210),
    ("ArXiv: Constitutional AI paper released", "arxiv", 380),
    ("Lobsters: Why LLMs are not databases", "lobsters", 150),
    ("OpenAI blog: GPT-4 Vision capabilities", "openai-blog", 95),
    ("Reddit r/MachineLearning: LoRA fine-tuning guide", "reddit", 480),
    ("Show HN: Self-improving agent system", "hackernews", 270),
    ("Meta AI releases LLaMA 3", "company-blog", 140),
    ("GitHub Trending: Rust-based vector DB", "github", 200),
]


# ============================================================================
# Helper Functions
# ============================================================================

def hash_content(text: str) -> str:
    """Generate content hash."""
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def random_datetime(start: datetime, end: datetime) -> datetime:
    """Random datetime between start and end (timezone-aware)."""
    delta = end - start
    random_seconds = random.randint(0, int(delta.total_seconds()))
    result = start + timedelta(seconds=random_seconds)
    # Ensure timezone-aware
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result


def get_skill_version_at_time(skill_name: str, dt: datetime) -> int:
    """Determine which skill version was active at a given time."""
    if skill_name not in EVOLVING_SKILLS:
        return 1

    # Ensure dt is timezone-aware for comparison
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    skill = EVOLVING_SKILLS[skill_name]
    if dt < skill["v1_end"]:
        return 1
    elif skill["v2_end"] and dt < skill["v2_end"]:
        return 2
    else:
        return 3 if skill["v3_confidence"] else 2


def get_skill_confidence_at_time(skill_name: str, dt: datetime) -> float:
    """Get skill confidence score at a given time."""
    if skill_name not in EVOLVING_SKILLS:
        return 0.5 + random.uniform(0, 0.15)

    skill = EVOLVING_SKILLS[skill_name]
    version = get_skill_version_at_time(skill_name, dt)

    if version == 1:
        return skill["v1_confidence"]
    elif version == 2:
        return skill["v2_confidence"]
    else:
        return skill["v3_confidence"] or skill["v2_confidence"]


def generate_engagement_curve(
    base_engagement: int,
    platform: str,
    skill_version: int = 1,
    is_winner: bool = False
) -> dict[str, dict[str, int]]:
    """
    Generate realistic engagement progression over time.
    v2/v3 skills and winning A/B variants get boosted engagement.
    """
    variance = PLATFORMS[platform]["variance"]

    # Version boost
    version_multiplier = 1.0
    if skill_version == 2:
        version_multiplier = 1.5
    elif skill_version >= 3:
        version_multiplier = 2.1

    # Winner boost
    if is_winner:
        version_multiplier *= 1.3

    base = int(base_engagement * version_multiplier)

    # Engagement grows over time with variance
    return {
        "1h": {
            "views": int(base * 0.15 * random.uniform(0.8, 1.2)),
            "likes": int(base * 0.02 * random.uniform(0.7, 1.3)),
            "comments": int(base * 0.005 * random.uniform(0.5, 1.5)),
            "shares": int(base * 0.003 * random.uniform(0.4, 1.6)),
            "clicks": int(base * 0.01 * random.uniform(0.6, 1.4)),
        },
        "6h": {
            "views": int(base * 0.45 * random.uniform(0.85, 1.15)),
            "likes": int(base * 0.06 * random.uniform(0.75, 1.25)),
            "comments": int(base * 0.012 * random.uniform(0.6, 1.4)),
            "shares": int(base * 0.008 * random.uniform(0.5, 1.5)),
            "clicks": int(base * 0.025 * random.uniform(0.7, 1.3)),
        },
        "24h": {
            "views": int(base * 0.75 * random.uniform(0.9, 1.1)),
            "likes": int(base * 0.10 * random.uniform(0.8, 1.2)),
            "comments": int(base * 0.020 * random.uniform(0.7, 1.3)),
            "shares": int(base * 0.012 * random.uniform(0.6, 1.4)),
            "clicks": int(base * 0.04 * random.uniform(0.75, 1.25)),
        },
        "48h": {
            "views": int(base * random.uniform(0.95, 1.05)),
            "likes": int(base * 0.12 * random.uniform(0.85, 1.15)),
            "comments": int(base * 0.025 * random.uniform(0.75, 1.25)),
            "shares": int(base * 0.015 * random.uniform(0.7, 1.3)),
            "clicks": int(base * 0.05 * random.uniform(0.8, 1.2)),
        },
        "7d": {
            "views": int(base * 1.2 * random.uniform(0.9, 1.1)),
            "likes": int(base * 0.14 * random.uniform(0.85, 1.15)),
            "comments": int(base * 0.030 * random.uniform(0.75, 1.25)),
            "shares": int(base * 0.018 * random.uniform(0.7, 1.3)),
            "clicks": int(base * 0.055 * random.uniform(0.8, 1.2)),
        },
    }


# ============================================================================
# Seed Functions
# ============================================================================

async def seed_playbook(session: AsyncSession):
    """Update playbook with proper brand configuration."""
    print("Updating playbook configuration...")

    result = await session.execute(select(ContentPlaybook))
    playbook = result.scalar_one_or_none()

    if playbook:
        playbook.brand_name = "Autopilot by Kairox AI"
        playbook.voice_guide = (
            "Confident, technical but accessible, forward-thinking. "
            "Builder-to-builder tone. No hype, no buzzwords. Show don't tell."
        )
        playbook.topics = json.dumps([
            "AI agents",
            "content automation",
            "platform arbitrage",
            "self-improving systems",
            "autonomous marketing",
        ])
        playbook.avoid_topics = json.dumps([
            "Buffer",
            "Hootsuite",
            "generic social media tips",
            "growth hacking cliches",
        ])
        playbook.updated_at = START_DATE
    else:
        playbook = ContentPlaybook(
            brand_name="Autopilot by Kairox AI",
            voice_guide=(
                "Confident, technical but accessible, forward-thinking. "
                "Builder-to-builder tone. No hype, no buzzwords. Show don't tell."
            ),
            topics=json.dumps([
                "AI agents",
                "content automation",
                "platform arbitrage",
                "self-improving systems",
                "autonomous marketing",
            ]),
            avoid_topics=json.dumps([
                "Buffer",
                "Hootsuite",
                "generic social media tips",
                "growth hacking cliches",
            ]),
            updated_at=START_DATE,
        )
        session.add(playbook)

    await session.commit()
    print(f"✓ Playbook configured: {playbook.brand_name}")


async def seed_discoveries(session: AsyncSession) -> list[int]:
    """Add backdated discoveries with strategic timing."""
    print(f"\nSeeding discoveries ({DEMO_DAYS} days)...")

    discovery_ids = []
    counter = 0

    # Generate ~15-20 discoveries per day
    for day in range(DEMO_DAYS):
        day_start = START_DATE + timedelta(days=day)
        day_end = day_start + timedelta(days=1)

        discoveries_this_day = random.randint(15, 20)

        for _ in range(discoveries_this_day):
            topic, source, arbitrage_minutes = random.choice(SAMPLE_TOPICS)

            # Add unique variation to ensure no hash collisions
            counter += 1
            title = f"{topic} [D{day}N{counter}]"
            unique_content = f"{title}_{source}_{counter}"

            discovered_at = random_datetime(day_start, day_end)

            discovery = ContentDiscovery(
                source=source,
                source_id=f"{source}_{hash_content(unique_content)[:8]}",
                title=title,
                url=f"https://example.com/{hash_content(unique_content)[:12]}",
                content_hash=hash_content(unique_content),
                raw_score=random.uniform(0.6, 0.95),
                relevance_score=random.uniform(0.7, 0.98),
                velocity_score=random.uniform(0.5, 0.9),
                risk_level=random.choice(["low", "low", "low", "medium"]),
                platform_fit=json.dumps({
                    "linkedin": random.uniform(0.6, 0.95),
                    "twitter": random.uniform(0.5, 0.9),
                    "youtube": random.uniform(0.3, 0.7),
                }),
                status="published" if random.random() > 0.3 else "analyzed",
                discovered_at=discovered_at,
                analyzed_at=discovered_at + timedelta(minutes=random.randint(5, 30)),
            )

            session.add(discovery)
            await session.flush()
            discovery_ids.append(discovery.id)

    await session.commit()
    print(f"✓ Seeded {len(discovery_ids)} discoveries")
    return discovery_ids


async def seed_publications_and_metrics(
    session: AsyncSession,
    discovery_ids: list[int]
):
    """
    Create publications and their engagement metrics.
    Show skill evolution impact on performance.
    """
    print("\nSeeding publications and metrics...")

    target_publications = 180  # ~13 per day over 14 days
    publications_created = 0

    # Sample discoveries for publication
    published_discovery_ids = random.sample(
        discovery_ids,
        min(target_publications, len(discovery_ids))
    )

    for discovery_id in published_discovery_ids:
        # Get discovery
        result = await session.execute(
            select(ContentDiscovery).where(ContentDiscovery.id == discovery_id)
        )
        discovery = result.scalar_one()

        # Choose platform based on weights
        platform = random.choices(
            list(PLATFORMS.keys()),
            weights=[p["weight"] for p in PLATFORMS.values()],
        )[0]

        # Determine skill version based on discovery time
        skill_version = get_skill_version_at_time(
            "linkedin-hook-writing",
            discovery.discovered_at
        )

        # Create content creation
        creation = ContentCreation(
            discovery_id=discovery_id,
            platform=platform,
            format=random.choice(["post", "thread", "short", "article"]),
            title=discovery.title,
            body=f"Generated content for: {discovery.title}",
            skills_used=json.dumps([
                "linkedin-hook-writing",
                "optimal-posting-windows",
                f"{platform}-optimization",
            ]),
            risk_score=random.uniform(0.1, 0.3),
            approval_status="auto_approved" if random.random() > 0.15 else "approved",
            created_at=discovery.analyzed_at,
            approved_at=discovery.analyzed_at + timedelta(minutes=random.randint(2, 15)),
        )

        session.add(creation)
        await session.flush()

        # Create publication
        published_at = creation.approved_at + timedelta(minutes=random.randint(5, 45))
        # Ensure timezone-aware
        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=timezone.utc)

        # Generate realistic platform post IDs
        if platform == "linkedin":
            post_id = f"urn:li:share:{random.randint(7000000000000000000, 7999999999999999999)}"
        elif platform == "twitter":
            post_id = str(random.randint(1600000000000000000, 1699999999999999999))
        elif platform == "youtube":
            post_id = f"YT_{hash_content(str(creation.id))[:11]}"
        elif platform == "medium":
            post_id = f"{hash_content(str(creation.id))[:12]}"
        else:  # tiktok
            post_id = f"TT{random.randint(7000000000000000000, 7999999999999999999)}"

        publication = ContentPublication(
            creation_id=creation.id,
            platform=platform,
            platform_post_id=post_id,
            platform_url=f"https://{platform}.com/post/{post_id}",
            arbitrage_window_minutes=random.randint(60, 720),  # 1-12 hours early
            published_at=published_at,
        )

        session.add(publication)
        await session.flush()

        # Create engagement metrics at intervals
        base_engagement = PLATFORMS[platform]["avg_engagement"]

        # Boost engagement for better skill versions
        engagement_data = generate_engagement_curve(
            base_engagement,
            platform,
            skill_version=skill_version,
        )

        for interval, metrics in engagement_data.items():
            # Only create metrics if enough time has passed
            if interval == "1h":
                metric_time = published_at + timedelta(hours=1)
            elif interval == "6h":
                metric_time = published_at + timedelta(hours=6)
            elif interval == "24h":
                metric_time = published_at + timedelta(hours=24)
            elif interval == "48h":
                metric_time = published_at + timedelta(hours=48)
            else:  # 7d
                metric_time = published_at + timedelta(days=7)

            # Skip if metric time is in the future
            if metric_time > END_DATE:
                continue

            total_engagement = metrics["likes"] + metrics["comments"] + metrics["shares"]
            engagement_rate = total_engagement / max(metrics["views"], 1) if metrics["views"] > 0 else 0.0

            metric = ContentMetric(
                publication_id=publication.id,
                interval=interval,
                views=metrics["views"],
                likes=metrics["likes"],
                comments=metrics["comments"],
                shares=metrics["shares"],
                clicks=metrics["clicks"],
                followers_gained=random.randint(0, 5) if random.random() > 0.7 else 0,
                engagement_rate=round(engagement_rate, 4),
                collected_at=metric_time,
            )

            session.add(metric)

        publications_created += 1

        if publications_created % 20 == 0:
            await session.commit()
            print(f"  Progress: {publications_created}/{target_publications} publications")

    await session.commit()
    print(f"✓ Seeded {publications_created} publications with engagement metrics")


async def seed_experiments(session: AsyncSession):
    """Seed completed A/B experiments with results."""
    print("\nSeeding A/B experiments...")

    experiments = [
        {
            "skill_name": "linkedin-hook-writing",
            "variant_a": "Question hooks (e.g., 'What happens when...')",
            "variant_b": "Statement hooks (e.g., 'The future of...')",
            "metric_target": "engagement_rate",
            "sample_size": 47,
            "variant_a_score": 0.087,
            "variant_b_score": 0.041,
            "winner": "A",
            "started_at": START_DATE + timedelta(days=1),
            "completed_at": START_DATE + timedelta(days=4),
        },
        {
            "skill_name": "optimal-posting-windows",
            "variant_a": "Tuesday 9am PST",
            "variant_b": "Friday 3pm PST",
            "metric_target": "engagement_rate",
            "sample_size": 52,
            "variant_a_score": 0.093,
            "variant_b_score": 0.054,
            "winner": "A",
            "started_at": START_DATE + timedelta(days=2),
            "completed_at": START_DATE + timedelta(days=5),
        },
        {
            "skill_name": "heygen-avatar-video",
            "variant_a": "Direct-to-camera opening",
            "variant_b": "Side-angle framing",
            "metric_target": "views",
            "sample_size": 28,
            "variant_a_score": 4872.0,
            "variant_b_score": 3481.0,
            "winner": "A",
            "started_at": START_DATE + timedelta(days=3),
            "completed_at": START_DATE + timedelta(days=7),
        },
        {
            "skill_name": "twitter-thread-structure",
            "variant_a": "3-tweet threads",
            "variant_b": "5-tweet threads",
            "metric_target": "engagement_rate",
            "sample_size": 41,
            "variant_a_score": 0.112,
            "variant_b_score": 0.089,
            "winner": "A",
            "started_at": START_DATE + timedelta(days=2),
            "completed_at": START_DATE + timedelta(days=6),
        },
        {
            "skill_name": "linkedin-optimization",
            "variant_a": "Technical depth with accessible examples",
            "variant_b": "High-level overview only",
            "metric_target": "shares",
            "sample_size": 38,
            "variant_a_score": 17.2,
            "variant_b_score": 10.1,
            "winner": "A",
            "started_at": START_DATE + timedelta(days=4),
            "completed_at": START_DATE + timedelta(days=8),
        },
        {
            "skill_name": "linkedin-hook-writing",
            "variant_a": "No emoji in professional content",
            "variant_b": "Strategic emoji usage",
            "metric_target": "engagement_rate",
            "sample_size": 44,
            "variant_a_score": 0.081,
            "variant_b_score": 0.058,
            "winner": "A",
            "started_at": START_DATE + timedelta(days=3),
            "completed_at": START_DATE + timedelta(days=7),
        },
        {
            "skill_name": "content-spacing",
            "variant_a": "4-hour minimum gap between same-platform posts",
            "variant_b": "No spacing constraints",
            "metric_target": "engagement_rate",
            "sample_size": 56,
            "variant_a_score": 0.079,
            "variant_b_score": 0.061,
            "winner": "A",
            "started_at": START_DATE + timedelta(days=2),
            "completed_at": START_DATE + timedelta(days=5),
        },
        {
            "skill_name": "medium-article-format",
            "variant_a": "6-8 word titles",
            "variant_b": "12-15 word titles",
            "metric_target": "clicks",
            "sample_size": 31,
            "variant_a_score": 142.3,
            "variant_b_score": 61.8,
            "winner": "A",
            "started_at": START_DATE + timedelta(days=5),
            "completed_at": START_DATE + timedelta(days=9),
        },
    ]

    for exp_data in experiments:
        experiment = ContentExperiment(
            status="completed",
            **exp_data
        )
        session.add(experiment)

    await session.commit()
    print(f"✓ Seeded {len(experiments)} completed A/B experiments")


async def seed_skill_records(session: AsyncSession):
    """Populate skill_records table with all skills and their evolution."""
    print("\nSeeding skill records...")

    # Get all skill files
    library_path = Path(__file__).parent.parent / "skills" / "library"
    skill_files = list(library_path.rglob("*.md"))

    skills_created = 0

    for skill_file in skill_files:
        # Parse skill metadata
        import frontmatter
        post = frontmatter.load(skill_file)
        meta = post.metadata

        skill_name = meta.get("name", skill_file.stem)

        # Determine final version and confidence
        if skill_name in EVOLVING_SKILLS:
            skill_data = EVOLVING_SKILLS[skill_name]
            if skill_data["v3_confidence"]:
                final_version = 3
                final_confidence = skill_data["v3_confidence"]
            else:
                final_version = 2
                final_confidence = skill_data["v2_confidence"]
        else:
            final_version = 1
            final_confidence = 0.5 + random.uniform(0.05, 0.20)

        # Generate realistic usage stats
        total_uses = random.randint(15, 85)
        success_count = int(total_uses * random.uniform(0.65, 0.92))

        skill_record = SkillRecord(
            name=skill_name,
            category=meta.get("category", "tools"),
            platform=meta.get("platform"),
            confidence=round(final_confidence, 4),
            status=meta.get("status", "active"),
            version=final_version,
            total_uses=total_uses,
            success_count=success_count,
            failure_streak=0 if random.random() > 0.1 else random.randint(1, 2),
            tags=json.dumps(meta.get("tags", [])),
            file_path=str(skill_file),
            last_used_at=END_DATE - timedelta(hours=random.randint(1, 48)),
            last_validated_at=END_DATE - timedelta(days=random.randint(1, 5)),
            created_at=START_DATE,
            updated_at=END_DATE - timedelta(days=random.randint(0, 3)),
        )

        session.add(skill_record)
        skills_created += 1

    await session.commit()
    print(f"✓ Seeded {skills_created} skill records")


async def seed_skill_metrics(session: AsyncSession):
    """Generate individual skill usage outcomes."""
    print("\nSeeding skill usage metrics...")

    # Get all skill records
    result = await session.execute(select(SkillRecord))
    skill_records = result.scalars().all()

    metrics_created = 0

    for skill_record in skill_records:
        # Generate metrics based on total_uses
        for use_num in range(skill_record.total_uses):
            # Spread usage over demo period
            used_at = random_datetime(START_DATE, END_DATE)

            # Determine version at this time
            version = get_skill_version_at_time(skill_record.name, used_at)

            # Success likelihood increases with better versions
            if version == 1:
                success_chance = 0.65
            elif version == 2:
                success_chance = 0.80
            else:
                success_chance = 0.88

            outcome = "success" if random.random() < success_chance else "failure"
            score = random.uniform(0.7, 0.95) if outcome == "success" else random.uniform(0.2, 0.5)

            metric = SkillMetric(
                skill_name=skill_record.name,
                agent=random.choice(["creator", "analyst", "engagement"]),
                task=random.choice(["content_creation", "platform_optimization", "engagement"]),
                outcome=outcome,
                score=round(score, 4),
                context=json.dumps({"version": version}),
                recorded_at=used_at,
            )

            session.add(metric)
            metrics_created += 1

            if metrics_created % 50 == 0:
                await session.commit()

    await session.commit()
    print(f"✓ Seeded {metrics_created} skill usage metrics")


async def seed_agent_runs(session: AsyncSession):
    """Generate agent run logs with cost tracking."""
    print("\nSeeding agent execution logs...")

    # Agents and their characteristics
    agents = {
        "scout": {"avg_tokens": 2500, "runs_per_day": 4},
        "analyst": {"avg_tokens": 8000, "runs_per_day": 15},
        "creator": {"avg_tokens": 12000, "runs_per_day": 13},
        "engagement": {"avg_tokens": 3500, "runs_per_day": 8},
        "tracker": {"avg_tokens": 1500, "runs_per_day": 20},
        "reviewer": {"avg_tokens": 5000, "runs_per_day": 5},
    }

    # Bedrock pricing (approximate for Claude Sonnet)
    INPUT_COST_PER_1K = 0.003
    OUTPUT_COST_PER_1K = 0.015

    runs_created = 0
    total_cost = 0.0

    for day in range(DEMO_DAYS):
        day_start = START_DATE + timedelta(days=day)
        day_end = day_start + timedelta(days=1)

        for agent_name, agent_config in agents.items():
            runs_today = agent_config["runs_per_day"]

            for _ in range(runs_today):
                started_at = random_datetime(day_start, day_end)
                duration = random.uniform(2.0, 30.0)
                completed_at = started_at + timedelta(seconds=duration)

                # Token counts with variation
                base_tokens = agent_config["avg_tokens"]
                input_tokens = int(base_tokens * random.uniform(0.7, 1.3))
                output_tokens = int((base_tokens * 0.3) * random.uniform(0.6, 1.4))

                # Cost calculation
                cost = (
                    (input_tokens / 1000) * INPUT_COST_PER_1K +
                    (output_tokens / 1000) * OUTPUT_COST_PER_1K
                )
                total_cost += cost

                # 95% success rate
                status = "completed" if random.random() > 0.05 else "failed"

                agent_run = ContentAgentRun(
                    agent=agent_name,
                    task=random.choice([
                        "source_scanning",
                        "content_analysis",
                        "content_creation",
                        "risk_assessment",
                        "engagement_tracking",
                        "skill_review",
                    ]),
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    estimated_cost_usd=round(cost, 6),
                    duration_seconds=round(duration, 2),
                    status=status,
                    error="Timeout" if status == "failed" and random.random() > 0.5 else None,
                    started_at=started_at,
                    completed_at=completed_at,
                )

                session.add(agent_run)
                runs_created += 1

                if runs_created % 50 == 0:
                    await session.commit()

    await session.commit()
    print(f"✓ Seeded {runs_created} agent runs")
    print(f"  Total cost: ${total_cost:.2f} over {DEMO_DAYS} days")


async def create_skill_versions():
    """Create version files for evolved skills."""
    print("\nCreating skill version files...")

    versions_dir = Path(__file__).parent.parent / "skills" / "versions"
    versions_dir.mkdir(parents=True, exist_ok=True)

    # linkedin-hook-writing v2
    linkedin_v2_dir = versions_dir / "linkedin-hook-writing"
    linkedin_v2_dir.mkdir(exist_ok=True)

    (linkedin_v2_dir / "v2.md").write_text("""---
name: linkedin-hook-writing
category: creation
platform: linkedin
confidence: 0.67
status: active
version: 2
tags: [hooks, copywriting, engagement-drivers, questions]
change_reason: "Discovered question hooks get 2.1x engagement vs statements"
---
# LinkedIn Hook Writing v2

## When to Use
Apply when creating the opening lines of LinkedIn posts. The hook determines 80% of engagement.

## Brand Voice
Calm, confident, technical, grounded. Builder-to-builder. No buzzwords, no exclamation points, no sales CTAs. Short paragraphs, declarative statements, minimal adjectives, one idea per paragraph.

## Core Patterns (UPDATED)
- **Question hooks [PRIMARY]**: "What happens when..." — creates curiosity gap (2.1x engagement boost)
- Contrarian hooks: "Most teams are wrong about..." — challenges assumptions
- Data hooks: "We analyzed 1,000 AI deployments..." — establishes authority
- Story hooks: "Last Tuesday, our system caught something..." — narrative pull
- Statement hooks: "The future of work isn't AI replacing humans." — bold claim

## Question Hook Formulas
- "What happens when [unexpected combination]?"
- "Why do [surprising fact]?"
- "How does [technical detail] actually work?"
- "When should you [contrarian advice]?"

## Structure
1. Hook line (< 15 words, preferably a question)
2. One-line expansion
3. Blank line (forces "see more" click)
4. Body content (3-5 short paragraphs)
5. Closing thought (no CTA, no question)

## What to Avoid
- Starting with "I'm excited to announce..."
- Exclamation points anywhere
- Hashtag-heavy openings
- "Revolutionary", "game-changing", "leverage AI"
- Rhetorical or salesy questions

## Performance Notes
A/B test (n=47): Question hooks 0.087 engagement rate vs statements 0.041. Winner: questions.
Uses: 35 | Success rate: 82% | Last validated: day 4
""")

    (linkedin_v2_dir / "v3.md").write_text("""---
name: linkedin-hook-writing
category: creation
platform: linkedin
confidence: 0.82
status: active
version: 3
tags: [hooks, copywriting, engagement-drivers, questions, technical]
change_reason: "Refined question patterns - technical 'how' and 'why' outperform generic 'what'"
---
# LinkedIn Hook Writing v3

## When to Use
Apply when creating the opening lines of LinkedIn posts. The hook determines 80% of engagement.

## Brand Voice
Calm, confident, technical, grounded. Builder-to-builder. No buzzwords, no exclamation points, no sales CTAs. Short paragraphs, declarative statements, minimal adjectives, one idea per paragraph.

## Core Patterns (REFINED)
- **Technical question hooks [PRIMARY]**: "How does [system] actually handle..." or "Why does [behavior] happen when..."
  - Technical 'how' questions: 1.4x boost over generic questions
  - Technical 'why' questions: 1.3x boost over generic questions
- **Counter-intuitive questions**: "Why is [common practice] actually wrong?"
- Data hooks: "We analyzed 1,000 AI deployments..." — establishes authority
- Story hooks: "Last Tuesday, our system caught something..." — narrative pull

## Best-Performing Question Types (by engagement)
1. "How does X actually work?" (technical deep-dive)
2. "Why does Y happen when..." (debugging mindset)
3. "What happens when [unexpected combo]?" (curiosity)
4. "When should you ignore [conventional wisdom]?" (contrarian)

## Structure
1. Technical question hook (< 15 words)
2. One-line answer preview (creates information gap)
3. Blank line (forces "see more" click)
4. Body content (3-5 short paragraphs, technical but accessible)
5. Closing insight (no CTA, no question)

## What to Avoid
- Generic questions ("What is AI?")
- Yes/no questions
- Exclamation points anywhere
- "Revolutionary", "game-changing", "leverage AI"
- Questions about feelings or opinions

## Performance Notes
Evolution: v1 (0.5) → v2 question focus (0.67, +34%) → v3 technical refinement (0.82, +22%)
Pattern: Technical how/why questions in our niche = 2.8x baseline engagement
Uses: 73 | Success rate: 88% | Last validated: day 9
""")

    # optimal-posting-windows v2
    posting_v2_dir = versions_dir / "optimal-posting-windows"
    posting_v2_dir.mkdir(exist_ok=True)

    (posting_v2_dir / "v2.md").write_text("""---
name: optimal-posting-windows
category: timing
confidence: 0.71
status: active
version: 2
tags: [timing, scheduling, engagement, platform-specific]
change_reason: "Discovered Tuesday 9am PST crushes all other times for LinkedIn"
---
# Optimal Posting Windows v2

## When to Use
Apply when scheduling content publication across platforms.

## Platform-Specific Windows (UPDATED)

### LinkedIn [HIGH CONFIDENCE]
- **Primary: Tuesday 9am PST** (1.7x engagement vs other times)
- Secondary: Wednesday 8am PST
- Avoid: Friday afternoons, weekends

### Twitter/X
- Primary: Thursday 11am-1pm PST
- Secondary: Tuesday 3pm PST
- High variance - trending topics override timing

### YouTube Shorts
- Primary: Saturday 10am PST
- Secondary: Wednesday 7pm PST
- Weekend consumption patterns

### Medium
- Primary: Monday 7am PST (commute reading)
- Secondary: Sunday 8pm PST
- Lower time sensitivity

### TikTok
- Primary: Friday 6pm PST
- Secondary: Tuesday 9am PST
- Very high variance

## Key Insights
- B2B platforms (LinkedIn): Early week mornings
- Consumer platforms (TikTok): Evenings and weekends
- Tuesday is universally strong across platforms
- Friday is weak for professional content

## Performance Notes
A/B test (n=52): Tuesday 9am 0.093 engagement vs Friday 3pm 0.054. Winner: Tuesday.
Uses: 48 | Success rate: 79% | Last validated: day 5
""")

    print(f"✓ Created skill version files in {versions_dir}")


# ============================================================================
# Main
# ============================================================================

async def seed_demo_data(clear_existing: bool = True, verbose: bool = False):
    """
    Seed 14 days of demo data. Safe to call from main.py startup.

    Args:
        clear_existing: If True, clear existing data before seeding
        verbose: If True, print detailed progress messages
    """
    import logging
    logger = logging.getLogger(__name__)

    if verbose:
        print("=" * 70)
        print("Content Autopilot Demo Data Seeder")
        print("=" * 70)
        print(f"Demo period: {START_DATE.date()} to {END_DATE.date()} ({DEMO_DAYS} days)")
        print()

    # Create tables
    if verbose:
        print("Initializing database...")
    await create_tables()

    async with async_session() as session:
        # Optionally clear existing data
        if clear_existing:
            if verbose:
                print("\nClearing existing demo data...")
            logger.info("Clearing existing demo data...")
            await session.execute(delete(ContentMetric))
            await session.execute(delete(ContentPublication))
            await session.execute(delete(ContentCreation))
            await session.execute(delete(ContentExperiment))
            await session.execute(delete(SkillMetric))
            await session.execute(delete(SkillRecord))
            await session.execute(delete(ContentAgentRun))
            await session.execute(delete(ContentDiscovery))
            await session.commit()
            if verbose:
                print("✓ Cleared tables")

        # Run seeding operations
        logger.info("Seeding playbook...")
        await seed_playbook(session)

        logger.info("Seeding discoveries...")
        discovery_ids = await seed_discoveries(session)

        logger.info("Seeding publications and metrics...")
        await seed_publications_and_metrics(session, discovery_ids)

        logger.info("Seeding experiments...")
        await seed_experiments(session)

        logger.info("Seeding skill records...")
        await seed_skill_records(session)

        logger.info("Seeding skill metrics...")
        await seed_skill_metrics(session)

        logger.info("Seeding agent runs...")
        await seed_agent_runs(session)

    # Create version files
    logger.info("Creating skill version files...")
    await create_skill_versions()

    if verbose:
        print("\n" + "=" * 70)
        print("Demo data seeding complete!")
        print("=" * 70)
        print("\nNext steps:")
        print("1. Start the system: python main.py")
        print("2. Open dashboard: http://localhost:8001")
        print("3. Navigate to Skills view to see evolution")
        print("4. Check Metrics view for engagement data")
        print("5. Review Experiments view for A/B test results")
        print()


async def main():
    """CLI entry point for manual seeding."""
    await seed_demo_data(clear_existing=True, verbose=True)


if __name__ == "__main__":
    asyncio.run(main())
