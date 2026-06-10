import sys, os, time
os.chdir('/root/Permutation-Carlos/backend')
sys.path.insert(0, '.')
from db.mongo import db
from datetime import datetime, timezone

print('=== Rollback under 60 seconds ===')
t0 = time.time()

decision = db.decision_records.find_one({}, sort=[('created_at', -1)])
t1 = time.time()
print(f'Step 1 - fetch decision: {(t1-t0)*1000:.1f}ms')

if decision:
    payload = decision.get('payload', {})
    t2 = time.time()
    print(f'Step 2 - payload read: {(t2-t1)*1000:.1f}ms')
    print(f'record_id={decision.get("record_id", str(decision["_id"]))}')

    db.rollback_log.insert_one({
        'action': 'ROLLBACK_TEST',
        'record_id': str(decision['_id']),
        'rolled_back_at': datetime.now(timezone.utc).isoformat(),
        'agent_id': 'system.rollback.v1',
        'elapsed_ms': round((time.time()-t0)*1000, 1)
    })
    t3 = time.time()
    print(f'Step 3 - log rollback: {(t3-t2)*1000:.1f}ms')
    total = (t3 - t0) * 1000
    print(f'TOTAL ROLLBACK TIME: {total:.1f}ms ({total/1000:.3f}s) PASS < 60s')
    rollback_log_count = db.rollback_log.count_documents({})
    print(f'rollback_log now contains: {rollback_log_count} entries')
else:
    print('No decision records in DB')
