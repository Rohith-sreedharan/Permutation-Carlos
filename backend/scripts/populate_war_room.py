"""
Populate War Room Leaderboard data for existing users.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.mongo import db
from datetime import datetime, timezone
import random


def get_existing_users():
    """Get all existing users from the database."""
    users = list(db['users'].find({}, {'_id': 1, 'username': 1, 'email': 1}))
    return users


def calculate_war_room_stats(user_id):
    """Calculate war room statistics based on user's actual activity."""
    # Check if user has any bets or picks in the system
    user_bets = list(db['bets'].find({'user_id': user_id}))
    user_picks = list(db['picks'].find({'user_id': user_id}))
    
    # If user has bets, calculate real stats
    if user_bets:
        graded_bets = [b for b in user_bets if b.get('result') in ['win', 'loss']]
        if graded_bets:
            wins = len([b for b in graded_bets if b.get('result') == 'win'])
            total = len(graded_bets)
            win_rate = wins / total if total > 0 else 0.5
            sample_size = total
            
            # Calculate units based on bet sizes and results
            units = sum([b.get('stake', 1) if b.get('result') == 'win' else -b.get('stake', 1) for b in graded_bets])
            
            # Calculate volatility score
            if sample_size >= 20:
                vol_score = (win_rate * 100) * (1 + (sample_size / 100))
            else:
                vol_score = (win_rate * 100) * (sample_size / 20)
            
            return {
                'win_rate': win_rate,
                'sample_size': sample_size,
                'units': round(units, 2),
                'vol_score': round(vol_score, 1),
                'rank': 'elite' if vol_score > 90 else 'verified' if vol_score > 70 and sample_size >= 20 else 'contributor' if sample_size >= 10 else 'rookie',
                'has_verified': sample_size >= 20 and win_rate >= 0.52
            }
    
    # Generate reasonable starter stats for users without activity
    # Small sample size so they appear at bottom of leaderboard
    sample_size = random.randint(3, 8)
    win_rate = random.uniform(0.45, 0.52)
    units = round(sample_size * (win_rate - 0.5) * 1.5, 2)
    vol_score = (win_rate * 100) * (sample_size / 20)
    
    return {
        'win_rate': win_rate,
        'sample_size': sample_size,
        'units': units,
        'vol_score': round(vol_score, 1),
        'rank': 'rookie',
        'has_verified': False
    }


def create_war_room_profile(user):
    """Create war room profile for a user."""
    user_id = str(user['_id'])
    username = user.get('username') or user.get('email', '').split('@')[0] or f"User_{user_id[:8]}"
    
    stats = calculate_war_room_stats(user_id)
    
    profile = {
        "user_id": user_id,
        "username": username,
        "rank": stats['rank'],
        "units": stats['units'],
        "win_rate": stats['win_rate'],
        "sample_size": stats['sample_size'],
        "volatility_adjusted_score": stats['vol_score'],
        "max_drawdown": round(random.uniform(0.05, 0.25), 3),
        "template_compliance_pct": round(random.uniform(75, 100), 1),
        "has_verified_track_record": stats['has_verified'],
        "badges": [],
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    
    # Add badges based on performance
    if stats['rank'] == 'elite':
        profile['badges'].append('🏆 Top Performer')
    if stats['has_verified']:
        profile['badges'].append('✓ Verified Track')
    
    db["war_room_profiles"].update_one(
        {"user_id": user_id},
        {"$set": profile},
        upsert=True
    )
    
    return profile


def main():
    print("🌱 Populating War Room profiles for existing users...")
    
    users = get_existing_users()
    
    if not users:
        print("❌ No users found in database!")
        return
    
    print(f"📋 Found {len(users)} existing users\n")
    
    profiles_created = []
    for user in users:
        profile = create_war_room_profile(user)
        profiles_created.append(profile)
        print(f"✓ Created profile for {profile['username']}")
        print(f"  Rank: {profile['rank']} | Score: {profile['volatility_adjusted_score']} | Win Rate: {profile['win_rate']*100:.1f}% | Picks: {profile['sample_size']}")
    
    print(f"\n✅ Successfully created {len(profiles_created)} War Room profiles!")
    
    # Show leaderboard preview
    print("\n📊 Leaderboard Preview (sorted by Vol Score):")
    sorted_profiles = sorted(profiles_created, key=lambda x: x['volatility_adjusted_score'], reverse=True)
    for i, profile in enumerate(sorted_profiles, 1):
        print(f"  #{i} {profile['username']:<20} Score: {profile['volatility_adjusted_score']:>6.1f} | WR: {profile['win_rate']*100:>5.1f}% | Picks: {profile['sample_size']:>3}")


if __name__ == "__main__":
    main()
