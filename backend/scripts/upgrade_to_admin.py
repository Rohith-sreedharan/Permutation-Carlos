"""
Script to upgrade user account to Admin tier with full RBAC access.
Admin tier features:
- 500,000 Monte Carlo iterations
- All features unlocked (Phase 16 Betting Command Center, Phase 17 Trust Loop, etc.)
- Full access to all API endpoints
- AI Parlay Architect
- Advanced analytics
- Premium support
"""

import sys
import os
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from db.mongo import db

def upgrade_user_to_admin(email: str):
    """
    Upgrade user account to Admin tier with full privileges.
    
    Args:
        email: User's email address
    """
    users_collection = db['users']
    
    # Find user by email
    user = users_collection.find_one({'email': email})
    
    if not user:
        print(f"❌ User not found: {email}")
        print("\nCreating new admin user...")
        
        # Create new admin user
        new_admin = {
            'email': email,
            'full_name': 'Admin User',
            'tier': 'Admin',
            'iteration_limit': 500000,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow(),
            'subscription': {
                'tier': 'Admin',
                'status': 'active',
                'started_at': datetime.utcnow(),
                'credits': 999999,
                'features': [
                    'monte_carlo_simulations',
                    'advanced_analytics',
                    'ai_parlay_architect',
                    'betting_command_center',
                    'trust_loop_access',
                    'edge_calculator',
                    'live_odds_integration',
                    'prop_simulator',
                    'risk_profiles',
                    'parlay_builder',
                    'performance_tracking',
                    'smart_alerts',
                    'unlimited_simulations',
                    'priority_support',
                    'api_access',
                    'webhook_integration',
                    'custom_risk_profiles',
                    'white_label_access'
                ]
            },
            'rbac': {
                'role': 'super_admin',
                'permissions': [
                    'read:all',
                    'write:all',
                    'delete:all',
                    'admin:all',
                    'system:manage',
                    'users:manage',
                    'tiers:manage',
                    'features:manage',
                    'analytics:view',
                    'betting:manage',
                    'trust_metrics:view',
                    'trust_metrics:manage',
                    'grading:manual',
                    'notifications:send'
                ]
            }
        }
        
        result = users_collection.insert_one(new_admin)
        print(f"✅ Created new admin user: {email}")
        print(f"   User ID: {result.inserted_id}")
        print(f"   Tier: Admin")
        print(f"   Iteration Limit: 500,000")
        print(f"   Role: super_admin")
        print(f"   Features: {len(new_admin['subscription']['features'])} enabled")
        return
    
    # User exists - upgrade to Admin
    print(f"📊 Current user status:")
    print(f"   Email: {user.get('email')}")
    print(f"   Current Tier: {user.get('tier', 'Free')}")
    print(f"   Current Iteration Limit: {user.get('iteration_limit', 10000)}")
    print(f"   Current Role: {user.get('rbac', {}).get('role', 'user')}")
    
    # Upgrade to Admin
    update_result = users_collection.update_one(
        {'email': email},
        {
            '$set': {
                'tier': 'Admin',
                'iteration_limit': 500000,
                'updated_at': datetime.utcnow(),
                'subscription': {
                    'tier': 'Admin',
                    'status': 'active',
                    'started_at': datetime.utcnow(),
                    'credits': 999999,
                    'features': [
                        'monte_carlo_simulations',
                        'advanced_analytics',
                        'ai_parlay_architect',
                        'betting_command_center',
                        'trust_loop_access',
                        'edge_calculator',
                        'live_odds_integration',
                        'prop_simulator',
                        'risk_profiles',
                        'parlay_builder',
                        'performance_tracking',
                        'smart_alerts',
                        'unlimited_simulations',
                        'priority_support',
                        'api_access',
                        'webhook_integration',
                        'custom_risk_profiles',
                        'white_label_access'
                    ]
                },
                'rbac': {
                    'role': 'super_admin',
                    'permissions': [
                        'read:all',
                        'write:all',
                        'delete:all',
                        'admin:all',
                        'system:manage',
                        'users:manage',
                        'tiers:manage',
                        'features:manage',
                        'analytics:view',
                        'betting:manage',
                        'trust_metrics:view',
                        'trust_metrics:manage',
                        'grading:manual',
                        'notifications:send'
                    ]
                }
            }
        }
    )
    
    if update_result.modified_count > 0:
        print(f"\n✅ User upgraded to Admin tier successfully!")
        print(f"\n🎉 New privileges:")
        print(f"   Tier: Admin")
        print(f"   Iteration Limit: 500,000")
        print(f"   Role: super_admin")
        print(f"   Credits: 999,999")
        print(f"\n🔓 Unlocked Features:")
        print(f"   ✅ Phase 16: Betting Command Center")
        print(f"   ✅ Phase 17: Trust Loop & Auto-Grading")
        print(f"   ✅ AI Parlay Architect")
        print(f"   ✅ Edge Calculator")
        print(f"   ✅ Live Odds Integration")
        print(f"   ✅ Prop Simulator")
        print(f"   ✅ Risk Profiles")
        print(f"   ✅ Parlay Builder")
        print(f"   ✅ Performance Tracking")
        print(f"   ✅ Smart Alerts")
        print(f"   ✅ Unlimited Simulations")
        print(f"   ✅ Priority Support")
        print(f"   ✅ API Access")
        print(f"   ✅ Webhook Integration")
        print(f"   ✅ Custom Risk Profiles")
        print(f"   ✅ White Label Access")
        print(f"\n🔐 RBAC Permissions:")
        print(f"   ✅ read:all")
        print(f"   ✅ write:all")
        print(f"   ✅ delete:all")
        print(f"   ✅ admin:all")
        print(f"   ✅ system:manage")
        print(f"   ✅ users:manage")
        print(f"   ✅ tiers:manage")
        print(f"   ✅ features:manage")
        print(f"   ✅ analytics:view")
        print(f"   ✅ betting:manage")
        print(f"   ✅ trust_metrics:view")
        print(f"   ✅ trust_metrics:manage")
        print(f"   ✅ grading:manual")
        print(f"   ✅ notifications:send")
    else:
        print(f"\n⚠️ No changes made (user may already be Admin)")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python upgrade_to_admin.py <user_email>")
        print("Example: python upgrade_to_admin.py user@example.com")
        sys.exit(1)
    
    email = sys.argv[1]
    upgrade_user_to_admin(email)
