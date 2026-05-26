"""
Phase 6B — Parlay Engine
Full end-to-end parlay execution pipeline.

TOKEN MODEL (LOCKED — no deviation):
  2-leg: 50 tokens | 3-leg: 75 | 4-leg: 100 | 5-leg: 150 | 6-leg: 200
  Monthly allocation: 1,500 tokens
  Overage: token_shortfall × 0.02 USD

EXECUTION PIPELINE (6 steps, sequential, no shortcuts):
  1. validate  → all legs pass required field gate
  2. construct → priority-ordered leg list
  3. simulate  → combined probability
  4. score     → correlation controls
  5. log       → write parlay_execution_log BEFORE returning
  6. return    → parlay or NO_PARLAY with reason codes

CORRELATION CONTROLS:
  - Max 1 pick per game
  - Spread + total from same game prevented
  - Team exposure limit enforced
  - Totals limit per slate enforced

DETERMINISM:
  Same build_sequence_index + same mode + same candidate pool = identical output.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from db.mongo import db
from config.agent_config import AGENT_CONFIG

logger = logging.getLogger(__name__)

# ── Token model (6B.4 — locked) ───────────────────────────────────────────────
TOKEN_COST: Dict[int, int] = {2: 50, 3: 75, 4: 100, 5: 150, 6: 200}
MONTHLY_ALLOCATION = 1500
OVERAGE_RATE_USD = 0.02  # per token shortfall

# ── Build modes (6B.8) ────────────────────────────────────────────────────────
BUILD_MODES = {"HIGH_CONFIDENCE", "BALANCED", "HIGH_VOL"}

# ── Leg selection priority (6B.2) — lower index = higher priority ─────────────
# (mode, classification, constrained)
_LEG_PRIORITY = [
    ("HIGH_CONFIDENCE", "EDGE", False),
    ("HIGH_CONFIDENCE", "EDGE", True),
    ("BALANCED", "EDGE", False),
    ("BALANCED", "EDGE", True),
    ("BALANCED", "LEAN", False),
    ("BALANCED", "LEAN", True),
    ("HIGH_VOL", "EDGE", False),
    ("HIGH_VOL", "EDGE", True),
    ("HIGH_VOL", "LEAN", False),
    ("HIGH_VOL", "LEAN", True),
    ("HIGH_VOL", "MARKET_ALIGNED", False),
]

# ── Collections ───────────────────────────────────────────────────────────────
_exec_log = db["parlay_execution_log"]
_overage_log = db["parlay_overage_charge_log"]
_token_ledger = db["parlay_token_ledger"]

# ── Concurrency lock — prevents race conditions on token deduction ─────────────
_token_lock = threading.Lock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _cfg() -> Dict[str, Any]:
    return AGENT_CONFIG.get("phase6", {}).get("parlay", {})


# ─────────────────────────────────────────────────────────────────────────────
# Step 1 — Validate
# ─────────────────────────────────────────────────────────────────────────────

_REQUIRED_LEG_FIELDS = [
    "decision_id", "selection_id", "snapshot_hash",
    "event_id", "market_type", "classification",
    "prob_edge",
]


def _validate_legs(candidates: List[Dict[str, Any]]) -> Tuple[List[Dict], List[Dict]]:
    """
    Validate all candidate legs against required field gate + candidate pool rules.
    Returns (valid_legs, rejected_legs_with_reasons).
    """
    valid, rejected = [], []
    for leg in candidates:
        # DB-level candidate pool filters (6B.1) re-enforced at service layer
        if not leg.get("selection_id"):
            rejected.append({**leg, "_reject_reason": "selection_id missing — not a candidate"})
            continue
        if not leg.get("snapshot_hash"):
            rejected.append({**leg, "_reject_reason": "snapshot_hash missing — not a candidate"})
            continue
        if leg.get("release_status", "") != "OFFICIAL":
            rejected.append({**leg, "_reject_reason": f"release_status={leg.get('release_status')!r} is not OFFICIAL"})
            continue
        if leg.get("validator_status", "") != "PASS":
            rejected.append({**leg, "_reject_reason": f"validator_status={leg.get('validator_status')!r} failed validation — not a candidate"})
            continue

        missing = [f for f in _REQUIRED_LEG_FIELDS if not leg.get(f)]
        if missing:
            rejected.append({**leg, "_reject_reason": f"required fields missing: {missing}"})
            continue

        valid.append(leg)
    return valid, rejected


# ─────────────────────────────────────────────────────────────────────────────
# Step 2 — Construct (priority ordering by mode)
# ─────────────────────────────────────────────────────────────────────────────

_MIN_PROB_EDGE: Dict[str, float] = {"EDGE": 5.0, "LEAN": 2.5}


def _construct_legs(
    valid_legs: List[Dict[str, Any]],
    mode: str,
    requested_size: int,
) -> Tuple[List[Dict], str]:
    """
    Select legs in priority order for the given build mode.
    Returns (selected_legs, reason_code).
    """
    mode_upper = mode.upper()
    if mode_upper not in BUILD_MODES:
        return [], f"INVALID_MODE:{mode}"

    # Determine which classifications are eligible for this mode
    eligible_classifications: List[str]
    if mode_upper == "HIGH_CONFIDENCE":
        eligible_classifications = ["EDGE"]
    elif mode_upper == "BALANCED":
        eligible_classifications = ["EDGE", "LEAN"]
    else:  # HIGH_VOL
        eligible_classifications = ["EDGE", "LEAN", "MARKET_ALIGNED"]

    # Sort by priority: EDGE first, then LEAN, then MARKET_ALIGNED;
    # unconstrained before constrained; highest prob_edge within group.
    def sort_key(leg: Dict) -> Tuple:
        cls = str(leg.get("classification", "")).upper()
        cls_order = {"EDGE": 0, "LEAN": 1, "MARKET_ALIGNED": 2}.get(cls, 9)
        constrained = 1 if leg.get("has_constraints") else 0
        prob_edge = float(leg.get("prob_edge", 0) or 0)
        return (cls_order, constrained, -prob_edge)

    candidates = [
        leg for leg in valid_legs
        if str(leg.get("classification", "")).upper() in eligible_classifications
        and float(leg.get("prob_edge", 0) or 0) >= _MIN_PROB_EDGE.get(
            str(leg.get("classification", "")).upper(), 0
        )
    ]

    candidates.sort(key=sort_key)
    selected = candidates[:requested_size]

    if not selected:
        return [], "NO_QUALIFYING_LEGS"
    if len(selected) < 2:
        return selected, f"INSUFFICIENT_LEGS:only {len(selected)} qualifying leg(s) found"
    if len(selected) < requested_size:
        return selected, f"SMALLER_PARLAY:only {len(selected)} of {requested_size} requested legs qualify"

    return selected, "OK"


# ─────────────────────────────────────────────────────────────────────────────
# Step 3 — Simulate (combined probability)
# ─────────────────────────────────────────────────────────────────────────────

def _simulate_combined(legs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute combined probability as product of individual probabilities (independence assumption)."""
    probs = []
    for leg in legs:
        p = float(leg.get("probability", 0) or 0)
        if p <= 0 or p >= 1:
            p = float(leg.get("probability", 0) or 0) / 100.0 if float(leg.get("probability", 0) or 0) > 1 else p
        probs.append(max(0.01, min(0.99, p)))

    combined = 1.0
    for p in probs:
        combined *= p

    return {
        "combined_probability": combined,
        "combined_probability_pct": round(combined * 100, 4),
        "leg_probabilities": probs,
        "leg_count": len(probs),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Step 4 — Score (correlation controls 6B.5)
# ─────────────────────────────────────────────────────────────────────────────

def _score_correlation(legs: List[Dict[str, Any]]) -> Tuple[str, List[Dict]]:
    """
    Apply correlation controls. Returns ("PASS", []) or ("REJECT", [rejection_records]).
    """
    rejections = []
    seen_games: Dict[str, List[str]] = {}  # event_id → [market_types]
    team_exposure: Dict[str, int] = {}
    total_count = 0
    cfg = _cfg()
    max_totals = cfg.get("max_totals_per_slate", 3)

    for leg in legs:
        event_id = leg.get("event_id", "")
        market_type = str(leg.get("market_type", "")).upper()
        team = leg.get("team_name", "")
        selection_id = leg.get("selection_id", "")

        # Correlation control 1: max 1 pick per game
        if event_id in seen_games:
            rejections.append({
                "selection_id": selection_id,
                "reason": f"GAME_LIMIT: second pick for event_id={event_id!r} rejected",
                "rule": "max_1_pick_per_game",
            })
            continue

        # Correlation control 3: spread + total from same game prevented
        if event_id in seen_games:
            existing_markets = seen_games[event_id]
            if "SPREAD" in existing_markets and market_type == "TOTAL":
                rejections.append({
                    "selection_id": selection_id,
                    "reason": f"MARKET_CLUSTER: TOTAL rejected — SPREAD already in parlay for event_id={event_id!r}",
                    "rule": "spread_total_same_game",
                })
                continue
            if "TOTAL" in existing_markets and market_type == "SPREAD":
                rejections.append({
                    "selection_id": selection_id,
                    "reason": f"MARKET_CLUSTER: SPREAD rejected — TOTAL already in parlay for event_id={event_id!r}",
                    "rule": "spread_total_same_game",
                })
                continue

        # Correlation control 2: team exposure
        if team:
            team_exposure[team] = team_exposure.get(team, 0) + 1
            max_team_exp = cfg.get("max_team_exposure", 2)
            if team_exposure[team] > max_team_exp:
                rejections.append({
                    "selection_id": selection_id,
                    "reason": f"TEAM_LIMIT: {team!r} appears {team_exposure[team]} times (max {max_team_exp})",
                    "rule": "team_exposure_limit",
                })
                continue

        # Correlation control 4: totals limit
        if market_type == "TOTAL":
            total_count += 1
            if total_count > max_totals:
                rejections.append({
                    "selection_id": selection_id,
                    "reason": f"TOTALS_LIMIT: {total_count} totals exceeds max {max_totals} per slate",
                    "rule": "totals_limit",
                })
                continue

        seen_games.setdefault(event_id, []).append(market_type)

    if rejections:
        return "REJECT", rejections

    return "PASS", []


# ─────────────────────────────────────────────────────────────────────────────
# Token management (with concurrency lock)
# ─────────────────────────────────────────────────────────────────────────────

def _get_user_token_balance(user_id: str) -> int:
    """Get remaining token allocation for this billing period."""
    now = datetime.now(timezone.utc)
    period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    used = _token_ledger.aggregate([
        {"$match": {"user_id": user_id, "period_start": {"$gte": period_start.isoformat()}}},
        {"$group": {"_id": None, "total": {"$sum": "$tokens_used"}}},
    ])
    used_list = list(used)
    tokens_used = used_list[0]["total"] if used_list else 0
    return max(0, MONTHLY_ALLOCATION - tokens_used)


def _deduct_tokens(user_id: str, parlay_run_id: str, token_cost: int) -> Dict[str, Any]:
    """
    Atomically deduct tokens. Returns {"success": True} or {"success": False, "reason": ...}.
    Logs overage if applicable.
    """
    now = datetime.now(timezone.utc)
    period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    with _token_lock:
        balance = _get_user_token_balance(user_id)
        if balance <= 0:
            # Overage block — 100% allocation used
            overage_entry = {
                "overage_id": str(uuid4()),
                "user_id": user_id,
                "parlay_run_id": parlay_run_id,
                "event_type": "OVERAGE_BLOCK",
                "tokens_requested": token_cost,
                "tokens_available": 0,
                "overage_amount_usd": token_cost * OVERAGE_RATE_USD,
                "logged_at_utc": _now_iso(),
            }
            _overage_log.insert_one(overage_entry)
            return {
                "success": False,
                "reason": "OVERAGE_BLOCK",
                "tokens_available": 0,
                "tokens_requested": token_cost,
                "upgrade_required": True,
            }

        # Deduct
        _token_ledger.insert_one({
            "ledger_id": str(uuid4()),
            "user_id": user_id,
            "parlay_run_id": parlay_run_id,
            "tokens_used": token_cost,
            "period_start": period_start.isoformat(),
            "logged_at_utc": _now_iso(),
        })

        new_balance = balance - token_cost
        pct_used = ((MONTHLY_ALLOCATION - new_balance) / MONTHLY_ALLOCATION) * 100

        # Alert at 80% usage
        if pct_used >= 80:
            db["ops_alert"].insert_one({
                "alert_type": "PARLAY_TOKEN_80PCT",
                "user_id": user_id,
                "pct_used": pct_used,
                "tokens_remaining": new_balance,
                "logged_at_utc": _now_iso(),
            })

        return {"success": True, "tokens_remaining": new_balance, "pct_used": pct_used}


# ─────────────────────────────────────────────────────────────────────────────
# Step 5 — Log (6B.6)
# ─────────────────────────────────────────────────────────────────────────────

def _log_execution(
    *,
    parlay_run_id: str,
    user_id: str,
    trace_id: str,
    decision_ids: List[str],
    snapshot_hash: str,
    build_mode: str,
    build_sequence_index: int,
    token_cost: int,
    result: str,
    reason_codes: List[str],
    simulation: Optional[Dict],
    legs: List[Dict],
) -> None:
    """Write to parlay_execution_log BEFORE returning to user. Append-only."""
    _exec_log.insert_one({
        "parlay_run_id": parlay_run_id,
        "decision_ids": decision_ids,
        "trace_id": trace_id,
        "snapshot_hash": snapshot_hash,
        "build_mode": build_mode,
        "build_sequence_index": build_sequence_index,
        "token_cost": token_cost,
        "created_at_utc": _now_iso(),
        "user_id": user_id,
        "result": result,
        "reason_codes": reason_codes,
        "simulation": simulation,
        "leg_count": len(legs),
        "legs_summary": [
            {
                "decision_id": leg.get("decision_id"),
                "selection_id": leg.get("selection_id"),
                "market_type": leg.get("market_type"),
                "classification": leg.get("classification"),
            }
            for leg in legs
        ],
    })


# ─────────────────────────────────────────────────────────────────────────────
# Build sequence index (determinism 6B.8)
# ─────────────────────────────────────────────────────────────────────────────

def _compute_build_sequence_index(candidate_ids: List[str], mode: str) -> int:
    """Deterministic index: same ids + mode always produces same integer."""
    import hashlib
    key = mode.upper() + "|" + "|".join(sorted(candidate_ids))
    return int(hashlib.sha256(key.encode()).hexdigest(), 16) % (10**9)


# ─────────────────────────────────────────────────────────────────────────────
# Public API — build_parlay (the 6-step pipeline)
# ─────────────────────────────────────────────────────────────────────────────

def build_parlay(
    *,
    user_id: str,
    candidates: List[Dict[str, Any]],
    requested_size: int,
    mode: str = "HIGH_CONFIDENCE",
    trace_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Execute the 6-step parlay pipeline. Atomic, sequential, no shortcuts.
    Returns parlay result with token cost confirmation, or NO_PARLAY with reason codes.
    """
    if trace_id is None:
        trace_id = str(uuid4())

    parlay_run_id = str(uuid4())
    mode_upper = mode.upper()

    # Token cost check — must show cost before execution (6B.9)
    leg_count = min(requested_size, len(candidates))
    leg_count = max(2, min(6, leg_count))
    token_cost = TOKEN_COST.get(leg_count, TOKEN_COST[6])

    # ── STEP 1: Validate ─────────────────────────────────────────────────────
    valid_legs, rejected_legs = _validate_legs(candidates)
    if not valid_legs:
        reason_codes = ["NO_VALID_CANDIDATES"] + [r.get("_reject_reason", "") for r in rejected_legs[:3]]
        _log_execution(
            parlay_run_id=parlay_run_id, user_id=user_id, trace_id=trace_id,
            decision_ids=[], snapshot_hash="", build_mode=mode_upper,
            build_sequence_index=0, token_cost=0,
            result="NO_PARLAY", reason_codes=reason_codes, simulation=None, legs=[],
        )
        return {
            "result": "NO_PARLAY",
            "reason_codes": reason_codes,
            "parlay_run_id": parlay_run_id,
            "token_cost": 0,
        }

    # ── STEP 2: Construct ────────────────────────────────────────────────────
    selected_legs, construct_reason = _construct_legs(valid_legs, mode_upper, requested_size)

    if len(selected_legs) < 2:
        reason_codes = [construct_reason]
        _log_execution(
            parlay_run_id=parlay_run_id, user_id=user_id, trace_id=trace_id,
            decision_ids=[l.get("decision_id", "") for l in selected_legs],
            snapshot_hash="", build_mode=mode_upper,
            build_sequence_index=0, token_cost=0,
            result="NO_PARLAY", reason_codes=reason_codes, simulation=None, legs=selected_legs,
        )
        return {
            "result": "NO_PARLAY",
            "reason_codes": reason_codes,
            "parlay_run_id": parlay_run_id,
            "token_cost": 0,
        }

    # Actual cost based on legs selected (may be smaller than requested)
    actual_leg_count = len(selected_legs)
    token_cost = TOKEN_COST.get(actual_leg_count, TOKEN_COST.get(max(TOKEN_COST.keys()), 200))

    # Snapshot hash — must be consistent across all legs
    hashes = list({leg.get("snapshot_hash", "") for leg in selected_legs if leg.get("snapshot_hash")})
    if len(hashes) != 1:
        reason_codes = [f"SNAPSHOT_HASH_INCONSISTENT: {len(hashes)} distinct hashes found"]
        _log_execution(
            parlay_run_id=parlay_run_id, user_id=user_id, trace_id=trace_id,
            decision_ids=[l.get("decision_id", "") for l in selected_legs],
            snapshot_hash="INCONSISTENT", build_mode=mode_upper,
            build_sequence_index=0, token_cost=0,
            result="NO_PARLAY", reason_codes=reason_codes, simulation=None, legs=selected_legs,
        )
        return {"result": "NO_PARLAY", "reason_codes": reason_codes, "parlay_run_id": parlay_run_id, "token_cost": 0}

    snapshot_hash = hashes[0]
    candidate_ids = [leg.get("decision_id", leg.get("selection_id", "")) for leg in selected_legs]
    build_sequence_index = _compute_build_sequence_index(candidate_ids, mode_upper)

    # ── STEP 3: Simulate ─────────────────────────────────────────────────────
    simulation = _simulate_combined(selected_legs)

    # ── STEP 4: Score (correlation controls) ─────────────────────────────────
    corr_result, corr_rejections = _score_correlation(selected_legs)

    if corr_result == "REJECT":
        reason_codes = ["CORRELATION_REJECTED"] + [r["reason"] for r in corr_rejections]
        _log_execution(
            parlay_run_id=parlay_run_id, user_id=user_id, trace_id=trace_id,
            decision_ids=candidate_ids, snapshot_hash=snapshot_hash,
            build_mode=mode_upper, build_sequence_index=build_sequence_index,
            token_cost=0, result="NO_PARLAY", reason_codes=reason_codes,
            simulation=simulation, legs=selected_legs,
        )
        return {
            "result": "NO_PARLAY",
            "reason_codes": reason_codes,
            "correlation_rejections": corr_rejections,
            "parlay_run_id": parlay_run_id,
            "token_cost": 0,
        }

    # ── Token deduction (with cost confirmation) ──────────────────────────────
    deduct_result = _deduct_tokens(user_id, parlay_run_id, token_cost)
    if not deduct_result["success"]:
        reason_codes = [deduct_result["reason"]]
        _log_execution(
            parlay_run_id=parlay_run_id, user_id=user_id, trace_id=trace_id,
            decision_ids=candidate_ids, snapshot_hash=snapshot_hash,
            build_mode=mode_upper, build_sequence_index=build_sequence_index,
            token_cost=token_cost, result="NO_PARLAY", reason_codes=reason_codes,
            simulation=simulation, legs=selected_legs,
        )
        return {
            "result": "NO_PARLAY",
            "reason_codes": reason_codes,
            "token_cost": token_cost,
            "tokens_available": deduct_result.get("tokens_available", 0),
            "upgrade_required": deduct_result.get("upgrade_required", False),
            "http_status": 402,
            "parlay_run_id": parlay_run_id,
        }

    # ── STEP 5: Log (before returning) ───────────────────────────────────────
    _log_execution(
        parlay_run_id=parlay_run_id, user_id=user_id, trace_id=trace_id,
        decision_ids=candidate_ids, snapshot_hash=snapshot_hash,
        build_mode=mode_upper, build_sequence_index=build_sequence_index,
        token_cost=token_cost, result="PARLAY_BUILT",
        reason_codes=[construct_reason] if construct_reason != "OK" else [],
        simulation=simulation, legs=selected_legs,
    )

    # ── STEP 6: Return ────────────────────────────────────────────────────────
    return {
        "result": "PARLAY_BUILT",
        "parlay_run_id": parlay_run_id,
        "trace_id": trace_id,
        "build_mode": mode_upper,
        "build_sequence_index": build_sequence_index,
        "snapshot_hash": snapshot_hash,
        "token_cost": token_cost,
        "tokens_remaining": deduct_result.get("tokens_remaining", 0),
        "leg_count": actual_leg_count,
        "simulation": simulation,
        "legs": [
            {
                "decision_id": leg.get("decision_id"),
                "selection_id": leg.get("selection_id"),
                "team_name": leg.get("team_name"),
                "market_type": leg.get("market_type"),
                "classification": leg.get("classification"),
                "prob_edge": leg.get("prob_edge"),
                "has_constraints": leg.get("has_constraints", False),
            }
            for leg in selected_legs
        ],
        "reason_codes": [construct_reason] if construct_reason not in ("OK",) else [],
    }
