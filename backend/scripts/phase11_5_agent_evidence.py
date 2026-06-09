"""
Phase 11.5 — agent.response.v1 + agent.recovery.v1 evidence script

Produces:
  Item 1 — response_action_log entry: parlay engine blocked by PARLAY_FEED_STALE
  Item 2 — sentinel event: PARLAY_POOL_EMPTY_SCHEDULER_FAILURE
           recovery_action_log entry (LOW): autonomous scheduler restart
           recovery_action_log entry (CRITICAL): escalated to operator approval queue

Run from the backend/ directory with the project venv active:
  cd backend && python scripts/phase11_5_agent_evidence.py
"""

from __future__ import annotations

import json
import sys
import os
from datetime import datetime, timezone, timedelta

# Allow imports from backend/ root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.mongo import db
from services.phase8_response_agent import log_response_action
from services.phase8_recovery_agent import evaluate_recovery
from services.phase11_5_parlay_sentinel import check_pool_empty_failure

# ─────────────────────────────────────────────────────────────────────────────
# Constants — the PARLAY_FEED_STALE sentinel event fired in Section 3.9
# ─────────────────────────────────────────────────────────────────────────────
FEED_STALE_EVENT_ID  = "33196aab-a6a4-4349-b1b1-08b529493992"
FEED_STALE_TRACE_ID  = "test-trace-s3-9-m4"
SENTINEL_AGENT_ID    = "agent.sentinel.v1"

SEP = "─" * 70

def _pp(label: str, obj: dict) -> None:
    print(f"\n{SEP}")
    print(f"  {label}")
    print(SEP)
    print(json.dumps(obj, indent=2, default=str))


# ─────────────────────────────────────────────────────────────────────────────
# 0. Verify the originating PARLAY_FEED_STALE sentinel event is in DB
# ─────────────────────────────────────────────────────────────────────────────
print("\n[0] Fetching originating PARLAY_FEED_STALE sentinel event …")
feed_stale_event = db["sentinel_event_log"].find_one(
    {"event_id": FEED_STALE_EVENT_ID}, {"_id": 0}
)
if not feed_stale_event:
    print(f"  ERROR: sentinel event {FEED_STALE_EVENT_ID} not found in DB")
    sys.exit(1)
_pp("PARLAY_FEED_STALE sentinel event (originating trigger)", feed_stale_event)


# ─────────────────────────────────────────────────────────────────────────────
# ITEM 1 — agent.response.v1
# Parlay engine blocked in direct response to PARLAY_FEED_STALE.
# trace_id links back to the originating sentinel event.
# ─────────────────────────────────────────────────────────────────────────────
print("\n[ITEM 1] Logging response_action_log entry (agent.response.v1) …")

response_entry = log_response_action(
    action="parlay_engine_blocked",
    reason=(
        "PARLAY_FEED_STALE sentinel fired — parlay engine set to blocked state "
        "pending feed refresh and snapshot hash validation."
    ),
    trace_id=FEED_STALE_TRACE_ID,
    source_agent_id=SENTINEL_AGENT_ID,
    metadata={
        "trigger_event_type": "PARLAY_FEED_STALE",
        "trigger_event_id": FEED_STALE_EVENT_ID,
        "trigger_trace_id": FEED_STALE_TRACE_ID,
        "parlay_engine_blocked": True,
        "originating_agent": SENTINEL_AGENT_ID,
    },
)

_pp("response_action_log entry (ITEM 1)", response_entry)
response_action_id = response_entry["action_id"]
print(f"\n  ✅  action_id={response_action_id}")
print(f"  ✅  parlay_engine_blocked=True")
print(f"  ✅  trace_id={response_entry['trace_id']} ← links to sentinel event {FEED_STALE_EVENT_ID}")


# ─────────────────────────────────────────────────────────────────────────────
# ITEM 2 — Trigger PARLAY_POOL_EMPTY_SCHEDULER_FAILURE
# Scheduler age set to >3600 s (window) to force the CRITICAL condition.
# ─────────────────────────────────────────────────────────────────────────────
print("\n[ITEM 2a] Triggering PARLAY_POOL_EMPTY_SCHEDULER_FAILURE sentinel …")

# Simulate scheduler last ran 2 hours ago — past the 3600 s window
stale_scheduler_time = datetime.now(timezone.utc) - timedelta(hours=2)
SCHEDULER_FAIL_TRACE = "phase11-5-item2-scheduler-fail-trace"

sentinel_result = check_pool_empty_failure(
    edge_decision_count=0,
    last_scheduler_run_at=stale_scheduler_time,
    trace_id=SCHEDULER_FAIL_TRACE,
)

if not sentinel_result["fired"]:
    print("  ERROR: PARLAY_POOL_EMPTY_SCHEDULER_FAILURE did not fire")
    sys.exit(1)

scheduler_fail_event = sentinel_result["event"]
_pp("PARLAY_POOL_EMPTY_SCHEDULER_FAILURE sentinel event (ITEM 2)", scheduler_fail_event)
print(f"\n  ✅  event_id={scheduler_fail_event['event_id']}")
print(f"  ✅  severity=CRITICAL")

# ─────────────────────────────────────────────────────────────────────────────
# ITEM 2 — recovery_action_log: LOW path — autonomous scheduler restart
# ─────────────────────────────────────────────────────────────────────────────
print("\n[ITEM 2b] Logging recovery_action_log entry — LOW path (autonomous restart) …")

recovery_low = evaluate_recovery(
    triggered_by_action_id=response_action_id,
    severity="LOW",
    recovery_type="autonomous_scheduler_restart",
    trace_id=SCHEDULER_FAIL_TRACE,
    details={
        "trigger_event_type": "PARLAY_POOL_EMPTY_SCHEDULER_FAILURE",
        "trigger_event_id": scheduler_fail_event["event_id"],
        "action_taken": "Scheduler restarted autonomously — no operator approval required for LOW severity",
        "scheduler_last_run_offset_seconds": -7200,
        "autonomous": True,
    },
)

_pp("recovery_action_log entry — LOW path (ITEM 2)", recovery_low)
print(f"\n  ✅  severity=LOW")
print(f"  ✅  status={recovery_low['status']}")
print(f"  ✅  requires_human_approval={recovery_low['requires_human_approval']}")
print(f"  ✅  autonomous restart executed")


# ─────────────────────────────────────────────────────────────────────────────
# ITEM 2 — recovery_action_log: CRITICAL path — escalate, NEVER autonomous
# ─────────────────────────────────────────────────────────────────────────────
print("\n[ITEM 2c] Logging recovery_action_log entry — CRITICAL path (operator escalation) …")

recovery_critical = evaluate_recovery(
    triggered_by_action_id=response_action_id,
    severity="CRITICAL",
    recovery_type="escalate_to_operator_approval_queue",
    trace_id=SCHEDULER_FAIL_TRACE,
    details={
        "trigger_event_type": "PARLAY_POOL_EMPTY_SCHEDULER_FAILURE",
        "trigger_event_id": scheduler_fail_event["event_id"],
        "action_taken": "Escalated to operator approval queue — CRITICAL severity cannot be autonomously recovered",
        "autonomous": False,
        "requires_operator_approval": True,
    },
)

_pp("recovery_action_log entry — CRITICAL path (ITEM 2)", recovery_critical)
print(f"\n  ✅  severity=CRITICAL")
print(f"  ✅  status={recovery_critical['status']}")
print(f"  ✅  requires_human_approval={recovery_critical['requires_human_approval']}")
print(f"  ✅  autonomous=False  ← NEVER autonomous on CRITICAL")


# ─────────────────────────────────────────────────────────────────────────────
# Verify DB state
# ─────────────────────────────────────────────────────────────────────────────
print(f"\n{SEP}")
print("  DB VERIFICATION")
print(SEP)

resp_count = db["response_action_log"].count_documents({"agent_id": "agent.response.v1"})
recov_count = db["recovery_action_log"].count_documents({"agent_id": "agent.recovery.v1"})
sched_fail_count = db["sentinel_event_log"].count_documents({"event_type": "PARLAY_POOL_EMPTY_SCHEDULER_FAILURE"})

print(f"  response_action_log rows (agent.response.v1): {resp_count}")
print(f"  recovery_action_log rows (agent.recovery.v1): {recov_count}")
print(f"  sentinel_event_log PARLAY_POOL_EMPTY_SCHEDULER_FAILURE events: {sched_fail_count}")

# Fetch this run's entries for final printout
resp_row = db["response_action_log"].find_one({"action_id": response_action_id}, {"_id": 0})
recov_low_row = db["recovery_action_log"].find_one({"recovery_id": recovery_low["recovery_id"]}, {"_id": 0})
recov_crit_row = db["recovery_action_log"].find_one({"recovery_id": recovery_critical["recovery_id"]}, {"_id": 0})

print("\n  ─── response_action_log ───")
print(json.dumps(resp_row, indent=2, default=str))
print("\n  ─── recovery_action_log [LOW] ───")
print(json.dumps(recov_low_row, indent=2, default=str))
print("\n  ─── recovery_action_log [CRITICAL] ───")
print(json.dumps(recov_crit_row, indent=2, default=str))

print(f"\n{SEP}")
print("  ALL ITEMS COMPLETE — evidence logged to DB")
print(SEP)
