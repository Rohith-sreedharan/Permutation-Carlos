"""
Phase 8 — Approval Queue (append-only)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from db.mongo import db

_approval_col = db["approval_queue"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_approval_request(
    *,
    queue_type: str,
    requested_by_agent: str,
    trace_id: str,
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    approval_id = str(uuid4())
    row = {
        "event_id": str(uuid4()),
        "event_type": "APPROVAL_REQUESTED",
        "approval_id": approval_id,
        "queue_type": queue_type,
        "requested_by_agent": requested_by_agent,
        "decision": "PENDING",
        "operator_id": None,
        "trace_id": trace_id,
        "payload": payload or {},
        "logged_at_utc": _now_iso(),
    }
    _approval_col.insert_one({**row})
    return {k: v for k, v in row.items() if k != "_id"}


def decide_approval(
    *,
    approval_id: str,
    decision: str,
    operator_id: str,
    trace_id: Optional[str] = None,
    note: Optional[str] = None,
) -> Dict[str, Any]:
    normalized = decision.strip().lower()
    if normalized not in {"approved", "rejected"}:
        raise ValueError("decision must be approved or rejected")

    base = _approval_col.find_one({"approval_id": approval_id}, {"_id": 0}, sort=[("logged_at_utc", 1)])
    if not base:
        raise ValueError(f"approval_id not found: {approval_id}")

    row = {
        "event_id": str(uuid4()),
        "event_type": "APPROVAL_DECIDED",
        "approval_id": approval_id,
        "queue_type": base.get("queue_type"),
        "requested_by_agent": base.get("requested_by_agent"),
        "decision": normalized,
        "operator_id": operator_id,
        "trace_id": trace_id or base.get("trace_id"),
        "payload": {"note": note} if note else {},
        "logged_at_utc": _now_iso(),
    }
    _approval_col.insert_one({**row})
    return {k: v for k, v in row.items() if k != "_id"}


def get_pending_approvals(limit: int = 100) -> List[Dict[str, Any]]:
    rows = list(_approval_col.find({}, {"_id": 0}).sort("logged_at_utc", -1).limit(1000))
    latest_by_id: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        aid = row.get("approval_id")
        if aid and aid not in latest_by_id:
            latest_by_id[aid] = row

    pending = [r for r in latest_by_id.values() if r.get("decision") == "PENDING"]
    pending.sort(key=lambda x: x.get("logged_at_utc", ""), reverse=True)
    return pending[:limit]


def get_recent_approval_events(limit: int = 50) -> List[Dict[str, Any]]:
    return list(_approval_col.find({}, {"_id": 0}).sort("logged_at_utc", -1).limit(limit))
