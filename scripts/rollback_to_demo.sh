#!/bin/bash
# Rollback to demo mode with backup database
# Usage: ./scripts/rollback_to_demo.sh

set -e

echo "=============================================="
echo "Autopilot - Rollback to Demo Mode"
echo "=============================================="
echo ""

# Stop running app
echo "1. Stopping running app..."
pkill -f "python main.py" || echo "   (no running process found)"
pkill -f "uvicorn main:app" || true
sleep 1
echo "   ✓ App stopped"

# Restore backup if it exists
if [ -f autopilot_demo_backup.db ]; then
    echo "2. Restoring database from backup..."
    cp autopilot_demo_backup.db autopilot.db
    echo "   ✓ Database restored from autopilot_demo_backup.db"
else
    echo "2. No backup found - demo data will be reseeded on startup"
fi

# Update .env to demo mode
echo "3. Updating configuration to demo mode..."
if [ -f .env ]; then
    # Update existing .env
    if grep -q "^DEMO_MODE=" .env; then
        sed -i.bak 's/^DEMO_MODE=.*/DEMO_MODE=true/' .env
    else
        echo "DEMO_MODE=true" >> .env
    fi

    if grep -q "^SEED_ON_STARTUP=" .env; then
        # If backup exists, don't reseed; otherwise reseed
        if [ -f autopilot_demo_backup.db ]; then
            sed -i.bak 's/^SEED_ON_STARTUP=.*/SEED_ON_STARTUP=false/' .env
        else
            sed -i.bak 's/^SEED_ON_STARTUP=.*/SEED_ON_STARTUP=true/' .env
        fi
    else
        if [ -f autopilot_demo_backup.db ]; then
            echo "SEED_ON_STARTUP=false" >> .env
        else
            echo "SEED_ON_STARTUP=true" >> .env
        fi
    fi

    # Clean up backup file
    rm -f .env.bak
    echo "   ✓ Configuration updated"
else
    echo "   ✗ No .env file found - please create one from .env.example"
    exit 1
fi

echo ""
echo "=============================================="
echo "Rollback complete!"
echo "=============================================="
echo ""
echo "Next steps:"
echo "  1. Restart the app: python main.py"
echo "  2. Open dashboard: http://localhost:8001"
echo ""
echo "The app will start in DEMO MODE with:"
if [ -f autopilot_demo_backup.db ]; then
    echo "  - Restored demo data (no reseeding)"
else
    echo "  - Fresh demo data (reseeding on startup)"
fi
echo "  - Manual triggers only (no auto-scheduling)"
echo ""
