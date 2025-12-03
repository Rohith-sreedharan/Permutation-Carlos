"""
Script to upgrade user account to Elite tier.
Elite tier features:
- 100,000 Monte Carlo iterations
- All core features unlocked
- Advanced analytics
- AI Parlay Architect
- Premium insights
"""

import sys
import os
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from db.mongo import db

def upgrade_user_to_elite(email: str):
    """
    Upgrade user account to Elite tier.
    
    Args:
        email: User's email address
    """
    users_collection = db['users']
    subscribers_collection = db['subscribers']
    
    # Find user by email in users collection
    user = users_collection.find_one({'email': email})
    
    # Also check subscribers collection
    subscriber = subscribers_collection.find_one({'email': email})
    
    if not user and not subscriber:
        print(f"❌ User not found: {email}")
        print("\nCreating new Elite user...")
        
        # Create new elite user
        new_elite_user = {
            'email': email,
            'full_name': 'Elite User',
            'tier': 'elite',
            'iteration_limit': 100000,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow(),
            'subscription': {
                'tier': 'elite',
                'status': 'active',
                'started_at': datetime.utcnow(),
                'credits': 99999,
                'features': [
                    'monte_carlo_simulations',
                    'advanced_analytics',
                    'ai_parlay_architect',
                    'betting_command_center',
                    'edge_calculator',
                    'live_odds_integration',
                    'prop_simulator',
                    'risk_profiles',
                    'parlay_builder',
                    'performance_tracking',
                    'smart_alerts',
                    'priority_support'
                ]
            }
        }
        
        result = users_collection.insert_one(new_elite_user)
        
        # Also create in subscribers if needed
        new_subscriber = {
            'email': email,
            'tier': 'elite',
            'status': 'active',
            'created_at': datetime.utcnow(),
            'metadata': {
                'upgrade_date': datetime.utcnow(),
                'upgrade_source': 'manual_script'
            }
        }
        subscribers_collection.insert_one(new_subscriber)
        
        print(f"✅ Created new Elite user: {email}")
        print(f"User ID: {result.inserted_id}")
        print(f"Iteration Limit: 100,000")
        print(f"Features: All Elite features unlocked")
        return
    
    # Update existing user
    update_data = {
        'tier': 'elite',
        'iteration_limit': 100000,
        'updated_at': datetime.utcnow(),
        'subscription.tier': 'elite',
        'subscription.status': 'active',
        'subscription.features': [
            'monte_carlo_simulations',
            'advanced_analytics',
            'ai_parlay_architect',
            'betting_command_center',
            'edge_calculator',
            'live_odds_integration',
            'prop_simulator',
            'risk_profiles',
            'parlay_builder',
            'performance_tracking',
            'smart_alerts',
            'priority_support'
        ]
    }
    
    if user:
        users_collection.update_one(
            {'email': email},
            {'$set': update_data}
        )
    
    if subscriber:
        subscribers_collection.update_one(
            {'email': email},
            {'$set': {
                'tier': 'elite',
                'status': 'active',
                'updated_at': datetime.utcnow(),
                'metadata.upgrade_date': datetime.utcnow(),
                'metadata.upgrade_source': 'manual_script'
            }}
        )
    
    print(f"✅ User upgraded to Elite tier: {email}")
    print(f"Iteration Limit: 100,000")
    print(f"Status: Active")
    print(f"Features: All Elite features unlocked")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python upgrade_to_elite.py <email>")
        print("Example: python upgrade_to_elite.py user@example.com")
        sys.exit(1)
    
    email = sys.argv[1]
    upgrade_user_to_elite(email)
