#!/bin/bash
# Real-time cost monitoring for 24-hour test runs
# Usage: ./scripts/monitor_costs.sh [interval_seconds]

INTERVAL=${1:-300}  # Default: check every 5 minutes (300 seconds)
PORT=${PORT:-8001}

echo "=============================================="
echo "Autopilot - Cost Monitor"
echo "=============================================="
echo "Checking costs every ${INTERVAL} seconds"
echo "Press Ctrl+C to stop"
echo ""

while true; do
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

    # Fetch cost data
    COST_DATA=$(curl -s "http://localhost:${PORT}/costs")

    if [ $? -eq 0 ]; then
        # Extract key metrics using jq if available, otherwise basic parsing
        if command -v jq &> /dev/null; then
            TOTAL_COST=$(echo "$COST_DATA" | jq -r '.total_cost_usd')
            COST_TODAY=$(echo "$COST_DATA" | jq -r '.cost_today_usd')
            COST_LIMIT=$(echo "$COST_DATA" | jq -r '.daily_cost_limit_usd')
            TOTAL_TOKENS=$(echo "$COST_DATA" | jq -r '(.total_input_tokens + .total_output_tokens)')

            echo "[$TIMESTAMP] Total: \$${TOTAL_COST} | Today: \$${COST_TODAY} / \$${COST_LIMIT} | Tokens: ${TOTAL_TOKENS}"

            # Check if we're approaching the limit
            if (( $(echo "$COST_TODAY >= $COST_LIMIT * 0.8" | bc -l) )); then
                echo "  ⚠️  WARNING: Approaching daily cost limit (80%+)"
            fi

            if (( $(echo "$COST_TODAY >= $COST_LIMIT" | bc -l) )); then
                echo "  🚨 ALERT: Daily cost limit exceeded!"
            fi
        else
            # Fallback: just show raw JSON
            echo "[$TIMESTAMP]"
            echo "$COST_DATA"
        fi
    else
        echo "[$TIMESTAMP] ✗ Failed to fetch cost data (is the app running on port ${PORT}?)"
    fi

    echo ""
    sleep $INTERVAL
done
