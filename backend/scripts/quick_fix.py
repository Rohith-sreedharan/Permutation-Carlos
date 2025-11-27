"""
Quick fix script to update simulation field names and ensure passwords are hashed
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from db.mongo import db
import bcrypt

print("=" * 70)
print("FIXING REMAINING AUDIT ISSUES")
print("=" * 70)

# Fix 1: Rename 'sport' to 'sport_key' in simulations
print("\n🔄 Updating simulation field names...")
result = db.monte_carlo_simulations.update_many(
    {"sport": {"$exists": True}},
    {"$rename": {"sport": "sport_key"}}
)
print(f"   ✅ Updated {result.modified_count} simulation documents")

# Fix 2: Check password hashing again
print("\n🔒 Verifying password hashing...")
total_users = db.users.count_documents({})
bcrypt_users = db.users.count_documents({"hashed_password": {"$regex": "^\\$2b\\$"}})

if total_users == 0:
    print("   ℹ️  No users in database")
elif bcrypt_users == total_users:
    print(f"   ✅ All {total_users} users have bcrypt passwords")
else:
    print(f"   ⚠️  {total_users - bcrypt_users} users with plain text passwords")
    
    # Hash any remaining plain text passwords
    plain_users = list(db.users.find({"hashed_password": {"$not": {"$regex": "^\\$2b\\$"}}}))
    for user in plain_users:
        plain_password = user.get('hashed_password', 'DefaultPassword123!')
        
        # Truncate password if too long for bcrypt (72 byte limit)
        if isinstance(plain_password, str):
            plain_password_bytes = plain_password.encode('utf-8')[:72]
        else:
            plain_password_bytes = str(plain_password).encode('utf-8')[:72]
        
        # Generate bcrypt hash
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(plain_password_bytes, salt).decode('utf-8')
        
        db.users.update_one(
            {"_id": user["_id"]},
            {"$set": {"hashed_password": hashed}}
        )
    print(f"   ✅ Re-hashed {len(plain_users)} passwords with bcrypt")

# Verify collections exist
print("\n📦 Verifying collections...")
collections = db.list_collection_names()
required = ['user_bets', 'api_keys', 'prediction_logs', 'parlay_analysis']
for coll in required:
    exists = coll in collections
    symbol = "✅" if exists else "❌"
    print(f"   {symbol} {coll}: {'EXISTS' if exists else 'MISSING'}")

print("\n" + "=" * 70)
print("FIXES COMPLETE")
print("=" * 70)
