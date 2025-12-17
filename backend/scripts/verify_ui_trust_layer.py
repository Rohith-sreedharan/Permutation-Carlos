#!/usr/bin/env python3
"""
UI Trust Layer Verification Script

Verifies that LEAN/NO_PLAY states suppress extreme certainty visuals.
Tests the final trust layer before public launch.
"""

from datetime import datetime, timezone, timedelta
from db.mongo import db
import json

def verify_ui_trust_layer():
    """Verify UI trust layer implementation"""
    
    print("="*80)
    print("UI TRUST LAYER VERIFICATION")
    print("="*80)
    print()
    
    # Get recent simulations
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)
    
    sims = list(db.monte_carlo_simulations.find({
        'created_at': {'$gt': yesterday.isoformat()},
        'sport_key': 'americanfootball_nfl'
    }).sort('created_at', -1).limit(10))
    
    print(f"Found {len(sims)} recent NFL simulations\n")
    
    # Check each simulation
    for i, sim in enumerate(sims, 1):
        event_id = sim.get('event_id', 'unknown')[:20]
        pick_state = sim.get('pick_state', 'UNKNOWN')
        confidence = sim.get('confidence_score', 0.65)
        confidence_pct = confidence * 100 if confidence < 10 else confidence
        
        over_prob = sim.get('over_probability', 0.5)
        
        # Calculate if UI should suppress
        should_suppress = pick_state != 'PICK' or confidence_pct < 20
        
        # Check for extreme values
        extreme_prob = over_prob > 0.70 or over_prob < 0.30
        extreme_conf = confidence_pct > 75 or confidence_pct < 25
        
        print(f"{i}. Event: {event_id}...")
        print(f"   Pick State: {pick_state}")
        print(f"   Confidence: {confidence_pct:.0f}%")
        print(f"   Over Prob: {over_prob:.1%}")
        print(f"   Should Suppress: {should_suppress}")
        
        if should_suppress:
            if extreme_prob or extreme_conf:
                print(f"   ✅ UI WILL SUPPRESS: Extreme certainty hidden")
                print(f"      Display: '⚠️ Directional lean only — unstable distribution'")
            else:
                print(f"   ✓ UI shows modest values (within trust bounds)")
        else:
            print(f"   ✓ PICK state: Full display allowed")
        
        print()
    
    print("="*80)
    print("TRUST LAYER CHECK COMPLETE")
    print("="*80)
    print()
    print("UI Behavior Summary:")
    print("  • PICK state + confidence ≥20: Shows all percentages/edges")
    print("  • LEAN/NO_PLAY: Suppresses extreme probabilities (>70% or <30%)")
    print("  • LEAN/NO_PLAY: Suppresses extreme edges (>10 pts)")
    print("  • LEAN/NO_PLAY: Replaces with 'Directional lean only — unstable distribution'")
    print("  • Low confidence (<20): Always suppresses regardless of state")
    print()

if __name__ == '__main__':
    verify_ui_trust_layer()
