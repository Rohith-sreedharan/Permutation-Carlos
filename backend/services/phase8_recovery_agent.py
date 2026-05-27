"""
Phase 8B.1 — Recovery Agent (agent.recovery.v1)

Evaluates system state after response action intervention.
- LOW: autonomous safe recovery (no human approval)
- WARNING: proposal only, operator decision required
- CRITICAL: escalate only, no autonomous execution ever

All actions append-only to recovery_action_log.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from db.mongo import db
from config.agent_config import AGENT_CONFIG

logger = logging.getLogger(__name__)

AGENT_ID = "agent.recovery.v1"

_recovery_log = db["recovery_action_log"]
_sentinel_log = db["sentinel_event_log"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def evaluate_recovery(
    *,
    triggered_by_action_id: str,
    severity: str,
    recovery_type: str,
    trace_id: Optional[str] = None,
    approved_by: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Evaluate and record recovery action decision."""
    sev = (severity or "").upper().strip()
    if sev not in {"LOW", "WARNING", "CRITICAL"}:
        raise ValueError("severity must be one of LOW|WARNING|CRITICAL")

    recovery_id = str(uuid4())
    trace = trace_id or str(uuid4())
    now = _now_iso()

    requires_human_approval = sev in {"WARNING", "CRITICAL"}

    if sev == "LOW":
        status = "EXECUTED_AUTONOMOUS"
        executed_at = now
        approved_at = None
        approval_actor = None
    elif sev == "WARNING":
        status = "PENDING_OPERATOR_APPROVAL"
        executed_at = None
        approved_at = None
        approval_actor = None
    else:
        status = "ESCALATED_CRITICAL_NO_AUTONOMOUS_ACTION"
        executed_at = None
        approved_at = None
        approval_actor = None

        _sentinel_log.insert_one({
            "event_id": str(uuid4()),
            "event_type": "RECOVERY_ESCALATION_REQUIRED",
            "severity": "CRITICAL",
            "agent_id": AGENT_ID,
            "trace_id": trace,
            "timestamp": now,
            "detail": {
                "triggered_by_action_id": triggered_by_action_id,
                "recovery_type": recovery_type,
                "reason": "CRITICAL severity cannot be autonomously recovered",
            },
        })

    row = {
        "recovery_id": recovery_id,
        "agent_id": AGENT_ID,
        "triggered_by_action_id": triggered_by_action_id,
        "recovery_type": recovery_type,
        "severity": sev,
        "status": status,
        "requires_human_approval": requires_human_approval,
        "approved_by": approval_actor,
        "approved_at_utc": approved_at,
        "executed_at_utc": executed_at,
        "trace_id": trace,
        "details": details or {},
        "created_at_utc": now,
    }

    _recovery_log.insert_one(row)
    logger.info("[%s] recovery evaluation logged recovery_id=%s severity=%s status=%s", AGENT_ID, recovery_id, sev, status)
    return row


def operator_approve_recovery(
    *,
    recovery_id: str,
    operator_id: str,
) -> Dict[str, Any]:
    """
    Append-only operator approval event for a pending recovery.
    Does not mutate previous rows.
    """
    base = _recovery_log.find_one({"recovery_id": recovery_id}, {"_id": 0})
    if not base:
        raise ValueError(f"recovery_id not found: {recovery_id}")

    if not base.get("requires_human_approval"):
        raise ValueError("recovery does not require human approval")

    now = _now_iso()
    approval_event = {
        "recovery_id": recovery_id,
        "agent_id": AGENT_ID,
        "event_type": "RECOVERY_OPERATOR_APPROVAL",
        "triggered_by_action_id": base.get("triggered_by_action_id"),
        "recovery_type": base.get("recovery_type"),
        "severity": base.get("severity"),
        "status": "APPROVED_BY_OPERATOR",
        "requires_human_approval": True,
        "approved_by": operator_id,
        "approved_at_utc": now,
        "executed_at_utc": now,
        "trace_id": base.get("trace_id"),
        "details": {"approved_from_recovery_id": recovery_id},
        "created_at_utc": now,
    }
    _recovery_log.insert_one(approval_event)
    return approval_event


def latest_recovery(limit: int = 20) -> list:
    cur = _recovery_log.find({}, {"_id": 0}).sort("created_at_utc", -1).limit(limit)
    return list(cur)
