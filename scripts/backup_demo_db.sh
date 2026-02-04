#!/bin/bash
# Backup the current demo database
# Usage: ./scripts/backup_demo_db.sh

set -e

echo "=============================================="
echo "Autopilot - Database Backup"
echo "=============================================="
echo ""

# Check if autopilot.db exists
if [ ! -f autopilot.db ]; then
    echo "✗ No autopilot.db file found in current directory"
    echo "  Run this script from the content-autopilot root directory"
    exit 1
fi

# Create backup
BACKUP_FILE="autopilot_demo_backup.db"
echo "Creating backup: ${BACKUP_FILE}"
cp autopilot.db "${BACKUP_FILE}"

# Get file sizes
ORIGINAL_SIZE=$(du -h autopilot.db | cut -f1)
BACKUP_SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)

echo "✓ Backup created successfully"
echo ""
echo "Original: autopilot.db (${ORIGINAL_SIZE})"
echo "Backup:   ${BACKUP_FILE} (${BACKUP_SIZE})"
echo ""

# Count records in key tables
if command -v sqlite3 &> /dev/null; then
    echo "Database contents:"
    echo "  Publications:  $(sqlite3 autopilot.db 'SELECT COUNT(*) FROM content_publications')"
    echo "  Discoveries:   $(sqlite3 autopilot.db 'SELECT COUNT(*) FROM content_discoveries')"
    echo "  Creations:     $(sqlite3 autopilot.db 'SELECT COUNT(*) FROM content_creations')"
    echo "  Skills:        $(sqlite3 autopilot.db 'SELECT COUNT(*) FROM skill_records')"
    echo "  Agent runs:    $(sqlite3 autopilot.db 'SELECT COUNT(*) FROM content_agent_runs')"
    echo ""
fi

echo "Use './scripts/rollback_to_demo.sh' to restore this backup"
echo ""
