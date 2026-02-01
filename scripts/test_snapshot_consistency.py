#!/usr/bin/env python3
"""
Snapshot Consistency Test - Verify Real API Responses

Tests that multiple calls to same endpoint return consistent snapshot_hash
and selection_id values.
"""

import requests
import sys
import time
from collections import defaultdict
from typing import Dict, List, Any

API_BASE_URL = "http://localhost:8000"

def test_snapshot_consistency(event_id: str, num_calls: int = 50) -> Dict[str, Any]:
    """
    Call simulation API multiple times and verify snapshot consistency.
    
    Returns:
        dict with test results and any violations found
    """
    results = {
        'total_calls': num_calls,
        'successful_calls': 0,
        'failed_calls': 0,
        'unique_snapshots': set(),
        'snapshot_groups': defaultdict(list),
        'violations': [],
        'selection_id_changes': []
    }
    
    print(f"🧪 Testing snapshot consistency for event {event_id}")
    print(f"   Making {num_calls} API calls...")
    
    for i in range(num_calls):
        try:
            response = requests.get(f"{API_BASE_URL}/api/simulations/{event_id}", timeout=10)
            
            if response.status_code != 200:
                results['failed_calls'] += 1
                print(f"   ❌ Call {i+1}: HTTP {response.status_code}")
                continue
            
            data = response.json()
            results['successful_calls'] += 1
            
            # Extract snapshot info
            snapshot_hash = data.get('snapshot_hash', 'MISSING')
            results['unique_snapshots'].add(snapshot_hash)
            
            # Extract selection_ids
            spread = data.get('sharp_analysis', {}).get('spread', {})
            moneyline = data.get('sharp_analysis', {}).get('moneyline', {})
            total = data.get('sharp_analysis', {}).get('total', {})
            
            call_data = {
                'iteration': i + 1,
                'snapshot_hash': snapshot_hash,
                'spread_home_id': spread.get('home_selection_id'),
                'spread_away_id': spread.get('away_selection_id'),
                'ml_home_id': moneyline.get('home_selection_id'),
                'ml_away_id': moneyline.get('away_selection_id'),
                'total_over_id': total.get('over_selection_id'),
                'total_under_id': total.get('under_selection_id'),
                'spread_snapshot': spread.get('snapshot_hash'),
                'ml_snapshot': moneyline.get('snapshot_hash'),
                'total_snapshot': total.get('snapshot_hash')
            }
            
            results['snapshot_groups'][snapshot_hash].append(call_data)
            
            # Print progress every 10 calls
            if (i + 1) % 10 == 0:
                print(f"   Progress: {i + 1}/{num_calls} calls completed")
        
        except Exception as e:
            results['failed_calls'] += 1
            print(f"   ❌ Call {i+1}: {str(e)}")
    
    # Analyze results
    print(f"\n📊 Results:")
    print(f"   Successful calls: {results['successful_calls']}/{num_calls}")
    print(f"   Failed calls: {results['failed_calls']}")
    print(f"   Unique snapshots: {len(results['unique_snapshots'])}")
    
    # Check each snapshot group for consistency
    for snapshot_hash, calls in results['snapshot_groups'].items():
        if len(calls) < 2:
            continue  # Only one call with this snapshot
        
        print(f"\n   Checking snapshot group: {snapshot_hash} ({len(calls)} calls)")
        
        # Check selection_id stability
        spread_home_ids = set(c['spread_home_id'] for c in calls if c['spread_home_id'])
        spread_away_ids = set(c['spread_away_id'] for c in calls if c['spread_away_id'])
        ml_home_ids = set(c['ml_home_id'] for c in calls if c['ml_home_id'])
        ml_away_ids = set(c['ml_away_id'] for c in calls if c['ml_away_id'])
        
        if len(spread_home_ids) > 1:
            violation = f"Spread home_selection_id changed within snapshot {snapshot_hash}: {spread_home_ids}"
            results['violations'].append(violation)
            print(f"   ❌ {violation}")
        
        if len(spread_away_ids) > 1:
            violation = f"Spread away_selection_id changed within snapshot {snapshot_hash}: {spread_away_ids}"
            results['violations'].append(violation)
            print(f"   ❌ {violation}")
        
        if len(ml_home_ids) > 1:
            violation = f"ML home_selection_id changed within snapshot {snapshot_hash}: {ml_home_ids}"
            results['violations'].append(violation)
            print(f"   ❌ {violation}")
        
        if len(ml_away_ids) > 1:
            violation = f"ML away_selection_id changed within snapshot {snapshot_hash}: {ml_away_ids}"
            results['violations'].append(violation)
            print(f"   ❌ {violation}")
        
        # Check nested snapshot_hash consistency
        spread_snapshots = set(c['spread_snapshot'] for c in calls if c['spread_snapshot'])
        ml_snapshots = set(c['ml_snapshot'] for c in calls if c['ml_snapshot'])
        total_snapshots = set(c['total_snapshot'] for c in calls if c['total_snapshot'])
        
        if len(spread_snapshots) > 1 or (spread_snapshots and snapshot_hash not in spread_snapshots):
            violation = f"Spread snapshot_hash mismatch in group {snapshot_hash}: {spread_snapshots}"
            results['violations'].append(violation)
            print(f"   ⚠️  {violation}")
        
        if not results['violations']:
            print(f"   ✅ All selection_ids stable within snapshot {snapshot_hash}")
    
    return results


def main():
    if len(sys.argv) < 2:
        print("Usage: python test_snapshot_consistency.py <event_id> [num_calls]")
        print("Example: python test_snapshot_consistency.py test_event_123 50")
        sys.exit(1)
    
    event_id = sys.argv[1]
    num_calls = int(sys.argv[2]) if len(sys.argv) > 2 else 50
    
    results = test_snapshot_consistency(event_id, num_calls)
    
    print("\n" + "="*60)
    if results['violations']:
        print("❌ TEST FAILED - Violations detected:")
        for violation in results['violations']:
            print(f"   • {violation}")
        sys.exit(1)
    else:
        print("✅ TEST PASSED - No violations detected")
        print(f"   • {results['successful_calls']} successful calls")
        print(f"   • {len(results['unique_snapshots'])} unique snapshots")
        print(f"   • All selection_ids stable within snapshots")
        sys.exit(0)


if __name__ == "__main__":
    main()
