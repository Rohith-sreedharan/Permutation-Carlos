from pymongo import MongoClient

client = MongoClient('mongodb://localhost:27017')
db = client['beatvegas']

print("=" * 70)
print("UPDATING beatvegas DATABASE")
print("=" * 70)

# Get all simulations from beatvegas
sims = list(db.monte_carlo_simulations.find())
print(f"\nFound {len(sims)} simulations in beatvegas database")

# Update each simulation to have sport_key
updated = 0
for sim in sims:
    if 'sport' in sim and 'sport_key' not in sim:
        db.monte_carlo_simulations.update_one(
            {"_id": sim["_id"]},
            {"$set": {"sport_key": sim["sport"]}}
        )
        updated += 1
        print(f"  ✅ Added sport_key='{sim['sport']}' to simulation {sim.get('simulation_id', sim['_id'])}")

print(f"\n✅ Updated {updated} simulations")

# Verify
sports = db.monte_carlo_simulations.distinct("sport_key")
print(f"\nDistinct sport_key values: {sports}")
print(f"Count: {len(sports)} sports")

print("\n" + "=" * 70)
print("DONE")
print("=" * 70)
