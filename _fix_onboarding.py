import sys, os
os.chdir('/root/Permutation-Carlos/backend')
sys.path.insert(0, '.')
from db.mongo import db
from bson import ObjectId
result = db.users.update_one({'_id': ObjectId('69faa2266ee8fd32ae152b31')}, {'$set': {'onboarding_complete': True}})
print('MODIFIED:', result.modified_count)
u = db.users.find_one({'_id': ObjectId('69faa2266ee8fd32ae152b31')}, {'onboarding_complete':1, 'email':1, 'tier':1})
print('STATUS:', u.get('onboarding_complete'), 'email:', u.get('email'), 'tier:', u.get('tier'))
