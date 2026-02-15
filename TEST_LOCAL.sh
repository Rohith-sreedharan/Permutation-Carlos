#!/bin/bash
# Quick Test - Decisions Endpoint (Local Development)

set -e

echo "=========================================="
echo "TESTING DECISIONS ENDPOINT (LOCAL)"
echo "=========================================="
echo ""

# Find a game that has both event AND simulation
echo "🔍 Finding game with simulation data..."
GAME_ID=$(curl -s "http://localhost:8000/api/odds/list?limit=50" | \
  jq -r '.events[0].event_id // .events[0].id // empty' | head -1)

if [ -z "$GAME_ID" ]; then
    echo "❌ No games found in database"
    exit 1
fi

echo "📌 Testing with game_id: $GAME_ID"
echo ""

# Test decisions endpoint
echo "📡 Fetching decisions..."
RESPONSE=$(curl -s "http://localhost:8000/api/games/NCAAB/${GAME_ID}/decisions")

# Check for error
if echo "$RESPONSE" | jq -e '.detail' > /dev/null 2>&1; then
    echo "❌ ERROR: $(echo "$RESPONSE" | jq -r '.detail')"
    echo ""
    echo "This likely means:"
    echo "  1. Game exists in events collection but no simulation_results"
    echo "  2. You need to run: python3 -m backend.generate_simulations"
    echo ""
    exit 1
fi

# Show atomic consistency
echo "$RESPONSE" | jq -r '
if .spread and .total then
  "✅ SUCCESS - Atomic Decision Loaded\n\n" +
  "Spread:\n" +
  "  decision_version: " + (.spread.debug.decision_version | tostring) + "\n" +
  "  trace_id: " + .spread.debug.trace_id + "\n" +
  "  team: " + .spread.pick.team_name + "\n" +
  "  inputs_hash: " + .spread.debug.inputs_hash + "\n\n" +
  "Total:\n" +
  "  decision_version: " + (.total.debug.decision_version | tostring) + "\n" +
  "  trace_id: " + .total.debug.trace_id + "\n" +
  "  inputs_hash: " + .total.debug.inputs_hash + "\n\n" +
  "🎯 Atomic Consistency Check:\n" +
  "  Versions match: " + (if .spread.debug.decision_version == .total.debug.decision_version then "✅ PASS" else "❌ FAIL" end) + "\n" +
  "  Trace IDs match: " + (if .spread.debug.trace_id == .total.debug.trace_id then "✅ PASS" else "❌ FAIL" end) + "\n" +
  "  Inputs hash match: " + (if .spread.debug.inputs_hash == .total.debug.inputs_hash then "✅ PASS" else "❌ FAIL" end) + "\n\n" +
  "🚀 Charlotte vs Atlanta bug: " + (if .spread.debug.decision_version == .total.debug.decision_version and .spread.debug.trace_id == .total.debug.trace_id then "✅ PREVENTED" else "❌ STILL PRESENT" end)
else
  "❌ Missing market data"
end'

echo ""
echo "=========================================="
echo "NEXT STEPS"
echo "=========================================="
echo ""
echo "1. Test in browser with debug overlay:"
echo "   http://localhost:5173/games/NCAAB/${GAME_ID}?debug=1"
echo ""
echo "2. Run Playwright tests:"
echo "   export BASE_URL=http://localhost:5173"
echo "   export TEST_GAME_ID=${GAME_ID}"
echo "   npx playwright test atomic-decision.spec.ts --headed"
echo ""
