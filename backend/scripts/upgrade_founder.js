// Find most recent user and upgrade to FOUNDER
const user = db.users.findOne({}, {sort: {created_at: -1}});

if (!user) {
  print('❌ No user found');
} else {
  const userId = user.user_id;
  const email = user.email || 'N/A';
  
  print('✅ Found user: ' + email);
  print('   User ID: ' + userId);
  
  // Delete old subscriptions
  const delResult = db.subscriptions.deleteMany({user_id: userId});
  print('🗑️  Deleted ' + delResult.deletedCount + ' old subscriptions');
  
  // Create FOUNDER subscription
  const subscription = {
    user_id: userId,
    tier: 'FOUNDER',
    status: 'active',
    start_date: new Date().toISOString(),
    end_date: new Date(Date.now() + 365*24*60*60*1000).toISOString(),
    payment_id: 'manual_founder_upgrade',
    created_at: new Date().toISOString()
  };
  
  db.subscriptions.insertOne(subscription);
  
  print('');
  print('🎉 SUCCESS! Upgraded to FOUNDER tier');
  print('   • Unlimited free parlays');
  print('   • Full parlay visibility');
  print('   • All premium features');
  print('');
  print('🔄 REFRESH YOUR BROWSER NOW');
}
