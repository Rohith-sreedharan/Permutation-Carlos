from fastapi import APIRouter, HTTPException, Header
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from pydantic import BaseModel
from bson import ObjectId

from core.monte_carlo_engine import MonteCarloEngine
from db.mongo import db
from config import (
    SIMULATION_TIERS, 
    PRECISION_LABELS, 
    CONFIDENCE_INTERVALS,
    SIM_TIER_FREE
)

router = APIRouter(prefix="/api/simulations", tags=["simulations"])


def _get_user_tier_from_auth(authorization: Optional[str]) -> str:
    """
    Extract user tier from authorization token
    Returns tier name or 'free' if not authenticated
    """
    if not authorization:
        return "free"
    
    try:
        parts = authorization.split()
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            return "free"
        
        token = parts[1]
        if not token.startswith('user:'):
            return "free"
        
        user_id = token.split(':', 1)[1]
        
        # Fetch user from database
        try:
            oid = ObjectId(user_id)
            user = db["users"].find_one({"_id": oid})
            if not user:
                return "free"
            
            # Get subscription tier
            subscription = db["subscriptions"].find_one({"user_id": user_id})
            if subscription:
                tier = subscription.get("tier", "free")
                return tier.lower()
            
            # Check user document for tier
            user_tier = user.get("tier", "free")
            return user_tier.lower()
            
        except Exception:
            return "free"
    except Exception:
        return "free"


class SimulationRequest(BaseModel):
    event_id: str
    iterations: int = 50000
    mode: str = "full"  # "full" or "basic"


@router.get("/{event_id}")
async def get_simulation(
    event_id: str, 
    mode: str = "full",
    authorization: Optional[str] = Header(None)
):
    """
    Get existing Monte Carlo simulation for an event, or auto-generate if missing
    
    🔥 TIERED COMPUTE: Simulation depth based on subscription tier
    - Free: 10,000 iterations (Standard precision)
    - Explorer: 25,000 iterations (Enhanced precision)
    - Pro: 50,000 iterations (High precision)
    - Elite: 100,000 iterations (Institutional precision)
    
    Args:
        event_id: Event identifier
        mode: "full" for comprehensive analysis, "basic" for quick results
        authorization: Bearer token (optional, defaults to Free tier)
    
    Returns:
        Simulation with metadata: iterations_run, precision_level, confidence_interval
    """
    try:
        # Determine user's tier and assigned iterations
        user_tier = _get_user_tier_from_auth(authorization)
        assigned_iterations = SIMULATION_TIERS.get(user_tier, SIM_TIER_FREE)
        precision_level = PRECISION_LABELS.get(assigned_iterations, "STANDARD")
        confidence_interval = CONFIDENCE_INTERVALS.get(assigned_iterations, 0.15)
        
        # Find most recent simulation for this event
        simulation = db.monte_carlo_simulations.find_one(
            {"event_id": event_id},
            sort=[("created_at", -1)]
        )
        
        if not simulation:
            # Auto-generate simulation if it doesn't exist
            print(f"⚡ Auto-generating simulation for event {event_id} (Tier: {user_tier}, Iterations: {assigned_iterations})")
            
            # Fetch event data
            event = db.events.find_one({"event_id": event_id})
            if not event:
                raise HTTPException(status_code=404, detail=f"Event not found: {event_id}")
            
            # Initialize Monte Carlo engine
            from core.monte_carlo_engine import MonteCarloEngine
            from integrations.player_api import get_team_data_with_roster
            engine = MonteCarloEngine()
            
            # Get team rosters with real player data
            sport_key = event.get("sport_key", "basketball_nba")
            team_a_data = get_team_data_with_roster(
                event.get("home_team", "Team A"),
                sport_key,
                is_home=True
            )
            team_b_data = get_team_data_with_roster(
                event.get("away_team", "Team B"),
                sport_key,
                is_home=False
            )
            
            try:
                # Run simulation with real player rosters
                simulation = engine.run_simulation(
                    event_id=event_id,
                    team_a=team_a_data,
                    team_b=team_b_data,
                    market_context={
                        "current_spread": 0,
                        "total_line": 220,
                        "public_betting_pct": 0.50,
                        "sport_key": sport_key
                    },
                    iterations=assigned_iterations,  # TIERED COMPUTE
                    mode=mode
                )
                
                # Inject metadata
                simulation["metadata"] = {
                    "user_tier": user_tier,
                    "iterations_run": assigned_iterations,
                    "precision_level": precision_level,
                    "confidence_interval_width": confidence_interval,
                    "generated_at": datetime.now(timezone.utc).isoformat()
                }
                
                print(f"✓ Simulation generated successfully for {event_id} ({assigned_iterations} iterations)")
                return simulation
                
            except Exception as e:
                print(f"✗ Simulation generation failed for {event_id}: {str(e)}")
                import traceback
                traceback.print_exc()
                raise HTTPException(status_code=500, detail=f"Simulation generation failed: {str(e)}")
        
        # Convert ObjectId to string
        simulation["_id"] = str(simulation["_id"])
        
        # Inject metadata if missing (for cached simulations)
        if "metadata" not in simulation:
            simulation["metadata"] = {
                "user_tier": user_tier,
                "iterations_run": simulation.get("iterations", assigned_iterations),
                "precision_level": precision_level,
                "confidence_interval_width": confidence_interval,
                "cached": True
            }
        
        return simulation
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"✗ Unexpected error in get_simulation for {event_id}: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@router.post("/run")
async def run_simulation(
    request: SimulationRequest,
    authorization: Optional[str] = Header(None)
):
    """
    Run a new Monte Carlo simulation for an event
    
    🔥 TIERED COMPUTE: Ignores requested iterations, enforces tier-based limits
    """
    # Fetch event data
    event = db.events.find_one({"event_id": request.event_id})
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Determine user's tier and enforce iteration limit
    user_tier = _get_user_tier_from_auth(authorization)
    assigned_iterations = SIMULATION_TIERS.get(user_tier, SIM_TIER_FREE)
    precision_level = PRECISION_LABELS.get(assigned_iterations, "STANDARD")
    
    # Initialize Monte Carlo engine
    from integrations.player_api import get_team_data_with_roster
    engine = MonteCarloEngine()
    
    # Get team rosters with real player data
    sport_key = event.get("sport_key", "basketball_nba")
    team_a_data = get_team_data_with_roster(
        event.get("home_team", "Team A"),
        sport_key,
        is_home=True
    )
    team_b_data = get_team_data_with_roster(
        event.get("away_team", "Team B"),
        sport_key,
        is_home=False
    )
    
    try:
        # Run simulation with real player rosters
        result = engine.run_simulation(
            event_id=request.event_id,
            team_a=team_a_data,
            team_b=team_b_data,
            market_context={
                "current_spread": 0,
                "total_line": 220,
                "public_betting_pct": 0.50,
                "sport_key": sport_key
            },
            iterations=assigned_iterations  # ENFORCED TIER LIMIT
        )
        
        # Inject metadata
        result["metadata"] = {
            "user_tier": user_tier,
            "iterations_run": assigned_iterations,
            "precision_level": precision_level,
            "requested_iterations": request.iterations,  # Show what was requested vs granted
            "generated_at": datetime.now(timezone.utc).isoformat()
        }
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Simulation failed: {str(e)}")


@router.get("/event/{event_id}/props")
async def get_prop_mispricings(event_id: str):
    """Get prop bet mispricings from simulations"""
    # Find prop mispricings
    mispricings = list(db.prop_mispricings.find(
        {"event_id": event_id},
        {"_id": 0}
    ).sort("edge", -1).limit(10))
    
    return {"event_id": event_id, "mispricings": mispricings}
