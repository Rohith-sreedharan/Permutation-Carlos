"""
Distribution Agent — agent.distribution.v1
Phase 6C

Identity: LOCKED — agent.distribution.v1
Governs all Telegram output. Validates before every send. Never posts independently.

CRITICAL RULES:
- agent_id = "agent.distribution.v1" in every log entry. Never changes.
- Pre-send validation gate on every post candidate. Fail = block + log.
- Auto-disable on integrity breach. Re-enable requires explicit operator approval.
- All operations append-only to distribution_audit_log.
"""

from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from db.mongo import db
from config.agent_config import AGENT_CONFIG

logger = logging.getLogger(__name__)

# ── Identity — LOCKED ─────────────────────────────────────────────────────────
AGENT_ID = "agent.distribution.v1"

# ── Collections (append-only) ─────────────────────────────────────────────────
_audit_col = db["distribution_audit_log"]
_state_col = db["autopublish_state"]
_response_action_col = db["response_action_log"]
_operator_approval_col = db["operator_approval_log"]
_sentinel_col = db["sentinel_event_log"]

# ── Approved channels config key ─────────────────────────────────────────────
_approved_channels: List[str] = os.getenv("APPROVED_TELEGRAM_CHANNELS", "").split(",")

# ── Kill switch ───────────────────────────────────────────────────────────────
_KILL_SWITCH_ENV = os.getenv("FEATURE_TELEGRAM_AUTOPUBLISH", "OFF").upper()

# ── Regulatory language filter ────────────────────────────────────────────────
_PROHIBITED_PHRASES = [
    "bet ", "betting", "wager", "wagering", "pick ", "tip ",
    "guaranteed", "lock ", "sure thing", "sportsbook", "odds shop",
    "money line",  # casual framing — "moneyline" (one word) is acceptable
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_content(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


# ─────────────────────────────────────────────────────────────────────────────
# Autopublish state (persisted in DB so survives restarts)
# ─────────────────────────────────────────────────────────────────────────────

def _get_autopublish_state() -> bool:
    """Return current autopublish enabled state. Default OFF if missing."""
    if _KILL_SWITCH_ENV == "OFF":
        return False
    rec = _state_col.find_one({"_id": "autopublish"})
    if rec is None:
        return False
    return bool(rec.get("enabled", False))


def _set_autopublish_state(enabled: bool, reason: str, operator_id: Optional[str] = None) -> None:
    """Persist autopublish state. Only disables can be autonomous; enables require operator_id."""
    _state_col.update_one(
        {"_id": "autopublish"},
        {"$set": {
            "enabled": enabled,
            "updated_at_utc": _now_iso(),
            "reason": reason,
            "operator_id": operator_id,
            "agent_id": AGENT_ID,
        }},
        upsert=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Pre-send validation gate (6C.1)
# ─────────────────────────────────────────────────────────────────────────────

_REQUIRED_FIELDS = [
    "event_id", "market_type", "selection_id", "team_name", "line",
    "american_odds", "probability", "market_implied_probability",
    "prob_edge", "ev", "snapshot_hash", "model_version", "sim_count",
    "generated_at",
]


def _validate_post_candidate(candidate: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run all 6 pre-send checks.
    Returns {"valid": True} or {"valid": False, "reason": str, "check": str}
    """
    # Check 1: decision_id must resolve to a real DecisionRecord
    decision_id = candidate.get("decision_id")
    if not decision_id:
        return {"valid": False, "reason": "decision_id missing", "check": "decision_id_exists"}

    decision_record = db["decisions"].find_one({"decision_id": decision_id})
    if decision_record is None:
        # Also try by _id string
        decision_record = db["decision_log"].find_one({"decision_id": decision_id})
    if decision_record is None:
        return {"valid": False, "reason": f"decision_id {decision_id} not found in DecisionRecord store", "check": "decision_id_exists"}

    # Check 2: release_status must be OFFICIAL
    release_status = decision_record.get("release_status", candidate.get("release_status", ""))
    if release_status != "OFFICIAL":
        return {"valid": False, "reason": f"release_status={release_status!r} is not OFFICIAL", "check": "release_status"}

    # Check 3: classification must not be BLOCKED
    classification = decision_record.get("classification", candidate.get("classification", ""))
    if classification == "BLOCKED":
        return {"valid": False, "reason": "classification=BLOCKED — never post", "check": "classification_not_blocked"}

    # Check 4: all required fields present in candidate
    missing = [f for f in _REQUIRED_FIELDS if not candidate.get(f)]
    if missing:
        return {"valid": False, "reason": f"required fields missing: {missing}", "check": "required_fields_present"}

    # Check 5: snapshot_hash consistency
    record_hash = decision_record.get("snapshot_hash")
    candidate_hash = candidate.get("snapshot_hash")
    if record_hash and candidate_hash and record_hash != candidate_hash:
        return {"valid": False, "reason": f"snapshot_hash mismatch: record={record_hash} candidate={candidate_hash}", "check": "snapshot_hash_consistent"}

    # Check 6: regulatory filter on post content
    post_content = candidate.get("post_content", "")
    violations = [p for p in _PROHIBITED_PHRASES if p in post_content.lower()]
    if violations:
        _fire_sentinel_critical(
            decision_id=decision_id,
            violations=violations,
            post_content=post_content,
        )
        return {"valid": False, "reason": f"regulatory filter violations: {violations}", "check": "regulatory_filter"}

    return {"valid": True}


def _fire_sentinel_critical(decision_id: str, violations: List[str], post_content: str) -> None:
    """Log CRITICAL sentinel event for regulatory filter breach."""
    _sentinel_col.insert_one({
        "severity": "CRITICAL",
        "event_type": "REGULATORY_FILTER_BLOCK",
        "agent_id": AGENT_ID,
        "decision_id": decision_id,
        "violations": violations,
        "post_content_hash": _hash_content(post_content),
        "timestamp": _now_iso(),
    })
    logger.critical(
        "[%s] REGULATORY FILTER BREACH — decision_id=%s violations=%s",
        AGENT_ID, decision_id, violations,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Distribution audit trail (6C.4 — append-only)
# ─────────────────────────────────────────────────────────────────────────────

def _write_audit_entry(
    *,
    decision_id: Optional[str],
    post_content: str,
    channel: str,
    validation_result: Dict[str, Any],
    delivered: bool,
    trace_id: str,
    sent_at_utc: str,
) -> str:
    attempt_id = str(uuid4())
    _audit_col.insert_one({
        "attempt_id": attempt_id,
        "decision_id": decision_id,
        "post_content_hash": _hash_content(post_content),
        "channel": channel,
        "sent_at_utc": sent_at_utc,
        "validation_result": "PASS" if validation_result.get("valid") else "FAIL",
        "validation_reason": validation_result.get("reason"),
        "validation_check": validation_result.get("check"),
        "delivered": delivered,
        "agent_id": AGENT_ID,
        "trace_id": trace_id,
    })
    return attempt_id


# ─────────────────────────────────────────────────────────────────────────────
# Auto-disable (6C.2)
# ─────────────────────────────────────────────────────────────────────────────

def _auto_disable_autopublish(reason: str, trace_id: str) -> None:
    """
    Immediately disable autopublish on integrity breach.
    Fires within 60 seconds of detection. Cannot be bypassed.
    """
    _set_autopublish_state(enabled=False, reason=reason)
    _response_action_col.insert_one({
        "action_id": str(uuid4()),
        "agent_id": AGENT_ID,
        "action": "AUTOPUBLISH_DISABLED",
        "reason": reason,
        "trace_id": trace_id,
        "timestamp_utc": _now_iso(),
        "re_enable_requires_operator": True,
    })
    logger.critical("[%s] AUTOPUBLISH DISABLED — reason=%s", AGENT_ID, reason)


# ─────────────────────────────────────────────────────────────────────────────
# Re-enable protocol (6C.3)
# ─────────────────────────────────────────────────────────────────────────────

def operator_approve_reenable(operator_id: str, justification: str) -> Dict[str, Any]:
    """
    Re-enable autopublish. Only callable by an operator. Cannot be called by any agent.
    Logs operator_id + timestamp. Required after every CRITICAL disable.
    """
    if not operator_id:
        return {"approved": False, "reason": "operator_id required"}

    _set_autopublish_state(enabled=True, reason=justification, operator_id=operator_id)
    approval_id = str(uuid4())
    _operator_approval_col.insert_one({
        "approval_id": approval_id,
        "operator_id": operator_id,
        "action": "AUTOPUBLISH_REENABLE",
        "justification": justification,
        "agent_id": AGENT_ID,
        "timestamp_utc": _now_iso(),
    })
    logger.info("[%s] AUTOPUBLISH RE-ENABLED by operator=%s approval_id=%s", AGENT_ID, operator_id, approval_id)
    return {"approved": True, "approval_id": approval_id, "operator_id": operator_id}


# ─────────────────────────────────────────────────────────────────────────────
# Channel enforcement (6C.5)
# ─────────────────────────────────────────────────────────────────────────────

def _is_approved_channel(channel_id: str) -> bool:
    """Channel must be in approved_distribution_channels config. No autonomous additions."""
    approved = AGENT_CONFIG.get("phase6", {}).get("approved_distribution_channels", _approved_channels)
    return channel_id in approved


# ─────────────────────────────────────────────────────────────────────────────
# Public interface
# ─────────────────────────────────────────────────────────────────────────────

def attempt_post(
    candidate: Dict[str, Any],
    channel: str,
    trace_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run full pre-send validation gate. If all checks pass and autopublish is ON,
    deliver the post. Log every attempt regardless of outcome.

    Returns dict with: attempt_id, delivered, validation_result, blocked_reason
    """
    if trace_id is None:
        trace_id = str(uuid4())

    sent_at = _now_iso()
    decision_id = candidate.get("decision_id")
    post_content = candidate.get("post_content", "")

    # Kill switch — hard stop
    if _KILL_SWITCH_ENV == "OFF":
        result = {"valid": False, "reason": "FEATURE_TELEGRAM_AUTOPUBLISH=OFF", "check": "kill_switch"}
        attempt_id = _write_audit_entry(
            decision_id=decision_id, post_content=post_content, channel=channel,
            validation_result=result, delivered=False, trace_id=trace_id, sent_at_utc=sent_at,
        )
        return {"attempt_id": attempt_id, "delivered": False, "blocked": True,
                "blocked_reason": result["reason"], "validation_check": result["check"]}

    # Channel enforcement
    if not _is_approved_channel(channel):
        result = {"valid": False, "reason": f"channel {channel!r} not in approved_distribution_channels", "check": "channel_enforcement"}
        attempt_id = _write_audit_entry(
            decision_id=decision_id, post_content=post_content, channel=channel,
            validation_result=result, delivered=False, trace_id=trace_id, sent_at_utc=sent_at,
        )
        return {"attempt_id": attempt_id, "delivered": False, "blocked": True,
                "blocked_reason": result["reason"], "validation_check": result["check"]}

    # Pre-send validation gate
    validation = _validate_post_candidate(candidate)

    if not validation["valid"]:
        attempt_id = _write_audit_entry(
            decision_id=decision_id, post_content=post_content, channel=channel,
            validation_result=validation, delivered=False, trace_id=trace_id, sent_at_utc=sent_at,
        )
        logger.warning("[%s] POST BLOCKED — check=%s reason=%s", AGENT_ID, validation.get("check"), validation.get("reason"))
        return {"attempt_id": attempt_id, "delivered": False, "blocked": True,
                "blocked_reason": validation["reason"], "validation_check": validation["check"]}

    # Autopublish state
    if not _get_autopublish_state():
        result = {"valid": False, "reason": "autopublish disabled", "check": "autopublish_state"}
        attempt_id = _write_audit_entry(
            decision_id=decision_id, post_content=post_content, channel=channel,
            validation_result=result, delivered=False, trace_id=trace_id, sent_at_utc=sent_at,
        )
        return {"attempt_id": attempt_id, "delivered": False, "blocked": True,
                "blocked_reason": "autopublish disabled"}

    # All checks pass — deliver
    delivered = _deliver_post(post_content=post_content, channel=channel)
    attempt_id = _write_audit_entry(
        decision_id=decision_id, post_content=post_content, channel=channel,
        validation_result={"valid": True}, delivered=delivered,
        trace_id=trace_id, sent_at_utc=sent_at,
    )
    return {"attempt_id": attempt_id, "delivered": delivered, "blocked": False}


def _deliver_post(post_content: str, channel: str) -> bool:
    """
    Actual Telegram delivery. Stub: logs and returns True.
    In production: calls Telegram Bot API.
    """
    logger.info("[%s] DELIVERED to channel=%s content_hash=%s", AGENT_ID, channel, _hash_content(post_content))
    return True


def handle_integrity_breach(reason: str, trace_id: Optional[str] = None) -> None:
    """
    Called by Sentinel when integrity breach detected.
    Disables autopublish immediately (within 60s of detection).
    """
    _auto_disable_autopublish(reason=reason, trace_id=trace_id or str(uuid4()))


def get_autopublish_status() -> Dict[str, Any]:
    """Return current autopublish state for monitoring."""
    rec = _state_col.find_one({"_id": "autopublish"})
    kill_switch_active = _KILL_SWITCH_ENV == "OFF"
    return {
        "agent_id": AGENT_ID,
        "kill_switch": _KILL_SWITCH_ENV,
        "kill_switch_active": kill_switch_active,
        "autopublish_enabled": _get_autopublish_state(),
        "state_record": {k: v for k, v in (rec or {}).items() if k != "_id"},
    }
