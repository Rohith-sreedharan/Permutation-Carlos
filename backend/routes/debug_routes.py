"""
Edge State Debug Endpoint
Provides detailed diagnostics for each game's EDGE/LEAN/NO_PLAY classification
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List
from datetime import datetime, timezone, timedelta
from db.mongo import db

router = APIRouter()


@router.get("/api/debug/edge-states")
async def debug_edge_states(sport: str = "americanfootball_nfl", hours: int = 48) -> Dict[str, Any]:
    """
    Debug endpoint: Per-game edge state diagnostics
    
    Shows:
    - market_total, model_total, edge_pts
    - over_prob, variance, confidence
    - thresholds used
    - exact rule that failed (if blocked)
    
    Query params:
        sport: Sport key (default: americanfootball_nfl)
        hours: Lookback window (default: 48)
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=hours)
    
    # Get recent simulations for sport
    sims = list(db.monte_carlo_simulations.find({
        'sport_key': sport,
        'created_at': {'$gt': cutoff.isoformat()}
    }).sort('created_at', -1).limit(20))
    
    diagnostics = []
    
    for sim in sims:
        event_id = sim.get('event_id', 'unknown')
        edge_state = sim.get('edge_state') or sim.get('pick_state', 'NO_PLAY')
        
        # Get market context
        market_total = sim.get('total_line') or sim.get('market_context', {}).get('total_line', 0)
        model_total = sim.get('avg_total_score', 0)
        edge_pts = abs(model_total - market_total) if market_total else 0
        
        # Get probabilities and stats
        over_prob = sim.get('over_probability', 0.5)
        variance = sim.get('variance_total', 0)
        confidence = sim.get('confidence_score', 0)
        
        # Get calibration info
        cal_result = sim.get('calibration_result', {})
        cal_publish = cal_result.get('publish', False)
        cal_block_reasons = cal_result.get('block_reasons', [])
        
        # Get classification
        pick_class = sim.get('pick_classification', {})
        can_publish = pick_class.get('can_publish', False) if pick_class else sim.get('can_publish', False)
        can_parlay = pick_class.get('can_parlay', False) if pick_class else sim.get('can_parlay', False)
        thresholds_met = pick_class.get('thresholds_met', {}) if pick_class else {}
        
        # Get state machine reasons
        state_reasons = sim.get('state_machine_reasons', [])
        
        # Build diagnostic entry
        diagnostic = {
            "event_id": event_id[:30],
            "timestamp": sim.get('created_at', ''),
            
            # Core metrics
            "metrics": {
                "market_total": round(market_total, 1) if market_total else None,
                "model_total": round(model_total, 1) if model_total else None,
                "edge_pts": round(edge_pts, 1) if edge_pts else None,
                "over_prob": f"{over_prob:.1%}" if over_prob is not None else None,
                "variance": round(variance, 1) if variance else None,
                "confidence": confidence if confidence else None
            },
            
            # Edge state (EDGE/LEAN/NO_PLAY)
            "edge_state": edge_state,
            "can_publish": can_publish,
            "can_parlay": can_parlay,
            
            # Governance chain
            "governance": {
                "calibration_publish": cal_publish,
                "calibration_block_reasons": cal_block_reasons,
                "state_machine_reasons": state_reasons
            },
            
            # Thresholds (sport-specific)
            "thresholds_met": thresholds_met,
            
            # Exact failure reason
            "failure_reason": None
        }
        
        # Determine exact failure reason
        if edge_state == 'NO_PLAY':
            if not cal_publish:
                diagnostic["failure_reason"] = f"CALIBRATION_BLOCKED: {', '.join(cal_block_reasons)}"
            elif state_reasons:
                diagnostic["failure_reason"] = f"STATE_MACHINE: {', '.join(state_reasons)}"
            else:
                diagnostic["failure_reason"] = "NO_PLAY (unknown reason)"
        elif edge_state == 'LEAN':
            diagnostic["failure_reason"] = f"LEAN (parlay-blocked): {', '.join(state_reasons)}"
        elif edge_state == 'EDGE':
            diagnostic["failure_reason"] = None  # Success
        elif edge_state == 'UNKNOWN':
            # Should never happen after our fix
            missing = []
            if not cal_result:
                missing.append("CALIBRATION_NOT_RUN")
            if confidence == 0:
                missing.append("CONFIDENCE_NOT_COMPUTED")
            if variance == 0:
                missing.append("VARIANCE_NOT_COMPUTED")
            if market_total == 0:
                missing.append("NO_MARKET_LINE")
            diagnostic["failure_reason"] = f"UNKNOWN_STATE: {', '.join(missing) if missing else 'No inputs missing'}"
        
        diagnostics.append(diagnostic)
    
    # Summary stats
    state_counts = {}
    for d in diagnostics:
        state = d['edge_state']
        state_counts[state] = state_counts.get(state, 0) + 1
    
    return {
        "sport": sport,
        "window_hours": hours,
        "total_simulations": len(diagnostics),
        "state_distribution": state_counts,
        "diagnostics": diagnostics,
        "notes": {
            "EDGE": "Parlay-eligible, meets all thresholds",
            "LEAN": "Publishable but not recommended for parlays",
            "NO_PLAY": "Not publishable, failed governance",
            "UNKNOWN": "ERROR - should not exist in production"
        }
    }


@router.get("/api/debug/edge-states/export")
async def export_edge_states_csv(sport: str = "americanfootball_nfl", hours: int = 48) -> str:
    """
    Export edge state diagnostics as CSV
    """
    data = await debug_edge_states(sport=sport, hours=hours)
    
    lines = [
        "event_id,timestamp,edge_state,can_publish,can_parlay,market_total,model_total,edge_pts,over_prob,variance,confidence,failure_reason"
    ]
    
    for d in data['diagnostics']:
        m = d['metrics']
        lines.append(
            f"{d['event_id']},{d['timestamp']},{d['edge_state']},{d['can_publish']},{d['can_parlay']},"
            f"{m['market_total']},{m['model_total']},{m['edge_pts']},{m['over_prob']},{m['variance']},{m['confidence']},"
            f"\"{d['failure_reason'] or 'SUCCESS'}\""
        )
    
    return "\n".join(lines)
