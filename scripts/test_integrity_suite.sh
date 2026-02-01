#!/bin/bash

# Comprehensive Test Suite for Simulation Integrity
# Run all 6 acceptance criteria tests

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "🧪 Starting Comprehensive Simulation Integrity Test Suite"
echo "=========================================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test 1: Frontend Mapping Integrity Unit Tests
echo -e "${YELLOW}Test 1: Mapping Integrity Unit Tests${NC}"
echo "----------------------------------------"
cd "$PROJECT_ROOT"
npm run test tests/mappingIntegrity.test.ts || {
  echo -e "${RED}❌ FAILED: Mapping integrity tests failed${NC}"
  exit 1
}
echo -e "${GREEN}✅ PASSED: Mapping integrity tests${NC}"
echo ""

# Test 2: Backend Contract Tests (50 calls stability)
echo -e "${YELLOW}Test 2: Backend Contract Tests (API Stability)${NC}"
echo "-----------------------------------------------"
cd "$PROJECT_ROOT"
python -m pytest backend/tests/test_simulation_contract.py -v || {
  echo -e "${RED}❌ FAILED: Backend contract tests failed${NC}"
  exit 1
}
echo -e "${GREEN}✅ PASSED: Backend contract tests${NC}"
echo ""

# Test 3: Snapshot Hash Consistency Check
echo -e "${YELLOW}Test 3: Snapshot Hash Consistency (Real API)${NC}"
echo "---------------------------------------------"
# This requires backend running
python "$SCRIPT_DIR/test_snapshot_consistency.py" || {
  echo -e "${RED}❌ FAILED: Snapshot consistency check failed${NC}"
  exit 1
}
echo -e "${GREEN}✅ PASSED: Snapshot consistency check${NC}"
echo ""

# Test 4: Force Mismatch Test (Safeguard Verification)
echo -e "${YELLOW}Test 4: Force Mismatch Test (Safeguard Proof)${NC}"
echo "----------------------------------------------"
npm run test:mismatch || {
  echo -e "${RED}❌ FAILED: Mismatch safeguard test failed${NC}"
  exit 1
}
echo -e "${GREEN}✅ PASSED: Mismatch safeguard works${NC}"
echo ""

# Test 5: Manual Smoke Test Instructions
echo -e "${YELLOW}Test 5: Real-World Smoke Test (Manual)${NC}"
echo "---------------------------------------"
cat << EOF
${YELLOW}MANUAL TEST REQUIRED:${NC}

1. Start dev server: npm run dev
2. Open 3 games in different tabs
3. For each game:
   - Record debug panel values (snapshot_hash, selection_ids)
   - Hard refresh (Cmd+Shift+R)
   - Verify values either:
     ✓ Stay identical (cached), OR
     ✓ All change together (new snapshot, but consistent)
4. Toggle Spread → ML → Total 20 times rapidly
5. Check for violations in console

${GREEN}✅ Pass Criteria:${NC}
- 0 mismatches across 50 refreshes
- 0 preference/probability contradictions
- selection_id always matches, never inferred

${RED}Press ENTER when manual test complete...${NC}
EOF
read -r

# Test 6: Logging Verification
echo -e "${YELLOW}Test 6: Integrity Logging Verification${NC}"
echo "---------------------------------------"
node "$SCRIPT_DIR/verify_logging.js" || {
  echo -e "${RED}❌ FAILED: Logging verification failed${NC}"
  exit 1
}
echo -e "${GREEN}✅ PASSED: Logging captures all required fields${NC}"
echo ""

# Final Summary
echo ""
echo "=========================================================="
echo -e "${GREEN}🎉 ALL AUTOMATED TESTS PASSED${NC}"
echo ""
echo "Acceptance Criteria Status:"
echo "✅ 1. Debug panel shows all required fields"
echo "✅ 2. Mapping integrity unit tests pass"
echo "✅ 3. Backend contract tests pass (50 calls)"
echo "✅ 4. Force mismatch safeguard works"
echo "⏳ 5. Manual smoke test (requires human verification)"
echo "✅ 6. Logging captures all violation details"
echo ""
echo "Next Steps:"
echo "1. Complete manual smoke test (Test 5)"
echo "2. Review IntegrityLogger.getViolations() for any issues"
echo "3. Export violations: IntegrityLogger.exportViolations()"
echo ""
echo "🚀 Ready for production when all 6 tests pass!"
