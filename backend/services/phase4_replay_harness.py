"""
Phase 4E – Replay Harness
==========================
AC-9 requirement.

Given a decision_id (Phase 4) or publish_id (legacy), build a
deterministic replay bundle that includes:

  inputs              – odds snapshot, injury snapshot, weather snapshot
  decision_output     – phase4_decision_class + probabilities + edge
  reason_codes        – why this classification was assigned
  integrity_flags     – data quality, calibration status, immutability check

The harness is READ-ONLY: it never mutates any truth table or decision record.
Replay bundles are stored in `deterministic_replay_cache` for fast re-access.
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

REPLAY_AGENT_ID = "agent.replay.v1"   # identity for log entries

# Module-level db reference (patchable in tests)
try:
    _db = _get_db()
except Exception:
    db = None  # type: ignore[assignment]


def _get_db():
    import services.phase4_replay_harness as _self
    if _self.db is not None:
        return _self.db
    from db.mongo import db as _db
    return _db



# ============================================================================
# Bundle assembler
# ============================================================================

def build_replay_bundle(
    decision_id: str,
    *,
    force_rebuild: bool = False,
) -> Optional[Dict[str, Any]]:
    """
    Assemble a deterministic replay bundle for a Phase-4 decision_id.

    Returns the bundle dict or None if the decision_id is not found.
    Caches result in `deterministic_replay_cache`.
    """
    _db = _get_db()

    # ── Cache check ─────────────────────────────────────────────────────────
    if not force_rebuild:
        cached = db["deterministic_replay_cache"].find_one(
            {"decision_id": decision_id},
            {"_id": 0},
        )
        if cached:
            logger.debug(f"[{REPLAY_AGENT_ID}] Cache hit: {decision_id}")
            return cached

    # ── Load decision record ─────────────────────────────────────────────────
    decision = db["phase4_decision_records"].find_one(
        {"decision_id": decision_id},
        {"_id": 0},
    )
    if not decision:
        logger.warning(f"[{REPLAY_AGENT_ID}] Decision not found: {decision_id}")
        return None

    event_id   = decision.get("event_id", "")
    sport_key  = decision.get("sport_key", "")

    # ── Inputs assembly ──────────────────────────────────────────────────────
    inputs = _assemble_inputs(event_id, sport_key, decision)

    # ── Decision output ──────────────────────────────────────────────────────
    decision_output = _assemble_decision_output(decision)

    # ── Reason codes ─────────────────────────────────────────────────────────
    reason_codes = _assemble_reason_codes(decision)

    # ── Integrity flags ──────────────────────────────────────────────────────
    integrity_flags = _assemble_integrity_flags(decision, inputs)

    # ── Build bundle ─────────────────────────────────────────────────────────
    replay_id = str(uuid.uuid4())
    bundle: Dict[str, Any] = {
        "replay_id":        replay_id,
        "decision_id":      decision_id,
        "assembled_at":     datetime.now(timezone.utc).isoformat(),
        "agent_id":         REPLAY_AGENT_ID,
        "read_only":        True,
        "inputs":           inputs,
        "decision_output":  decision_output,
        "reason_codes":     reason_codes,
        "integrity_flags":  integrity_flags,
        "bundle_hash":      _compute_bundle_hash(decision_output, reason_codes),
    }

    # ── Store in cache (idempotent) ──────────────────────────────────────────
    _get_db()["deterministic_replay_cache"].update_one(
        {"decision_id": decision_id},
        {"$setOnInsert": bundle},
        upsert=True,
    )
    logger.info(f"[{REPLAY_AGENT_ID}] Bundle assembled: replay_id={replay_id}")
    return bundle


# ============================================================================
# Input assembly
# ============================================================================

def _assemble_inputs(
    event_id: str,
    sport_key: str,
    decision: Dict[str, Any],
) -> Dict[str, Any]:
    """Gather all inputs that were used during simulation."""
    _db = _get_db()

    inputs: Dict[str, Any] = {
        "event_id":    event_id,
        "sport_key":   sport_key,
        "home_team":   decision.get("home_team"),
        "away_team":   decision.get("away_team"),
        "start_time_utc": decision.get("start_time_utc"),
    }

    # Odds snapshot at simulation time
    odds_snap = db["odds_snapshots"].find_one(
        {"event_id": event_id},
        {"_id": 0},
    )
    inputs["odds_snapshot"] = odds_snap or {
        "market_line":             decision.get("market_line"),
        "market_implied_probability": decision.get("market_implied_probability"),
        "source":                  "phase4_decision_record_fallback",
    }

    # Injury snapshot
    injury_snap = db["injury_snapshots"].find_one(
        {"event_id": event_id},
        {"_id": 0},
    )
    inputs["injury_snapshot"] = injury_snap

    # Weather snapshot (where applicable)
    weather_snap = db["weather_snapshots"].find_one(
        {"event_id": event_id},
        {"_id": 0},
    )
    inputs["weather_snapshot"] = weather_snap

    # Calibration version in use at simulation time
    inputs["calibration_version"] = decision.get("calibration_version_applied")

    return inputs


# ============================================================================
# Decision output assembly
# ============================================================================

def _assemble_decision_output(decision: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "phase4_decision_class":      decision.get("phase4_decision_class"),
        "model_probability":          decision.get("model_probability"),
        "market_implied_probability": decision.get("market_implied_probability"),
        "edge_points":                decision.get("edge_points"),
        "block_reasons":              decision.get("block_reasons", []),
        "run_id":                     decision.get("run_id"),
        "created_at":                 decision.get("created_at"),
    }


# ============================================================================
# Reason codes
# ============================================================================

def _assemble_reason_codes(decision: Dict[str, Any]) -> List[str]:
    """
    Derive canonical reason codes from the decision record.
    Maps Phase-4 classification to standard reason codes.
    """
    cls           = decision.get("phase4_decision_class", "BLOCKED")
    block_reasons = decision.get("block_reasons", [])
    edge_points   = decision.get("edge_points", 0.0) or 0.0

    codes: List[str] = []

    if cls == "EDGE":
        codes.append("EDGE_CONFIRMED")
        if edge_points >= 0.05:
            codes.append("STRONG_MODEL_SIGNAL")
        else:
            codes.append("MODERATE_MODEL_SIGNAL")

    elif cls == "LEAN":
        codes.append("MODEL_LEAN_SIGNAL")
        if edge_points >= 0.02:
            codes.append("LEAN_ABOVE_THRESHOLD")
        else:
            codes.append("LEAN_MARGINAL")

    elif cls == "MARKET_ALIGNED":
        codes.append("MARKET_ALIGNED")
        codes.append("NO_MODEL_EDGE")

    elif cls == "BLOCKED":
        codes.append("BLOCKED")
        for reason in block_reasons:
            codes.append(f"BLOCK_REASON:{reason}")
        if not block_reasons:
            codes.append("BLOCK_REASON:UNKNOWN")

    return codes


# ============================================================================
# Integrity flags
# ============================================================================

def _assemble_integrity_flags(
    decision: Dict[str, Any],
    inputs: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Produce integrity flags that allow downstream audit to verify this
    replay bundle is self-consistent.
    """
    flags: Dict[str, Any] = {
        "has_odds_snapshot":    inputs.get("odds_snapshot") is not None,
        "has_injury_snapshot":  inputs.get("injury_snapshot") is not None,
        "has_weather_snapshot": inputs.get("weather_snapshot") is not None,
        "calibration_version":  inputs.get("calibration_version"),
        "calibration_active":   _check_calibration_active(
            inputs.get("calibration_version")
        ),
        "graded":               decision.get("graded", False),
        "result_code":          decision.get("result_code"),
        "clv_captured":         decision.get("clv_captured", False),
    }

    # Data quality: warn if key inputs are missing
    missing_inputs = []
    if not flags["has_odds_snapshot"]:
        missing_inputs.append("odds_snapshot")
    if missing_inputs:
        flags["missing_inputs"] = missing_inputs
        flags["data_quality_warning"] = True
    else:
        flags["data_quality_warning"] = False

    return flags


def _check_calibration_active(calibration_version: Optional[str]) -> Optional[bool]:
    """Return True if the calibration version is ACTIVE, False otherwise."""
    if not calibration_version:
        return None
    try:
        _db = _get_db()
        doc = db["calibration_versions"].find_one(
            {"calibration_version": calibration_version},
            {"status": 1},
        )
        if doc:
            return doc.get("status") == "ACTIVE"
        return None
    except Exception:
        return None


# ============================================================================
# Bundle integrity hash
# ============================================================================

def _compute_bundle_hash(
    decision_output: Dict[str, Any],
    reason_codes: List[str],
) -> str:
    """SHA-256 hash of deterministic fields for tamper detection."""
    payload = json.dumps(
        {
            "phase4_decision_class": decision_output.get("phase4_decision_class"),
            "model_probability":     decision_output.get("model_probability"),
            "edge_points":           decision_output.get("edge_points"),
            "reason_codes":          sorted(reason_codes),
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


# ============================================================================
# Batch replay (for testing / audit)
# ============================================================================

def build_replay_bundles_for_run(run_id: str) -> List[Dict[str, Any]]:
    """
    Build replay bundles for all decisions in a given run_id.
    Returns list of bundles (read-only).
    """
    _db = _get_db()

    decisions = list(
        _get_db()["phase4_decision_records"].find(
            {"run_id": run_id},
            {"decision_id": 1},
        )
    )
    bundles = []
    for d in decisions:
        bundle = build_replay_bundle(d["decision_id"])
        if bundle:
            bundles.append(bundle)
    return bundles
