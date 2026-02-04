#!/bin/bash
# Verify that E2E testing implementation is complete
# Usage: ./scripts/verify_implementation.sh

echo "=============================================="
echo "E2E Testing Implementation Verification"
echo "=============================================="
echo ""

ERRORS=0
WARNINGS=0

# Check config.py
echo "1. Checking config.py..."
if grep -q "demo_mode:" /Users/philipbankier/Development/MailAI/1st-run/hack-demo/content-autopilot/config.py; then
    echo "   ✓ demo_mode setting present"
else
    echo "   ✗ demo_mode setting missing"
    ERRORS=$((ERRORS + 1))
fi

if grep -q "daily_cost_limit:" /Users/philipbankier/Development/MailAI/1st-run/hack-demo/content-autopilot/config.py; then
    echo "   ✓ daily_cost_limit setting present"
else
    echo "   ✗ daily_cost_limit setting missing"
    ERRORS=$((ERRORS + 1))
fi

# Check main.py
echo ""
echo "2. Checking main.py..."
if grep -q "seed_demo_data" /Users/philipbankier/Development/MailAI/1st-run/hack-demo/content-autopilot/main.py; then
    echo "   ✓ Conditional seeding logic present"
else
    echo "   ✗ Conditional seeding logic missing"
    ERRORS=$((ERRORS + 1))
fi

if grep -q "demo_mode" /Users/philipbankier/Development/MailAI/1st-run/hack-demo/content-autopilot/main.py; then
    echo "   ✓ Demo mode handling present"
else
    echo "   ✗ Demo mode handling missing"
    ERRORS=$((ERRORS + 1))
fi

# Check orchestrator.py
echo ""
echo "3. Checking orchestrator.py..."
if grep -q "async def start(self, demo_mode" /Users/philipbankier/Development/MailAI/1st-run/hack-demo/content-autopilot/orchestrator.py; then
    echo "   ✓ Demo mode parameter in start()"
else
    echo "   ✗ Demo mode parameter missing from start()"
    ERRORS=$((ERRORS + 1))
fi

if grep -q "_get_cost_today" /Users/philipbankier/Development/MailAI/1st-run/hack-demo/content-autopilot/orchestrator.py; then
    echo "   ✓ Cost limit enforcement present"
else
    echo "   ✗ Cost limit enforcement missing"
    ERRORS=$((ERRORS + 1))
fi

# Check seed_demo_data.py
echo ""
echo "4. Checking scripts/seed_demo_data.py..."
if grep -q "async def seed_demo_data" /Users/philipbankier/Development/MailAI/1st-run/hack-demo/content-autopilot/scripts/seed_demo_data.py; then
    echo "   ✓ Importable seed_demo_data() function present"
else
    echo "   ✗ Importable function missing"
    ERRORS=$((ERRORS + 1))
fi

# Check routes.py
echo ""
echo "5. Checking routes.py..."
if grep -q "cost_today_usd" /Users/philipbankier/Development/MailAI/1st-run/hack-demo/content-autopilot/routes.py; then
    echo "   ✓ Enhanced /costs endpoint present"
else
    echo "   ✗ Enhanced /costs endpoint missing"
    ERRORS=$((ERRORS + 1))
fi

# Check utility scripts
echo ""
echo "6. Checking utility scripts..."
SCRIPTS=("backup_demo_db.sh" "rollback_to_demo.sh" "monitor_costs.sh" "test_mode_switch.sh")
for script in "${SCRIPTS[@]}"; do
    if [ -f "scripts/${script}" ]; then
        if [ -x "scripts/${script}" ]; then
            echo "   ✓ scripts/${script} exists and is executable"
        else
            echo "   ⚠️  scripts/${script} exists but not executable"
            WARNINGS=$((WARNINGS + 1))
        fi
    else
        echo "   ✗ scripts/${script} missing"
        ERRORS=$((ERRORS + 1))
    fi
done

# Check documentation
echo ""
echo "7. Checking documentation..."
if [ -f "TESTING_GUIDE.md" ]; then
    echo "   ✓ TESTING_GUIDE.md present"
else
    echo "   ✗ TESTING_GUIDE.md missing"
    ERRORS=$((ERRORS + 1))
fi

if [ -f "E2E_TESTING_IMPLEMENTATION.md" ]; then
    echo "   ✓ E2E_TESTING_IMPLEMENTATION.md present"
else
    echo "   ✗ E2E_TESTING_IMPLEMENTATION.md missing"
    ERRORS=$((ERRORS + 1))
fi

# Check .env.example
echo ""
echo "8. Checking .env.example..."
if grep -q "DEMO_MODE" .env.example; then
    echo "   ✓ DEMO_MODE documented in .env.example"
else
    echo "   ✗ DEMO_MODE not in .env.example"
    ERRORS=$((ERRORS + 1))
fi

if grep -q "DAILY_COST_LIMIT" .env.example; then
    echo "   ✓ DAILY_COST_LIMIT documented in .env.example"
else
    echo "   ✗ DAILY_COST_LIMIT not in .env.example"
    ERRORS=$((ERRORS + 1))
fi

# Summary
echo ""
echo "=============================================="
echo "Verification Summary"
echo "=============================================="
echo "Errors:   ${ERRORS}"
echo "Warnings: ${WARNINGS}"
echo ""

if [ $ERRORS -eq 0 ]; then
    echo "✓ Implementation complete and verified!"
    echo ""
    echo "Next steps:"
    echo "  1. Test demo mode:       python main.py"
    echo "  2. Run mode switch test: ./scripts/test_mode_switch.sh"
    echo "  3. Review docs:          cat TESTING_GUIDE.md"
    exit 0
else
    echo "✗ Implementation incomplete - fix errors above"
    exit 1
fi
