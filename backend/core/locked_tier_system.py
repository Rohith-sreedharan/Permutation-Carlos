"""
LOCKED TIER SYSTEM v1.0
========================
Single source of truth for tier classification and Telegram output.

🚨 LOCKED IMPLEMENTATION: Do NOT modify thresholds without explicit approval.

TIERS (CANONICAL DEFINITIONS):
------------------------------
- EDGE (Tier A): Actionable bet now. All gates pass. Telegram: PLAY
- LEAN (Tier B): Directional value, one+ gate fails. Telegram: LIVE WATCH
- NEUTRAL (Tier C): No mispricing, market aligned. Telegram: NO PLAY

BLOCKED is a REASON CODE, not a tier:
- If EDGE is blocked by risk controls → downgrade to LEAN
- LEAN must ALWAYS produce a Telegram post (LIVE WATCH)

EDGE CALCULATION (Spread):
--------------------------
edge_pts = market_line - model_fair_line
Example: Jazz market +9.5, model fair +2.9 → edge = 6.6 pts

CONFIDENCE CALCULATION:
-----------------------
Confidence is NOT win probability. It's a QUALITY score based on stability.
Start at 100, subtract penalties for variance, instability, injury, etc.
If inputs missing → confidence = NULL (not 1%)
"""

from typing import Dict, List, Optional, Tuple, Any, Literal
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json


# =============================================================================
# LOCKED THRESHOLDS (DO NOT MODIFY WITHOUT APPROVAL)
# =============================================================================

class LockedThresholds:
    """Locked thresholds for tier classification — spread markets"""
    
    # EDGE (Tier A) - Must pass ALL
    EDGE_MIN_PTS: float = 6.0           # NBA spread edge minimum
    EDGE_MIN_WINPROB: float = 0.60      # 60% win probability
    EDGE_MIN_STABILITY: float = 70.0    # Stability score (S/A/B/C/D scale)
    
    # LEAN (Tier B) - Pass value, fail one gate
    LEAN_MIN_PTS: float = 2.5           # Minimum edge for LEAN consideration
    
    # Variance thresholds
    VAR_OK: float = 150.0               # Variance below this = no penalty
    VAR_BAD: float = 400.0              # Variance above this = max penalty
    
    # Stability thresholds
    STABILITY_MIN: float = 70.0         # Below this = penalty
    
    # Risk control penalties
    INJURY_UNCERTAINTY_PENALTY: float = 20.0
    MARKET_DISAGREEMENT_PENALTY: float = 10.0


# =============================================================================
# ENUMS
# =============================================================================

class Tier(str, Enum):
    """Canonical tiers — ONLY these three exist"""
    EDGE = "EDGE"       # Tier A — Actionable, PLAY
    LEAN = "LEAN"       # Tier B — Watch, LIVE WATCH
    NEUTRAL = "NEUTRAL" # Tier C — No play, market aligned


class TelegramPostType(str, Enum):
    """Telegram output types corresponding to tiers"""
    PLAY = "PLAY"             # For EDGE tier
    LIVE_WATCH = "LIVE_WATCH" # For LEAN tier
    NO_PLAY = "NO_PLAY"       # For NEUTRAL tier


class ReasonCode(str, Enum):
    """Reason codes for classification decisions"""
    # EDGE reasons
    ALL_GATES_PASS = "all_gates_pass"
    STRONG_EDGE = "strong_edge"
    HIGH_CONFIDENCE = "high_confidence"
    
    # Block/downgrade reasons (EDGE → LEAN)
    HIGH_VARIANCE = "high_variance"
    LOW_STABILITY = "low_stability"
    EV_NOT_PROVEN = "ev_not_proven"
    INJURY_UNCERTAINTY = "injury_uncertainty"
    LATE_SCRATCHES_RISK = "late_scratches_risk"
    INCOMPLETE_DATA = "incomplete_data"
    
    # LEAN reasons
    VALUE_DETECTED = "value_detected"
    ONE_GATE_FAILED = "one_gate_failed"
    MULTIPLE_GATES_FAILED = "multiple_gates_failed"
    
    # NEUTRAL reasons
    NO_MISPRICING = "no_mispricing"
    MARKET_ALIGNED = "market_aligned"
    EDGE_BELOW_THRESHOLD = "edge_below_threshold"
    
    # Confidence reasons
    MISSING_INPUTS = "missing_inputs"
    VARIANCE_PENALTY = "variance_penalty"
    STABILITY_PENALTY = "stability_penalty"


class SizingTag(str, Enum):
    """Bet sizing recommendations"""
    STANDARD = "standard"       # Full unit
    REDUCED = "reduced"         # ½ unit (high variance)
    SMALL = "small"             # ¼ unit (LEAN only)
    WAIT = "wait"               # Wait for better number


# =============================================================================
# CONFIDENCE CALCULATION
# =============================================================================

@dataclass
class ConfidenceResult:
    """
    Confidence calculation result
    
    🚨 CRITICAL: confidence_score MUST be null if inputs missing
                 Never default to 1%
    """
    confidence_score: Optional[int]     # 0-100, NULL if inputs missing
    confidence_label: str               # "High" / "Medium" / "Low" / "N/A"
    confidence_reason_codes: List[ReasonCode]
    confidence_inputs: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "confidence_score": self.confidence_score,
            "confidence_label": self.confidence_label,
            "confidence_reason_codes": [rc.value for rc in self.confidence_reason_codes],
            "confidence_inputs": self.confidence_inputs
        }


def calculate_confidence(
    variance: Optional[float],
    stability_score: Optional[float],
    injury_uncertainty: bool = False,
    market_disagreement: bool = False
) -> ConfidenceResult:
    """
    Calculate confidence score using penalty system
    
    🚨 RULE: If ANY input missing → return NULL, label "N/A"
    
    Formula:
        Start at 100, subtract penalties:
        - Variance penalty: up to 40 pts
        - Stability penalty: up to 40 pts
        - Injury uncertainty: 20 pts
        - Market disagreement: 10 pts
    """
    inputs = {
        "variance": variance,
        "stability_score": stability_score,
        "injury_uncertainty": injury_uncertainty,
        "market_disagreement": market_disagreement
    }
    reason_codes: List[ReasonCode] = []
    
    # Check for missing inputs — NEVER default to 1%
    if variance is None or stability_score is None:
        return ConfidenceResult(
            confidence_score=None,  # NOT 1%!
            confidence_label="N/A",
            confidence_reason_codes=[ReasonCode.MISSING_INPUTS],
            confidence_inputs=inputs
        )
    
    # Start at 100
    score = 100.0
    
    # Variance penalty (0-40 pts)
    if variance > LockedThresholds.VAR_OK:
        pen_var = min(40.0, (
            (variance - LockedThresholds.VAR_OK) / 
            (LockedThresholds.VAR_BAD - LockedThresholds.VAR_OK) * 40
        ))
        score -= pen_var
        if pen_var > 10:
            reason_codes.append(ReasonCode.VARIANCE_PENALTY)
    
    # Stability penalty (0-40 pts)
    if stability_score < LockedThresholds.STABILITY_MIN:
        pen_stab = min(40.0, (
            (LockedThresholds.STABILITY_MIN - stability_score) / 
            LockedThresholds.STABILITY_MIN * 40
        ))
        score -= pen_stab
        if pen_stab > 10:
            reason_codes.append(ReasonCode.STABILITY_PENALTY)
    
    # Injury uncertainty penalty (0 or 20)
    if injury_uncertainty:
        score -= LockedThresholds.INJURY_UNCERTAINTY_PENALTY
        reason_codes.append(ReasonCode.INJURY_UNCERTAINTY)
    
    # Market disagreement penalty (0 or 10)
    if market_disagreement:
        score -= LockedThresholds.MARKET_DISAGREEMENT_PENALTY
    
    # Clamp to 0-100
    final_score = max(0, min(100, int(round(score))))
    
    # Determine label
    if final_score >= 70:
        label = "High"
    elif final_score >= 50:
        label = "Medium"
    else:
        label = "Low"
    
    return ConfidenceResult(
        confidence_score=final_score,
        confidence_label=label,
        confidence_reason_codes=reason_codes,
        confidence_inputs=inputs
    )


# =============================================================================
# TIER CLASSIFICATION
# =============================================================================

@dataclass
class TierClassification:
    """Complete tier classification result"""
    
    # Core classification
    tier: Tier
    raw_tier: Tier                  # Before any downgrades
    telegram_post_type: TelegramPostType
    
    # Numeric inputs
    edge_pts: float
    win_prob: float
    market_line: float
    model_fair_line: float
    
    # Confidence
    confidence: ConfidenceResult
    
    # Gate results
    gates_passed: List[str]
    gates_failed: List[str]
    
    # Risk controls
    risk_blocked: bool
    risk_reason_codes: List[ReasonCode]
    
    # Sizing
    sizing_tag: SizingTag
    sizing_reason: str
    
    # Entry plan (for LEAN)
    entry_plan: Optional[Dict[str, Any]] = None
    
    # Metadata
    reason_codes: List[ReasonCode] = field(default_factory=list)
    state_reasons: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "tier": self.tier.value,
            "raw_tier": self.raw_tier.value,
            "telegram_post_type": self.telegram_post_type.value,
            "edge_pts": self.edge_pts,
            "win_prob": self.win_prob,
            "market_line": self.market_line,
            "model_fair_line": self.model_fair_line,
            "confidence": self.confidence.to_dict(),
            "gates_passed": self.gates_passed,
            "gates_failed": self.gates_failed,
            "risk_blocked": self.risk_blocked,
            "risk_reason_codes": [rc.value for rc in self.risk_reason_codes],
            "sizing_tag": self.sizing_tag.value,
            "sizing_reason": self.sizing_reason,
            "entry_plan": self.entry_plan,
            "reason_codes": [rc.value for rc in self.reason_codes],
            "state_reasons": self.state_reasons
        }


def classify_tier(
    market_line: float,
    model_fair_line: float,
    win_prob: float,
    variance: Optional[float] = None,
    stability_score: Optional[float] = None,
    injury_impact_ok: bool = True,
    volatility_extreme: bool = False,
    injury_uncertainty: bool = False,
    market_disagreement: bool = False
) -> TierClassification:
    """
    LOCKED TIER CLASSIFICATION
    
    Rules:
    1. EDGE: ALL gates pass
    2. LEAN: Value detected, one+ gate fails
    3. NEUTRAL: No significant mispricing
    
    If EDGE is blocked → downgrade to LEAN (never eliminate post)
    """
    # Calculate edge
    edge_pts = market_line - model_fair_line
    
    # Calculate confidence
    confidence = calculate_confidence(
        variance=variance,
        stability_score=stability_score,
        injury_uncertainty=injury_uncertainty,
        market_disagreement=market_disagreement
    )
    
    # Track gates
    gates_passed: List[str] = []
    gates_failed: List[str] = []
    risk_reason_codes: List[ReasonCode] = []
    state_reasons: List[str] = []
    
    # ===================
    # GATE EVALUATION
    # ===================
    
    # Gate 1: Edge points
    if edge_pts >= LockedThresholds.EDGE_MIN_PTS:
        gates_passed.append(f"Edge {edge_pts:.1f} pts >= {LockedThresholds.EDGE_MIN_PTS}")
    elif edge_pts >= LockedThresholds.LEAN_MIN_PTS:
        gates_failed.append(f"Edge {edge_pts:.1f} pts < {LockedThresholds.EDGE_MIN_PTS} (LEAN range)")
    else:
        gates_failed.append(f"Edge {edge_pts:.1f} pts < {LockedThresholds.LEAN_MIN_PTS} (below LEAN)")
    
    # Gate 2: Win probability
    if win_prob >= LockedThresholds.EDGE_MIN_WINPROB:
        gates_passed.append(f"Win prob {win_prob*100:.0f}% >= {LockedThresholds.EDGE_MIN_WINPROB*100:.0f}%")
    else:
        gates_failed.append(f"Win prob {win_prob*100:.0f}% < {LockedThresholds.EDGE_MIN_WINPROB*100:.0f}%")
    
    # Gate 3: Stability
    if stability_score is not None and stability_score >= LockedThresholds.EDGE_MIN_STABILITY:
        gates_passed.append(f"Stability {stability_score:.0f} >= {LockedThresholds.EDGE_MIN_STABILITY}")
    elif stability_score is not None:
        gates_failed.append(f"Stability {stability_score:.0f} < {LockedThresholds.EDGE_MIN_STABILITY}")
        risk_reason_codes.append(ReasonCode.LOW_STABILITY)
    else:
        gates_failed.append("Stability score unavailable")
        risk_reason_codes.append(ReasonCode.INCOMPLETE_DATA)
    
    # Gate 4: Injury impact
    if injury_impact_ok:
        gates_passed.append("Injury impact acceptable")
    else:
        gates_failed.append("Injury impact concern")
        risk_reason_codes.append(ReasonCode.INJURY_UNCERTAINTY)
    
    # Gate 5: Volatility
    if not volatility_extreme:
        gates_passed.append("Volatility not extreme")
    else:
        gates_failed.append("Extreme volatility")
        risk_reason_codes.append(ReasonCode.HIGH_VARIANCE)
    
    # ===================
    # TIER DETERMINATION
    # ===================
    
    reason_codes: List[ReasonCode] = []
    
    # Check for NEUTRAL first (no value)
    if edge_pts < LockedThresholds.LEAN_MIN_PTS:
        tier = Tier.NEUTRAL
        raw_tier = Tier.NEUTRAL
        telegram_post_type = TelegramPostType.NO_PLAY
        sizing_tag = SizingTag.WAIT
        sizing_reason = "No actionable edge"
        reason_codes.append(ReasonCode.NO_MISPRICING)
        state_reasons.append(f"Edge {edge_pts:.1f} pts below LEAN threshold ({LockedThresholds.LEAN_MIN_PTS})")
    
    # Check for EDGE (all gates pass)
    elif len(gates_failed) == 0:
        raw_tier = Tier.EDGE
        risk_blocked = len(risk_reason_codes) > 0
        
        if risk_blocked:
            # 🚨 CRITICAL: Downgrade to LEAN, don't eliminate
            tier = Tier.LEAN
            telegram_post_type = TelegramPostType.LIVE_WATCH
            reason_codes.append(ReasonCode.ONE_GATE_FAILED)
            state_reasons.append("EDGE downgraded to LEAN due to risk controls")
        else:
            tier = Tier.EDGE
            telegram_post_type = TelegramPostType.PLAY
            reason_codes.append(ReasonCode.ALL_GATES_PASS)
            state_reasons.append("All gates passed — actionable EDGE")
        
        # Sizing for EDGE
        if volatility_extreme:
            sizing_tag = SizingTag.REDUCED
            sizing_reason = "High variance → ½ unit"
        else:
            sizing_tag = SizingTag.STANDARD
            sizing_reason = "Standard sizing"
    
    # LEAN (value detected, one+ gate fails)
    else:
        tier = Tier.LEAN
        raw_tier = Tier.LEAN
        telegram_post_type = TelegramPostType.LIVE_WATCH
        sizing_tag = SizingTag.SMALL
        sizing_reason = "LEAN signal → small size or wait"
        
        if len(gates_failed) == 1:
            reason_codes.append(ReasonCode.ONE_GATE_FAILED)
        else:
            reason_codes.append(ReasonCode.MULTIPLE_GATES_FAILED)
        reason_codes.append(ReasonCode.VALUE_DETECTED)
        state_reasons.append(f"Value detected ({edge_pts:.1f} pts) but {len(gates_failed)} gate(s) failed")
    
    # Generate entry plan for LEAN
    entry_plan = None
    if tier == Tier.LEAN:
        entry_plan = generate_entry_plan(market_line, edge_pts)
    
    return TierClassification(
        tier=tier,
        raw_tier=raw_tier,
        telegram_post_type=telegram_post_type,
        edge_pts=edge_pts,
        win_prob=win_prob,
        market_line=market_line,
        model_fair_line=model_fair_line,
        confidence=confidence,
        gates_passed=gates_passed,
        gates_failed=gates_failed,
        risk_blocked=len(risk_reason_codes) > 0,
        risk_reason_codes=risk_reason_codes,
        sizing_tag=sizing_tag,
        sizing_reason=sizing_reason,
        entry_plan=entry_plan,
        reason_codes=reason_codes,
        state_reasons=state_reasons
    )


def generate_entry_plan(market_line: float, edge_pts: float) -> Dict[str, Any]:
    """
    Generate entry plan for LEAN signals
    
    🚨 LEAN must ALWAYS have entry thresholds, never "informational only"
    """
    return {
        "playable_at": market_line,                    # Current line is playable
        "strong_value_at": market_line + 1.0,          # +1 pt better is strong
        "invalidate_below": market_line - 1.0,         # Avoid if line gets worse
        "current_edge_pts": edge_pts,
        "instructions": f"Take {market_line:+.1f} or better. Strong value at {market_line + 1.0:+.1f}+. Avoid below {market_line - 1.0:+.1f}."
    }


# =============================================================================
# TELEGRAM MESSAGE FORMATTERS
# =============================================================================

def format_telegram_edge(
    classification: TierClassification,
    team: str,
    opponent: str,
    sport: str,
    sim_power: int = 100000,
    timestamp: Optional[datetime] = None,
    home_team: str = "",
    away_team: str = "",
    market_spread_home: float = 0.0
) -> str:
    """
    Format EDGE tier as PLAY message
    
    🚨 EDGE MUST include:
    - Pick (team + line)
    - SHARP SIDE explicitly stated (with team label)
    - Entry threshold
    - Model edge + win prob
    - Sizing tag
    - Timestamp + sim power
    
    🚨 LOCKED RULE: Always show Sharp Side as "team + spread"
    """
    from backend.core.model_spread_logic import calculate_spread_context
    
    ts = timestamp or datetime.now(timezone.utc)
    
    entry_threshold = f"Take {classification.market_line:+.1f} or better"
    best_line = classification.market_line + 0.5
    
    sizing_note = ""
    if classification.sizing_tag == SizingTag.REDUCED:
        sizing_note = "\nRisk: High variance → ½ unit"
    
    # Calculate sharp side with team labels
    sharp_side_display = f"{team} {classification.market_line:+.1f}"
    if home_team and away_team:
        spread_ctx = calculate_spread_context(
            home_team, away_team, market_spread_home, classification.model_fair_line
        )
        sharp_side_display = spread_ctx.sharp_side_display
    
    return f"""🟢 PLAY — {team} {classification.market_line:+.1f} ({sim_power//1000}K sims)

{sport.upper()} | {team} @ {opponent}

🎯 Sharp Side: {sharp_side_display}

Edge: {classification.edge_pts:+.1f} pts
Win Prob: {classification.win_prob*100:.0f}%
Confidence: {classification.confidence.confidence_label} ({classification.confidence.confidence_score}%)

Entry: {entry_threshold} (best ≥ {best_line:+.1f}){sizing_note}

⏰ {ts.strftime('%I:%M %p ET')} | Simulations: {sim_power:,}
"""


def format_telegram_lean(
    classification: TierClassification,
    team: str,
    opponent: str,
    sport: str,
    sim_power: int = 100000,
    timestamp: Optional[datetime] = None,
    home_team: str = "",
    away_team: str = "",
    market_spread_home: float = 0.0
) -> str:
    """
    Format LEAN tier as LIVE WATCH message
    
    🚨 LEAN MUST include:
    - What side you lean (Sharp Side explicitly!)
    - Exact numbers to wait for
    - What invalidates
    - Entry plan auto-generated
    
    🚨 LOCKED RULE: Always show Sharp Side as "team + spread"
    """
    from backend.core.model_spread_logic import calculate_spread_context
    
    ts = timestamp or datetime.now(timezone.utc)
    ep = classification.entry_plan or generate_entry_plan(
        classification.market_line, 
        classification.edge_pts
    )
    
    # Calculate sharp side with team labels
    sharp_side_display = f"{team} {classification.market_line:+.1f}"
    if home_team and away_team:
        spread_ctx = calculate_spread_context(
            home_team, away_team, market_spread_home, classification.model_fair_line
        )
        sharp_side_display = spread_ctx.sharp_side_display
    
    # Determine why it's not EDGE
    block_reasons = []
    for reason in classification.risk_reason_codes:
        if reason == ReasonCode.HIGH_VARIANCE:
            block_reasons.append("high variance")
        elif reason == ReasonCode.LOW_STABILITY:
            block_reasons.append("low stability")
        elif reason == ReasonCode.INJURY_UNCERTAINTY:
            block_reasons.append("injury uncertainty")
    
    reason_text = ", ".join(block_reasons) if block_reasons else "one or more gates failed"
    
    return f"""🟡 LIVE WATCH (LEAN) — {team} {classification.market_line:+.1f} ({sim_power//1000}K sims)

{sport.upper()} | {team} @ {opponent}

🎯 Sharp Side: {sharp_side_display}

Model shows value but {reason_text}.

Edge: {classification.edge_pts:+.1f} pts
Win Prob: {classification.win_prob*100:.0f}%

Entry Plan:
✅ Playable at: {ep['playable_at']:+.1f}+
🔥 Strong at: {ep['strong_value_at']:+.1f}+
❌ Avoid below: {ep['invalidate_below']:+.1f}

Size: small / wait for better number

⏰ {ts.strftime('%I:%M %p ET')} | Simulations: {sim_power:,}
"""


def format_telegram_neutral(
    team: str,
    opponent: str,
    sport: str
) -> str:
    """
    Format NEUTRAL tier as NO PLAY message
    """
    return f"""⚪ NO PLAY — Market aligned

{sport.upper()} | {team} @ {opponent}

No significant mispricing detected.
"""


def format_telegram_message(
    classification: TierClassification,
    team: str,
    opponent: str,
    sport: str,
    sim_power: int = 100000,
    timestamp: Optional[datetime] = None,
    home_team: str = "",
    away_team: str = "",
    market_spread_home: float = 0.0
) -> str:
    """
    Main entry point for formatting Telegram messages
    
    Routes to appropriate formatter based on tier.
    
    🚨 LOCKED: All PLAY and LIVE_WATCH outputs must include explicit Sharp Side
    """
    if classification.tier == Tier.EDGE:
        return format_telegram_edge(
            classification, team, opponent, sport, sim_power, timestamp,
            home_team, away_team, market_spread_home
        )
    elif classification.tier == Tier.LEAN:
        return format_telegram_lean(
            classification, team, opponent, sport, sim_power, timestamp,
            home_team, away_team, market_spread_home
        )
    else:
        return format_telegram_neutral(team, opponent, sport)


# =============================================================================
# SIMULATION SNAPSHOT SYSTEM
# =============================================================================

@dataclass
class SimulationSnapshot:
    """
    Immutable snapshot of simulation results
    
    🚨 CRITICAL: Refresh loads SAME snapshot_id
                 Only "Re-run" generates NEW snapshot
    """
    snapshot_id: str
    seed: int
    inputs_hash: str
    injury_inputs_hash: str
    market_line_at_snapshot: float
    n_sims: int
    timestamp: datetime
    
    # Results (frozen)
    edge_pts: float
    win_prob: float
    variance: float
    stability_score: float
    
    # Classification at snapshot time
    tier: Tier
    confidence_score: Optional[int]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "seed": self.seed,
            "inputs_hash": self.inputs_hash,
            "injury_inputs_hash": self.injury_inputs_hash,
            "market_line_at_snapshot": self.market_line_at_snapshot,
            "n_sims": self.n_sims,
            "timestamp": self.timestamp.isoformat(),
            "edge_pts": self.edge_pts,
            "win_prob": self.win_prob,
            "variance": self.variance,
            "stability_score": self.stability_score,
            "tier": self.tier.value,
            "confidence_score": self.confidence_score
        }


def create_snapshot(
    seed: int,
    inputs: Dict[str, Any],
    injury_inputs: Dict[str, Any],
    market_line: float,
    n_sims: int,
    results: Dict[str, Any],
    classification: TierClassification
) -> SimulationSnapshot:
    """
    Create immutable simulation snapshot
    
    Call this after simulation completes.
    Store in DB for later retrieval.
    """
    # Compute hashes
    inputs_hash = hashlib.sha256(
        json.dumps(inputs, sort_keys=True, default=str).encode()
    ).hexdigest()[:16]
    
    injury_hash = hashlib.sha256(
        json.dumps(injury_inputs, sort_keys=True, default=str).encode()
    ).hexdigest()[:16]
    
    # Generate snapshot ID
    snapshot_id = f"snap_{inputs_hash}_{int(datetime.now(timezone.utc).timestamp())}"
    
    return SimulationSnapshot(
        snapshot_id=snapshot_id,
        seed=seed,
        inputs_hash=inputs_hash,
        injury_inputs_hash=injury_hash,
        market_line_at_snapshot=market_line,
        n_sims=n_sims,
        timestamp=datetime.now(timezone.utc),
        edge_pts=classification.edge_pts,
        win_prob=classification.win_prob,
        variance=results.get("variance", 0),
        stability_score=results.get("stability_score", 0),
        tier=classification.tier,
        confidence_score=classification.confidence.confidence_score
    )


@dataclass  
class SnapshotComparison:
    """
    Compare current market to snapshot
    
    Used to detect:
    - Line movement since snapshot
    - Injury status changes
    """
    snapshot_id: str
    market_line_at_snapshot: float
    current_market_line: float
    line_moved: float
    injury_hash_changed: bool
    snapshot_still_valid: bool
    invalidation_reason: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "market_line_at_snapshot": self.market_line_at_snapshot,
            "current_market_line": self.current_market_line,
            "line_moved": self.line_moved,
            "injury_hash_changed": self.injury_hash_changed,
            "snapshot_still_valid": self.snapshot_still_valid,
            "invalidation_reason": self.invalidation_reason
        }


def compare_snapshot(
    snapshot: SimulationSnapshot,
    current_market_line: float,
    current_injury_hash: str,
    max_line_movement: float = 2.0
) -> SnapshotComparison:
    """
    Compare current state to snapshot
    
    Returns whether snapshot is still valid or needs re-run
    """
    line_moved = current_market_line - snapshot.market_line_at_snapshot
    injury_changed = current_injury_hash != snapshot.injury_inputs_hash
    
    # Determine validity
    still_valid = True
    invalidation_reason = None
    
    if abs(line_moved) > max_line_movement:
        still_valid = False
        invalidation_reason = f"Line moved {line_moved:+.1f} pts (threshold: {max_line_movement})"
    
    if injury_changed:
        still_valid = False
        invalidation_reason = "Injury inputs changed"
    
    return SnapshotComparison(
        snapshot_id=snapshot.snapshot_id,
        market_line_at_snapshot=snapshot.market_line_at_snapshot,
        current_market_line=current_market_line,
        line_moved=line_moved,
        injury_hash_changed=injury_changed,
        snapshot_still_valid=still_valid,
        invalidation_reason=invalidation_reason
    )


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_telegram_post_should_generate(tier: Tier) -> bool:
    """
    Determine if tier should generate a Telegram post
    
    🚨 RULE: EDGE and LEAN both generate posts
             Only NEUTRAL is silent
    """
    return tier in [Tier.EDGE, Tier.LEAN]


def downgrade_edge_to_lean(
    classification: TierClassification,
    downgrade_reason: ReasonCode
) -> TierClassification:
    """
    Downgrade an EDGE classification to LEAN
    
    🚨 CRITICAL: Never eliminate the post, always downgrade
    """
    if classification.tier != Tier.EDGE:
        return classification
    
    # Create entry plan
    entry_plan = generate_entry_plan(
        classification.market_line,
        classification.edge_pts
    )
    
    return TierClassification(
        tier=Tier.LEAN,
        raw_tier=classification.raw_tier,
        telegram_post_type=TelegramPostType.LIVE_WATCH,
        edge_pts=classification.edge_pts,
        win_prob=classification.win_prob,
        market_line=classification.market_line,
        model_fair_line=classification.model_fair_line,
        confidence=classification.confidence,
        gates_passed=classification.gates_passed,
        gates_failed=classification.gates_failed + [f"Blocked: {downgrade_reason.value}"],
        risk_blocked=True,
        risk_reason_codes=classification.risk_reason_codes + [downgrade_reason],
        sizing_tag=SizingTag.SMALL,
        sizing_reason="Downgraded from EDGE → small size",
        entry_plan=entry_plan,
        reason_codes=classification.reason_codes + [downgrade_reason],
        state_reasons=classification.state_reasons + [f"EDGE downgraded to LEAN: {downgrade_reason.value}"]
    )
