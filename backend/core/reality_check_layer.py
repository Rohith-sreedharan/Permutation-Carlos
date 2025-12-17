"""
Reality Check Layer (RCL) - Total Projection Sanity System
Prevents inflated/deflated totals that don't pass reality checks

Module: Reflexive Calibration + Reality Check Layer
Scope: Fix inflated totals like 153 vs 145.5 when game reality doesn't support it

Three-layer guardrail system:
1. Historical RCL - Compare against league historical norms (±2σ)
2. Live Pace Guardrail - Check current game pace compatibility
3. Per-Team Pace Guardrail - Verify each team's required pace is realistic
"""
import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timezone
from db.mongo import db
import numpy as np

logger = logging.getLogger(__name__)


# ===== CONFIGURATION =====
MAX_SIGMA = 2.0  # Maximum allowed standard deviations from historical mean
MIN_PPM_FOR_MODEL = 2.0  # Minimum points per minute for model credibility
MAX_DELTA_FROM_PACE = 15.0  # Max allowed difference between model and live pace projection
PER_TEAM_PACE_THRESHOLD = 3.5  # Maximum realistic points per minute per team (NBA record ~3.0)


# ===== LEAGUE HISTORICAL STATS =====

def get_league_total_stats(league_code: str) -> Optional[Dict[str, Any]]:
    """
    Get historical total statistics for a league
    
    Args:
        league_code: League identifier (NCAAB, NBA, etc.)
    
    Returns:
        Dict with mean_total, std_total, or None if no data
    """
    try:
        stats = db["league_total_stats"].find_one({"league_code": league_code})
        if stats:
            return {
                "mean_total": stats.get("mean_total"),
                "std_total": stats.get("std_total"),
                "sample_size": stats.get("sample_size", 0),
                "min_total": stats.get("min_total"),
                "max_total": stats.get("max_total"),
            }
        return None
    except Exception as e:
        logger.error(f"Failed to fetch league stats for {league_code}: {e}")
        return None


def update_league_total_stats(league_code: str, totals_data: list) -> None:
    """
    Update historical total statistics for a league
    
    Args:
        league_code: League identifier
        totals_data: List of historical game totals
    """
    if not totals_data:
        logger.warning(f"No data to update stats for {league_code}")
        return
    
    totals_array = np.array(totals_data)
    
    stats = {
        "league_code": league_code,
        "sample_size": len(totals_data),
        "mean_total": float(np.mean(totals_array)),
        "std_total": float(np.std(totals_array)),
        "min_total": float(np.min(totals_array)),
        "max_total": float(np.max(totals_array)),
        "p25_total": float(np.percentile(totals_array, 25)),
        "p50_total": float(np.percentile(totals_array, 50)),
        "p75_total": float(np.percentile(totals_array, 75)),
        "updated_at": datetime.now(timezone.utc)
    }
    
    try:
        db["league_total_stats"].update_one(
            {"league_code": league_code},
            {"$set": stats},
            upsert=True
        )
        logger.info(f"Updated league stats for {league_code}: mean={stats['mean_total']:.1f}, std={stats['std_total']:.1f}")
    except Exception as e:
        logger.error(f"Failed to update league stats for {league_code}: {e}")


# ===== LAYER 1: HISTORICAL RCL =====

def apply_historical_rcl(
    model_total: float,
    league_code: str,
    sim_audit_id: str
) -> Tuple[float, bool, Dict[str, Any]]:
    """
    Apply historical reality check - clamp outliers beyond ±2σ
    
    Args:
        model_total: Raw total from simulation
        league_code: League identifier
        sim_audit_id: Audit record ID for logging
    
    Returns:
        (clamped_total, passed, details_dict)
    """
    stats = get_league_total_stats(league_code)
    
    if not stats:
        logger.warning(f"No historical data for {league_code}, allowing projection through")
        details: Dict[str, Any] = {
            "rcl_reason": "NO_HISTORICAL_DATA",
            "rcl_passed": True,
            "historical_mean": None,
            "historical_std": None,
            "historical_z_score": None
        }
        update_sim_audit(sim_audit_id, details)
        return model_total, True, details
    
    mean_total = stats["mean_total"]
    std_total = stats["std_total"]
    
    # Calculate z-score
    if std_total > 0:
        z_score = (model_total - mean_total) / std_total
    else:
        z_score = 0.0
    
    # Check if within acceptable range
    if abs(z_score) <= MAX_SIGMA:
        # PASSED - projection is reasonable
        details: Dict[str, Any] = {
            "rcl_reason": "RCL_OK",
            "rcl_passed": True,
            "historical_mean": mean_total,
            "historical_std": std_total,
            "historical_z_score": round(z_score, 2)
        }
        update_sim_audit(sim_audit_id, details)
        logger.info(f"✅ Historical RCL PASSED: {model_total:.1f} (z={z_score:.2f}, league={league_code})")
        return model_total, True, details
    
    # FAILED - clamp to edge of acceptable range
    direction = 1 if z_score > 0 else -1
    clamped_total = mean_total + (MAX_SIGMA * std_total * direction)
    
    details: Dict[str, Any] = {
        "rcl_reason": f"HISTORICAL_OUTLIER_Z={z_score:.2f}",
        "rcl_passed": False,
        "historical_mean": mean_total,
        "historical_std": std_total,
        "historical_z_score": round(z_score, 2)
    }
    update_sim_audit(sim_audit_id, details)
    
    logger.warning(
        f"🚫 Historical RCL FAILED: {model_total:.1f} → {clamped_total:.1f} "
        f"(z={z_score:.2f}, max=±{MAX_SIGMA}, league={league_code})"
    )
    
    return clamped_total, False, details


# ===== LAYER 2: LIVE PACE GUARDRAIL =====

def compute_live_pace_projection(
    current_total_points: float,
    elapsed_minutes: float,
    regulation_minutes: float
) -> Optional[Tuple[float, float]]:
    """
    Compute final score projection based on current pace
    
    Args:
        current_total_points: Combined score so far
        elapsed_minutes: Game time elapsed
        regulation_minutes: Total regulation time (40 or 48)
    
    Returns:
        (projected_final, points_per_minute) or None if too early
    """
    if elapsed_minutes <= 0:
        return None
    
    points_per_min = current_total_points / elapsed_minutes
    projected_final = points_per_min * regulation_minutes
    
    return projected_final, points_per_min


def apply_live_pace_guardrail(
    model_total: float,
    current_total_points: Optional[float],
    elapsed_minutes: Optional[float],
    regulation_minutes: float,
    sim_audit_id: str
) -> Tuple[float, bool, Dict[str, Any]]:
    """
    Apply live pace guardrail - check if current pace supports projection
    
    Args:
        model_total: Total from previous RCL stage
        current_total_points: Current combined score (None if pre-game)
        elapsed_minutes: Game time elapsed (None if pre-game)
        regulation_minutes: Total regulation time
        sim_audit_id: Audit record ID
    
    Returns:
        (adjusted_total, passed, details_dict)
    """
    # Skip if pre-game
    if current_total_points is None or elapsed_minutes is None:
        details: Dict[str, Any] = {
            "live_pace_projection": None,
            "live_pace_ppm": None,
            "current_total_points": None,
            "elapsed_minutes": None
        }
        return model_total, True, details
    
    # Too early in game to judge pace
    if elapsed_minutes < 5.0:
        details: Dict[str, Any] = {
            "live_pace_projection": None,
            "live_pace_ppm": None,
            "current_total_points": current_total_points,
            "elapsed_minutes": elapsed_minutes
        }
        return model_total, True, details
    
    pace_result = compute_live_pace_projection(
        current_total_points, elapsed_minutes, regulation_minutes
    )
    
    if not pace_result:
        return model_total, True, {}
    
    projected_final, ppm = pace_result
    
    details: Dict[str, Any] = {
        "live_pace_projection": round(projected_final, 2),
        "live_pace_ppm": round(ppm, 2),
        "current_total_points": current_total_points,
        "elapsed_minutes": elapsed_minutes
    }
    
    # Check if pace is too slow for model projection
    if ppm < MIN_PPM_FOR_MODEL and (model_total - projected_final) > MAX_DELTA_FROM_PACE:
        # FAILED - pace is way too slow
        details["rcl_reason"] = f"LIVE_PACE_TOO_SLOW_PPM={ppm:.2f}"
        details["rcl_passed"] = False
        update_sim_audit(sim_audit_id, details)
        
        logger.warning(
            f"🚫 Live Pace Guardrail FAILED: Model={model_total:.1f}, "
            f"Pace projection={projected_final:.1f} (PPM={ppm:.2f})"
        )
        
        return projected_final, False, details
    
    # PASSED
    logger.info(f"✅ Live Pace Guardrail PASSED: PPM={ppm:.2f}, projection={projected_final:.1f}")
    return model_total, True, details


# ===== LAYER 3: PER-TEAM PACE GUARDRAIL =====

def apply_per_team_pace_guardrail(
    model_total: float,
    current_total_points: Optional[float],
    elapsed_minutes: Optional[float],
    regulation_minutes: float,
    sim_audit_id: str
) -> Tuple[float, bool, Dict[str, Any]]:
    """
    Apply per-team pace guardrail - check if EACH team's required pace is realistic
    
    This is the critical missing check: prevents totals requiring both teams to
    score at historically impossible rates simultaneously.
    
    Args:
        model_total: Total from previous RCL stage
        current_total_points: Current combined score (None if pre-game)
        elapsed_minutes: Game time elapsed (None if pre-game)
        regulation_minutes: Total regulation time
        sim_audit_id: Audit record ID
    
    Returns:
        (adjusted_total, passed, details_dict)
    """
    # Skip if pre-game or too early
    if current_total_points is None or elapsed_minutes is None:
        details: Dict[str, Any] = {
            "per_team_pace_needed": None,
            "pace_guardrail_status": "not_applicable"
        }
        return model_total, True, details
    
    if elapsed_minutes < 5.0:
        details: Dict[str, Any] = {
            "per_team_pace_needed": None,
            "pace_guardrail_status": "too_early"
        }
        return model_total, True, details
    
    # Calculate remaining time
    minutes_remaining = regulation_minutes - elapsed_minutes
    
    if minutes_remaining <= 0:
        # Game over or in OT
        details: Dict[str, Any] = {
            "per_team_pace_needed": None,
            "pace_guardrail_status": "game_complete"
        }
        return model_total, True, details
    
    # Required points to reach model projection
    points_needed = model_total - current_total_points
    
    if points_needed <= 0:
        # Already pacing ahead of projection → safe
        details: Dict[str, Any] = {
            "per_team_pace_needed": 0.0,
            "pace_guardrail_status": "passed"
        }
        update_sim_audit(sim_audit_id, details)
        logger.info("✅ Per-Team Pace Guardrail PASSED: already ahead of projection")
        return model_total, True, details
    
    # Per-team required pace (divide by 2 teams)
    per_team_pace_needed = points_needed / minutes_remaining / 2.0
    
    details: Dict[str, Any] = {
        "per_team_pace_needed": round(per_team_pace_needed, 2),
        "pace_guardrail_status": None  # Set below
    }
    
    # Check against institutional threshold
    if per_team_pace_needed > PER_TEAM_PACE_THRESHOLD:
        # FAILED - unrealistic pace required
        details["pace_guardrail_status"] = "failed_unrealistic"
        details["rcl_reason"] = f"PER_TEAM_PACE_UNREALISTIC={per_team_pace_needed:.2f}"
        details["rcl_passed"] = False
        update_sim_audit(sim_audit_id, details)
        
        logger.warning(
            f"🚫 Per-Team Pace Guardrail FAILED: Each team needs {per_team_pace_needed:.2f} pts/min "
            f"for next {minutes_remaining:.1f} min (threshold={PER_TEAM_PACE_THRESHOLD})"
        )
        
        return model_total, False, details
    
    # PASSED
    details["pace_guardrail_status"] = "passed"
    update_sim_audit(sim_audit_id, details)
    logger.info(
        f"✅ Per-Team Pace Guardrail PASSED: {per_team_pace_needed:.2f} pts/min per team "
        f"(threshold={PER_TEAM_PACE_THRESHOLD})"
    )
    
    return model_total, True, details


# ===== MASTER RCL FLOW =====

def get_public_total_projection(
    sim_stats: Dict[str, Any],
    league_code: str,
    live_context: Optional[Dict[str, Any]],
    simulation_id: str,
    event_id: str,
    regulation_minutes: float = 40.0
) -> Dict[str, Any]:
    """
    Master RCL flow - apply all three guardrail layers
    
    Args:
        sim_stats: Simulation statistics with median_total, etc.
        league_code: League identifier (NCAAB, NBA, etc.)
        live_context: Optional live game context {current_total_points, elapsed_minutes}
        simulation_id: Simulation ID for linking
        event_id: Event ID
        regulation_minutes: Total regulation time (40 for college, 48 for NBA)
    
    Returns:
        Dict with model_total, rcl_ok, rcl_reason, audit details
    """
    # Create audit record
    sim_audit_id = f"audit_{event_id}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    
    # Extract raw model total
    raw_total = sim_stats.get("median_total", sim_stats.get("mean_total", 0))
    
    if raw_total == 0:
        raise ValueError("Invalid sim_stats: no median_total or mean_total")
    
    # Initialize audit record
    audit_record = {
        "sim_audit_id": sim_audit_id,
        "simulation_id": simulation_id,
        "event_id": event_id,
        "raw_total": raw_total,
        "vegas_total": sim_stats.get("total_line", 0),
        "league_code": league_code,
        "regulation_minutes": regulation_minutes,
        "created_at": datetime.now(timezone.utc)
    }
    
    # Insert initial record
    try:
        db["sim_audit"].insert_one(audit_record.copy())
    except Exception as e:
        logger.error(f"Failed to create sim_audit record: {e}")
    
    # LAYER 1: Historical RCL
    total_after_hist, hist_ok, hist_details = apply_historical_rcl(
        raw_total, league_code, sim_audit_id
    )
    
    # LAYER 2: Live Pace Guardrail
    if live_context:
        total_after_live, live_ok, live_details = apply_live_pace_guardrail(
            total_after_hist,
            live_context.get("current_total_points"),
            live_context.get("elapsed_minutes"),
            regulation_minutes,
            sim_audit_id
        )
    else:
        total_after_live, live_ok, live_details = total_after_hist, True, {}
    
    # LAYER 3: Per-Team Pace Guardrail
    if live_context:
        total_final, perteam_ok, perteam_details = apply_per_team_pace_guardrail(
            total_after_live,
            live_context.get("current_total_points"),
            live_context.get("elapsed_minutes"),
            regulation_minutes,
            sim_audit_id
        )
    else:
        total_final, perteam_ok, perteam_details = total_after_live, True, {}
    
    # Combined RCL result
    rcl_ok = hist_ok and live_ok and perteam_ok
    
    # Determine final reason
    if not rcl_ok:
        if not hist_ok:
            rcl_reason = hist_details.get("rcl_reason", "HISTORICAL_OUTLIER")
        elif not live_ok:
            rcl_reason = live_details.get("rcl_reason", "LIVE_PACE_TOO_SLOW")
        elif not perteam_ok:
            rcl_reason = perteam_details.get("rcl_reason", "PER_TEAM_PACE_UNREALISTIC")
        else:
            rcl_reason = "RCL_FAILED"
    else:
        rcl_reason = "RCL_OK"
    
    # Update final audit record
    final_update = {
        "rcl_total": total_final,
        "rcl_passed": rcl_ok,
        "rcl_reason": rcl_reason,
        "edge_eligible": rcl_ok,
        "confidence_adjustment": None if rcl_ok else "DOWNGRADE_2_TIERS"
    }
    update_sim_audit(sim_audit_id, final_update)
    
    logger.info(
        f"{'✅' if rcl_ok else '🚫'} RCL COMPLETE: "
        f"{raw_total:.1f} → {total_final:.1f} | {rcl_reason}"
    )
    
    return {
        "model_total": round(total_final, 2),
        "raw_total": round(raw_total, 2),
        "rcl_ok": rcl_ok,
        "rcl_reason": rcl_reason,
        "sim_audit_id": sim_audit_id,
        "edge_eligible": rcl_ok,
        "confidence_adjustment": None if rcl_ok else "DOWNGRADE_2_TIERS",
        **hist_details,
        **live_details,
        **perteam_details
    }


# ===== DATABASE HELPERS =====

def update_sim_audit(sim_audit_id: str, update_fields: Dict[str, Any]) -> None:
    """
    Update sim_audit record with new fields
    
    Args:
        sim_audit_id: Audit record ID
        update_fields: Fields to update
    """
    try:
        db["sim_audit"].update_one(
            {"sim_audit_id": sim_audit_id},
            {"$set": update_fields}
        )
    except Exception as e:
        logger.error(f"Failed to update sim_audit {sim_audit_id}: {e}")


def get_sim_audit(sim_audit_id: str) -> Optional[Dict[str, Any]]:
    """Get sim_audit record by ID"""
    try:
        return db["sim_audit"].find_one({"sim_audit_id": sim_audit_id})
    except Exception as e:
        logger.error(f"Failed to fetch sim_audit {sim_audit_id}: {e}")
        return None
