#!/usr/bin/env python3
"""Schema drift detection and repair utility for the Content Autopilot demo.

This lightweight script checks for common schema drift issues (missing indexes,
columns) without requiring full Alembic migrations. Suitable for demo projects.

Usage:
    python scripts/sync_schema.py          # Report drift only
    python scripts/sync_schema.py --fix    # Apply fixes
"""

import argparse
import sqlite3
import sys
from pathlib import Path

# Database path (relative to project root)
DB_PATH = Path(__file__).parent.parent / "autopilot.db"

# Expected indexes: (index_name, table_name, column_name)
# Only list indexes that are defined with index=True in models.py
EXPECTED_INDEXES = [
    # ContentDiscovery
    ("ix_content_discoveries_source", "content_discoveries", "source"),
    ("ix_content_discoveries_content_hash", "content_discoveries", "content_hash"),
    ("ix_content_discoveries_status", "content_discoveries", "status"),
    # ContentCreation
    ("ix_content_creations_discovery_id", "content_creations", "discovery_id"),
    ("ix_content_creations_platform", "content_creations", "platform"),
    ("ix_content_creations_variant_group", "content_creations", "variant_group"),
    # ContentPublication
    ("ix_content_publications_creation_id", "content_publications", "creation_id"),
    ("ix_content_publications_platform", "content_publications", "platform"),
    # ContentMetric
    ("ix_content_metrics_publication_id", "content_metrics", "publication_id"),
    # ContentExperiment
    ("ix_content_experiments_skill_name", "content_experiments", "skill_name"),
    # ContentAgentRun
    ("ix_content_agent_runs_agent", "content_agent_runs", "agent"),
    ("ix_content_agent_runs_provider", "content_agent_runs", "provider"),
    # SkillRecord
    ("ix_skill_records_name", "skill_records", "name"),
    ("ix_skill_records_category", "skill_records", "category"),
    ("ix_skill_records_status", "skill_records", "status"),
    # SkillMetric
    ("ix_skill_metrics_skill_name", "skill_metrics", "skill_name"),
    # SkillComparison
    ("ix_skill_comparisons_skill_a", "skill_comparisons", "skill_a"),
    ("ix_skill_comparisons_skill_b", "skill_comparisons", "skill_b"),
    # EngagementAction
    ("ix_engagement_actions_action_type", "engagement_actions", "action_type"),
    ("ix_engagement_actions_platform", "engagement_actions", "platform"),
    ("ix_engagement_actions_publication_id", "engagement_actions", "publication_id"),
]

# Expected columns that may be missing: (table_name, column_name, column_def)
EXPECTED_COLUMNS = [
    ("content_agent_runs", "provider", "TEXT"),
]


def get_existing_indexes(conn: sqlite3.Connection) -> set:
    """Get all existing index names from the database."""
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'ix_%'"
    )
    return {row[0] for row in cursor.fetchall()}


def get_table_columns(conn: sqlite3.Connection, table_name: str) -> set:
    """Get all column names for a table."""
    cursor = conn.execute(f"PRAGMA table_info({table_name})")
    return {row[1] for row in cursor.fetchall()}


def table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    """Check if a table exists in the database."""
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    )
    return cursor.fetchone() is not None


def check_drift(conn: sqlite3.Connection) -> tuple[list, list]:
    """Check for schema drift. Returns (missing_indexes, missing_columns)."""
    existing_indexes = get_existing_indexes(conn)
    missing_indexes = []

    for index_name, table_name, column_name in EXPECTED_INDEXES:
        # Skip indexes for tables that don't exist yet
        if not table_exists(conn, table_name):
            continue
        if index_name not in existing_indexes:
            missing_indexes.append((index_name, table_name, column_name))

    missing_columns = []
    for table_name, column_name, column_def in EXPECTED_COLUMNS:
        # Skip columns for tables that don't exist yet
        if not table_exists(conn, table_name):
            continue
        columns = get_table_columns(conn, table_name)
        if column_name not in columns:
            missing_columns.append((table_name, column_name, column_def))

    return missing_indexes, missing_columns


def fix_drift(conn: sqlite3.Connection, missing_indexes: list, missing_columns: list) -> None:
    """Apply fixes for detected schema drift."""
    cursor = conn.cursor()

    # Fix missing columns first (indexes may depend on them)
    for table_name, column_name, column_def in missing_columns:
        print(f"  Adding column {table_name}.{column_name}...")
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}")

    # Fix missing indexes
    for index_name, table_name, column_name in missing_indexes:
        print(f"  Creating index {index_name}...")
        cursor.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({column_name})")

    conn.commit()


def main():
    parser = argparse.ArgumentParser(description="Detect and fix schema drift")
    parser.add_argument("--fix", action="store_true", help="Apply fixes for detected drift")
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"Database not found at {DB_PATH}")
        print("Run the server first to create the database: python main.py")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)

    try:
        missing_indexes, missing_columns = check_drift(conn)

        if not missing_indexes and not missing_columns:
            print("No schema drift detected. Database is in sync with models.")
            sys.exit(0)

        print("Schema drift detected:")
        print()

        if missing_columns:
            print("Missing columns:")
            for table_name, column_name, column_def in missing_columns:
                print(f"  - {table_name}.{column_name} ({column_def})")
            print()

        if missing_indexes:
            print("Missing indexes:")
            for index_name, table_name, column_name in missing_indexes:
                print(f"  - {index_name} on {table_name}({column_name})")
            print()

        if args.fix:
            print("Applying fixes...")
            fix_drift(conn, missing_indexes, missing_columns)
            print("Done. Schema is now in sync.")
        else:
            print("Run with --fix to apply these changes:")
            print(f"  python {Path(__file__).name} --fix")
            sys.exit(1)

    finally:
        conn.close()


if __name__ == "__main__":
    main()
