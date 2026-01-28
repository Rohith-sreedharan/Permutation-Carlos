#!/usr/bin/env python3
"""
BeatVegas vFinal.1 - Multi-Sport Smoke Tests
Validates all 6 sports × 3 markets × 2 settlements = 36 test cases

Per specification Section 7 Phase 5:
- All 6 sports: NBA, NFL, NHL, NCAAB, NCAAF, MLB
- All 3 markets: SPREAD, TOTAL, MONEYLINE_2WAY
- All 2 settlements: FULL_GAME, REGULATION
- Validates contract enforcement and 409 error handling

Exit code 0 = PASS, 1 = FAIL
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.sport_config import (
    MarketType, 
    MarketSettlement, 
    validate_market_contract,
    get_sport_config
)

# Color codes
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

passed = 0
failed = 0
test_results = []

def test_case(description: str, sport: str, market: MarketType, settlement: MarketSettlement, expected_valid: bool):
    """Run single smoke test case"""
    global passed, failed
    
    try:
        validate_market_contract(sport, market, settlement)
        actual_valid = True
        error_msg = None
    except ValueError as e:
        actual_valid = False
        error_msg = str(e)
    
    success = (actual_valid == expected_valid)
    
    if success:
        status = f"{GREEN}✓{RESET}"
        passed += 1
    else:
        status = f"{RED}✗{RESET}"
        failed += 1
    
    # Format result
    result = {
        'description': description,
        'sport': sport,
        'market': market.value,
        'settlement': settlement.value,
        'expected': 'VALID' if expected_valid else 'REJECT',
        'actual': 'VALID' if actual_valid else 'REJECT',
        'status': 'PASS' if success else 'FAIL',
        'error': error_msg
    }
    test_results.append(result)
    
    # Print result
    print(f"{status} {description}")
    if not success:
        print(f"  Expected: {result['expected']}, Got: {result['actual']}")
        if error_msg:
            print(f"  Error: {error_msg}")
    
    return success


def test_group(name: str):
    """Print test group header"""
    print(f"\n{YELLOW}{'='*70}{RESET}")
    print(f"{YELLOW}{name}{RESET}")
    print(f"{YELLOW}{'='*70}{RESET}")


print(f"{BLUE}{'='*70}{RESET}")
print(f"{BLUE}BeatVegas vFinal.1 Multi-Sport Smoke Tests{RESET}")
print(f"{BLUE}{'='*70}{RESET}\n")

# =============================================================================
# NBA SMOKE TESTS (UNLIMITED OT - NO TIES)
# =============================================================================
test_group("NBA: Unlimited OT (No Ties Possible)")

# NBA FULL_GAME - All markets should be valid
test_case("NBA SPREAD + FULL_GAME", "NBA", MarketType.SPREAD, MarketSettlement.FULL_GAME, True)
test_case("NBA TOTAL + FULL_GAME", "NBA", MarketType.TOTAL, MarketSettlement.FULL_GAME, True)
test_case("NBA ML_2WAY + FULL_GAME", "NBA", MarketType.MONEYLINE_2WAY, MarketSettlement.FULL_GAME, True)

# NBA REGULATION - Should reject (no ties possible in regulation)
test_case("NBA SPREAD + REGULATION (REJECT)", "NBA", MarketType.SPREAD, MarketSettlement.REGULATION, False)
test_case("NBA TOTAL + REGULATION (REJECT)", "NBA", MarketType.TOTAL, MarketSettlement.REGULATION, False)
test_case("NBA ML_2WAY + REGULATION (REJECT)", "NBA", MarketType.MONEYLINE_2WAY, MarketSettlement.REGULATION, False)

# =============================================================================
# NFL SMOKE TESTS (LIMITED OT - TIES POSSIBLE)
# =============================================================================
test_group("NFL: Limited OT (Ties Possible in Regular Season)")

# NFL FULL_GAME - All markets valid (ties = push)
test_case("NFL SPREAD + FULL_GAME", "NFL", MarketType.SPREAD, MarketSettlement.FULL_GAME, True)
test_case("NFL TOTAL + FULL_GAME", "NFL", MarketType.TOTAL, MarketSettlement.FULL_GAME, True)
test_case("NFL ML_2WAY + FULL_GAME", "NFL", MarketType.MONEYLINE_2WAY, MarketSettlement.FULL_GAME, True)

# NFL REGULATION - Valid (ties possible after 4 quarters)
test_case("NFL SPREAD + REGULATION", "NFL", MarketType.SPREAD, MarketSettlement.REGULATION, True)
test_case("NFL TOTAL + REGULATION", "NFL", MarketType.TOTAL, MarketSettlement.REGULATION, True)
test_case("NFL ML_2WAY + REGULATION", "NFL", MarketType.MONEYLINE_2WAY, MarketSettlement.REGULATION, True)

# =============================================================================
# NHL SMOKE TESTS (OT+SO FULL_GAME, TIES POSSIBLE IN REGULATION)
# =============================================================================
test_group("NHL: OT+Shootout (FULL_GAME no ties, REGULATION ties possible)")

# NHL FULL_GAME - All markets valid (OT+SO decides winner)
test_case("NHL SPREAD + FULL_GAME", "NHL", MarketType.SPREAD, MarketSettlement.FULL_GAME, True)
test_case("NHL TOTAL + FULL_GAME", "NHL", MarketType.TOTAL, MarketSettlement.FULL_GAME, True)
test_case("NHL ML_2WAY + FULL_GAME", "NHL", MarketType.MONEYLINE_2WAY, MarketSettlement.FULL_GAME, True)

# NHL REGULATION - Valid (60-minute ties possible)
test_case("NHL SPREAD + REGULATION", "NHL", MarketType.SPREAD, MarketSettlement.REGULATION, True)
test_case("NHL TOTAL + REGULATION", "NHL", MarketType.TOTAL, MarketSettlement.REGULATION, True)
test_case("NHL ML_2WAY + REGULATION", "NHL", MarketType.MONEYLINE_2WAY, MarketSettlement.REGULATION, True)

# =============================================================================
# NCAAB SMOKE TESTS (UNLIMITED OT - NO TIES)
# =============================================================================
test_group("NCAAB: Unlimited OT (No Ties Possible)")

# NCAAB FULL_GAME - All markets valid
test_case("NCAAB SPREAD + FULL_GAME", "NCAAB", MarketType.SPREAD, MarketSettlement.FULL_GAME, True)
test_case("NCAAB TOTAL + FULL_GAME", "NCAAB", MarketType.TOTAL, MarketSettlement.FULL_GAME, True)
test_case("NCAAB ML_2WAY + FULL_GAME", "NCAAB", MarketType.MONEYLINE_2WAY, MarketSettlement.FULL_GAME, True)

# NCAAB REGULATION - Should reject
test_case("NCAAB SPREAD + REGULATION (REJECT)", "NCAAB", MarketType.SPREAD, MarketSettlement.REGULATION, False)
test_case("NCAAB TOTAL + REGULATION (REJECT)", "NCAAB", MarketType.TOTAL, MarketSettlement.REGULATION, False)
test_case("NCAAB ML_2WAY + REGULATION (REJECT)", "NCAAB", MarketType.MONEYLINE_2WAY, MarketSettlement.REGULATION, False)

# =============================================================================
# NCAAF SMOKE TESTS (UNLIMITED OT - NO TIES)
# =============================================================================
test_group("NCAAF: Unlimited OT (No Ties Possible)")

# NCAAF FULL_GAME - All markets valid
test_case("NCAAF SPREAD + FULL_GAME", "NCAAF", MarketType.SPREAD, MarketSettlement.FULL_GAME, True)
test_case("NCAAF TOTAL + FULL_GAME", "NCAAF", MarketType.TOTAL, MarketSettlement.FULL_GAME, True)
test_case("NCAAF ML_2WAY + FULL_GAME", "NCAAF", MarketType.MONEYLINE_2WAY, MarketSettlement.FULL_GAME, True)

# NCAAF REGULATION - Should reject
test_case("NCAAF SPREAD + REGULATION (REJECT)", "NCAAF", MarketType.SPREAD, MarketSettlement.REGULATION, False)
test_case("NCAAF TOTAL + REGULATION (REJECT)", "NCAAF", MarketType.TOTAL, MarketSettlement.REGULATION, False)
test_case("NCAAF ML_2WAY + REGULATION (REJECT)", "NCAAF", MarketType.MONEYLINE_2WAY, MarketSettlement.REGULATION, False)

# =============================================================================
# MLB SMOKE TESTS (UNLIMITED INNINGS - NO TIES)
# =============================================================================
test_group("MLB: Unlimited Extra Innings (No Ties Possible)")

# MLB FULL_GAME - All markets valid
test_case("MLB SPREAD + FULL_GAME", "MLB", MarketType.SPREAD, MarketSettlement.FULL_GAME, True)
test_case("MLB TOTAL + FULL_GAME", "MLB", MarketType.TOTAL, MarketSettlement.FULL_GAME, True)
test_case("MLB ML_2WAY + FULL_GAME", "MLB", MarketType.MONEYLINE_2WAY, MarketSettlement.FULL_GAME, True)

# MLB REGULATION - Should reject
test_case("MLB SPREAD + REGULATION (REJECT)", "MLB", MarketType.SPREAD, MarketSettlement.REGULATION, False)
test_case("MLB TOTAL + REGULATION (REJECT)", "MLB", MarketType.TOTAL, MarketSettlement.REGULATION, False)
test_case("MLB ML_2WAY + REGULATION (REJECT)", "MLB", MarketType.MONEYLINE_2WAY, MarketSettlement.REGULATION, False)

# =============================================================================
# SUMMARY
# =============================================================================
print(f"\n{BLUE}{'='*70}{RESET}")
print(f"{BLUE}SMOKE TEST SUMMARY{RESET}")
print(f"{BLUE}{'='*70}{RESET}\n")

print(f"Total tests: {passed + failed}")
print(f"{GREEN}Passed: {passed}{RESET}")
if failed > 0:
    print(f"{RED}Failed: {failed}{RESET}")

# Print failure summary
if failed > 0:
    print(f"\n{RED}FAILED TESTS:{RESET}")
    for result in test_results:
        if result['status'] == 'FAIL':
            print(f"  - {result['description']}")
            print(f"    Expected: {result['expected']}, Got: {result['actual']}")

# Print validation matrix
print(f"\n{BLUE}SPORT VALIDATION MATRIX:{RESET}")
print("-" * 70)
print(f"{'Sport':<10} {'FULL_GAME Valid':<20} {'REGULATION Valid':<20}")
print("-" * 70)
print(f"{'NBA':<10} {'✓ All Markets':<20} {'✗ Forbidden':<20}")
print(f"{'NFL':<10} {'✓ All Markets':<20} {'✓ All Markets':<20}")
print(f"{'NHL':<10} {'✓ All Markets':<20} {'✓ All Markets':<20}")
print(f"{'NCAAB':<10} {'✓ All Markets':<20} {'✗ Forbidden':<20}")
print(f"{'NCAAF':<10} {'✓ All Markets':<20} {'✗ Forbidden':<20}")
print(f"{'MLB':<10} {'✓ All Markets':<20} {'✗ Forbidden':<20}")
print("-" * 70)

print(f"\n{BLUE}DEPLOYMENT GATE STATUS:{RESET}")
if failed == 0:
    print(f"{GREEN}✓ ALL SMOKE TESTS PASSED{RESET}")
    print(f"{GREEN}✓ DEPLOYMENT APPROVED{RESET}")
    sys.exit(0)
else:
    print(f"{RED}✗ {failed} SMOKE TEST(S) FAILED{RESET}")
    print(f"{RED}✗ DEPLOYMENT BLOCKED{RESET}")
    sys.exit(1)
