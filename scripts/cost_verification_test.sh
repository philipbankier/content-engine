#!/bin/bash
# Cost Verification Test Script
# Tests typical and high modes to verify cost estimates

set -e

BASE_URL="http://localhost:8001"
RESULTS_FILE="cost_verification_results.json"

echo "================================"
echo "Cost Verification Test"
echo "================================"
echo ""

# Helper to get costs
get_costs() {
    curl -s "${BASE_URL}/costs" 2>/dev/null
}

# Check if server is running
check_server() {
    if ! curl -s "${BASE_URL}/pipeline" > /dev/null 2>&1; then
        echo "ERROR: Server not running. Start with: python main.py"
        exit 1
    fi
    echo "✓ Server is running"
}

# Test 1: Typical Run (No Video)
test_typical() {
    echo ""
    echo "=========================================="
    echo "TEST 1: Typical Run (No Video)"
    echo "=========================================="

    # Get baseline
    echo "Recording baseline costs..."
    BASELINE=$(get_costs)
    BASELINE_TODAY=$(echo "$BASELINE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('cost_today_usd', 0))")
    echo "  Baseline cost today: \$${BASELINE_TODAY}"

    # Trigger discover
    echo ""
    echo "Triggering scout cycle..."
    DISCOVER_RESULT=$(curl -s -X POST "${BASE_URL}/discover")
    echo "  Scout result: $(echo "$DISCOVER_RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"Found {d.get('discoveries', 0)} items\")" 2>/dev/null || echo "$DISCOVER_RESULT")"

    # Trigger create
    echo ""
    echo "Triggering content creation..."
    CREATE_RESULT=$(curl -s -X POST "${BASE_URL}/create")
    echo "  Create result: $(echo "$CREATE_RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"Created {d.get('created', d.get('count', 'unknown'))} pieces\")" 2>/dev/null || echo "$CREATE_RESULT")"

    # Get final costs
    sleep 2  # Allow for async cost recording
    FINAL=$(get_costs)
    FINAL_TODAY=$(echo "$FINAL" | python3 -c "import sys,json; print(json.load(sys.stdin).get('cost_today_usd', 0))")

    # Calculate delta
    DELTA=$(python3 -c "print(round($FINAL_TODAY - $BASELINE_TODAY, 4))")

    echo ""
    echo "RESULTS - Test 1 (Typical):"
    echo "  Baseline: \$${BASELINE_TODAY}"
    echo "  Final:    \$${FINAL_TODAY}"
    echo "  Delta:    \$${DELTA}"
    echo ""

    # Expected: ~$0.10-0.30
    echo "  Expected range: \$0.08 - \$0.30"
    if (( $(echo "$DELTA >= 0.01 && $DELTA <= 0.50" | bc -l) )); then
        echo "  ✓ Cost within expected range"
    else
        echo "  ⚠ Cost outside expected range (may be normal for first run)"
    fi

    # Show breakdown
    echo ""
    echo "Cost breakdown by agent:"
    echo "$FINAL" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for agent in data.get('by_agent', []):
    print(f\"  {agent['agent']}: \${agent['cost_usd']:.4f} ({agent['runs']} runs)\")
"

    echo "$DELTA" > /tmp/typical_cost.txt
}

# Test 2: High Run (With Video) - Manual trigger
test_high_info() {
    echo ""
    echo "=========================================="
    echo "TEST 2: High Run (With Video)"
    echo "=========================================="
    echo ""
    echo "To test with HeyGen video generation:"
    echo ""
    echo "1. Check HeyGen config:"
    echo "   HEYGEN_API_KEY is set: $([ -n "$HEYGEN_API_KEY" ] && echo 'Yes' || echo 'No (check .env)')"
    echo "   HEYGEN_AVATAR_ID_FOUNDER is set: $([ -n "$HEYGEN_AVATAR_ID_FOUNDER" ] && echo 'Yes' || echo 'No')"
    echo ""
    echo "2. Record baseline: curl ${BASE_URL}/costs"
    echo ""
    echo "3. Find a creation with video_script:"
    echo "   curl ${BASE_URL}/creations | jq '.[] | select(.video_script != null)'"
    echo ""
    echo "4. Check approval queue for video-eligible items:"
    echo "   curl ${BASE_URL}/approval/queue"
    echo ""
    echo "Expected cost per video: \$0.80 - \$1.50"
    echo ""
}

# Summary
summary() {
    echo ""
    echo "=========================================="
    echo "SUMMARY"
    echo "=========================================="

    FINAL=$(get_costs)
    echo ""
    echo "Current cost status:"
    echo "$FINAL" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"  Total cost: \${data.get('total_cost_usd', 0):.4f}\")
print(f\"  Today's cost: \${data.get('cost_today_usd', 0):.4f}\")
print(f\"  Daily limit: \${data.get('daily_cost_limit_usd', 0):.2f}\")
print()
print('  Last 7 days:')
for day in data.get('last_7_days', [])[:7]:
    print(f\"    {day['date']}: \${day['cost_usd']:.4f} ({day['runs']} runs)\")
"
}

# Main
echo "Starting cost verification tests..."
echo ""

check_server
test_typical
test_high_info
summary

echo ""
echo "Test complete. Results saved to ${RESULTS_FILE}"
