"""
Seed test data for War Room Leaderboard
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from db.mongodb import db
import uuid
from datetime import datetime, timezone

def seed_leaderboard():
    """Create sample leaderboard entries"""
    
    # Clear existing data
    db["war_room_leaderboard"].delete_many({})
    
    sample_users = [
        {
            "user_id": str(uuid.uuid4()),
            "username": "SharpShooter",
            "rank": "elite",
            "units": 125.5,
            "win_rate": 0.582,
            "sample_size": 87,
            "volatility_adjusted_score": 94.2,
            "max_drawdown": 0.15,
            "template_compliance_pct": 98.5,
            "has_verified_track_record": True,
            "badges": ["Top 10", "Streak Master"],
        },
        {
            "user_id": str(uuid.uuid4()),
            "username": "ValueHunter",
            "rank": "elite",
            "units": 98.3,
            "win_rate": 0.567,
            "sample_size": 124,
            "volatility_adjusted_score": 91.8,
            "max_drawdown": 0.12,
            "template_compliance_pct": 96.2,
            "has_verified_track_record": True,
            "badges": ["Consistent", "High Volume"],
        },
        {
            "user_id": str(uuid.uuid4()),
            "username": "LineWizard",
            "rank": "verified",
            "units": 76.2,
            "win_rate": 0.554,
            "sample_size": 65,
            "volatility_adjusted_score": 87.5,
            "max_drawdown": 0.18,
            "template_compliance_pct": 95.0,
            "has_verified_track_record": True,
            "badges": ["Rising Star"],
        },
        {
            "user_id": str(uuid.uuid4()),
            "username": "BankrollBoss",
            "rank": "verified",
            "units": 54.8,
            "win_rate": 0.561,
            "sample_size": 43,
            "volatility_adjusted_score": 84.3,
            "max_drawdown": 0.14,
            "template_compliance_pct": 97.8,
            "has_verified_track_record": True,
            "badges": [],
        },
        {
            "user_id": str(uuid.uuid4()),
            "username": "EdgeSeeker",
            "rank": "verified",
            "units": 42.1,
            "win_rate": 0.548,
            "sample_size": 52,
            "volatility_adjusted_score": 81.7,
            "max_drawdown": 0.16,
            "template_compliance_pct": 93.5,
            "has_verified_track_record": True,
            "badges": ["Disciplined"],
        },
        {
            "user_id": str(uuid.uuid4()),
            "username": "PropMaster",
            "rank": "contributor",
            "units": 31.5,
            "win_rate": 0.537,
            "sample_size": 38,
            "volatility_adjusted_score": 78.2,
            "max_drawdown": 0.20,
            "template_compliance_pct": 91.0,
            "has_verified_track_record": False,
            "badges": [],
        },
        {
            "user_id": str(uuid.uuid4()),
            "username": "DataDriven",
            "rank": "contributor",
            "units": 28.3,
            "win_rate": 0.529,
            "sample_size": 45,
            "volatility_adjusted_score": 75.8,
            "max_drawdown": 0.22,
            "template_compliance_pct": 89.5,
            "has_verified_track_record": False,
            "badges": ["Methodical"],
        },
        {
            "user_id": str(uuid.uuid4()),
            "username": "SmartMoney",
            "rank": "contributor",
            "units": 19.7,
            "win_rate": 0.521,
            "sample_size": 29,
            "volatility_adjusted_score": 72.4,
            "max_drawdown": 0.19,
            "template_compliance_pct": 94.2,
            "has_verified_track_record": False,
            "badges": [],
        },
        {
            "user_id": str(uuid.uuid4()),
            "username": "UnderDogKing",
            "rank": "rookie",
            "units": 12.4,
            "win_rate": 0.516,
            "sample_size": 19,
            "volatility_adjusted_score": 68.9,
            "max_drawdown": 0.25,
            "template_compliance_pct": 87.0,
            "has_verified_track_record": False,
            "badges": [],
        },
        {
            "user_id": str(uuid.uuid4()),
            "username": "GrinderPro",
            "rank": "rookie",
            "units": 8.2,
            "win_rate": 0.509,
            "sample_size": 23,
            "volatility_adjusted_score": 65.3,
            "max_drawdown": 0.28,
            "template_compliance_pct": 85.5,
            "has_verified_track_record": False,
            "badges": [],
        },
    ]
    
    # Insert all users
    if sample_users:
        db["war_room_leaderboard"].insert_many(sample_users)
        print(f"✅ Seeded {len(sample_users)} leaderboard entries")
    else:
        print("⚠️ No data to seed")

if __name__ == "__main__":
    seed_leaderboard()
    print("🎉 War Room leaderboard seeded successfully!")
