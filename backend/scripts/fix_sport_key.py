import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from db.mongo import db

# Get all simulations and update each one
sims = list(db.monte_carlo_simulations.find({"sport": {"$exists": True}}))
print(f"Found {len(sims)} simulations with 'sport' field")

count = 0
for sim in sims:
    if 'sport' in sim:
        db.monte_carlo_simulations.update_one(
            {"_id": sim["_id"]},
            {"$set": {"sport_key": sim["sport"]}}
        )
        count += 1

print(f"✅ Updated {count} simulations with sport_key field")

# Verify
sims_check = list(db.monte_carlo_simulations.find().limit(1))
if sims_check:
    print(f"Sample simulation has sport_key: {'sport_key' in sims_check[0]}")
    print(f"Value: {sims_check[0].get('sport_key', 'NOT FOUND')}")
