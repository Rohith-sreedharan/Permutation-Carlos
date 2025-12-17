#!/usr/bin/env python3
"""
Check if scheduler is running and when last grading occurred
"""
import sys
sys.path.insert(0, '/Users/rohithaditya/Downloads/Permutation-Carlos/backend')

from db.mongo import db
from datetime import datetime, timedelta

print("=" * 60)
print("SCHEDULER & GRADING STATUS CHECK")
print("=" * 60)

# Check if there are any completed events
now = datetime.utcnow()
two_days_ago = now - timedelta(days=2)

completed_events = list(db['events'].find({
    'commence_time': {'$lt': now.isoformat()},
    'scores': {'$exists': True, '$ne': None}
}).limit(10))

print(f"\n📅 Completed events with scores: {len(completed_events)}")
if completed_events:
    print("\n🏈 Sample completed events:")
    for event in completed_events[:5]:
        print(f"   - {event.get('away_team')} @ {event.get('home_team')}")
        print(f"     Commenced: {event.get('commence_time')}")
        print(f"     Scores: {event.get('scores')}")

# Check simulations for these events
if completed_events:
    event_ids = [e['id'] for e in completed_events]
    sims_for_completed = db['monte_carlo_simulations'].count_documents({
        'event_id': {'$in': event_ids}
    })
    print(f"\n🎲 Simulations for completed events: {sims_for_completed}")
    
    graded_sims_for_completed = db['monte_carlo_simulations'].count_documents({
        'event_id': {'$in': event_ids},
        'status': {'$in': ['WIN', 'LOSS', 'PUSH']}
    })
    print(f"✅ Graded simulations: {graded_sims_for_completed}")
    
    if sims_for_completed > 0 and graded_sims_for_completed == 0:
        print("\n⚠️  ISSUE DETECTED: Games completed but simulations not graded!")
        print("   The scheduler may not be running or grading logic has an issue.")

# Check logs for grading attempts
print("\n📋 Recent core AI logs (grading related):")
grading_logs = list(db['logs_core_ai'].find({
    'stage': {'$in': ['result_grading', 'auto_grading', 'grade_completed_games']}
}).sort('timestamp', -1).limit(5))

if grading_logs:
    for log in grading_logs:
        print(f"   [{log.get('timestamp')}] {log.get('stage')} - {log.get('status')}")
        if log.get('output_payload'):
            print(f"      Output: {log.get('output_payload')}")
else:
    print("   ❌ No grading logs found!")
    print("   This suggests the scheduler grading jobs have never run.")

# Check system_performance for last metric calculation
print("\n💾 Trust metrics cache:")
perf = db['system_performance'].find_one({}, sort=[('calculated_at', -1)])
if perf:
    calc_time = perf.get('calculated_at')
    if isinstance(calc_time, str):
        calc_time = datetime.fromisoformat(calc_time.replace('Z', '+00:00'))
    age = (datetime.now(calc_time.tzinfo) - calc_time).total_seconds() / 3600
    print(f"   Last calculated: {perf.get('calculated_at')}")
    print(f"   Age: {age:.1f} hours ago")
    print(f"   Metrics: {perf.get('metrics', {}).get('overall', {})}")
else:
    print("   ❌ No cached metrics found!")

print("\n" + "=" * 60)
print("DIAGNOSIS:")
print("=" * 60)

if completed_events and sims_for_completed > 0 and graded_sims_for_completed == 0:
    print("❌ SCHEDULER NOT RUNNING OR GRADING FAILING")
    print("\nTo fix:")
    print("1. Check if backend server is running with scheduler enabled")
    print("2. Check backend logs for scheduler errors")
    print("3. Manually trigger grading:")
    print("   python -c 'from services.scheduler import grade_completed_games; grade_completed_games()'")
elif not completed_events:
    print("⏳ NO COMPLETED GAMES YET")
    print("\nAll events are still upcoming. Wait for games to complete.")
else:
    print("✅ SYSTEM APPEARS TO BE WORKING")
    print("\nEither games are being graded or there are no completed games to grade.")

print("=" * 60)
