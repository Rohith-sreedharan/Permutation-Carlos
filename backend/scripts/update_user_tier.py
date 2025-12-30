"""
Quick script to update a user to elite tier in production
Usage: python update_user_tier.py
"""
from pymongo import MongoClient
from datetime import datetime, timezone
import os

# MongoDB connection
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
client = MongoClient(MONGO_URI)
db = client["aibets"]

def update_user_to_elite(email: str):
    """Update user to elite tier with all features enabled"""
    
    # Define elite tier settings
    elite_settings = {
        "plan": "founder",  # Highest tier
        "status": "converted",
        "monthly_value": 0.0,  # Free elite access
        "access_monte_carlo": True,
        "access_clv_tracker": True,
        "access_advanced_dashboards": True,
        "access_prop_mispricing": True,
        "access_parlay_correlation": True,
        "max_picks_per_day": 999999,  # Unlimited
        "converted_at": datetime.now(timezone.utc).isoformat()
    }
    
    # Update the user
    result = db.subscribers.update_one(
        {"email": email},
        {"$set": elite_settings}
    )
    
    if result.matched_count == 0:
        print(f"❌ User not found: {email}")
        print("Creating new user with elite access...")
        
        # Create new user if doesn't exist
        from uuid import uuid4
        new_user = {
            "id": str(uuid4()),
            "email": email,
            "ref": None,
            "variant": None,
            "stripe_customer_id": None,
            "stripe_subscription_id": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "trial_started_at": None,
            "churned_at": None,
            **elite_settings
        }
        db.subscribers.insert_one(new_user)
        print(f"✅ Created new user {email} with elite (founder) tier")
    else:
        print(f"✅ Updated {email} to elite (founder) tier")
        print(f"   - Plan: founder")
        print(f"   - All features: ENABLED")
        print(f"   - Max picks: UNLIMITED")
    
    # Verify
    user = db.subscribers.find_one({"email": email})
    if user:
        print(f"\n📊 Current settings:")
        print(f"   Email: {user['email']}")
        print(f"   Plan: {user.get('plan', 'N/A')}")
        print(f"   Status: {user.get('status', 'N/A')}")
        print(f"   Monte Carlo: {user.get('access_monte_carlo', False)}")
        print(f"   CLV Tracker: {user.get('access_clv_tracker', False)}")
        print(f"   Max Picks: {user.get('max_picks_per_day', 0)}")

if __name__ == "__main__":
    email = "beatvegasapp@gmail.com"
    print(f"🚀 Updating {email} to elite tier...")
    update_user_to_elite(email)
    print("\n✨ Done!")
