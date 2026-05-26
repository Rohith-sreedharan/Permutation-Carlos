"""
Phase 7B — AOS Trust Monitoring Sentinel

Three monitors:
  1. check_write_attempt()    — blocks and logs manual writes to truth_dataset_v1
  2. check_sample_gate()      — fires if a metric is served below threshold
  3. check_page_availability() — monitors /performance page availability

All thresholds sourced from AGENT_CONFIG["phase7"].  Zero hardcoded values
in this file (thresholds come from config; the LOCKED N_ constants are in
phase7_trust_record.py which is the single source of truth for sample thresholds).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from db.mongo import db
from config.agent_config import AGENT_CONFIG

logger = logging.getLogger(__name__)

AGENT_ID = "agent.sentinel.v1"

_cfg = AGENT_CONFIG["phase7"]
_sentinel_log = db["sentinel_event_log"]
_suppression_log = db["sentinel_event_log"]   # same collection, different event_types


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fire(
    event_type: str,
    severity: str,
    subject: str,
    detail: Dict[str, Any],
    trace_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Append-only sentinel event log writer."""
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
    logger.warning("[phase7-sentinel] %s | severity=%s | subject=%s", event_type, severity, subject)
    return event


# ─────────────────────────────────────────────────────────────────────────────
# 1. Write-attempt sentinel (AC-1 / 7B.1)
# ─────────────────────────────────────────────────────────────────────────────

def check_write_attempt(
    collection_name: str,
    actor: str,
    action: str,
    trace_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Called whenever a direct write to a truth source table is attempted.
    Any write to truth_dataset_v1 is unconditionally blocked and logged as CRITICAL.

    Returns:
        {"blocked": True/False, "event": <sentinel event dict>|None, "reason": str}
    """
    PROTECTED_COLLECTIONS = {"truth_dataset_v1", "grading_records", "calibration_records"}

    if collection_name in PROTECTED_COLLECTIONS:
        event = _fire(
            event_type="MANUAL_WRITE_BLOCKED",
            severity="CRITICAL",
            subject=collection_name,
            detail={
                "actor": actor,
                "action": action,
                "collection": collection_name,
                "rule": "Manual writes to truth-source collections are prohibited under Phase 7 AOS policy.",
            },
            trace_id=trace_id,
        )
        return {
            "blocked": True,
            "reason": f"Direct write to '{collection_name}' is prohibited. Audit trail preserved.",
            "event_id": event["event_id"],
            "event_type": "MANUAL_WRITE_BLOCKED",
            "severity": "CRITICAL",
        }

    return {
        "blocked": False,
        "reason": f"Collection '{collection_name}' is not protected; write allowed.",
        "event": None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 2. Sample gate sentinel (AC-2 / 7A.2)
# ─────────────────────────────────────────────────────────────────────────────

def check_sample_gate(
    segment_key: str,
    n_actual: int,
    n_required: int,
    trace_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Fires and logs a suppression event if n_actual < n_required.
    Called by the trust record service when any metric falls below threshold.

    Returns:
        {"suppressed": True/False, "event_id": str|None}
    """
    if n_actual < n_required:
        event = _fire(
            event_type="SAMPLE_GATE_SUPPRESSION",
            severity="INFO",
            subject=segment_key,
            detail={
                "segment_key": segment_key,
                "n_actual": n_actual,
                "n_required": n_required,
                "suppression_copy": "Track record building — check back soon.",
            },
            trace_id=trace_id,
        )
        return {
            "suppressed": True,
            "event_id": event["event_id"],
            "segment_key": segment_key,
            "n_actual": n_actual,
            "n_required": n_required,
        }

    return {
        "suppressed": False,
        "segment_key": segment_key,
        "n_actual": n_actual,
        "n_required": n_required,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 3. Page availability sentinel (7B.3)
# ─────────────────────────────────────────────────────────────────────────────

def check_page_availability(
    status_code: int,
    response_time_ms: float,
    page_path: str = "/performance",
    trace_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Called after probing the /performance page.
    Fires WARNING if response_time exceeds threshold.
    Fires CRITICAL if page is unavailable (non-200 status).

    All thresholds sourced from AGENT_CONFIG (zero hardcoded here).
    """
    warn_ms = _cfg["availability_response_time_warning_ms"]
    events = []

    if status_code != 200:
        events.append(_fire(
            event_type="PAGE_UNAVAILABLE",
            severity="CRITICAL",
            subject=page_path,
            detail={
                "status_code": status_code,
                "page_path": page_path,
                "rule": "Performance page must return HTTP 200 at all times.",
            },
            trace_id=trace_id,
        ))

    if response_time_ms > warn_ms:
        events.append(_fire(
            event_type="PAGE_SLOW_RESPONSE",
            severity="WARNING",
            subject=page_path,
            detail={
                "response_time_ms": response_time_ms,
                "threshold_ms": warn_ms,
                "page_path": page_path,
            },
            trace_id=trace_id,
        ))

    ok = status_code == 200 and response_time_ms <= warn_ms
    return {
        "ok": ok,
        "status_code": status_code,
        "response_time_ms": response_time_ms,
        "events_fired": [e["event_id"] for e in events],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Evidence / read helpers
# ─────────────────────────────────────────────────────────────────────────────

def get_suppression_log(limit: int = 50) -> list:
    """Return the most recent suppression and blocked-write events."""
    cursor = _sentinel_log.find(
        {"event_type": {"$in": ["SAMPLE_GATE_SUPPRESSION", "MANUAL_WRITE_BLOCKED"]}},
        {"_id": 0},
    ).sort("timestamp", -1).limit(limit)
    return list(cursor)
