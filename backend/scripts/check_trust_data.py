#!/usr/bin/env python3
"""
Quick script to check Trust Loop data availability
"""
import sys
sys.path.insert(0, '/Users/rohithaditya/Downloads/Permutation-Carlos/backend')

from db.mongo import db
from datetime import datetime, timedelta

print("=" * 60)
print("TRUST LOOP DATA CHECK")
print("=" * 60)

# Check simulations collection
total_sims = db['monte_carlo_simulations'].count_documents({})
print(f"\n📊 Total simulations in DB: {total_sims}")

# Check for graded predictions
graded_sims = db['monte_carlo_simulations'].count_documents({
    'status': {'$in': ['WIN', 'LOSS', 'PUSH']}
})
print(f"✅ Graded simulations (WIN/LOSS/PUSH): {graded_sims}")

# Check for graded_at field
with_graded_at = db['monte_carlo_simulations'].count_documents({
    'graded_at': {'$exists': True, '$ne': None}
})
print(f"📅 Simulations with graded_at: {with_graded_at}")

# Check recent 7 days
seven_days_ago = datetime.utcnow() - timedelta(days=7)
recent_graded = db['monte_carlo_simulations'].count_documents({
    'graded_at': {'$gte': seven_days_ago},
    'status': {'$in': ['WIN', 'LOSS', 'PUSH']}
})
print(f"🕐 Graded in last 7 days: {recent_graded}")

# Check system_performance cache
performance_records = db['system_performance'].count_documents({})
print(f"\n💾 Cached performance records: {performance_records}")

# Sample a graded prediction if exists
sample = db['monte_carlo_simulations'].find_one({
    'status': {'$in': ['WIN', 'LOSS', 'PUSH']}
})

if sample:
    print("\n📋 Sample graded prediction:")
    print(f"   Event ID: {sample.get('event_id', 'N/A')}")
    print(f"   Status: {sample.get('status', 'N/A')}")
    print(f"   Graded At: {sample.get('graded_at', 'N/A')}")
    print(f"   Units Won: {sample.get('units_won', 0)}")
    print(f"   Confidence: {sample.get('confidence', 'N/A')}")
else:
    print("\n❌ No graded predictions found!")
    print("\n💡 This explains why Trust Loop shows all zeros.")
    print("   Games need to be completed and graded before metrics appear.")

# Check available collections
print("\n📚 Available collections:")
for col in sorted(db.list_collection_names()):
    count = db[col].count_documents({})
    if count > 0:
        print(f"   - {col}: {count} documents")

print("\n" + "=" * 60)
print("To populate Trust Loop metrics:")
print("1. Wait for games to complete")
print("2. Run the grading service to mark predictions as WIN/LOSS")
print("3. The Trust Loop will automatically show metrics")
print("=" * 60)
