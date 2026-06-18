"""
Canonical Data Contract Enforcer
Ensures every simulation response includes ALL required fields before reaching frontend

This prevents "partially hydrated" objects that cause integrity violations.

🔒 LOCKED: Model Direction uses model_direction_canonical.py (single source of truth)
"""
import hashlib
import json
from typing import Dict, Any
from datetime import datetime, timezone
import logging

# Import canonical model direction module (SINGLE SOURCE OF TRUTH)
from core.model_direction_canonical import (
    calculate_model_direction,
    format_display_line,
    to_legacy_format
)

logger = logging.getLogger(__name__)


def generate_snapshot_hash(simulation: Dict[str, Any]) -> str:
    """
    Generate deterministic snapshot hash from critical simulation fields
    
    Hash includes:
    - event_id
    - iterations
    - created_at timestamp
    - home/away teams
    - median_total
    - win probabilities
    """
    # Extract canonical fields for hash
    hash_input = {
        "event_id": simulation.get("event_id"),
        "iterations": simulation.get("iterations"),
        "created_at": simulation.get("created_at"),
        "team_a": simulation.get("team_a"),
        "team_b": simulation.get("team_b"),
        "median_total": simulation.get("median_total"),
        "team_a_win_probability": simulation.get("team_a_win_probability"),
        "team_b_win_probability": simulation.get("team_b_win_probability"),
    }
    
    # Create deterministic JSON string
    hash_string = json.dumps(hash_input, sort_keys=True)
    
    # Generate SHA-256 hash
    return hashlib.sha256(hash_string.encode()).hexdigest()[:16]


def determine_selection_id(simulation: Dict[str, Any]) -> str:
    """
    Determine canonical selection_id based on sharp analysis
    
    Returns:
    - "home" if model favors home team
    - "away" if model favors away team  
    - "no_selection" if no edge (NO_PLAY state)
    """
    # Check pick state
    pick_state = simulation.get("pick_state", "NO_PLAY")
    
    if pick_state == "NO_PLAY":
        return "no_selection"
    
    # Check spread analysis
    spread_analysis = simulation.get("sharp_analysis", {}).get("spread", {})
    sharp_side = spread_analysis.get("sharp_side")
    
    if sharp_side:
        # sharp_side is team name - map to home/away
        home_team = simulation.get("team_a")
        away_team = simulation.get("team_b")
        
        if sharp_side == home_team:
            return "home"
        elif sharp_side == away_team:
            return "away"
    
    # Fallback: use win probabilities
    home_win_prob = simulation.get("team_a_win_probability", 0.5)
    away_win_prob = simulation.get("team_b_win_probability", 0.5)
    
    if home_win_prob > away_win_prob:
        return "home"
    elif away_win_prob > home_win_prob:
        return "away"
    
    return "no_selection"


def _normalize_spread_contract(simulation: Dict[str, Any]) -> None:
    """Fail closed when spread binding is inconsistent or missing.

    The spread summary must never present an edge unless a canonical selection
    is bound and both backend contract surfaces agree on that selection.
    """
    sharp_analysis = simulation.get("sharp_analysis") or {}
    spread_analysis = sharp_analysis.get("spread") or {}
    market_views = simulation.get("market_views") or {}
    spread_view = market_views.get("spread") or {}

    if not isinstance(spread_analysis, dict) or not isinstance(spread_view, dict):
        return

    has_edge = bool(spread_analysis.get("has_edge"))
    sharp_team = spread_analysis.get("sharp_team")
    sharp_selection = spread_analysis.get("sharp_selection")
    model_pref = spread_view.get("model_preference_selection_id")
    model_dir = spread_view.get("model_direction_selection_id")
    edge_class = str(spread_view.get("edge_class") or "").upper()

    binding_missing = has_edge and (
        not sharp_team
        or not sharp_selection
        or str(sharp_selection).upper() == "NO PLAY"
        or model_pref in {None, "NO_EDGE", "INVALID"}
        or model_dir in {None, "NO_EDGE", "INVALID"}
    )

    aligned_with_edge = edge_class == "MARKET_ALIGNED" and has_edge

    if aligned_with_edge:
        binding_missing = True

    if not binding_missing:
        return

    # Spread binding is ambiguous or missing: fail closed.
    spread_analysis["has_edge"] = False
    spread_analysis["sharp_selection"] = "NO PLAY"
    spread_analysis["sharp_side"] = "NO PLAY"
    spread_analysis["sharp_team"] = None
    spread_analysis["sharp_line"] = None
    spread_analysis["sharp_action"] = "NO_SHARP_PLAY"
    spread_analysis["sharp_side_display"] = "NO PLAY"
    spread_analysis["recommended_bet"] = "NO PLAY"
    spread_analysis["reasoning"] = "BLOCKED: canonical spread binding missing"
    spread_analysis["validator_status"] = {
        "passed": False,
        "errors": ["SPREAD_CANONICAL_BINDING_MISSING"],
        "warnings": [],
        "details": {
            "model_preference_selection_id": model_pref,
            "model_direction_selection_id": model_dir,
            "sharp_team": sharp_team,
            "sharp_selection": sharp_selection,
        },
    }

    spread_view["edge_class"] = "INVALID"
    spread_view["ui_render_mode"] = "SAFE"
    spread_view["model_preference_selection_id"] = "NO_EDGE"
    spread_view["model_direction_selection_id"] = "NO_EDGE"
    spread_view["integrity_status"] = {
        "status": "invalid",
        "is_valid": False,
        "errors": list(set((spread_view.get("integrity_status", {}) or {}).get("errors", []) + ["SPREAD_CANONICAL_BINDING_MISSING"])),
    }

    simulation["sharp_analysis"] = sharp_analysis
    simulation["market_views"] = market_views
    simulation.setdefault("integrity_warnings", [])
    simulation["integrity_warnings"].append("SPREAD_CANONICAL_BINDING_MISSING")


def enforce_canonical_contract(simulation: Dict[str, Any]) -> Dict[str, Any]:
    """
    🔒 CANONICAL CONTRACT ENFORCER
    
    Ensures simulation object includes ALL required fields:
    1. snapshot_hash (integrity anchor)
    2. selection_id (pick direction: home/away/no_selection)
    3. market_settlement (FULL_GAME/FIRST_HALF/etc)
    4. model_direction (LOCKED to same selection as selection_id - prevents UI mismatch bug)
    5. Validates probability sums
    
    This prevents "simulation-lite" objects from reaching the UI.
    """
    # 1. Generate snapshot_hash if missing
    if not simulation.get("snapshot_hash"):
        snapshot_hash = generate_snapshot_hash(simulation)
        simulation["snapshot_hash"] = snapshot_hash
        logger.info(f"✅ Generated snapshot_hash: {snapshot_hash}")
    
    # 2. Determine selection_id if missing
    if not simulation.get("selection_id"):
        selection_id = determine_selection_id(simulation)
        simulation["selection_id"] = selection_id
        logger.info(f"✅ Set selection_id: {selection_id}")
    
    # 2b. 🔒 CALCULATE MODEL DIRECTION (CANONICAL - Single Source of Truth)
    # Uses model_direction_canonical.py to ensure Model Direction and Model Preference
    # are ALWAYS identical - prevents team inversion bug
    if not simulation.get("model_direction"):
        home_team = simulation.get("team_a") or simulation.get("home_team")
        away_team = simulation.get("team_b") or simulation.get("away_team")
        
        # Get spread analysis for market/fair lines
        spread_analysis = simulation.get("sharp_analysis", {}).get("spread", {})
        market_spread_home = spread_analysis.get("market_spread_home", 0.0)
        fair_spread_home = spread_analysis.get("fair_spread_home", 0.0)
        
        # Only calculate if we have valid spread data
        if market_spread_home != 0.0 or fair_spread_home != 0.0:
            try:
                if not home_team or not away_team:
                    raise ValueError("home_team and away_team required")
                # Calculate canonical direction (SINGLE SOURCE OF TRUTH)
                direction_result = calculate_model_direction(
                    home_team=home_team,
                    away_team=away_team,
                    market_spread_home=market_spread_home,
                    fair_spread_home=fair_spread_home
                )
                
                # Convert to legacy format for backward compatibility
                simulation["model_direction"] = to_legacy_format(
                    direction_result,
                    home_team=home_team,
                    away_team=away_team
                )
                
                logger.info(
                    f"✅ Set model_direction (canonical): {direction_result.preferred_team_id} "
                    f"{direction_result.preferred_market_line:+.1f} (edge: {direction_result.edge_pts:+.1f} pts, "
                    f"label: {direction_result.direction_label.value})"
                )
            except Exception as e:
                logger.error(f"❌ Failed to calculate canonical model_direction: {e}")
                # Fallback to no_selection
                simulation["model_direction"] = {
                    "selection_id": "no_selection",
                    "team": None,
                    "line": None,
                    "display": "No Selection",
                    "locked_to_preference": True
                }
        else:
            # No spread data - fallback
            simulation["model_direction"] = {
                "selection_id": simulation.get("selection_id", "no_selection"),
                "team": None,
                "line": None,
                "display": "No Selection",
                "locked_to_preference": True
            }

    # 2c. 🔒 ENFORCE SPREAD SIGN BINDING (fail closed on inconsistent spread state)
    _normalize_spread_contract(simulation)
    
    # 3. Set market_settlement if missing
    if not simulation.get("market_settlement"):
        # Check if period simulation (1H, 2H, etc)
        period = simulation.get("period")
        
        if period == "1H":
            market_settlement = "FIRST_HALF"
        elif period == "2H":
            market_settlement = "SECOND_HALF"
        elif period in ["Q1", "Q2", "Q3", "Q4"]:
            market_settlement = f"QUARTER_{period[1]}"
        else:
            market_settlement = "FULL_GAME"
        
        simulation["market_settlement"] = market_settlement
        logger.info(f"✅ Set market_settlement: {market_settlement}")
    
    # 4. Validate probability sums
    home_prob = simulation.get("team_a_win_probability", 0)
    away_prob = simulation.get("team_b_win_probability", 0)
    push_prob = simulation.get("push_probability", 0)
    
    prob_sum = home_prob + away_prob + push_prob
    
    if abs(prob_sum - 1.0) > 0.01:
        logger.warning(
            f"⚠️ Probability sum mismatch: {prob_sum:.4f} "
            f"(home={home_prob:.4f}, away={away_prob:.4f}, push={push_prob:.4f})"
        )
        simulation["integrity_warnings"] = simulation.get("integrity_warnings", [])
        simulation["integrity_warnings"].append(f"PROBABILITY_SUM_MISMATCH: {prob_sum:.4f}")
    
    # 5. Add contract_version for future migrations
    simulation["contract_version"] = "v1.0"
    simulation["contract_enforced_at"] = datetime.now(timezone.utc).isoformat()
    
    return simulation


def validate_canonical_contract(simulation: Dict[str, Any]) -> tuple[bool, list[str]]:
    """
    Validate that simulation meets canonical contract
    
    Returns:
        (is_valid, errors)
    """
    errors = []
    
    # Required fields
    required_fields = [
        "snapshot_hash",
        "selection_id",
        "market_settlement",
        "event_id",
        "team_a",
        "team_b",
        "team_a_win_probability",
        "team_b_win_probability",
    ]
    
    for field in required_fields:
        if field not in simulation or simulation[field] is None:
            errors.append(f"MISSING_FIELD: {field}")
    
    # Validate probability bounds
    for prob_field in ["team_a_win_probability", "team_b_win_probability", "push_probability"]:
        if prob_field in simulation:
            prob = simulation[prob_field]
            if not (0 <= prob <= 1):
                errors.append(f"INVALID_PROBABILITY: {prob_field}={prob}")
    
    is_valid = len(errors) == 0
    
    if not is_valid:
        logger.error(f"❌ Canonical contract validation FAILED: {errors}")
    
    return is_valid, errors
