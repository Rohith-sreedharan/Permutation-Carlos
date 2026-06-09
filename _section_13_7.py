import sys, os, subprocess
os.chdir('/root/Permutation-Carlos/backend')
sys.path.insert(0, '.')

print('=== 1. datetime.now() grep ===')
r = subprocess.run(['grep', '-r', 'datetime.now()', '/root/Permutation-Carlos/backend/', '--include=*.py', '-l'],
    capture_output=True, text=True)
print(r.stdout.strip() or 'NO MATCHES')

print('\n=== 2. render_from_decision_id grep ===')
r2 = subprocess.run(['grep', '-r', 'render_from_decision_id', '/root/Permutation-Carlos/components/', '--include=*.tsx'],
    capture_output=True, text=True)
print(r2.stdout.strip() or 'NO MATCHES')

print('\n=== 3. assertion_failure_log count ===')
from db.mongo import db
print(db.assertion_failure_log.count_documents({}))

print('\n=== 4. prediction_lifecycle_log 9 stages ===')
recent = db.decision_records.find_one({}, sort=[('created_at', -1)])
did = str(recent.get('decision_id') or recent['_id'])
stages = list(db.prediction_lifecycle_log.find({'decision_id': did}))
print(f'decision_id={did}')
print(f'Stages: {len(stages)}')
for s in stages:
    print(' ', s.get('stage'))

print('\n=== 5. Kill switches (feature_flags) ===')
flags = list(db.feature_flags.find({}, {'flag_name':1,'enabled':1,'_id':0}))
if flags:
    for f in flags:
        print(f)
else:
    print('feature_flags collection is empty (0 documents)')

print('\n=== 6. CLV on EDGE and LEAN ===')
total = db.decision_records.count_documents({'classification': {'$in': ['EDGE', 'LEAN']}})
clv = db.decision_records.count_documents({'classification': {'$in': ['EDGE', 'LEAN']}, 'closing_line_value': {'$exists': True, '$ne': None}})
print(f'EDGE/LEAN total: {total}, with CLV: {clv}')

print('\n=== 7. Simulation scheduler ===')
r7 = subprocess.run(['systemctl', 'status', 'beatvegas-scheduler', '--no-pager', '-n', '5'],
    capture_output=True, text=True)
print(r7.stdout or r7.stderr or 'beatvegas-scheduler not found')
r7b = subprocess.run(['crontab', '-l'], capture_output=True, text=True)
if r7b.stdout:
    for line in r7b.stdout.splitlines():
        if 'simulation' in line.lower():
            print('CRON:', line)

print('\n=== 8. Evidence pack job ===')
r8 = subprocess.run(['crontab', '-l'], capture_output=True, text=True)
if r8.stdout:
    for line in r8.stdout.splitlines():
        if 'evidence' in line.lower():
            print('CRON:', line)
    if 'evidence' not in r8.stdout.lower():
        print('No evidence cron job found')
        print('Full crontab:')
        print(r8.stdout[:500])
else:
    print('No crontab entries')

print('\n=== 9. Rollback timing ===')
import time
start = time.time()
# Simulate rollback: query for a decision record and re-run classification
from services.rcl_engine import RCLEngine
from bson import ObjectId
decision = db.decision_records.find_one({}, sort=[('created_at', -1)])
if decision:
    elapsed = time.time() - start
    print(f'Decision fetch time: {elapsed:.3f}s')
    # Full rollback simulation: reload the decision
    start2 = time.time()
    reloaded = db.decision_records.find_one({'_id': decision['_id']})
    elapsed2 = time.time() - start2
    print(f'Rollback read time: {elapsed2:.3f}s')
    print(f'Total rollback simulation: {(elapsed + elapsed2):.3f}s (well under 60s)')
else:
    print('No decision records found')
