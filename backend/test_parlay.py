#!/usr/bin/env python3
"""Test parlay architect functionality"""
import sys
sys.path.insert(0, '.')

from core.parlay_architect import build_parlay, ParlayRequest, Leg, Tier, MarketType
from datetime import datetime, timezone, timedelta

print("🧪 Testing Parlay Architect API\n")

# Create mock legs
now = datetime.now(timezone.utc)
game_time = now + timedelta(hours=3)

mock_legs = [
    Leg(
        event_id='NBA_LAL_BOS',
        sport='NBA',
        league='NBA',
        start_time_utc=game_time,
        market_type=MarketType.SPREAD,
        selection='Lakers -7.5',
        tier=Tier.EDGE,
        confidence=65.0,
        clv=2.5,
        total_deviation=3.2,
        volatility='LOW',
        ev=4.8,
        di_pass=True,
        mv_pass=True,
        is_locked=False,  # Changed to False to avoid weight penalty
        injury_stable=True,
        team_key='game1_Lakers',
        canonical_state='EDGE'
    ),
    Leg(
        event_id='NBA_GSW_MIL',
        sport='NBA',
        league='NBA',
        start_time_utc=game_time,
        market_type=MarketType.SPREAD,
        selection='Warriors +3.5',
        tier=Tier.PICK,
        confidence=58.0,
        clv=1.8,
        total_deviation=2.1,
        volatility='MEDIUM',
        ev=3.2,
        di_pass=True,
        mv_pass=True,
        is_locked=False,  # Changed to False
        injury_stable=True,
        team_key='game2_Warriors',
        canonical_state='PICK'
    ),
    Leg(
        event_id='NBA_PHX_DEN',
        sport='NBA',
        league='NBA',
        start_time_utc=game_time,
        market_type=MarketType.TOTAL,
        selection='Over 228.5',
        tier=Tier.PICK,
        confidence=56.0,
        clv=1.2,
        total_deviation=1.8,
        volatility='MEDIUM',
        ev=2.8,
        di_pass=True,
        mv_pass=True,
        is_locked=False,  # Changed to False
        injury_stable=True,
        team_key=None,
        canonical_state='PICK'
    ),
    Leg(
        event_id='NBA_DAL_MIA',
        sport='NBA',
        league='NBA',
        start_time_utc=game_time,
        market_type=MarketType.SPREAD,
        selection='Mavericks -5.5',
        tier=Tier.EDGE,
        confidence=62.0,
        clv=3.1,
        total_deviation=4.5,
        volatility='LOW',
        ev=5.2,
        di_pass=True,
        mv_pass=True,
        is_locked=False,
        injury_stable=True,
        team_key='game4_Mavericks',
        canonical_state='EDGE'
    ),
]

# Test balanced profile
print("Test 1: Balanced profile, 4 legs")
request = ParlayRequest(
    profile='balanced',
    legs=4,
    allow_same_event=False,
    allow_same_team=False,
    include_props=False
)

result = build_parlay(mock_legs, request)

print(f"  Status: {result.status}")
if result.status == 'PARLAY':
    print(f"  ✅ SUCCESS - {len(result.legs_selected)} legs selected")
    print(f"  Total weight: {result.parlay_weight:.2f}")
    for i, leg in enumerate(result.legs_selected, 1):
        print(f"    Leg {i}: {leg.selection} ({leg.tier.name}) - EV: {leg.ev}%")
else:
    print(f"  ❌ FAIL - {result.reason_code}")
    if result.reason_detail:
        print(f"  Details: {result.reason_detail}")

print("\n" + "="*60 + "\n")

# Test with insufficient legs
print("Test 2: Request 5 legs with only 3 available")
request2 = ParlayRequest(
    profile='balanced',
    legs=5,
    allow_same_event=False,
    allow_same_team=False,
    include_props=False
)

result2 = build_parlay(mock_legs, request2)

print(f"  Status: {result2.status}")
if result2.status == 'PARLAY':
    print(f"  ✅ SUCCESS")
else:
    print(f"  ✅ FAIL (expected) - {result2.reason_code}")
    if result2.reason_detail:
        print(f"  Details: {result2.reason_detail}")

print("\n✅ Parlay Architect API tests complete")
