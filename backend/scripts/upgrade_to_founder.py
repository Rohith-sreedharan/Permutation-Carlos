"""
Auto-upgrade most recent user to FOUNDER tier
"""
from db.mongo import db
from datetime import datetime, timezone, timedelta

# Find most recent user
user = db.users.find_one(sort=[("created_at", -1)])

if not user:
    print("❌ No users found in database")
    exit(1)

user_id = user.get("user_id")
email = user.get("email", "N/A")

print(f"✅ Found most recent user: {email}")
print(f"   User ID: {user_id}")

# Create FOUNDER subscription
subscription = {
    "user_id": user_id,
    "tier": "FOUNDER",
    "status": "active",
    "start_date": datetime.now(timezone.utc).isoformat(),
    "end_date": (datetime.now(timezone.utc) + timedelta(days=365)).isoformat(),
    "payment_id": "manual_founder_upgrade",
    "created_at": datetime.now(timezone.utc).isoformat()
}

# Delete old subscriptions
result = db.subscriptions.delete_many({"user_id": user_id})
print(f"🗑️  Deleted {result.deleted_count} old subscriptions")

# Insert new FOUNDER subscription
db.subscriptions.insert_one(subscription)

print(f"\n🎉 SUCCESS! User upgraded to FOUNDER tier")
print(f"   • Status: active")
print(f"   • Expires: {subscription['end_date'][:10]}")
print(f"\n✅ Benefits unlocked:")
print(f"   • Unlimited free parlay generations")
print(f"   • Full parlay visibility (no blur)")
print(f"   • All premium features")
print(f"\n🔄 Refresh your browser to see changes")
