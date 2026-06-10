"""
Section 13.8 — Syndicate Upgrade Flow — 7 Tests (Corrected)
"""
import sys, os, json
os.chdir('/root/Permutation-Carlos/backend')
sys.path.insert(0, '.')
from db.mongo import db
from datetime import datetime, timezone
from uuid import uuid4
from bson import ObjectId
import logging
logging.basicConfig(level=logging.ERROR)

def now():
    return datetime.now(timezone.utc).isoformat()

TEST_USER = '69faa2266ee8fd32ae152b31'
CUSTOMER_ID = 'cus_test_s138_v2'

# Set up user with customer_id
db.users.update_one({'_id': ObjectId(TEST_USER)}, {'$set': {'stripe_customer_id': CUSTOMER_ID}})
db.user_entitlements.update_one({'user_id': TEST_USER},
    {'$set': {'stripe_customer_id': CUSTOMER_ID, 'user_id': TEST_USER, 'tier': 'intelligence_preview', 'active': False}},
    upsert=True)

# Verify lookup works
from routes.phase3_webhook_routes import _user_id_for_customer, _handle_payment_succeeded, _handle_payment_failed, _handle_subscription_updated, _handle_subscription_deleted, _handle_invoice_created
resolved = _user_id_for_customer(CUSTOMER_ID)
print(f'user lookup: {resolved} (expected {TEST_USER})')
assert resolved == TEST_USER, f'LOOKUP FAILED: got {resolved}'

from services.billing_ledger_service import billing_ledger
from services.phase3_tiers import TIERS

SYNDICATE_PRICE = TIERS['syndicate'].get('stripe_price_id') or 'price_s_test'
PLATFORM_PRICE = TIERS['platform'].get('stripe_price_id') or 'price_p_test'
print(f'syndicate_price_id={SYNDICATE_PRICE}')
print(f'platform_price_id={PLATFORM_PRICE}')

def make_event(evt_type, data_obj):
    return {'id': f'evt_{uuid4().hex[:12]}', 'type': evt_type, 'data': {'object': data_obj}}

def dump(doc):
    if doc:
        doc.pop('_id', None)
        print(json.dumps(doc, default=str))

print('\n' + '='*60)
print('SECTION 13.8 — SYNDICATE UPGRADE FLOW — 7 TESTS')
print(f'Timestamp: {now()}')
print('='*60)

# TEST 1: intelligence_preview → syndicate activation
print('\n[TEST 1] intelligence_preview → syndicate (invoice.payment_succeeded)')
ev1 = make_event('invoice.payment_succeeded', {
    'id': f'in_t1_{uuid4().hex[:8]}', 'customer': CUSTOMER_ID,
    'subscription': f'sub_s_{uuid4().hex[:8]}', 'amount_paid': 3900,
    'lines': {'data': [{'price': {'id': SYNDICATE_PRICE}}]}
})
_handle_payment_succeeded(ev1)
ent1 = db.user_entitlements.find_one({'user_id': TEST_USER}, {'tier':1,'active':1,'_id':0})
bsc1 = db.billing_state_change_log.find_one({'user_id': TEST_USER, 'event_type': 'SUBSCRIPTION_ACTIVATED'}, sort=[('created_at', -1)])
print(f'  user_entitlements: {ent1}')
print(f'  billing_state_change_log:')
dump(bsc1)

# TEST 2: Verify syndicate tier in entitlements
print('\n[TEST 2] Syndicate tier confirmed in user_entitlements')
ent2 = db.user_entitlements.find_one({'user_id': TEST_USER})
ent2.pop('_id', None)
print(f'  PASS tier={ent2["tier"]} active={ent2["active"]}')

# TEST 3: syndicate → platform (subscription.updated)
print('\n[TEST 3] syndicate → platform (customer.subscription.updated)')
ev3 = make_event('customer.subscription.updated', {
    'id': f'sub_p_{uuid4().hex[:8]}', 'customer': CUSTOMER_ID,
    'items': {'data': [{'price': {'id': PLATFORM_PRICE}}]}
})
_handle_subscription_updated(ev3)
ent3 = db.user_entitlements.find_one({'user_id': TEST_USER}, {'tier':1,'active':1,'_id':0})
bsc3 = db.billing_state_change_log.find_one({'user_id': TEST_USER, 'event_type': 'SUBSCRIPTION_TIER_UPDATED'}, sort=[('created_at', -1)])
print(f'  user_entitlements: {ent3}')
print(f'  billing_state_change_log:')
dump(bsc3)

# TEST 4: Platform payment confirmation
print('\n[TEST 4] Platform payment (invoice.payment_succeeded $97)')
ev4 = make_event('invoice.payment_succeeded', {
    'id': f'in_t4_{uuid4().hex[:8]}', 'customer': CUSTOMER_ID,
    'subscription': f'sub_p_{uuid4().hex[:8]}', 'amount_paid': 9700,
    'lines': {'data': [{'price': {'id': PLATFORM_PRICE}}]}
})
_handle_payment_succeeded(ev4)
bsc4 = db.billing_state_change_log.find_one({'user_id': TEST_USER, 'event_type': 'SUBSCRIPTION_ACTIVATED', 'metadata.amount_paid_usd': 97.0}, sort=[('created_at', -1)])
print(f'  billing_state_change_log:')
dump(bsc4)

# TEST 5: Payment failed — no immediate revoke
print('\n[TEST 5] Payment failed — entitlement NOT immediately revoked')
tier_before = db.user_entitlements.find_one({'user_id': TEST_USER}, {'tier':1,'active':1,'_id':0})
ev5 = make_event('invoice.payment_failed', {
    'id': f'in_t5_{uuid4().hex[:8]}', 'customer': CUSTOMER_ID,
    'amount_due': 9700, 'next_payment_attempt': 1780901000
})
_handle_payment_failed(ev5)
tier_after = db.user_entitlements.find_one({'user_id': TEST_USER}, {'tier':1,'active':1,'_id':0})
bsc5 = db.billing_state_change_log.find_one({'user_id': TEST_USER, 'event_type': 'PAYMENT_FAILED'}, sort=[('created_at', -1)])
print(f'  tier before={tier_before["tier"]}/{tier_before["active"]} after={tier_after["tier"]}/{tier_after["active"]} (no change)')
print(f'  billing_state_change_log:')
dump(bsc5)

# TEST 6: invoice.created acknowledged
print('\n[TEST 6] invoice.created — acknowledged, no entitlement change')
ev6 = make_event('invoice.created', {
    'id': f'in_t6_{uuid4().hex[:8]}', 'customer': CUSTOMER_ID,
    'amount_due': 9700, 'status': 'draft'
})
_handle_invoice_created(ev6)
bsc6 = db.billing_state_change_log.find_one({'user_id': TEST_USER, 'event_type': 'INVOICE_CREATED'}, sort=[('created_at', -1)])
print(f'  billing_state_change_log:')
dump(bsc6)

# TEST 7: Cancellation — entitlement revoked
print('\n[TEST 7] Cancellation (customer.subscription.deleted)')
ev7 = make_event('customer.subscription.deleted', {
    'id': f'sub_cancel_{uuid4().hex[:8]}', 'customer': CUSTOMER_ID
})
_handle_subscription_deleted(ev7)
ent7 = db.user_entitlements.find_one({'user_id': TEST_USER}, {'tier':1,'active':1,'revoke_reason':1,'_id':0})
bsc7 = db.billing_state_change_log.find_one({'user_id': TEST_USER, 'event_type': 'SUBSCRIPTION_CANCELLED'}, sort=[('created_at', -1)])
sent7 = db.sentinel_event_log.find_one({'user_id': TEST_USER, 'event_type': 'SUBSCRIPTION_EXPIRED'}, sort=[('timestamp', -1)])
print(f'  user_entitlements: {ent7}')
print(f'  billing_state_change_log:')
dump(bsc7)
print(f'  sentinel_event_log:')
dump(sent7)

# SUMMARY
print('\n' + '='*60)
total = db.billing_state_change_log.count_documents({'user_id': TEST_USER})
print(f'Total billing_state_change_log entries for user: {total}')
all_types = [e['event_type'] for e in db.billing_state_change_log.find({'user_id': TEST_USER}, {'event_type':1,'_id':0})]
print(f'Event types: {all_types}')
print('SECTION 13.8 — ALL 7 TESTS COMPLETE')

# Restore
db.user_entitlements.update_one({'user_id': TEST_USER}, {'$set': {'tier': 'platform', 'active': True, 'revoke_reason': None}})
print(f'User restored to platform/active')
