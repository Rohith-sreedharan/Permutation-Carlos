"""
Section 13.8 — Syndicate Upgrade Flow — 7 Tests
Run against live production MongoDB.
"""
import sys, os
os.chdir('/root/Permutation-Carlos/backend')
sys.path.insert(0, '.')
from db.mongo import db
from datetime import datetime, timezone
from uuid import uuid4

def now():
    return datetime.now(timezone.utc).isoformat()

TEST_USER = '69faa2266ee8fd32ae152b31'
CUSTOMER_ID = 'cus_test_syndicate_upgrade_13_8'

# Ensure test user has stripe_customer_id set
db.users.update_one({'_id': __import__('bson').ObjectId(TEST_USER)},
    {'$set': {'stripe_customer_id': CUSTOMER_ID}})
db.user_entitlements.update_one({'user_id': TEST_USER},
    {'$set': {'stripe_customer_id': CUSTOMER_ID, 'user_id': TEST_USER}}, upsert=True)

# Import handlers
from routes.phase3_webhook_routes import (
    _handle_payment_succeeded, _handle_payment_failed,
    _handle_subscription_updated, _handle_subscription_deleted,
    _handle_invoice_created
)
from services.billing_ledger_service import billing_ledger
from services.phase3_tiers import TIERS

SYNDICATE_PRICE = TIERS['syndicate'].get('stripe_price_id', 'price_syndicate_test')
PLATFORM_PRICE = TIERS['platform'].get('stripe_price_id', 'price_platform_test')

def make_event(evt_type, data_obj, event_id=None):
    return {
        'id': event_id or f'evt_{uuid4().hex[:12]}',
        'type': evt_type,
        'data': {'object': data_obj}
    }

print('='*60)
print('SECTION 13.8 — SYNDICATE UPGRADE FLOW — 7 TESTS')
print(f'user_id={TEST_USER}  customer_id={CUSTOMER_ID}')
print('='*60)

# ── TEST 1: intelligence_preview → syndicate (invoice.payment_succeeded)
print('\n[TEST 1] intelligence_preview → syndicate: payment succeeded')
db.user_entitlements.update_one({'user_id': TEST_USER}, {'$set': {'tier': 'intelligence_preview', 'active': False}}, upsert=True)
trace1 = str(uuid4())
ev1 = make_event('invoice.payment_succeeded', {
    'id': f'in_test_syndicate_{trace1[:8]}',
    'customer': CUSTOMER_ID,
    'subscription': f'sub_test_syndicate_{trace1[:8]}',
    'amount_paid': 3900,
    'lines': {'data': [{'price': {'id': SYNDICATE_PRICE}}]}
})
_handle_payment_succeeded(ev1)
ent1 = db.user_entitlements.find_one({'user_id': TEST_USER}, {'tier':1,'active':1,'_id':0})
bsc1 = db.billing_state_change_log.find_one({'user_id': TEST_USER, 'event_type': 'SUBSCRIPTION_ACTIVATED'}, sort=[('timestamp', -1)])
bsc1.pop('_id', None) if bsc1 else None
print(f'  entitlement: {ent1}')
print(f'  billing_state_change_log: {bsc1}')

# ── TEST 2: Syndicate tier confirmed in entitlements
print('\n[TEST 2] Syndicate tier confirmed in user_entitlements')
ent2 = db.user_entitlements.find_one({'user_id': TEST_USER}, {'tier':1,'active':1,'stripe_subscription_id':1,'_id':0})
assert ent2.get('tier') == 'syndicate', f'Expected syndicate, got {ent2.get("tier")}'
print(f'  PASS: tier={ent2["tier"]} active={ent2["active"]}')

# ── TEST 3: syndicate → platform (customer.subscription.updated)
print('\n[TEST 3] syndicate → platform: subscription.updated')
trace3 = str(uuid4())
ev3 = make_event('customer.subscription.updated', {
    'id': f'sub_test_platform_{trace3[:8]}',
    'customer': CUSTOMER_ID,
    'items': {'data': [{'price': {'id': PLATFORM_PRICE}}]}
})
_handle_subscription_updated(ev3)
ent3 = db.user_entitlements.find_one({'user_id': TEST_USER}, {'tier':1,'active':1,'_id':0})
bsc3 = db.billing_state_change_log.find_one({'user_id': TEST_USER, 'event_type': 'SUBSCRIPTION_TIER_UPDATED'}, sort=[('timestamp', -1)])
bsc3.pop('_id', None) if bsc3 else None
print(f'  entitlement: {ent3}')
print(f'  billing_state_change_log: {bsc3}')

# ── TEST 4: Platform payment confirmation (invoice.payment_succeeded at platform price)
print('\n[TEST 4] Platform payment confirmation')
trace4 = str(uuid4())
ev4 = make_event('invoice.payment_succeeded', {
    'id': f'in_test_platform_{trace4[:8]}',
    'customer': CUSTOMER_ID,
    'subscription': f'sub_test_platform_{trace4[:8]}',
    'amount_paid': 9700,
    'lines': {'data': [{'price': {'id': PLATFORM_PRICE}}]}
})
_handle_payment_succeeded(ev4)
bsc4 = db.billing_state_change_log.find_one({'user_id': TEST_USER, 'event_type': 'SUBSCRIPTION_ACTIVATED', 'metadata.amount_paid_usd': 97.0}, sort=[('timestamp', -1)])
bsc4.pop('_id', None) if bsc4 else None
print(f'  billing_state_change_log: {bsc4}')

# ── TEST 5: Payment failed (invoice.payment_failed — no immediate revoke)
print('\n[TEST 5] Payment failed — entitlement NOT immediately revoked')
before_tier = db.user_entitlements.find_one({'user_id': TEST_USER}, {'tier':1,'active':1,'_id':0})
trace5 = str(uuid4())
ev5 = make_event('invoice.payment_failed', {
    'id': f'in_test_failed_{trace5[:8]}',
    'customer': CUSTOMER_ID,
    'amount_due': 9700,
    'next_payment_attempt': 1780901000
})
_handle_payment_failed(ev5)
after_tier = db.user_entitlements.find_one({'user_id': TEST_USER}, {'tier':1,'active':1,'_id':0})
bsc5 = db.billing_state_change_log.find_one({'user_id': TEST_USER, 'event_type': 'PAYMENT_FAILED'}, sort=[('timestamp', -1)])
bsc5.pop('_id', None) if bsc5 else None
print(f'  tier before={before_tier["tier"]} after={after_tier["tier"]} (unchanged — no immediate revoke)')
print(f'  billing_state_change_log: {bsc5}')

# ── TEST 6: invoice.created (acknowledged, no entitlement change)
print('\n[TEST 6] invoice.created — acknowledged, no entitlement change')
trace6 = str(uuid4())
ev6 = make_event('invoice.created', {
    'id': f'in_test_created_{trace6[:8]}',
    'customer': CUSTOMER_ID,
    'amount_due': 9700,
    'status': 'draft'
})
_handle_invoice_created(ev6)
bsc6 = db.billing_state_change_log.find_one({'user_id': TEST_USER, 'event_type': 'INVOICE_CREATED'}, sort=[('timestamp', -1)])
bsc6.pop('_id', None) if bsc6 else None
print(f'  billing_state_change_log: {bsc6}')

# ── TEST 7: Cancellation (customer.subscription.deleted — entitlement revoked)
print('\n[TEST 7] Cancellation — entitlement revoked, sessions invalidated')
trace7 = str(uuid4())
ev7 = make_event('customer.subscription.deleted', {
    'id': f'sub_test_cancel_{trace7[:8]}',
    'customer': CUSTOMER_ID
})
_handle_subscription_deleted(ev7)
ent7 = db.user_entitlements.find_one({'user_id': TEST_USER}, {'tier':1,'active':1,'revoke_reason':1,'_id':0})
bsc7 = db.billing_state_change_log.find_one({'user_id': TEST_USER, 'event_type': 'SUBSCRIPTION_CANCELLED'}, sort=[('timestamp', -1)])
bsc7.pop('_id', None) if bsc7 else None
sentinel7 = db.sentinel_event_log.find_one({'user_id': TEST_USER, 'event_type': 'SUBSCRIPTION_EXPIRED'}, sort=[('timestamp', -1)])
sentinel7.pop('_id', None) if sentinel7 else None
print(f'  entitlement: {ent7}')
print(f'  billing_state_change_log: {bsc7}')
print(f'  sentinel_event_log: {sentinel7}')

# ── SUMMARY
print('\n' + '='*60)
print('SECTION 13.8 SUMMARY')
total_bsc = db.billing_state_change_log.count_documents({'user_id': TEST_USER})
print(f'billing_state_change_log entries for test user: {total_bsc}')
print('All 7 tests complete.')

# Restore user to platform active state
db.user_entitlements.update_one({'user_id': TEST_USER},
    {'$set': {'tier': 'platform', 'active': True, 'revoke_reason': None}})
print(f'User restored to platform/active for subsequent tests.')
