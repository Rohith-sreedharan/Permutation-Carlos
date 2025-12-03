"""
Quick script to set user to FOUNDER tier for testing
"""
from db.mongo import db
from datetime import datetime, timezone, timedelta

# Get user_id from localStorage or input
user_id = input("Enter your user_id (from localStorage): ").strip()

if not user_id:
    print("❌ No user_id provided")
    exit(1)

# Check if user exists
user = db.users.find_one({"user_id": user_id})
if not user:
    print(f"❌ User {user_id} not found")
    exit(1)

print(f"✅ Found user: {user.get('email', 'N/A')}")

# Create or update subscription to FOUNDER tier
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
db.subscriptions.delete_many({"user_id": user_id})

# Insert new FOUNDER subscription
db.subscriptions.insert_one(subscription)

print(f"✅ User {user_id} upgraded to FOUNDER tier")
print(f"   • Status: active")
print(f"   • Expires: {subscription['end_date']}")
print(f"\n🎉 You now have unlimited free parlay access!")
print(f"   Refresh your browser to see changes.")
