// MongoDB script to upgrade user to Admin tier
// Run: mongosh beatvegas < upgrade_admin.js
// Or in mongosh: load('upgrade_admin.js')

// Note: 'use beatvegas' must be run separately in mongosh, not in this file

// Find the first user or create demo admin
const existingUser = db.users.findOne();

if (existingUser) {
    print(`Found user: ${existingUser.email}`);
    print(`Current tier: ${existingUser.tier || 'Free'}`);
    
    // Upgrade to Admin
    db.users.updateOne(
        { _id: existingUser._id },
        {
            $set: {
                tier: 'Admin',
                iteration_limit: 500000,
                updated_at: new Date(),
                subscription: {
                    tier: 'Admin',
                    status: 'active',
                    started_at: new Date(),
                    credits: 999999,
                    features: [
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
                rbac: {
                    role: 'super_admin',
                    permissions: [
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
    );
    
    print('\n✅ User upgraded to Admin tier successfully!');
    print('\n🎉 New privileges:');
    print('   Tier: Admin');
    print('   Iteration Limit: 500,000');
    print('   Role: super_admin');
    print('   Credits: 999,999');
    print('\n🔓 Unlocked Features:');
    print('   ✅ Phase 16: Betting Command Center');
    print('   ✅ Phase 17: Trust Loop & Auto-Grading');
    print('   ✅ AI Parlay Architect');
    print('   ✅ Edge Calculator');
    print('   ✅ All advanced features enabled');
    
} else {
    print('No users found. Creating admin user...');
    
    db.users.insertOne({
        email: 'admin@beatvegas.local',
        full_name: 'Admin User',
        tier: 'Admin',
        iteration_limit: 500000,
        created_at: new Date(),
        updated_at: new Date(),
        subscription: {
            tier: 'Admin',
            status: 'active',
            started_at: new Date(),
            credits: 999999,
            features: [
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
        rbac: {
            role: 'super_admin',
            permissions: [
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
    });
    
    print('✅ Created admin user: admin@beatvegas.local');
}

// Show final user state
const updatedUser = db.users.findOne();
print('\n📊 Final User State:');
print(JSON.stringify(updatedUser, null, 2));
