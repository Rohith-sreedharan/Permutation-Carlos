import sys, os
os.chdir('/root/Permutation-Carlos/backend')
sys.path.insert(0, '.')
from db.mongo import db

# Find and fix the non-canonical agent_id entries
old_id = 'agent.immutability_guard.v1'
correct_id = 'system.immutability_guard'

# Count before
before = db.sentinel_event_log.count_documents({'agent_id': old_id})
print(f'Before: {before} docs with agent_id={old_id}')

# Show them
for doc in db.sentinel_event_log.find({'agent_id': old_id}, {'agent_id':1,'event_type':1,'timestamp':1,'_id':0}):
    print('  DOC:', doc)

# Fix them
result = db.sentinel_event_log.update_many(
    {'agent_id': old_id},
    {'$set': {'agent_id': correct_id}}
)
print(f'Updated: {result.modified_count} documents')

# Verify
after = db.sentinel_event_log.count_documents({'agent_id': old_id})
correct_count = db.sentinel_event_log.count_documents({'agent_id': correct_id, 'event_type': 'CALIBRATION_IMMUTABILITY_VIOLATION'})
print(f'After: remaining old_id={after}, correct_id count={correct_count}')

# Show fixed docs
for doc in db.sentinel_event_log.find({'agent_id': correct_id, 'event_type': 'CALIBRATION_IMMUTABILITY_VIOLATION'}, {'agent_id':1,'event_type':1,'timestamp':1,'source':1,'_id':0}):
    print('  FIXED:', doc)
