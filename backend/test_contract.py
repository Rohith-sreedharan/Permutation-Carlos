#!/usr/bin/env python3
"""Test canonical contract enforcer"""
from core.canonical_contract_enforcer import enforce_canonical_contract, validate_canonical_contract

# Test with minimal simulation object
sim = {
    'event_id': 'test123',
    'iterations': 10000,
    'created_at': '2026-02-01T12:00:00Z',
    'team_a': 'Lakers',
    'team_b': 'Celtics',
    'median_total': 220.5,
    'team_a_win_probability': 0.55,
    'team_b_win_probability': 0.45,
    'push_probability': 0.0,
    'pick_state': 'PICK',
    'sharp_analysis': {
        'spread': {
            'sharp_side': 'Lakers'
        }
    }
}

# Enforce contract
sim = enforce_canonical_contract(sim)

# Validate
is_valid, errors = validate_canonical_contract(sim)

print(f'Snapshot Hash: {sim.get("snapshot_hash")}')
print(f'Selection ID: {sim.get("selection_id")}')
print(f'Market Settlement: {sim.get("market_settlement")}')
print(f'Contract Version: {sim.get("contract_version")}')
print(f'Valid: {is_valid}')
if errors:
    print(f'Errors: {errors}')
else:
    print('✅ All canonical fields present!')
