"""
Parlay Logging & Persistence Utilities
========================================
Provides comprehensive logging and MongoDB persistence for parlay generation.

Collections:
- parlay_generation_audit: One row per attempt (success or fail)
- parlay_claim: One row per successful parlay (app-only, never Telegram)
- parlay_fail_event: One row per failure (optional, for debugging)

This ensures ZERO silent failures and full traceability.
"""

from __future__ import annotations
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Iterable
import hashlib
import json
import uuid

from .parlay_architect import (
    Leg, ParlayRequest, ParlayResult, compute_leg_weight, tier_counts
)


# -----------------------------
# Utilities
# -----------------------------

def utcnow_iso() -> str:
    """Get current UTC time in ISO format"""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def new_id() -> str:
    """Generate new UUID"""
    return str(uuid.uuid4())


def fingerprint_parlay(legs: List[Leg], req: ParlayRequest) -> str:
    """
    Stable fingerprint = same inputs -> same fingerprint.
    Use this to reproduce and to detect accidental duplicates.
    """
    payload = {
        "profile": req.profile,
        "legs_requested": req.legs,
        "seed": req.seed,
        "include_props": req.include_props,
        "allow_same_event": req.allow_same_event,
        "allow_same_team": req.allow_same_team,
        "legs": [
            {
                "event_id": l.event_id,
                "market_type": l.market_type.value,
                "selection": l.selection,
                "tier": l.tier.value,
            }
            for l in sorted(legs, key=lambda x: (x.event_id, x.market_type.value, x.selection))
        ],
    }
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


# -----------------------------
# Inventory Tracking
# -----------------------------

def summarize_inventory(all_legs: Iterable[Leg], include_props: bool) -> Dict[str, Any]:
    """
    Mirrors the HARD gates: DI + MV. Props excluded unless include_props=True.
    Also counts blocked reasons so we can see feed problems instantly.
    """
    eligible: List[Leg] = []
    blocked = {"DI_FAIL": 0, "MV_FAIL": 0, "PROP_EXCLUDED": 0}
    
    for l in all_legs:
        if not l.di_pass:
            blocked["DI_FAIL"] += 1
            continue
        if not l.mv_pass:
            blocked["MV_FAIL"] += 1
            continue
        if (not include_props) and (l.market_type.value == "PROP"):
            blocked["PROP_EXCLUDED"] += 1
            continue
        eligible.append(l)
    
    tiers = tier_counts(eligible)
    by_market: Dict[str, int] = {}
    for l in eligible:
        by_market[l.market_type.value] = by_market.get(l.market_type.value, 0) + 1
    
    return {
        "eligible_total": len(eligible),
        "eligible_by_tier": {k.value: v for k, v in tiers.items()},
        "eligible_by_market": by_market,
        "blocked_counts": blocked,
    }


# -----------------------------
# Document Builders
# -----------------------------

def build_audit_doc(
    attempt_id: str,
    req: ParlayRequest,
    inventory: Dict[str, Any],
    rules_base: Dict[str, Any],
    result: ParlayResult,
) -> Dict[str, Any]:
    """
    Build audit document for parlay_generation_audit collection.
    
    This is created for EVERY attempt (success or fail).
    """
    doc: Dict[str, Any] = {
        "_id": attempt_id,
        "created_at_utc": utcnow_iso(),
        "request": {
            "profile": req.profile,
            "legs_requested": req.legs,
            "include_props": req.include_props,
            "allow_same_event": req.allow_same_event,
            "allow_same_team": req.allow_same_team,
            "seed": req.seed,
        },
        "inventory": inventory,
        "rules_base": rules_base,
        "fallback": {
            "step_used": (result.reason_detail or {}).get("fallback_step"),
            "rules_used": (result.reason_detail or {}).get("rules_used"),
        },
        "result": {
            "status": result.status,
            "reason_code": result.reason_code,
            "reason_detail": result.reason_detail,
            "parlay_weight": float(result.parlay_weight) if result.parlay_weight else 0.0,
            "legs_selected_count": len(result.legs_selected) if result.legs_selected else 0,
            "parlay_fingerprint": fingerprint_parlay(result.legs_selected, req) if result.status == "PARLAY" else None,
        },
    }
    return doc


def build_claim_doc(
    attempt_id: str,
    req: ParlayRequest,
    result: ParlayResult,
) -> Dict[str, Any]:
    """
    Build claim document for parlay_claim collection.
    
    This is ONLY created for successful parlays.
    APP-ONLY: Never published to Telegram.
    """
    assert result.status == "PARLAY"
    
    parlay_id = new_id()
    legs = result.legs_selected
    legs_payload = []
    
    for l in legs:
        legs_payload.append({
            "event_id": l.event_id,
            "sport": l.sport,
            "league": l.league,
            "start_time_utc": l.start_time_utc.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z"),
            "market_type": l.market_type.value,
            "selection": l.selection,
            "tier": l.tier.value,
            "confidence": float(l.confidence),
            "clv": float(l.clv),
            "total_deviation": float(l.total_deviation),
            "volatility": l.volatility,
            "ev": float(l.ev),
            "di_pass": bool(l.di_pass),
            "mv_pass": bool(l.mv_pass),
            "leg_weight": round(compute_leg_weight(l), 6),
            "canonical_state": l.canonical_state,
            "team_key": l.team_key,
        })
    
    return {
        "_id": parlay_id,
        "attempt_id": attempt_id,
        "created_at_utc": utcnow_iso(),
        "profile_used": req.profile,
        "legs_requested": req.legs,
        "legs_selected": legs_payload,
        "parlay_weight": float(result.parlay_weight),
        "parlay_fingerprint": fingerprint_parlay(legs, req),
        "notes": {
            "data_protection_mode": "internal_full_legs",
            "telegram_mode": "none",  # APP-ONLY, no Telegram publishing
            "scope": "app_only",
        },
    }


def build_fail_doc(attempt_id: str, result: ParlayResult) -> Dict[str, Any]:
    """
    Build fail document for parlay_fail_event collection.
    
    This is ONLY created for failed attempts (optional but useful for debugging).
    """
    assert result.status == "FAIL"
    
    return {
        "_id": new_id(),
        "attempt_id": attempt_id,
        "created_at_utc": utcnow_iso(),
        "status": "FAIL",
        "reason_code": result.reason_code,
        "reason_detail": result.reason_detail,
    }


# -----------------------------
# DB Writer (MongoDB interface)
# -----------------------------

def persist_parlay_attempt(
    mongo_db,  # pymongo database handle
    all_legs: Iterable[Leg],
    req: ParlayRequest,
    rules_base: Dict[str, Any],
    result: ParlayResult,
) -> str:
    """
    Persist parlay attempt to MongoDB.
    
    Always writes an audit row.
    Writes claim row on success.
    Writes fail row on failure.
    
    Args:
        mongo_db: PyMongo database instance
        all_legs: All candidate legs (for inventory tracking)
        req: Parlay request specification
        rules_base: Base profile rules (before fallback)
        result: Parlay generation result
    
    Returns:
        attempt_id: UUID of the attempt (for tracing)
    """
    attempt_id = new_id()
    inventory = summarize_inventory(all_legs, include_props=req.include_props)
    
    # ALWAYS write audit
    audit_doc = build_audit_doc(attempt_id, req, inventory, rules_base, result)
    mongo_db.parlay_generation_audit.insert_one(audit_doc)
    
    # Conditionally write claim or fail
    if result.status == "PARLAY":
        claim_doc = build_claim_doc(attempt_id, req, result)
        mongo_db.parlay_claim.insert_one(claim_doc)
    else:
        fail_doc = build_fail_doc(attempt_id, result)
        mongo_db.parlay_fail_event.insert_one(fail_doc)
    
    return attempt_id


# -----------------------------
# Analytics Helpers (Optional)
# -----------------------------

def get_parlay_stats(mongo_db, days: int = 7) -> Dict[str, Any]:
    """
    Get parlay generation stats for the last N days.
    
    Useful for monitoring parlay generation health.
    """
    from datetime import timedelta
    
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    cutoff_iso = cutoff.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    
    # Count attempts by status
    pipeline = [
        {"$match": {"created_at_utc": {"$gte": cutoff_iso}}},
        {"$group": {
            "_id": "$result.status",
            "count": {"$sum": 1}
        }}
    ]
    status_counts = {doc["_id"]: doc["count"] for doc in mongo_db.parlay_generation_audit.aggregate(pipeline)}
    
    # Count fails by reason_code
    fail_pipeline = [
        {"$match": {"created_at_utc": {"$gte": cutoff_iso}}},
        {"$group": {
            "_id": "$reason_code",
            "count": {"$sum": 1}
        }}
    ]
    fail_reasons = {doc["_id"]: doc["count"] for doc in mongo_db.parlay_fail_event.aggregate(fail_pipeline)}
    
    return {
        "period_days": days,
        "status_counts": status_counts,
        "fail_reasons": fail_reasons,
        "success_rate": status_counts.get("PARLAY", 0) / max(1, sum(status_counts.values())),
    }
