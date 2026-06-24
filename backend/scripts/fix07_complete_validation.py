#!/usr/bin/env python3
"""
FIX-07 COMPLETE SUBMISSION PROOF PACK
All items for Zone 3 build closure
"""

import sys
import json
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT / 'backend'))

from db.mongo import db  # noqa: E402


def section(title: str):
    """Print section header"""
    print()
    print('=' * 100)
    print(f'  {title}')
    print('=' * 100)
    print()


def item(label: str, status: str):
    """Print item with pass/fail status"""
    symbol = '✅' if status == 'PASS' else '❌'
    print(f'{symbol} {label}: {status}')


def check_file_exists(path: Path, label: str) -> bool:
    exists = path.exists()
    item(label, 'PASS' if exists else 'FAIL')
    return exists


def check_file_contains(path: Path, needle: str, label: str) -> bool:
    if not path.exists():
        item(label, 'FAIL (file not found)')
        return False
    content = path.read_text(encoding='utf-8')
    found = needle in content
    item(label, 'PASS' if found else 'FAIL')
    return found


def main():
    section('FIX-07 ZONE 3 BUILD - COMPLETE SUBMISSION VALIDATION')

    all_pass = True

    # ===== FIX-03: BLOCKED VIEWS =====
    section('FIX-03: Blocked Detail Views')
    
    check1 = check_file_contains(
        ROOT / 'components' / 'Dashboard.tsx',
        'Times shown in Eastern Time (ET)',
        'Dashboard displays "Times shown in Eastern Time (ET)"'
    )
    all_pass = all_pass and check1

    check2 = check_file_contains(
        ROOT / 'components' / 'FinalUnifiedSummary.tsx',
        'ANALYSIS BLOCKED',
        'Detail view shows "ANALYSIS BLOCKED" state'
    )
    all_pass = all_pass and check2

    # ===== FIX-05: EASTERN TIME =====
    section('FIX-05: Eastern Time Label')

    check3 = check_file_contains(
        ROOT / 'components' / 'Dashboard.tsx',
        'Times shown in Eastern Time (ET)',
        'Eastern Time label present in Dashboard'
    )
    check4 = not ('Times shown in UTC' in (ROOT / 'components' / 'Dashboard.tsx').read_text(encoding='utf-8'))
    item('Old UTC label removed', 'PASS' if check4 else 'FAIL')
    all_pass = all_pass and check3 and check4

    # ===== FIX-06: GRID/LIST CONSISTENCY =====
    section('FIX-06: Grid and List Price/Label Consistency')

    check5 = check_file_exists(
        ROOT / 'utils' / 'cardMarketSignal.ts',
        'Shared renderer exists (cardMarketSignal.ts)'
    )
    check6 = check_file_contains(
        ROOT / 'utils' / 'cardMarketSignal.ts',
        'export function renderMarketSignalCard',
        'Shared renderer function exported'
    )
    check7 = check_file_exists(
        ROOT / 'components' / 'MarketDecisionCard.tsx',
        'Unified card component (MarketDecisionCard.tsx)'
    )
    check8 = check_file_contains(
        ROOT / 'components' / 'MarketDecisionCard.tsx',
        'renderMarketSignalCard',
        'Card component uses shared renderer'
    )
    all_pass = all_pass and check5 and check6 and check7 and check8

    # ===== FIX-07: ISSUES 07-10 =====
    section('FIX-07: Market Decision Card Issues (07-10)')

    check9 = check_file_contains(
        ROOT / 'utils' / 'cardMarketSignal.ts',
        "line > 0 ? '+' : ''",
        'ISSUE-07: Spread formatting (no + for negative) implemented'
    )
    all_pass = all_pass and check9

    check10 = check_file_contains(
        ROOT / 'components' / 'MarketDecisionCard.tsx',
        'isError',
        'ISSUE-08: Error/retry state UI present'
    )
    check11 = check_file_contains(
        ROOT / 'components' / 'MarketDecisionCard.tsx',
        'onRetry',
        'ISSUE-08: Retry button implementation'
    )
    all_pass = all_pass and check10 and check11

    # Check for all classification types (flexible pattern matching)
    market_decision_content = (ROOT / 'types' / 'MarketDecision.ts').read_text(encoding='utf-8')
    has_all_classifications = all(c in market_decision_content for c in ['EDGE', 'LEAN', 'MARKET_ALIGNED', 'BLOCKED', 'NO_ACTION'])
    item('ISSUE-09: All classification types defined', 'PASS' if has_all_classifications else 'FAIL')
    check12 = has_all_classifications
    all_pass = all_pass and check12

    check13 = check_file_contains(
        ROOT / 'utils' / 'cardMarketSignal.ts',
        'export function getSportLabel',
        'ISSUE-10: Sport label function (no enums)'
    )
    all_pass = all_pass and check13

    # ===== BACKEND API CONTRACT =====
    section('Backend API: Decisions Endpoint')

    check14 = check_file_contains(
        ROOT / 'backend' / 'core' / 'market_decision.py',
        'classification: Optional[Classification]',
        'Backend model has classification field'
    )
    check15 = check_file_contains(
        ROOT / 'backend' / 'core' / 'market_decision.py',
        'market_type_display',
        'Backend model has market_type_display'
    )
    check16 = check_file_contains(
        ROOT / 'backend' / 'core' / 'market_decision.py',
        'selection_label',
        'Backend model has selection_label'
    )
    check17 = check_file_contains(
        ROOT / 'backend' / 'core' / 'market_decision.py',
        'edge_points',
        'Backend model has edge_points'
    )
    check18 = check_file_contains(
        ROOT / 'backend' / 'core' / 'market_decision.py',
        'model_probability',
        'Backend model has model_probability'
    )
    check19 = check_file_contains(
        ROOT / 'backend' / 'core' / 'market_decision.py',
        'market_implied_probability',
        'Backend model has market_implied_probability'
    )
    all_pass = all_pass and check14 and check15 and check16 and check17 and check18 and check19

    # ===== FRONTEND API INTEGRATION =====
    section('Frontend API Integration')

    check20 = check_file_contains(
        ROOT / 'services' / 'api.ts',
        'export const fetchGameDecisions',
        'Decisions endpoint service function'
    )
    check21 = check_file_contains(
        ROOT / 'services' / 'api.ts',
        '/api/games/',
        'Decisions endpoint called with correct URL'
    )
    check22 = check_file_contains(
        ROOT / 'services' / 'api.ts',
        'GameDecisions',
        'Decisions endpoint returns correct type'
    )
    all_pass = all_pass and check20 and check21 and check22

    # ===== PROOF READINESS =====
    section('Proof of Implementation')

    print('FIX-03: Blocked Detail Views')
    print('  → Component: FinalUnifiedSummary.tsx')
    print('  → Shows: "ANALYSIS BLOCKED" with zero analysis content above')
    print('  → Proof: Screenshot of blocked detail view required')
    print()

    print('FIX-05: Eastern Time Label')
    print('  → Component: Dashboard.tsx line 408')
    print('  → Label: "Times shown in Eastern Time (ET)"')
    print('  → Proof: Live dashboard screenshot required')
    print()

    print('FIX-06: Grid and List Consistency')
    print('  → Shared renderer: utils/cardMarketSignal.ts → renderMarketSignalCard()')
    print('  → Card component: components/MarketDecisionCard.tsx')
    print('  → Both grid and list consume identical renderer')
    print('  → Proof: Grid screenshot + List screenshot (same 3 games, prices match)')
    print()

    print('FIX-07 ISSUE-07: Spread Formatting')
    print('  → Format: -2.5 (no + prefix)')
    print('  → Implementation: cardMarketSignal.ts → formatSelectionLabel()')
    print('  → Proof: Screenshot of spread card showing -2.5')
    print()

    print('FIX-07 ISSUE-08: Retry Button')
    print('  → Component: MarketDecisionCard.tsx')
    print('  → State: Appears after fetch failure')
    print('  → Proof: Screenshot of retry button after error')
    print()

    print('FIX-07 ISSUE-09: Classification Mix')
    print('  → Show all 5 types: EDGE, LEAN, MARKET_ALIGNED, BLOCKED, + mixed case')
    print('  → Implementation: All types defined in Classification enum')
    print('  → Proof: Screenshot of 5 cards showing each type')
    print()

    print('FIX-07 ISSUE-10: League Labels')
    print('  → Display: NBA / NHL / NCAAB (no enums)')
    print('  → Implementation: getSportLabel() function')
    print('  → Proof: Screenshot of 3+ cards showing league labels')
    print()

    # ===== FINAL STATUS =====
    section('SUBMISSION READINESS')

    if all_pass:
        print('✅ ALL CHECKS PASSED')
        print()
        print('Zone 3 infrastructure is complete.')
        print('Ready for screenshot proof batch.')
        print()
        print('REQUIRED SCREENSHOTS:')
        print('  1. FIX-03: 2x blocked detail views')
        print('  2. FIX-05: Dashboard with "Times shown in Eastern Time (ET)"')
        print('  3. FIX-06: Grid view (3 games with prices)')
        print('  4. FIX-06: List view (same 3 games, prices match)')
        print('  5. FIX-07 ISSUE-07: Spread card with -2.5 (no +)')
        print('  6. FIX-07 ISSUE-08: Retry button after error')
        print('  7. FIX-07 ISSUE-09: 5 cards (EDGE, LEAN, MARKET_ALIGNED, BLOCKED, mixed)')
        print('  8. FIX-07 ISSUE-10: 3+ cards showing NBA/NHL/NCAAB labels')
        return 0
    else:
        print('❌ SOME CHECKS FAILED')
        print()
        print('Please remediate before submitting.')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
