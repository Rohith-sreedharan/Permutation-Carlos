"""
Phase 11.5 — Parlay Sentinel Monitors (Section 3.2)

Four monitors that run on every parlay build cycle:

  1. check_pool_empty()           — INFO  if scheduler ran but found zero EDGE decisions
  2. check_pool_empty_failure()   — CRIT  if pool is empty AND scheduler missed its window
  3. check_leg_field_integrity()  — WARN  exclude a DecisionRecord from the pool when
                                          required fields are null
  4. check_feed_staleness()       — CRIT  block all parlay builds when the freshest
                                          snapshot_hash is older than the staleness threshold

All thresholds sourced from AGENT_CONFIG["phase11_5"].
Zero hardcoded values in this file.
All events logged to sentinel_event_log with agent_id = "agent.sentinel.v1".
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from db.mongo import db
from config.agent_config import AGENT_CONFIG

logger = logging.getLogger(__name__)

AGENT_ID = "agent.sentinel.v1"

_cfg = AGENT_CONFIG["phase11_5"]
_sentinel_log = db["sentinel_event_log"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_ts() -> float:
    return datetime.now(timezone.utc).timestamp()


def _fire(
    event_type: str,
    severity: str,
    subject: str,
    detail: Dict[str, Any],
    trace_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Append-only sentinel event writer."""
    event = {
        "event_id": str(uuid4()),
        "event_type": event_type,
        "severity": severity,
        "agent_id": AGENT_ID,
        "subject": subject,
        "detail": detail,
        "trace_id": trace_id or str(uuid4()),
        "timestamp": _now_iso(),
    }
    _sentinel_log.insert_one({k: v for k, v in event.items() if k != "_id"})
    log_fn = logger.critical if severity == "CRITICAL" else (
        logger.warning if severity == "WARNING" else logger.info
    )
    log_fn(
        "[parlay-sentinel] %s | severity=%s | subject=%s",
        event_type, severity, subject,
    )
    return event


# ─────────────────────────────────────────────────────────────────────────────
# 1. PARLAY_POOL_EMPTY_LEGITIMATE
#    Fires INFO when the scheduler ran successfully but the edge decision pool is empty.
# ─────────────────────────────────────────────────────────────────────────────

def check_pool_empty(
    edge_decision_count: int,
    last_scheduler_run_at: datetime,
    trace_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Called after a scheduler run. Fires INFO if the pool legitimately has zero
    EDGE decisions (scheduler ran, but no qualifying picks exist right now).

    Args:
        edge_decision_count:   Count of OFFICIAL+EDGE+PASS records in the pool.
        last_scheduler_run_at: UTC timestamp of the most recent scheduler run.
        trace_id:              Optional correlation ID.

    Returns:
        {"fired": bool, "event": <sentinel event>|None}
    """
    window = _cfg["scheduler_run_window_seconds"]
    age_seconds = _now_ts() - last_scheduler_run_at.timestamp()

    if edge_decision_count == 0 and age_seconds <= window:
        event = _fire(
            event_type="PARLAY_POOL_EMPTY_LEGITIMATE",
            severity="INFO",
            subject="parlay_pool",
            detail={
                "edge_decision_count": 0,
                "scheduler_age_seconds": round(age_seconds, 1),
                "scheduler_run_window_seconds": window,
            },
            trace_id=trace_id,
        )
        return {"fired": True, "event": event}

    return {"fired": False, "event": None}


# ─────────────────────────────────────────────────────────────────────────────
# 2. PARLAY_POOL_EMPTY_SCHEDULER_FAILURE
#    Fires CRITICAL when the pool is empty AND the scheduler missed its window.
# ─────────────────────────────────────────────────────────────────────────────

def check_pool_empty_failure(
    edge_decision_count: int,
    last_scheduler_run_at: Optional[datetime],
    trace_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Fires CRITICAL when:
      - The parlay pool has zero EDGE decisions, AND
      - The scheduler has not run within the allowed window (or has never run).

    Args:
        edge_decision_count:   Count of OFFICIAL+EDGE+PASS records in the pool.
        last_scheduler_run_at: UTC timestamp of the most recent scheduler run,
                               or None if the scheduler has never run.
        trace_id:              Optional correlation ID.

    Returns:
        {"fired": bool, "event": <sentinel event>|None}
    """
    if edge_decision_count > 0:
        return {"fired": False, "event": None}

    window = _cfg["scheduler_run_window_seconds"]
    scheduler_age: Optional[float] = None

    if last_scheduler_run_at is not None:
        scheduler_age = _now_ts() - last_scheduler_run_at.timestamp()
        if scheduler_age <= window:
            # Scheduler ran recently — this is a legitimate empty pool (covered by monitor 1)
            return {"fired": False, "event": None}

    event = _fire(
        event_type="PARLAY_POOL_EMPTY_SCHEDULER_FAILURE",
        severity="CRITICAL",
        subject="parlay_pool",
        detail={
            "edge_decision_count": 0,
            "scheduler_age_seconds": round(scheduler_age, 1) if scheduler_age is not None else None,
            "scheduler_run_window_seconds": window,
            "scheduler_ever_ran": last_scheduler_run_at is not None,
        },
        trace_id=trace_id,
    )
    return {"fired": True, "event": event}


# ─────────────────────────────────────────────────────────────────────────────
# 3. PARLAY_LEG_FIELD_INTEGRITY_FAIL
#    Fires WARNING and excludes a DecisionRecord when required fields are null.
# ─────────────────────────────────────────────────────────────────────────────

def check_leg_field_integrity(
    decision_record: Dict[str, Any],
    trace_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Inspects a single DecisionRecord that has status OFFICIAL+EDGE+PASS.
    If any required leg field is null/missing, fires WARNING and marks the
    record as excluded from the parlay pool.

    Required fields are sourced from AGENT_CONFIG["phase11_5"]["required_leg_fields"].

    Args:
        decision_record:  A dict representing the DecisionRecord to inspect.
        trace_id:         Optional correlation ID.

    Returns:
        {
            "eligible": bool,      # True if all required fields present
            "missing_fields": list,
            "event": <sentinel event>|None,
        }
    """
    required_fields: List[str] = _cfg["required_leg_fields"]
    missing = [f for f in required_fields if not decision_record.get(f)]

    if not missing:
        return {"eligible": True, "missing_fields": [], "event": None}

    event = _fire(
        event_type="PARLAY_LEG_FIELD_INTEGRITY_FAIL",
        severity="WARNING",
        subject=decision_record.get("decision_id", "unknown"),
        detail={
            "decision_id": decision_record.get("decision_id"),
            "missing_fields": missing,
            "required_fields": required_fields,
            "action": "excluded_from_parlay_pool",
        },
        trace_id=trace_id,
    )
    return {"eligible": False, "missing_fields": missing, "event": event}


# ─────────────────────────────────────────────────────────────────────────────
# 4. PARLAY_FEED_STALE
#    Fires CRITICAL and blocks all parlay builds when data feed is stale.
# ─────────────────────────────────────────────────────────────────────────────

def check_feed_staleness(
    freshest_snapshot_at: Optional[datetime],
    trace_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Checks the age of the most recent snapshot_hash in the decision pool.
    If the freshest snapshot is older than the staleness threshold (or no
    snapshots exist), fires CRITICAL and signals that parlay builds must be blocked.

    Args:
        freshest_snapshot_at:  UTC datetime of the most recent snapshot, or
                               None if no snapshots are present.
        trace_id:              Optional correlation ID.

    Returns:
        {
            "blocked": bool,      # True if parlay builds should be blocked
            "snapshot_age_seconds": float|None,
            "event": <sentinel event>|None,
        }
    """
    threshold = _cfg["feed_staleness_threshold_seconds"]
    snapshot_age: Optional[float] = None

    if freshest_snapshot_at is not None:
        snapshot_age = _now_ts() - freshest_snapshot_at.timestamp()
        if snapshot_age <= threshold:
            return {"blocked": False, "snapshot_age_seconds": round(snapshot_age, 1), "event": None}

    event = _fire(
        event_type="PARLAY_FEED_STALE",
        severity="CRITICAL",
        subject="parlay_feed",
        detail={
            "snapshot_age_seconds": round(snapshot_age, 1) if snapshot_age is not None else None,
            "feed_staleness_threshold_seconds": threshold,
            "has_any_snapshot": freshest_snapshot_at is not None,
            "action": "parlay_builds_blocked",
        },
        trace_id=trace_id,
    )
    return {"blocked": True, "snapshot_age_seconds": snapshot_age, "event": event}
