import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from db.mongo import db

print("=" * 70)
print("FINAL FIX: Adding sport_key to simulations")
print("=" * 70)

# Fetch all simulations
all_sims = list(db.monte_carlo_simulations.find())
print(f"\nFound {len(all_sims)} total simulations")

if len(all_sims) > 0:
    print(f"Sample keys: {list(all_sims[0].keys())[:10]}")
    
    # Check if any already have sport_key
    with_sport_key = [s for s in all_sims if 'sport_key' in s]
    print(f"Already have sport_key: {len(with_sport_key)}")
    print(f"Need update: {len(all_sims) - len(with_sport_key)}")
    
    # Update each simulation individually
    updated_count = 0
    for sim in all_sims:
        if 'sport_key' not in sim and 'sport' in sim:
            db.monte_carlo_simulations.update_one(
                {"_id": sim["_id"]},
                {"$set": {"sport_key": sim["sport"]}}
            )
            updated_count += 1
    
    print(f"\n✅ Added sport_key to {updated_count} simulations")
    
    # Final verification
    final_check = list(db.monte_carlo_simulations.find().limit(1))
    if final_check:
        sim = final_check[0]
        print(f"\nVerification:")
        print(f"  Has 'sport': {'sport' in sim}")
        print(f"  Has 'sport_key': {'sport_key' in sim}")
        if 'sport_key' in sim:
            print(f"  sport_key value: {sim['sport_key']}")
    
    # Check distinct sports
    sports = db.monte_carlo_simulations.distinct("sport_key")
    print(f"\nDistinct sports in DB: {sports}")
    print(f"Count: {len(sports)} sports")
    
print("\n" + "=" * 70)
print("COMPLETE")
print("=" * 70)
