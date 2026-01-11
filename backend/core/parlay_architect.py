"""
Parlay Architect - Core Engine
================================
This implements a tiered pool (EDGE → PICK → LEAN) parlay generation system
that ALWAYS returns either a valid PARLAY or a structured FAIL with reasons.

Key Features:
- Tiered candidate pool instead of EDGE-only requirement
- Fallback ladder that relaxes constraints progressively
- Never returns silent failures
- Deterministic output via seed parameter
- Respects DI/MV hard gates (data integrity + market validity)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Tuple, Optional, Iterable
import random
import math
from datetime import datetime, timezone

# -----------------------------
# Models
# -----------------------------

class Tier(str, Enum):
    """Parlay tier classification"""
    EDGE = "EDGE"      # Strong edge, high confidence
    PICK = "PICK"      # Solid pick, medium-high confidence
    LEAN = "LEAN"      # Soft edge, lower confidence


class MarketType(str, Enum):
    """Supported market types"""
    SPREAD = "SPREAD"
    TOTAL = "TOTAL"
    MONEYLINE = "MONEYLINE"
    PROP = "PROP"


@dataclass(frozen=True)
class Leg:
    """
    A single candidate leg from your engine.
    """
    event_id: str
    sport: str
    league: str
    start_time_utc: datetime
    market_type: MarketType
    selection: str  # e.g. "Bulls +10.5", "Under 170", "Suns -4.5"
    tier: Tier  # EDGE/PICK/LEAN
    confidence: float  # 0-100 (or 0-1; normalize below)
    clv: float  # percent points, can be 0.0
    total_deviation: float  # pts vs book (abs)
    volatility: str  # "LOW"|"MEDIUM"|"HIGH"
    ev: float  # expected value (can be 0 if not computed)
    
    # gate flags (must pass to be eligible)
    di_pass: bool  # data integrity
    mv_pass: bool  # market validity
    is_locked: bool = False
    injury_stable: bool = True
    
    # dedupe keys
    team_key: Optional[str] = None  # useful for avoiding correlated legs
    canonical_state: Optional[str] = None  # original signal state for tracing


@dataclass
class ParlayRequest:
    """Request specification for parlay generation"""
    profile: str  # "premium"|"balanced"|"speculative"
    legs: int  # 3,4,5,6
    allow_same_event: bool = False
    allow_same_team: bool = True
    seed: Optional[int] = None  # deterministic output for testing / posting
    include_props: bool = False  # keep False unless DFS mode enabled


@dataclass
class ParlayResult:
    """
    Result from parlay generation.
    Always has status="PARLAY" or status="FAIL" with reason.
    """
    status: str  # "PARLAY"|"FAIL"
    profile: str
    legs_requested: int
    legs_selected: List[Leg] = field(default_factory=list)
    parlay_weight: float = 0.0
    reason_code: Optional[str] = None
    reason_detail: Optional[Dict] = None


# -----------------------------
# Tier Derivation (maps canonical_state → Tier)
# -----------------------------

def derive_tier(canonical_state: str, confidence: float, ev: float = 0.0) -> Tier:
    """
    Derive parlay tier from canonical signal state.
    
    Mapping rules:
    - EDGE signal → EDGE tier (always)
    - LEAN signal with confidence ≥ 60 → PICK tier (upgrade)
    - LEAN signal with confidence < 60 → LEAN tier
    - NO_PLAY → never eligible (filtered before this function)
    - PENDING → never eligible (filtered before this function)
    
    Args:
        canonical_state: Signal state from your engine
        confidence: 0-100 scale
        ev: Expected value (optional, for future use)
    
    Returns:
        Tier enum value
    """
    state = canonical_state.upper()
    
    if state == "EDGE":
        return Tier.EDGE
    elif state == "LEAN":
        # Upgrade strong LEANs to PICK tier
        if confidence >= 60.0:
            return Tier.PICK
        return Tier.LEAN
    elif state == "PICK":
        # Direct PICK mapping (if your system has this state)
        return Tier.PICK
    else:
        # NO_PLAY, PENDING, etc. should be filtered before this
        # Default to LEAN for safety (but log warning in production)
        return Tier.LEAN


# -----------------------------
# Scoring / Weighting
# -----------------------------

def _norm_confidence(conf: float) -> float:
    """Normalize confidence to 0..1 range"""
    if conf <= 1.0:
        return max(0.0, min(1.0, conf))
    return max(0.0, min(1.0, conf / 100.0))


def compute_leg_weight(leg: Leg) -> float:
    """
    Produce a stable, monotonic weight.
    Higher = better.
    
    IMPORTANT:
    - Does NOT force EV>0. If EV is 0, it doesn't kill the leg; it just doesn't boost it.
    - Volatility penalizes (especially HIGH).
    - Tier is the main driver: EDGE > PICK > LEAN.
    """
    tier_base = {
        Tier.EDGE: 1.00,
        Tier.PICK: 0.70,
        Tier.LEAN: 0.45,
    }[leg.tier]
    
    c = _norm_confidence(leg.confidence)  # 0..1
    clv_boost = max(-0.02, min(0.02, leg.clv / 100.0))  # cap ±2%
    dev_boost = min(0.25, abs(leg.total_deviation) / 20.0)  # cap
    ev_boost = min(0.10, max(0.0, leg.ev))  # small positive bonus if EV exists
    
    vol_penalty = {
        "LOW": 0.00,
        "MEDIUM": 0.06,
        "HIGH": 0.12,
    }.get(leg.volatility.upper(), 0.08)
    
    injury_penalty = 0.08 if not leg.injury_stable else 0.00
    locked_penalty = 0.15 if leg.is_locked else 0.00
    
    weight = (
        tier_base
        + (0.65 * c)
        + clv_boost
        + (0.35 * dev_boost)
        + ev_boost
        - vol_penalty
        - injury_penalty
        - locked_penalty
    )
    return max(0.0, weight)


def compute_parlay_weight(legs: List[Leg]) -> float:
    """
    Parlay weight is the product-ish of leg weights, but keep it stable:
    sum of log weights with floor to avoid zeroing out.
    """
    if not legs:
        return 0.0
    w = 0.0
    for leg in legs:
        lw = max(1e-6, compute_leg_weight(leg))
        w += math.log(lw + 1.0)  # log(1+w) keeps sane scale
    return w


# -----------------------------
# Eligibility / Pool building
# -----------------------------

def eligible_pool(all_legs: Iterable[Leg], include_props: bool) -> List[Leg]:
    """
    Hard gates: DI + MV must pass.
    (This is the "doesn't introduce other issues" part: we don't bypass integrity.)
    """
    pool = []
    for leg in all_legs:
        if not (leg.di_pass and leg.mv_pass):
            continue
        if not include_props and leg.market_type == MarketType.PROP:
            continue
        pool.append(leg)
    
    # sort by individual strength so selection is stable
    pool.sort(key=lambda x: compute_leg_weight(x), reverse=True)
    return pool


def tier_counts(legs: List[Leg]) -> Dict[Tier, int]:
    """Count legs by tier"""
    out = {Tier.EDGE: 0, Tier.PICK: 0, Tier.LEAN: 0}
    for l in legs:
        out[l.tier] += 1
    return out


# -----------------------------
# Profile constraints + fallback ladder
# -----------------------------

@dataclass(frozen=True)
class ProfileRules:
    """Constraints for each risk profile"""
    min_parlay_weight: float
    min_edges: int  # SOFT constraint (preference, not blocker)
    min_picks: int  # SOFT constraint (preference, not blocker)
    allow_lean: bool
    max_high_vol_legs: int
    max_same_event: int


PROFILE_RULES: Dict[str, ProfileRules] = {
    # tight
    "premium": ProfileRules(
        min_parlay_weight=3.10,
        min_edges=2,  # preference: 2+ EDGE legs
        min_picks=1,  # preference: 1+ PICK legs
        allow_lean=False,
        max_high_vol_legs=1,
        max_same_event=1,
    ),
    # medium
    "balanced": ProfileRules(
        min_parlay_weight=2.85,
        min_edges=1,  # preference: 1+ EDGE leg
        min_picks=1,  # preference: 1+ PICK leg
        allow_lean=True,
        max_high_vol_legs=2,
        max_same_event=1,
    ),
    # looser (but still gated)
    "speculative": ProfileRules(
        min_parlay_weight=2.55,
        min_edges=0,  # no EDGE requirement
        min_picks=0,  # no PICK requirement (will use tier ladder)
        allow_lean=True,
        max_high_vol_legs=3,
        max_same_event=1,
    ),
}


# fallback ladder: relax rules stepwise so the system returns something or a clear FAIL
FALLBACK_STEPS = [
    # step 0 = normal
    {},
    # step 1 = lower min_parlay_weight slightly
    {"min_parlay_weight_delta": -0.15},
    # step 2 = allow 1 more HIGH volatility
    {"max_high_vol_legs_delta": +1},
    # step 3 = relax tier requirements (SOFT - treat as preferences)
    {"min_edges_delta": -1, "min_picks_delta": -1},
    # step 4 = allow LEAN even for premium if it otherwise produces nothing
    {"force_allow_lean": True},
    # step 5 = further lower weight requirement
    {"min_parlay_weight_delta": -0.30},
]


def apply_fallback(base: ProfileRules, step: Dict) -> ProfileRules:
    """Apply fallback adjustments to base rules"""
    return ProfileRules(
        min_parlay_weight=max(0.0, base.min_parlay_weight + step.get("min_parlay_weight_delta", 0.0)),
        min_edges=max(0, base.min_edges + step.get("min_edges_delta", 0)),
        min_picks=max(0, base.min_picks + step.get("min_picks_delta", 0)),
        allow_lean=step.get("force_allow_lean", False) or base.allow_lean,
        max_high_vol_legs=max(0, base.max_high_vol_legs + step.get("max_high_vol_legs_delta", 0)),
        max_same_event=base.max_same_event,
    )


# -----------------------------
# Selection engine
# -----------------------------

def build_parlay(
    all_legs: Iterable[Leg],
    req: ParlayRequest,
) -> ParlayResult:
    """
    Main parlay generation function.
    
    ALWAYS returns either:
    - ParlayResult with status="PARLAY" and legs_selected populated, or
    - ParlayResult with status="FAIL" and reason_code/reason_detail explaining why
    
    Never returns None or silently fails.
    """
    if req.profile not in PROFILE_RULES:
        return ParlayResult(
            status="FAIL",
            profile=req.profile,
            legs_requested=req.legs,
            reason_code="INVALID_PROFILE",
            reason_detail={"allowed": list(PROFILE_RULES.keys())},
        )
    
    rng = random.Random(req.seed)
    pool = eligible_pool(all_legs, include_props=req.include_props)
    
    if len(pool) < req.legs:
        return ParlayResult(
            status="FAIL",
            profile=req.profile,
            legs_requested=req.legs,
            reason_code="INSUFFICIENT_POOL",
            reason_detail={
                "eligible_pool_size": len(pool),
                "legs_requested": req.legs,
            },
        )
    
    base_rules = PROFILE_RULES[req.profile]
    
    # Try normal + fallbacks
    for step_i, step in enumerate(FALLBACK_STEPS):
        rules = apply_fallback(base_rules, step)
        attempt = _attempt_build(pool, req, rules, rng)
        if attempt.status == "PARLAY":
            attempt.reason_detail = (attempt.reason_detail or {}) | {
                "fallback_step": step_i,
                "rules_used": rules.__dict__,
            }
            return attempt
    
    # If all attempts failed, return the best failure (most informative)
    return ParlayResult(
        status="FAIL",
        profile=req.profile,
        legs_requested=req.legs,
        reason_code="NO_VALID_PARLAY_FOUND",
        reason_detail={
            "eligible_pool_size": len(pool),
            "profile_rules": base_rules.__dict__,
            "note": "All fallback steps exhausted without meeting constraints.",
        },
    )


def _attempt_build(
    pool: List[Leg],
    req: ParlayRequest,
    rules: ProfileRules,
    rng: random.Random,
) -> ParlayResult:
    """
    Greedy + constrained selection:
    - start with best legs by weight
    - allow minor randomness within top band to avoid identical parlays
    - enforce correlation limits (same event, same team)
    - enforce volatility cap
    - check tier minimums (SOFT - preferences, not blockers)
    """
    selected: List[Leg] = []
    used_events: Dict[str, int] = {}
    used_teams: set = set()  # track team_key for correlation blocking
    high_vol = 0
    
    # Candidate banding: mostly top legs, but not always identical
    # (Still stable because pool is sorted by weight)
    top_n = min(len(pool), max(30, req.legs * 12))
    band = pool[:top_n]
    
    # Shuffle within band deterministically
    band = band[:]  # copy
    rng.shuffle(band)
    
    def can_add(leg: Leg) -> bool:
        # Same event check
        if not req.allow_same_event:
            if used_events.get(leg.event_id, 0) >= rules.max_same_event:
                return False
        
        # Same team check (using team_key)
        if not req.allow_same_team:
            if leg.team_key and leg.team_key in used_teams:
                return False
        
        # Volatility cap
        if leg.volatility.upper() == "HIGH" and high_vol >= rules.max_high_vol_legs:
            return False
        
        return True
    
    # First pass: add strongest feasible legs
    for leg in band:
        if len(selected) >= req.legs:
            break
        if not can_add(leg):
            continue
        
        selected.append(leg)
        used_events[leg.event_id] = used_events.get(leg.event_id, 0) + 1
        if leg.team_key:
            used_teams.add(leg.team_key)
        if leg.volatility.upper() == "HIGH":
            high_vol += 1
    
    # If we still don't have enough, widen pool
    if len(selected) < req.legs:
        for leg in pool[top_n:]:
            if len(selected) >= req.legs:
                break
            if not can_add(leg):
                continue
            
            selected.append(leg)
            used_events[leg.event_id] = used_events.get(leg.event_id, 0) + 1
            if leg.team_key:
                used_teams.add(leg.team_key)
            if leg.volatility.upper() == "HIGH":
                high_vol += 1
    
    if len(selected) < req.legs:
        return ParlayResult(
            status="FAIL",
            profile=req.profile,
            legs_requested=req.legs,
            reason_code="CONSTRAINT_BLOCKED",
            reason_detail={
                "selected": len(selected),
                "requested": req.legs,
                "high_vol_used": high_vol,
                "max_high_vol_allowed": rules.max_high_vol_legs,
                "max_same_event": rules.max_same_event,
                "allow_same_team": req.allow_same_team,
            },
        )
    
    # Tier checks (SOFT - log warnings but don't block if eligible_total >= legs_requested)
    counts = tier_counts(selected)
    
    # Check LEAN allowance (this is a HARD rule)
    if not rules.allow_lean and counts[Tier.LEAN] > 0:
        return ParlayResult(
            status="FAIL",
            profile=req.profile,
            legs_requested=req.legs,
            reason_code="LEAN_NOT_ALLOWED",
            reason_detail={"counts": {k.value: v for k, v in counts.items()}},
        )
    
    # SOFT tier checks (preferences, not blockers)
    # Only warn if we're below preference, don't fail
    tier_warnings = {}
    if counts[Tier.EDGE] < rules.min_edges:
        tier_warnings["edge_preference_not_met"] = {
            "actual": counts[Tier.EDGE],
            "preferred": rules.min_edges
        }
    if counts[Tier.PICK] < rules.min_picks:
        tier_warnings["pick_preference_not_met"] = {
            "actual": counts[Tier.PICK],
            "preferred": rules.min_picks
        }
    
    # Parlay weight check
    pw = compute_parlay_weight(selected)
    if pw < rules.min_parlay_weight:
        return ParlayResult(
            status="FAIL",
            profile=req.profile,
            legs_requested=req.legs,
            reason_code="PARLAY_WEIGHT_TOO_LOW",
            reason_detail={
                "parlay_weight": round(pw, 4),
                "min_required": rules.min_parlay_weight,
                "counts": {k.value: v for k, v in counts.items()},
                "tier_warnings": tier_warnings if tier_warnings else None,
            },
        )
    
    # SUCCESS
    result_detail = {
        "tier_counts": {k.value: v for k, v in counts.items()},
    }
    if tier_warnings:
        result_detail["tier_warnings"] = tier_warnings
    
    return ParlayResult(
        status="PARLAY",
        profile=req.profile,
        legs_requested=req.legs,
        legs_selected=selected,
        parlay_weight=pw,
        reason_detail=result_detail,
    )
