#!/bin/bash

# VERIFICATION SCRIPT: Proof of deletion of forbidden decision logic
# Per spec: "No merge without deletion" - must see files deleted or patterns removed

echo "========================================="
echo "FORBIDDEN PATTERN VERIFICATION"
echo "========================================="
echo ""

echo "Checking GameDetail_CANONICAL.tsx for forbidden patterns..."
echo ""

# Forbidden helper functions
echo "1. getSelection / getPreferredSelection:"
rg -c "getSelection|getPreferredSelection" components/GameDetail_CANONICAL.tsx || echo "✓ PASS: 0 matches"
echo ""

echo "2. validateMarketView / renderSAFEMode:"
rg -c "validateMarketView|renderSAFEMode" components/GameDetail_CANONICAL.tsx || echo "✓ PASS: 0 matches"
echo ""

echo "3. validateEdge / explainEdgeSource:"
rg -c "validateEdge|explainEdgeSource" components/GameDetail_CANONICAL.tsx || echo "✓ PASS: 0 matches"
echo ""

echo "4. calculateCLV:"
rg -c "calculateCLV" components/GameDetail_CANONICAL.tsx || echo "✓ PASS: 0 matches"
echo ""

echo "5. sharp_analysis:"
rg -c "sharp_analysis" components/GameDetail_CANONICAL.tsx || echo "✓ PASS: 0 matches"
echo ""

echo "6. Math.abs on spreads:"
rg -c "Math\.abs" components/GameDetail_CANONICAL.tsx || echo "✓ PASS: 0 matches"
echo ""

echo "7. baseline mode:"
rg -c "baseline|BASELINE" components/GameDetail_CANONICAL.tsx || echo "✓ PASS: 0 matches"
echo ""

echo "========================================="
echo "REQUIRED PATTERNS VERIFICATION"
echo "========================================="
echo ""

echo "1. MarketDecision import:"
rg "import.*MarketDecision" components/GameDetail_CANONICAL.tsx
echo ""

echo "2. Single /decisions endpoint fetch:"
rg "/api/games/.*decisions" components/GameDetail_CANONICAL.tsx
echo ""

echo "3. Classification rendering:"
rg "decision\.classification" components/GameDetail_CANONICAL.tsx | head -5
echo ""

echo "4. Unified Summary selector (deterministic):"
rg "OFFICIAL.*EDGE|primaryDecision" components/GameDetail_CANONICAL.tsx | head -5
echo ""

echo "========================================="
echo "PASS CRITERIA"
echo "========================================="
echo "All forbidden patterns must return 0 matches"
echo "All required patterns must be present"
echo ""
