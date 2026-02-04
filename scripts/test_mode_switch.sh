#!/bin/bash
# Quick test to verify demo/production mode switching works
# Usage: ./scripts/test_mode_switch.sh

set -e

PORT=8001
BASE_URL="http://localhost:${PORT}"

echo "=============================================="
echo "Autopilot - Mode Switch Test"
echo "=============================================="
echo ""

# Function to check if app is running
check_app() {
    if curl -s "${BASE_URL}/pipeline" > /dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Function to get demo mode status
get_demo_mode() {
    curl -s "${BASE_URL}/pipeline" | grep -o '"demo_mode":[^,}]*' | cut -d':' -f2 | tr -d ' '
}

# Function to count publications
count_publications() {
    curl -s "${BASE_URL}/pipeline" | grep -o '"publications":[0-9]*' | cut -d':' -f2
}

echo "Testing Mode Switching Functionality"
echo ""

# Test 1: Check app is running
echo "1. Checking if app is running on port ${PORT}..."
if check_app; then
    echo "   ✓ App is running"
else
    echo "   ✗ App is not running - start with: python main.py"
    exit 1
fi

# Test 2: Get current mode
echo ""
echo "2. Checking current mode..."
CURRENT_MODE=$(get_demo_mode)
PUB_COUNT=$(count_publications)
echo "   Demo mode: ${CURRENT_MODE}"
echo "   Publications: ${PUB_COUNT}"

# Test 3: Verify expected behavior
echo ""
echo "3. Verifying mode configuration..."
if [ "$CURRENT_MODE" = "true" ]; then
    echo "   Running in DEMO MODE"
    if [ "$PUB_COUNT" -gt 0 ]; then
        echo "   ✓ Demo data present (${PUB_COUNT} publications)"
    else
        echo "   ⚠️  Warning: Demo mode but no publications (was demo data seeded?)"
    fi
else
    echo "   Running in PRODUCTION MODE"
    echo "   ℹ️  Publications will appear as content is created"
fi

# Test 4: Check cost tracking
echo ""
echo "4. Checking cost tracking..."
COST_DATA=$(curl -s "${BASE_URL}/costs")
if echo "$COST_DATA" | grep -q "total_cost_usd"; then
    if command -v jq &> /dev/null; then
        TOTAL_COST=$(echo "$COST_DATA" | jq -r '.total_cost_usd')
        COST_TODAY=$(echo "$COST_DATA" | jq -r '.cost_today_usd')
        echo "   ✓ Cost tracking enabled"
        echo "   Total cost: \$${TOTAL_COST}"
        echo "   Cost today: \$${COST_TODAY}"
    else
        echo "   ✓ Cost tracking enabled (install jq for details)"
    fi
else
    echo "   ✗ Cost tracking not working"
fi

# Test 5: Check skills loaded
echo ""
echo "5. Checking skills system..."
SKILLS_DATA=$(curl -s "${BASE_URL}/skills")
if command -v jq &> /dev/null; then
    SKILL_COUNT=$(echo "$SKILLS_DATA" | jq 'length')
    echo "   ✓ ${SKILL_COUNT} skills loaded"

    # Show top 3 skills by confidence
    echo ""
    echo "   Top 3 skills by confidence:"
    echo "$SKILLS_DATA" | jq -r '.[:3] | .[] | "     - \(.name): \(.confidence)"'
else
    echo "   ✓ Skills endpoint responding (install jq for details)"
fi

# Test 6: Manual trigger test (if in demo mode)
if [ "$CURRENT_MODE" = "true" ]; then
    echo ""
    echo "6. Testing manual scout trigger (demo mode only)..."
    echo "   Triggering scout..."
    TRIGGER_RESULT=$(curl -s -X POST "${BASE_URL}/discover")
    if echo "$TRIGGER_RESULT" | grep -q "completed"; then
        echo "   ✓ Manual trigger works"
    else
        echo "   ⚠️  Trigger may have failed - check logs"
    fi
fi

echo ""
echo "=============================================="
echo "Test Summary"
echo "=============================================="
echo ""
echo "Current Configuration:"
echo "  Mode:         $([ "$CURRENT_MODE" = "true" ] && echo "DEMO" || echo "PRODUCTION")"
echo "  Publications: ${PUB_COUNT}"
echo "  Port:         ${PORT}"
echo ""

if [ "$CURRENT_MODE" = "true" ]; then
    echo "To switch to PRODUCTION mode:"
    echo "  1. Backup demo DB:    ./scripts/backup_demo_db.sh"
    echo "  2. Update .env:       DEMO_MODE=false"
    echo "  3. Restart app:       pkill -f 'python main.py' && python main.py"
else
    echo "To switch to DEMO mode:"
    echo "  1. Run rollback:      ./scripts/rollback_to_demo.sh"
    echo "  2. Restart app:       python main.py"
fi

echo ""
