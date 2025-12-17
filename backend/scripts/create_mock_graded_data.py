#!/usr/bin/env python3
"""
Create mock graded predictions to test Trust Loop UI
This populates the database with sample WIN/LOSS data
"""
import sys
sys.path.insert(0, '/Users/rohithaditya/Downloads/Permutation-Carlos/backend')

from db.mongo import db
from datetime import datetime, timedelta, timezone
import random

print("=" * 60)
print("CREATING MOCK GRADED PREDICTIONS FOR TRUST LOOP TESTING")
print("=" * 60)

# Get some simulations
simulations = list(db['monte_carlo_simulations'].find({}).limit(30))

if not simulations:
    print("\n❌ No simulations found! Run some simulations first.")
    exit(1)

print(f"\n📊 Found {len(simulations)} simulations to grade...")

graded_count = 0
wins = 0
losses = 0
pushes = 0

for i, sim in enumerate(simulations):
    # Randomly assign outcomes (weighted for realistic performance)
    outcome_roll = random.random()
    
    if outcome_roll < 0.58:  # 58% win rate (good performance)
        status = 'WIN'
        units_won = random.uniform(0.85, 0.95)  # Standard unit wins
        wins += 1
    elif outcome_roll < 0.90:  # 32% loss rate
        status = 'LOSS'
        units_won = -1.0  # Standard unit loss
        losses += 1
    else:  # 10% push rate
        status = 'PUSH'
        units_won = 0.0
        pushes += 1
    
    # Set graded_at to past 7 days (spread out)
    days_ago = random.randint(1, 7)
    graded_at = datetime.now(timezone.utc) - timedelta(days=days_ago)
    
    # Update the simulation
    db['monte_carlo_simulations'].update_one(
        {'_id': sim['_id']},
        {
            '$set': {
                'status': status,
                'units_won': units_won,
                'graded_at': graded_at.isoformat(),
                'graded': True,
                'actual_result': {
                    'outcome': status,
                    'mock_data': True
                }
            }
        }
    )
    
    graded_count += 1

print(f"\n✅ Graded {graded_count} simulations:")
print(f"   Wins: {wins} ({wins/graded_count*100:.1f}%)")
print(f"   Losses: {losses} ({losses/graded_count*100:.1f}%)")
print(f"   Pushes: {pushes} ({pushes/graded_count*100:.1f}%)")

# Calculate metrics
total_units = sum([
    sim.get('units_won', 0) 
    for sim in db['monte_carlo_simulations'].find({'status': {'$in': ['WIN', 'LOSS', 'PUSH']}})
])

win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
roi = (total_units / graded_count * 100) if graded_count > 0 else 0

print(f"\n📈 Performance Metrics:")
print(f"   Win Rate: {win_rate:.1f}%")
print(f"   Total Units: {total_units:+.2f}")
print(f"   ROI: {roi:+.1f}%")

# Manually trigger trust metrics calculation
print("\n🔄 Calculating trust metrics...")

try:
    from services.trust_metrics import trust_metrics_service
    import asyncio
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    metrics = loop.run_until_complete(
        trust_metrics_service.calculate_all_metrics()
    )
    
    loop.close()
    
    print("✅ Trust metrics calculated successfully!")
    print(f"\n📊 Trust Loop Metrics:")
    print(f"   7-day Accuracy: {metrics['overall']['7day_accuracy']}%")
    print(f"   7-day Record: {metrics['overall']['7day_record']}")
    print(f"   30-day ROI: {metrics['overall']['30day_roi']}%")
    print(f"   Brier Score: {metrics['overall']['brier_score']}")
    
except Exception as e:
    print(f"❌ Error calculating metrics: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("✅ MOCK DATA CREATED!")
print("Refresh your Trust Loop page to see the metrics.")
print("=" * 60)
print("\nNote: This is mock data for testing only.")
print("In production, you need a scores API to grade real predictions.")
