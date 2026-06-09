import sys, os, json
os.chdir('/root/Permutation-Carlos/backend')
sys.path.insert(0, '.')
from db.mongo import db
from services.billing_ledger_service import billing_ledger
from uuid import uuid4
from datetime import datetime, timezone

TEST_USER = '69faa2266ee8fd32ae152b31'

# Try writing directly
trace = str(uuid4())
print(f'Direct log_state_change test (trace={trace})')
try:
    billing_ledger.log_state_change(
        user_id=TEST_USER,
        event_type='SUBSCRIPTION_TIER_UPDATED',
        trace_id=trace,
        old_tier='syndicate',
        new_tier='platform',
        stripe_subscription_id='sub_direct_test',
    )
    print('WRITE OK')
except Exception as e:
    print(f'WRITE ERROR: {e}')

# Verify
doc = db.billing_state_change_log.find_one({'trace_id': trace}, {'_id':0})
print('Found doc:', json.dumps(doc, default=str) if doc else 'NOT FOUND')

# Count all
total = db.billing_state_change_log.count_documents({})
print(f'Total billing_state_change_log docs: {total}')

# Check for any errors in the collection
print('All event_types in collection:')
for d in db.billing_state_change_log.find({}, {'event_type':1, 'user_id':1, '_id':0}).limit(20):
    print(' ', d)
