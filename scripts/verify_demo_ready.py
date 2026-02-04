#!/usr/bin/env python3
"""
Quick verification script to check if demo is ready.

Run with: python scripts/verify_demo_ready.py
"""

import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
from sqlalchemy import select, func
from db import async_session
from models import (
    ContentPublication,
    ContentMetric,
    ContentExperiment,
    SkillRecord,
    SkillMetric,
    ContentAgentRun,
    ContentDiscovery,
)


async def verify():
    """Check if demo data is seeded and ready."""
    print("=" * 70)
    print("Content Autopilot - Demo Readiness Check")
    print("=" * 70)
    print()

    issues = []
    warnings = []

    async with async_session() as session:
        # Check publications
        pub_count = (await session.execute(select(func.count(ContentPublication.id)))).scalar() or 0
        print(f"✓ Publications: {pub_count}")
        if pub_count < 100:
            issues.append(f"Only {pub_count} publications (expected ~180)")

        # Check metrics
        metric_count = (await session.execute(select(func.count(ContentMetric.id)))).scalar() or 0
        print(f"✓ Engagement metrics: {metric_count}")
        if metric_count < 500:
            issues.append(f"Only {metric_count} metrics (expected ~1000)")

        # Check experiments
        exp_count = (await session.execute(select(func.count(ContentExperiment.id)))).scalar() or 0
        print(f"✓ A/B experiments: {exp_count}")
        if exp_count < 8:
            issues.append(f"Only {exp_count} experiments (expected 8)")

        # Check skill records
        skill_count = (await session.execute(select(func.count(SkillRecord.id)))).scalar() or 0
        print(f"✓ Skill records: {skill_count}")
        if skill_count < 21:
            issues.append(f"Only {skill_count} skill records (expected 21)")

        # Check skill metrics
        skill_metric_count = (await session.execute(select(func.count(SkillMetric.id)))).scalar() or 0
        print(f"✓ Skill usage metrics: {skill_metric_count}")
        if skill_metric_count < 200:
            warnings.append(f"Only {skill_metric_count} skill metrics (expected ~500)")

        # Check agent runs
        run_count = (await session.execute(select(func.count(ContentAgentRun.id)))).scalar() or 0
        print(f"✓ Agent runs: {run_count}")
        if run_count < 500:
            warnings.append(f"Only {run_count} agent runs (expected ~1000)")

        # Check discoveries
        disc_count = (await session.execute(select(func.count(ContentDiscovery.id)))).scalar() or 0
        print(f"✓ Discoveries: {disc_count}")
        if disc_count < 200:
            warnings.append(f"Only {disc_count} discoveries (expected ~270)")

        # Check for evolved skills
        evolved_skills = (await session.execute(
            select(SkillRecord).where(SkillRecord.version > 1)
        )).scalars().all()
        evolved_count = len(evolved_skills)
        print(f"✓ Evolved skills: {evolved_count}")
        if evolved_count < 6:
            issues.append(f"Only {evolved_count} evolved skills (expected 6)")
        if evolved_count > 0:
            print("  Evolved skills:")
            for skill in evolved_skills:
                print(f"    - {skill.name}: v{skill.version} (confidence {skill.confidence:.2f})")

        # Check completed experiments
        completed_exps = (await session.execute(
            select(ContentExperiment).where(ContentExperiment.status == "completed")
        )).scalars().all()
        completed_count = len(completed_exps)
        print(f"✓ Completed experiments: {completed_count}")
        if completed_count > 0:
            print("  Experiments:")
            for exp in completed_exps[:3]:  # Show first 3
                winner_score = exp.variant_a_score if exp.winner == "A" else exp.variant_b_score
                print(f"    - {exp.skill_name}: {exp.winner or 'TBD'} won ({winner_score:.2f})")

    # Check skill version files
    print()
    print("Checking skill version files...")
    versions_dir = Path(__file__).parent.parent / "skills" / "versions"
    if versions_dir.exists():
        version_files = list(versions_dir.rglob("*.md"))
        print(f"✓ Skill version files: {len(version_files)}")
        if len(version_files) > 0:
            print("  Version files found:")
            for vf in sorted(version_files)[:5]:  # Show first 5
                print(f"    - {vf.relative_to(versions_dir)}")
        if len(version_files) < 8:
            warnings.append(f"Only {len(version_files)} version files (expected 8+)")
    else:
        issues.append("skills/versions/ directory does not exist")

    # Summary
    print()
    print("=" * 70)
    if issues:
        print("❌ ISSUES FOUND:")
        for issue in issues:
            print(f"  - {issue}")
        print()
        print("ACTION REQUIRED: Run 'python scripts/seed_demo_data.py'")
    elif warnings:
        print("⚠️  WARNINGS:")
        for warning in warnings:
            print(f"  - {warning}")
        print()
        print("Demo should work, but data might be incomplete.")
    else:
        print("✅ DEMO READY!")
        print()
        print("Next steps:")
        print("  1. python main.py")
        print("  2. Open http://localhost:8001")
        print("  3. Navigate through Skills, Metrics, Experiments views")
        print("  4. Practice demo from DEMO_SCRIPT.md")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(verify())
