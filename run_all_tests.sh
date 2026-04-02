#!/bin/bash
# ============================================================================
# Run all tests across templates and demo agents
# ============================================================================
# Each agent uses the same 'app' package namespace, so tests must
# run in separate pytest processes to avoid import conflicts.

set -e
TOTAL=0
FAILED=0

run_suite() {
    local name="$1"
    shift
    echo "━━━ $name ━━━"
    if python -m pytest "$@" -q --tb=short 2>&1; then
        echo ""
    else
        FAILED=$((FAILED + 1))
        echo ""
    fi
}

# Template tests
run_suite "Generic Template" generic/test-suites/unit/ generic/test-suites/contract/ \
    --ignore=generic/test-suites/unit/test_resilience.py

run_suite "Custom Template" custom/test-suites/unit/ custom/test-suites/contract/ \
    --ignore=custom/test-suites/unit/test_resilience.py

run_suite "MCP Template" mcp/test-suites/unit/ mcp/test-suites/contract/ \
    --ignore=mcp/test-suites/unit/test_resilience.py

# Demo agent tests
run_suite "Uber Agent" Uber/test-suites/
run_suite "Zomato Agent" Zomato/test-suites/
run_suite "Airbnb Agent" Airbnb/test-suites/

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ $FAILED -eq 0 ]; then
    echo "ALL SUITES PASSED"
else
    echo "$FAILED SUITE(S) FAILED"
    exit 1
fi
