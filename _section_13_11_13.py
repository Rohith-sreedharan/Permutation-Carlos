import sys, os
os.chdir('/root/Permutation-Carlos/backend')
sys.path.insert(0, '.')
from db.mongo import db

print("=== SECTION 13.11: Compliance Integration ===")
se = db.self_exclusion_log.count_documents({})
print(f"self_exclusion_log count: {se}")

colls = db.list_collection_names()
ddl = db.data_deletion_log.count_documents({}) if "data_deletion_log" in colls else "collection_not_found"
print(f"data_deletion_log count: {ddl}")

from services.phase5_growth_agent import _TEMPLATES
prohibited = ["bet", "gamble", "wager", "win money", "beat the", "guaranteed"]
violations = []
for tid, tmpl in _TEMPLATES.items():
    body = tmpl.get("body", "").lower()
    for phrase in prohibited:
        if phrase in body:
            violations.append(f"{tid}: contains prohibited phrase: '{phrase}'")
print(f"Growth Agent templates scanned: {len(_TEMPLATES)}")
print(f"Prohibited language violations: {len(violations)}")
for v in violations:
    print(f"  VIOLATION: {v}")
if not violations:
    print("  CLEAN — zero violations")

print()
print("=== SECTION 13.12: Billing Edge Cases ===")
types = db.billing_state_change_log.distinct("event_type")
print(f"Distinct event_types in billing_state_change_log: {types}")
total_billing = db.billing_state_change_log.count_documents({})
print(f"Total billing_state_change_log documents: {total_billing}")
sentinel_types = db.sentinel_event_log.distinct("event_type")
print(f"Distinct event_types in sentinel_event_log: {sentinel_types}")
total_sentinel = db.sentinel_event_log.count_documents({})
print(f"Total sentinel_event_log documents: {total_sentinel}")

print()
print("=== SECTION 13.13: Agent Coordination ===")
ral = db.response_action_log.count_documents({}) if "response_action_log" in colls else 0
print(f"response_action_log count: {ral}")
rec = db.recovery_action_log.count_documents({}) if "recovery_action_log" in colls else 0
print(f"recovery_action_log count: {rec}")
ocl = db.outbound_communication_log.count_documents({})
print(f"outbound_communication_log count: {ocl}")
recent_ocl = list(db.outbound_communication_log.find({}, sort=[("sent_at", -1)]).limit(3))
for r in recent_ocl:
    uid = str(r.get("user_id", ""))[:8]
    print(f"  template={r.get('template_id')} user={uid}... at={r.get('sent_at')}")
